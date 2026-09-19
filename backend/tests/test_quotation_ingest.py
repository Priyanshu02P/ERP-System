import pytest

from app.master_data.unit.schemas import UnitCreate
from app.master_data.product.schemas import ProductCreate
from app.procurement.supplier.schemas import SupplierCreate
from app.procurement.vendor_quotation.schemas import VendorQuotationIngest, QuotationItemIngest
from app.shared.enums import ProductType, SupplierCategory, QuotationStatus, SourceChannel
from app.master_data.unit.service import UnitService
from app.master_data.product.service import ProductService
from app.procurement.supplier.service import SupplierService
from app.procurement.vendor_quotation.service import VendorQuotationService
from app.shared.fuzzy_match import best_product_match, ProductMatchCandidate
from app.shared.exceptions import ValidationError


@pytest.fixture
def unit(db_session):
    return UnitService(db_session).create_unit(UnitCreate(code="KG", name="Kilograms"))


@pytest.fixture
def crca_sheet(db_session, unit):
    return ProductService(db_session).create_product(
        ProductCreate(code="RM-CRCA-2MM", name="CRCA Sheet 2mm", product_type=ProductType.RAW, unit_id=unit.id)
    )


@pytest.fixture
def hex_bolt(db_session, unit):
    return ProductService(db_session).create_product(
        ProductCreate(code="HW-BOLT-M8", name="Hex Bolt M8x25", product_type=ProductType.RAW, unit_id=unit.id)
    )


@pytest.fixture
def supplier(db_session):
    return SupplierService(db_session).create_supplier(
        SupplierCreate(code="SUP-TATA-DIST", name="Tata Steel Distributor", category=SupplierCategory.STEEL)
    )


def _ingest_payload(supplier, items, **overrides):
    payload = dict(supplier_id=supplier.id, source=SourceChannel.OCR_BOT, items=items)
    payload.update(overrides)
    return VendorQuotationIngest(**payload)


def test_ingest_lands_in_pending_review(db_session, supplier, crca_sheet):
    items = [QuotationItemIngest(raw_description="CRCA Sheet 2mm", quantity=500, rate=62.5)]
    quotation = VendorQuotationService(db_session).ingest(_ingest_payload(supplier, items))
    assert quotation.status == QuotationStatus.PENDING_REVIEW
    assert quotation.source == SourceChannel.OCR_BOT


def test_ingest_matches_close_description_to_product(db_session, supplier, crca_sheet, hex_bolt):
    items = [QuotationItemIngest(raw_description="CRCA Sheet 2mm sheet", quantity=500, rate=62.5)]
    quotation = VendorQuotationService(db_session).ingest(_ingest_payload(supplier, items))
    line = quotation.items[0]
    assert line.product_id == crca_sheet.id
    assert line.match_confidence is not None
    assert line.match_confidence > 0.5


def test_ingest_leaves_unrecognized_description_unmapped(db_session, supplier, crca_sheet, hex_bolt):
    items = [QuotationItemIngest(raw_description="Xyzzy Widget Assembly Type-9", quantity=10, rate=999)]
    quotation = VendorQuotationService(db_session).ingest(_ingest_payload(supplier, items))
    line = quotation.items[0]
    assert line.product_id is None
    assert line.match_confidence is not None
    assert line.match_confidence < 0.55


def test_ingest_computes_amount_when_not_supplied(db_session, supplier, crca_sheet):
    items = [QuotationItemIngest(raw_description="CRCA Sheet 2mm", quantity=10, rate=100)]
    quotation = VendorQuotationService(db_session).ingest(_ingest_payload(supplier, items))
    assert quotation.items[0].amount == pytest.approx(1000)


def test_select_blocked_while_any_line_unmapped(db_session, supplier, crca_sheet, hex_bolt):
    items = [
        QuotationItemIngest(raw_description="CRCA Sheet 2mm", quantity=500, rate=62.5),
        QuotationItemIngest(raw_description="Xyzzy Widget Assembly Type-9", quantity=10, rate=999),
    ]
    service = VendorQuotationService(db_session)
    quotation = service.ingest(_ingest_payload(supplier, items))
    with pytest.raises(ValidationError):
        service.select(quotation.id)


def test_review_then_correcting_unmapped_line_allows_select(db_session, supplier, crca_sheet, hex_bolt):
    items = [QuotationItemIngest(raw_description="Bolt M8 hex 25mm", quantity=200, rate=3.5)]
    service = VendorQuotationService(db_session)
    quotation = service.ingest(_ingest_payload(supplier, items))

    unmapped = [i for i in quotation.items if i.product_id is None]
    for item in unmapped:
        from app.procurement.vendor_quotation.schemas import QuotationItemUpdate
        service.update_item(quotation.id, item.id, QuotationItemUpdate(product_id=hex_bolt.id))

    reviewed = service.review(quotation.id, "Priya Sharma")
    assert reviewed.status == QuotationStatus.REVIEWED

    selected = service.select(quotation.id)
    assert selected.status == QuotationStatus.SELECTED


def test_best_product_match_picks_closest_candidate():
    candidates = [
        ProductMatchCandidate(id=1, code="RM-CRCA-2MM", name="CRCA Sheet 2mm"),
        ProductMatchCandidate(id=2, code="HW-BOLT-M8", name="Hex Bolt M8x25"),
    ]
    result = best_product_match("CRCA Sheet 2mm x 1250 x 2500", candidates)
    assert result.product_id == 1
    assert result.confidence > 0
