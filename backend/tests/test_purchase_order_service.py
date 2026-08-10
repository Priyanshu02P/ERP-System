import pytest

from app.db.schemas.unit import UnitCreate
from app.db.schemas.product import ProductCreate
from app.db.schemas.supplier import SupplierCreate
from app.db.schemas.vendor_quotation import VendorQuotationCreate, QuotationItemCreate
from app.db.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderItemCreate,
    PurchaseOrderUpdate,
)
from app.db.models.enums import ProductType, SupplierCategory, POStatus
from app.services.unit_service import UnitService
from app.services.product_service import ProductService
from app.services.supplier_service import SupplierService
from app.services.vendor_quotation_service import VendorQuotationService
from app.services.purchase_order_service import PurchaseOrderService
from app.services.exceptions import ConflictError, ValidationError


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
def selected_quotation(db_session, product, supplier):
    service = VendorQuotationService(db_session)
    quotation = service.create_manual(
        None,
        VendorQuotationCreate(
            supplier_id=supplier.id,
            vendor_quotation_no="TSD/QT/0142",
            payment_terms="30% Advance, 70% on Delivery",
            items=[QuotationItemCreate(product_id=product.id, quantity=500, rate=62.5, gst_rate=18)],
        ),
    )
    return service.select(quotation.id)


def _manual_payload(product, supplier, **overrides):
    payload = dict(
        supplier_id=supplier.id,
        order_date="2026-08-03",
        items=[PurchaseOrderItemCreate(product_id=product.id, quantity=100, rate=50, gst_rate=18)],
    )
    payload.update(overrides)
    return PurchaseOrderCreate(**payload)


# ---------------------------------------------------------------------- #
# Creation - manual
# ---------------------------------------------------------------------- #

def test_create_manual_po_success(db_session, product, supplier):
    po = PurchaseOrderService(db_session).create_po(_manual_payload(product, supplier))
    assert po.status == POStatus.DRAFT
    assert po.po_number.startswith("PO-2026-")
    assert po.po_number.endswith("00001")
    assert po.quotation_id is None
    assert po.subtotal == pytest.approx(100 * 50)
    assert po.gst_amount == pytest.approx(100 * 50 * 0.18)
    assert po.total_amount == pytest.approx(po.subtotal + po.gst_amount)


def test_po_number_increments(db_session, product, supplier):
    service = PurchaseOrderService(db_session)
    po1 = service.create_po(_manual_payload(product, supplier))
    po2 = service.create_po(_manual_payload(product, supplier))
    assert po1.po_number != po2.po_number
    assert po2.po_number.endswith("00002")


def test_manual_po_requires_supplier_id():
    with pytest.raises(ValueError):
        PurchaseOrderCreate(
            order_date="2026-08-03",
            items=[PurchaseOrderItemCreate(product_id=1, quantity=1, rate=1)],
        )


def test_manual_po_requires_items():
    with pytest.raises(ValueError):
        PurchaseOrderCreate(supplier_id=1, order_date="2026-08-03")


def test_create_manual_po_with_invalid_supplier_raises(db_session, product):
    with pytest.raises(ValidationError):
        PurchaseOrderService(db_session).create_po(
            PurchaseOrderCreate(
                supplier_id=999,
                order_date="2026-08-03",
                items=[PurchaseOrderItemCreate(product_id=product.id, quantity=1, rate=1)],
            )
        )


def test_create_manual_po_with_invalid_product_raises(db_session, supplier):
    with pytest.raises(ValidationError):
        PurchaseOrderService(db_session).create_po(
            PurchaseOrderCreate(
                supplier_id=supplier.id,
                order_date="2026-08-03",
                items=[PurchaseOrderItemCreate(product_id=999, quantity=1, rate=1)],
            )
        )


# ---------------------------------------------------------------------- #
# Creation - from a SELECTED quotation
# ---------------------------------------------------------------------- #

def test_create_po_from_quotation_copies_lines_and_supplier(db_session, product, supplier, selected_quotation):
    po = PurchaseOrderService(db_session).create_po(
        PurchaseOrderCreate(quotation_id=selected_quotation.id, order_date="2026-08-03")
    )
    assert po.supplier_id == supplier.id
    assert po.quotation_id == selected_quotation.id
    assert po.payment_terms == "30% Advance, 70% on Delivery"
    assert len(po.items) == 1
    assert po.items[0].product_id == product.id
    assert po.items[0].quantity == pytest.approx(500)
    assert po.total_amount == pytest.approx(500 * 62.5 * 1.18)


def test_create_po_from_non_selected_quotation_raises(db_session, product, supplier):
    quotation = VendorQuotationService(db_session).create_manual(
        None,
        VendorQuotationCreate(
            supplier_id=supplier.id,
            items=[QuotationItemCreate(product_id=product.id, quantity=10, rate=5)],
        ),
    )
    with pytest.raises(ConflictError):
        PurchaseOrderService(db_session).create_po(
            PurchaseOrderCreate(quotation_id=quotation.id, order_date="2026-08-03")
        )


def test_create_po_from_quotation_twice_raises(db_session, selected_quotation):
    service = PurchaseOrderService(db_session)
    service.create_po(PurchaseOrderCreate(quotation_id=selected_quotation.id, order_date="2026-08-03"))
    with pytest.raises(ConflictError):
        service.create_po(PurchaseOrderCreate(quotation_id=selected_quotation.id, order_date="2026-08-03"))


def test_create_po_from_invalid_quotation_raises(db_session):
    with pytest.raises(ValidationError):
        PurchaseOrderService(db_session).create_po(
            PurchaseOrderCreate(quotation_id=999, order_date="2026-08-03")
        )


# ---------------------------------------------------------------------- #
# Header edit (DRAFT only)
# ---------------------------------------------------------------------- #

def test_update_po_only_while_draft(db_session, product, supplier):
    service = PurchaseOrderService(db_session)
    po = service.create_po(_manual_payload(product, supplier))
    updated = service.update_po(po.id, PurchaseOrderUpdate(payment_terms="50% Advance"))
    assert updated.payment_terms == "50% Advance"

    service.send(po.id, "Priya Sharma")
    with pytest.raises(ConflictError):
        service.update_po(po.id, PurchaseOrderUpdate(payment_terms="Full Advance"))


# ---------------------------------------------------------------------- #
# State machine: DRAFT -> SENT -> CONFIRMED ; DRAFT/SENT -> CANCELLED
# ---------------------------------------------------------------------- #

def test_send_po_requires_approver_and_transitions_status(db_session, product, supplier):
    service = PurchaseOrderService(db_session)
    po = service.create_po(_manual_payload(product, supplier))
    sent = service.send(po.id, "Priya Sharma")
    assert sent.status == POStatus.SENT
    assert sent.approved_by == "Priya Sharma"
    assert sent.approved_at is not None


def test_send_po_only_from_draft(db_session, product, supplier):
    service = PurchaseOrderService(db_session)
    po = service.create_po(_manual_payload(product, supplier))
    service.send(po.id, "Priya Sharma")
    with pytest.raises(ConflictError):
        service.send(po.id, "Priya Sharma")


def test_confirm_po_only_from_sent(db_session, product, supplier):
    service = PurchaseOrderService(db_session)
    po = service.create_po(_manual_payload(product, supplier))
    with pytest.raises(ConflictError):
        service.confirm(po.id)
    service.send(po.id, "Priya Sharma")
    confirmed = service.confirm(po.id)
    assert confirmed.status == POStatus.CONFIRMED


def test_cancel_po_from_draft(db_session, product, supplier):
    service = PurchaseOrderService(db_session)
    po = service.create_po(_manual_payload(product, supplier))
    cancelled = service.cancel(po.id, "Priya Sharma", "Duplicate order raised by mistake")
    assert cancelled.status == POStatus.CANCELLED
    assert cancelled.cancelled_by == "Priya Sharma"
    assert cancelled.cancellation_reason == "Duplicate order raised by mistake"


def test_cancel_po_from_sent(db_session, product, supplier):
    service = PurchaseOrderService(db_session)
    po = service.create_po(_manual_payload(product, supplier))
    service.send(po.id, "Priya Sharma")
    cancelled = service.cancel(po.id, "Priya Sharma", "Vendor unable to fulfill")
    assert cancelled.status == POStatus.CANCELLED


def test_cancel_po_blocked_once_confirmed(db_session, product, supplier):
    service = PurchaseOrderService(db_session)
    po = service.create_po(_manual_payload(product, supplier))
    service.send(po.id, "Priya Sharma")
    service.confirm(po.id)
    with pytest.raises(ConflictError):
        service.cancel(po.id, "Priya Sharma", "Too late")


# ---------------------------------------------------------------------- #
# Queries
# ---------------------------------------------------------------------- #

def test_get_by_status_and_supplier(db_session, product, supplier):
    service = PurchaseOrderService(db_session)
    po = service.create_po(_manual_payload(product, supplier))

    by_status = service.get_by_status(POStatus.DRAFT)
    assert po.id in [p.id for p in by_status]

    by_supplier = service.get_by_supplier(supplier.id)
    assert po.id in [p.id for p in by_supplier]
