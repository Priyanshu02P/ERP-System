import pytest

from app.db.schemas.unit import UnitCreate
from app.db.schemas.product import ProductCreate
from app.db.schemas.supplier import SupplierCreate
from app.db.schemas.manufacturer import ManufacturerCreate
from app.db.schemas.warehouse import WarehouseCreate, RackCreate, ShelfCreate, BinCreate, LocationCreate
from app.db.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderItemCreate
from app.db.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptItemCreate
from app.db.schemas.quality_inspection import QualityInspectionCreate, QualityInspectionItemCreate
from app.db.schemas.vendor_invoice import (
    VendorInvoiceCreate, VendorInvoiceItemCreate, VendorInvoiceIngest, VendorInvoiceItemIngest,
    VendorInvoiceUpdate, VendorInvoiceItemUpdate,
)
from app.db.models.enums import ProductType, SupplierCategory, QCItemDisposition, InvoiceStatus, SourceChannel
from app.services.unit_service import UnitService
from app.services.product_service import ProductService
from app.services.supplier_service import SupplierService
from app.services.manufacturer_service import ManufacturerService
from app.services.warehouse_service import WarehouseService
from app.services.rack_service import RackService
from app.services.shelf_service import ShelfService
from app.services.bin_service import BinService
from app.services.location_service import LocationService
from app.services.purchase_order_service import PurchaseOrderService
from app.services.goods_receipt_service import GoodsReceiptService
from app.services.quality_inspection_service import QualityInspectionService
from app.services.vendor_invoice_service import VendorInvoiceService
from app.services.exceptions import ConflictError, ValidationError, NotFoundError


@pytest.fixture
def product(db_session):
    unit = UnitService(db_session).create_unit(UnitCreate(code="KG", name="Kilograms"))
    return ProductService(db_session).create_product(
        ProductCreate(code="RM-CRCA-2MM", name="CRCA Sheet 2mm", product_type=ProductType.RAW, unit_id=unit.id)
    )


@pytest.fixture
def manufacturer(db_session):
    return ManufacturerService(db_session).create(ManufacturerCreate(code="MFG-TATA", name="Tata Steel"))


@pytest.fixture
def supplier(db_session, manufacturer):
    return SupplierService(db_session).create_supplier(
        SupplierCreate(
            code="SUP-TATA-DIST", name="Tata Steel Distributor",
            category=SupplierCategory.STEEL, manufacturer_id=manufacturer.id,
        )
    )


@pytest.fixture
def other_supplier(db_session):
    return SupplierService(db_session).create_supplier(
        SupplierCreate(code="SUP-OTHER", name="Some Other Vendor", category=SupplierCategory.HARDWARE)
    )


@pytest.fixture
def location(db_session):
    warehouse = WarehouseService(db_session).create(WarehouseCreate(code="WH1", name="Main Warehouse"))
    rack = RackService(db_session).create(RackCreate(code="A", warehouse_id=warehouse.id))
    shelf = ShelfService(db_session).create(ShelfCreate(code="03", rack_id=rack.id))
    bin_ = BinService(db_session).create(BinCreate(code="05", shelf_id=shelf.id))
    return LocationService(db_session).create_location(
        LocationCreate(warehouse_id=warehouse.id, rack_id=rack.id, shelf_id=shelf.id, bin_id=bin_.id)
    )


def _received_and_accepted_po(db_session, supplier, product, location, quantity=500, rate=62.5, gst_rate=18):
    """Full happy-path setup: PO confirmed, fully received via one GRN, QC
    fully accepted - ready for an invoice to be matched against."""
    po_service = PurchaseOrderService(db_session)
    po = po_service.create_po(
        PurchaseOrderCreate(
            supplier_id=supplier.id, order_date="2026-08-03",
            items=[PurchaseOrderItemCreate(product_id=product.id, quantity=quantity, rate=rate, gst_rate=gst_rate)],
        )
    )
    po_service.send(po.id, "Priya Sharma")
    po = po_service.confirm(po.id)

    grn = GoodsReceiptService(db_session).create_grn(
        GoodsReceiptCreate(
            po_id=po.id, received_by="Ramesh",
            items=[GoodsReceiptItemCreate(po_item_id=po.items[0].id, received_quantity=quantity)],
        )
    )
    QualityInspectionService(db_session).create_qc(
        QualityInspectionCreate(
            grn_id=grn.id, inspector="Anita",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=grn.items[0].id, disposition=QCItemDisposition.ACCEPT,
                    accepted_quantity=quantity, putaway_location_id=location.id,
                )
            ],
        )
    )
    return po, grn


# ---------------------------------------------------------------------- #
# Creation - manual
# ---------------------------------------------------------------------- #

def test_create_manual_invoice_auto_resolves_single_grn(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location)
    invoice = VendorInvoiceService(db_session).create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id, vendor_invoice_no="TSD-INV-9911",
            items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="CRCA 2mm", quantity=500, rate=62.5, gst_rate=18)],
        )
    )
    assert invoice.status == InvoiceStatus.PENDING_MATCH
    assert invoice.grn_id == grn.id  # auto-resolved: exactly one GRN on this PO
    assert float(invoice.subtotal) == pytest.approx(500 * 62.5)
    assert float(invoice.total_amount) == pytest.approx(500 * 62.5 * 1.18)


def test_create_manual_invoice_supplier_mismatch_raises(db_session, supplier, other_supplier, product, location):
    po, _ = _received_and_accepted_po(db_session, supplier, product, location)
    with pytest.raises(ValidationError):
        VendorInvoiceService(db_session).create_manual(
            VendorInvoiceCreate(
                supplier_id=other_supplier.id, po_id=po.id,
                items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="CRCA 2mm", quantity=500, rate=62.5, gst_rate=18)],
            )
        )


def test_create_manual_invoice_with_po_item_from_other_po_raises(db_session, supplier, product, location):
    po1, _ = _received_and_accepted_po(db_session, supplier, product, location, quantity=100)
    po2, _ = _received_and_accepted_po(db_session, supplier, product, location, quantity=200)
    with pytest.raises(ValidationError):
        VendorInvoiceService(db_session).create_manual(
            VendorInvoiceCreate(
                supplier_id=supplier.id, po_id=po1.id,
                items=[VendorInvoiceItemCreate(po_item_id=po2.items[0].id, description="x", quantity=100, rate=62.5, gst_rate=18)],
            )
        )


def test_create_manual_invoice_with_invalid_po_raises(db_session, supplier):
    with pytest.raises(ValidationError):
        VendorInvoiceService(db_session).create_manual(
            VendorInvoiceCreate(
                supplier_id=supplier.id, po_id=999,
                items=[VendorInvoiceItemCreate(po_item_id=1, description="x", quantity=1, rate=1)],
            )
        )


# ---------------------------------------------------------------------- #
# Creation - ingest
# ---------------------------------------------------------------------- #

def test_ingest_invoice_fuzzy_matches_po_line(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location)
    invoice = VendorInvoiceService(db_session).ingest(
        VendorInvoiceIngest(
            supplier_id=supplier.id, po_id=po.id, source=SourceChannel.OCR_BOT, source_confidence=0.9,
            items=[VendorInvoiceItemIngest(description="CRCA Sheet 2mm", quantity=500, rate=62.5)],
        )
    )
    assert invoice.status == InvoiceStatus.PENDING_MATCH
    assert invoice.items[0].po_item_id == po.items[0].id
    assert invoice.items[0].match_confidence is not None and invoice.items[0].match_confidence > 0


def test_ingest_invoice_leaves_unmatched_line_null(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location)
    invoice = VendorInvoiceService(db_session).ingest(
        VendorInvoiceIngest(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemIngest(description="totally unrelated gibberish xyz123", quantity=500, rate=62.5)],
        )
    )
    assert invoice.items[0].po_item_id is None


def test_match_blocked_while_any_line_unmapped(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location)
    invoice = VendorInvoiceService(db_session).ingest(
        VendorInvoiceIngest(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemIngest(description="totally unrelated gibberish xyz123", quantity=500, rate=62.5)],
        )
    )
    with pytest.raises(ValidationError):
        VendorInvoiceService(db_session).match(invoice.id, "Accounts Clerk")


def test_update_item_maps_unmatched_line_and_unblocks_match(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location)
    service = VendorInvoiceService(db_session)
    invoice = service.ingest(
        VendorInvoiceIngest(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemIngest(description="totally unrelated gibberish xyz123", quantity=500, rate=62.5, gst_rate=18)],
        )
    )
    updated = service.update_item(
        invoice.id, invoice.items[0].id, VendorInvoiceItemUpdate(po_item_id=po.items[0].id)
    )
    assert updated.items[0].po_item_id == po.items[0].id
    assert updated.items[0].match_confidence is None  # human override clears the fuzzy score

    matched = service.match(invoice.id, "Accounts Clerk")
    assert matched.status == InvoiceStatus.MATCHED


# ---------------------------------------------------------------------- #
# Header update / grn_id resolution
# ---------------------------------------------------------------------- #

def test_two_grns_leaves_grn_id_unresolved_until_set_explicitly(db_session, supplier, product, location):
    po_service = PurchaseOrderService(db_session)
    po = po_service.create_po(
        PurchaseOrderCreate(
            supplier_id=supplier.id, order_date="2026-08-03",
            items=[PurchaseOrderItemCreate(product_id=product.id, quantity=500, rate=62.5, gst_rate=18)],
        )
    )
    po_service.send(po.id, "Priya Sharma")
    po = po_service.confirm(po.id)
    grn_service = GoodsReceiptService(db_session)
    grn1 = grn_service.create_grn(
        GoodsReceiptCreate(po_id=po.id, received_by="Ramesh",
                            items=[GoodsReceiptItemCreate(po_item_id=po.items[0].id, received_quantity=300)])
    )
    grn2 = grn_service.create_grn(
        GoodsReceiptCreate(po_id=po.id, received_by="Ramesh",
                            items=[GoodsReceiptItemCreate(po_item_id=po.items[0].id, received_quantity=200)])
    )

    invoice_service = VendorInvoiceService(db_session)
    invoice = invoice_service.create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="x", quantity=300, rate=62.5, gst_rate=18)],
        )
    )
    assert invoice.grn_id is None  # ambiguous - two GRNs exist

    with pytest.raises(ValidationError):
        invoice_service.match(invoice.id, "Accounts Clerk")

    updated = invoice_service.update_header(invoice.id, VendorInvoiceUpdate(grn_id=grn1.id))
    assert updated.grn_id == grn1.id


# ---------------------------------------------------------------------- #
# 3-way match: matched / mismatch
# ---------------------------------------------------------------------- #

def test_match_within_tolerance_is_matched(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location, quantity=500, rate=62.5)
    invoice = VendorInvoiceService(db_session).create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="CRCA 2mm", quantity=500, rate=62.5, gst_rate=18)],
        )
    )
    matched = VendorInvoiceService(db_session).match(invoice.id, "Accounts Clerk")
    assert matched.status == InvoiceStatus.MATCHED
    assert matched.match_report["result"] == "MATCHED"
    assert matched.match_report["lines"][0]["ok"] is True
    assert matched.matched_by == "Accounts Clerk"


def test_match_quantity_beyond_tolerance_is_mismatch(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location, quantity=500, rate=62.5)
    # Invoice bills for 550 when only 500 was received - 10% over, well beyond the 2% tolerance.
    invoice = VendorInvoiceService(db_session).create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="CRCA 2mm", quantity=550, rate=62.5, gst_rate=18)],
        )
    )
    matched = VendorInvoiceService(db_session).match(invoice.id, "Accounts Clerk")
    assert matched.status == InvoiceStatus.MISMATCH
    assert matched.match_report["lines"][0]["ok"] is False
    assert matched.match_report["lines"][0]["quantity_diff_pct"] > 2.0


def test_match_rate_beyond_tolerance_is_mismatch(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location, quantity=500, rate=62.5)
    # Invoice bills at 70/unit vs the agreed PO rate of 62.5 - well beyond the 1% tolerance.
    invoice = VendorInvoiceService(db_session).create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="CRCA 2mm", quantity=500, rate=70, gst_rate=18)],
        )
    )
    matched = VendorInvoiceService(db_session).match(invoice.id, "Accounts Clerk")
    assert matched.status == InvoiceStatus.MISMATCH
    assert matched.match_report["lines"][0]["rate_diff_pct"] > 1.0


def test_rematch_after_correction_can_flip_mismatch_to_matched(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location, quantity=500, rate=62.5)
    service = VendorInvoiceService(db_session)
    invoice = service.create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="CRCA 2mm", quantity=550, rate=62.5, gst_rate=18)],
        )
    )
    mismatched = service.match(invoice.id, "Accounts Clerk")
    assert mismatched.status == InvoiceStatus.MISMATCH

    service.update_item(invoice.id, invoice.items[0].id, VendorInvoiceItemUpdate(quantity=500))
    rematched = service.match(invoice.id, "Accounts Clerk")
    assert rematched.status == InvoiceStatus.MATCHED


def test_match_without_grn_id_raises(db_session, supplier, product):
    po_service = PurchaseOrderService(db_session)
    po = po_service.create_po(
        PurchaseOrderCreate(
            supplier_id=supplier.id, order_date="2026-08-03",
            items=[PurchaseOrderItemCreate(product_id=product.id, quantity=500, rate=62.5, gst_rate=18)],
        )
    )
    po_service.send(po.id, "Priya Sharma")
    po = po_service.confirm(po.id)
    # No GRN recorded at all yet.
    invoice = VendorInvoiceService(db_session).create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="x", quantity=500, rate=62.5, gst_rate=18)],
        )
    )
    assert invoice.grn_id is None
    with pytest.raises(ValidationError):
        VendorInvoiceService(db_session).match(invoice.id, "Accounts Clerk")


def test_match_no_grn_line_for_po_item_is_mismatch(db_session, supplier, product, location):
    # Two-line PO, but the GRN only receives one of them - the other line's
    # invoice has nothing to check against.
    po_service = PurchaseOrderService(db_session)
    unit = ProductService(db_session).repository.get(product.id).unit_id
    product2 = ProductService(db_session).create_product(
        ProductCreate(code="RM-CRCA-3MM", name="CRCA Sheet 3mm", product_type=ProductType.RAW, unit_id=unit)
    )
    po = po_service.create_po(
        PurchaseOrderCreate(
            supplier_id=supplier.id, order_date="2026-08-03",
            items=[
                PurchaseOrderItemCreate(product_id=product.id, quantity=500, rate=62.5, gst_rate=18),
                PurchaseOrderItemCreate(product_id=product2.id, quantity=100, rate=70, gst_rate=18),
            ],
        )
    )
    po_service.send(po.id, "Priya Sharma")
    po = po_service.confirm(po.id)
    grn = GoodsReceiptService(db_session).create_grn(
        GoodsReceiptCreate(
            po_id=po.id, received_by="Ramesh",
            items=[GoodsReceiptItemCreate(po_item_id=po.items[0].id, received_quantity=500)],
        )
    )
    invoice = VendorInvoiceService(db_session).create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id,
            items=[
                VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="x", quantity=500, rate=62.5, gst_rate=18),
                VendorInvoiceItemCreate(po_item_id=po.items[1].id, description="y", quantity=100, rate=70, gst_rate=18),
            ],
        )
    )
    matched = VendorInvoiceService(db_session).match(invoice.id, "Accounts Clerk")
    assert matched.status == InvoiceStatus.MISMATCH
    assert matched.match_report["lines"][1]["ok"] is False
    assert "reason" in matched.match_report["lines"][1]


# ---------------------------------------------------------------------- #
# Payment
# ---------------------------------------------------------------------- #

def test_approve_payment_requires_matched(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location)
    invoice = VendorInvoiceService(db_session).create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="x", quantity=500, rate=62.5, gst_rate=18)],
        )
    )
    with pytest.raises(ConflictError):
        VendorInvoiceService(db_session).approve_payment(invoice.id, "Finance Manager")


def test_full_payment_flow(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location)
    service = VendorInvoiceService(db_session)
    invoice = service.create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="x", quantity=500, rate=62.5, gst_rate=18)],
        )
    )
    service.match(invoice.id, "Accounts Clerk")
    approved = service.approve_payment(invoice.id, "Finance Manager")
    assert approved.status == InvoiceStatus.APPROVED_FOR_PAYMENT
    assert approved.approved_by == "Finance Manager"

    paid = service.mark_paid(invoice.id, "Finance Manager")
    assert paid.status == InvoiceStatus.PAID
    assert paid.paid_by == "Finance Manager"


def test_mark_paid_requires_approved(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location)
    service = VendorInvoiceService(db_session)
    invoice = service.create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="x", quantity=500, rate=62.5, gst_rate=18)],
        )
    )
    with pytest.raises(ConflictError):
        service.mark_paid(invoice.id, "Finance Manager")


def test_cannot_edit_matched_invoice(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location)
    service = VendorInvoiceService(db_session)
    invoice = service.create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="x", quantity=500, rate=62.5, gst_rate=18)],
        )
    )
    service.match(invoice.id, "Accounts Clerk")
    with pytest.raises(ConflictError):
        service.update_item(invoice.id, invoice.items[0].id, VendorInvoiceItemUpdate(quantity=100))


# ---------------------------------------------------------------------- #
# Queries
# ---------------------------------------------------------------------- #

def test_get_by_status_and_po(db_session, supplier, product, location):
    po, grn = _received_and_accepted_po(db_session, supplier, product, location)
    invoice = VendorInvoiceService(db_session).create_manual(
        VendorInvoiceCreate(
            supplier_id=supplier.id, po_id=po.id,
            items=[VendorInvoiceItemCreate(po_item_id=po.items[0].id, description="x", quantity=500, rate=62.5, gst_rate=18)],
        )
    )
    service = VendorInvoiceService(db_session)
    assert invoice.id in [i.id for i in service.get_by_status(InvoiceStatus.PENDING_MATCH)]
    assert invoice.id in [i.id for i in service.get_by_po(po.id)]
