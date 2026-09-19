import pytest

from app.master_data.unit.schemas import UnitCreate
from app.master_data.product.schemas import ProductCreate
from app.procurement.supplier.schemas import SupplierCreate
from app.procurement.rfq.schemas import RFQCreate, RFQItemCreate, RFQSend
from app.procurement.vendor_quotation.schemas import (
    VendorQuotationCreate,
    QuotationItemCreate,
    QuotationItemUpdate,
)
from app.shared.enums import ProductType, SupplierCategory, QuotationStatus, RFQResponseStatus
from app.master_data.unit.service import UnitService
from app.master_data.product.service import ProductService
from app.procurement.supplier.service import SupplierService
from app.procurement.rfq.service import RFQService
from app.procurement.vendor_quotation.service import VendorQuotationService
from app.shared.exceptions import ConflictError, ValidationError, NotFoundError


@pytest.fixture
def product(db_session):
    unit = UnitService(db_session).create_unit(UnitCreate(code="KG", name="Kilograms"))
    return ProductService(db_session).create_product(
        ProductCreate(code="RM-CRCA-2MM", name="CRCA Sheet 2mm", product_type=ProductType.RAW, unit_id=unit.id)
    )


@pytest.fixture
def supplier(db_session):
    return SupplierService(db_session).create_supplier(
        SupplierCreate(code="SUP-TATA-DIST", name="Tata Steel Distributor", category=SupplierCategory.STEEL)
    )


@pytest.fixture
def supplier_2(db_session):
    return SupplierService(db_session).create_supplier(
        SupplierCreate(code="SUP-JSW", name="JSW Steel", category=SupplierCategory.STEEL)
    )


@pytest.fixture
def sent_rfq(db_session, product, supplier, supplier_2):
    service = RFQService(db_session)
    rfq = service.create_rfq(
        RFQCreate(due_date="2026-08-20", items=[RFQItemCreate(product_id=product.id, quantity=500)])
    )
    return service.send(rfq.id, RFQSend(supplier_ids=[supplier.id, supplier_2.id]))


def _quotation_payload(product, supplier, **overrides):
    payload = dict(
        supplier_id=supplier.id,
        vendor_quotation_no="TSD/QT/0142",
        items=[QuotationItemCreate(product_id=product.id, quantity=500, rate=62.5)],
    )
    payload.update(overrides)
    return VendorQuotationCreate(**payload)


def test_manual_create_starts_reviewed(db_session, product, supplier):
    quotation = VendorQuotationService(db_session).create_manual(None, _quotation_payload(product, supplier))
    assert quotation.status == QuotationStatus.REVIEWED
    assert quotation.items[0].amount == pytest.approx(500 * 62.5)
    assert quotation.items[0].raw_description  # defaulted from product name


def test_manual_create_marks_rfq_supplier_responded(db_session, product, supplier, sent_rfq):
    VendorQuotationService(db_session).create_manual(sent_rfq.id, _quotation_payload(product, supplier))
    refreshed = RFQService(db_session).get(sent_rfq.id)
    link = next(s for s in refreshed.suppliers if s.supplier_id == supplier.id)
    assert link.response_status == RFQResponseStatus.RESPONDED


def test_manual_create_with_invalid_supplier_raises(db_session, product):
    with pytest.raises(ValidationError):
        VendorQuotationService(db_session).create_manual(
            None,
            VendorQuotationCreate(
                supplier_id=999, items=[QuotationItemCreate(product_id=product.id, quantity=1, rate=1)]
            ),
        )


def test_update_item_blocked_once_selected(db_session, product, supplier):
    service = VendorQuotationService(db_session)
    quotation = service.create_manual(None, _quotation_payload(product, supplier))
    service.select(quotation.id)
    with pytest.raises(ConflictError):
        service.update_item(quotation.id, quotation.items[0].id, QuotationItemUpdate(rate=70))


def test_update_item_not_found_raises(db_session, product, supplier):
    service = VendorQuotationService(db_session)
    quotation = service.create_manual(None, _quotation_payload(product, supplier))
    with pytest.raises(NotFoundError):
        service.update_item(quotation.id, 999, QuotationItemUpdate(rate=70))


def test_select_requires_all_items_mapped(db_session, product, supplier):
    service = VendorQuotationService(db_session)
    quotation = service.create_manual(None, _quotation_payload(product, supplier))
    # Force an unmapped line the way ingest would leave one.
    quotation.items[0].product_id = None
    db_session.commit()
    with pytest.raises(ValidationError):
        service.select(quotation.id)


def test_select_auto_rejects_sibling_quotations_on_same_rfq(db_session, product, supplier, supplier_2, sent_rfq):
    service = VendorQuotationService(db_session)
    q1 = service.create_manual(sent_rfq.id, _quotation_payload(product, supplier))
    q2 = service.create_manual(sent_rfq.id, _quotation_payload(product, supplier_2, rate=58))

    service.select(q1.id)

    refreshed_q1 = service.get(q1.id)
    refreshed_q2 = service.get(q2.id)
    assert refreshed_q1.status == QuotationStatus.SELECTED
    assert refreshed_q2.status == QuotationStatus.REJECTED


def test_reject_quotation(db_session, product, supplier):
    service = VendorQuotationService(db_session)
    quotation = service.create_manual(None, _quotation_payload(product, supplier))
    rejected = service.reject(quotation.id, "Priya Sharma", "Rate too high vs. last PO")
    assert rejected.status == QuotationStatus.REJECTED
    assert rejected.rejected_by == "Priya Sharma"


def test_reject_already_selected_raises(db_session, product, supplier):
    service = VendorQuotationService(db_session)
    quotation = service.create_manual(None, _quotation_payload(product, supplier))
    service.select(quotation.id)
    with pytest.raises(ConflictError):
        service.reject(quotation.id, "Priya Sharma", "too late")
