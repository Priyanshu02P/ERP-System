import pytest

from app.db.schemas.unit import UnitCreate
from app.db.schemas.product import ProductCreate
from app.db.schemas.supplier import SupplierCreate
from app.db.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderItemCreate
from app.db.schemas.goods_receipt import GoodsReceiptCreate, GoodsReceiptItemCreate
from app.db.models.enums import ProductType, SupplierCategory, POStatus, POLineStatus, GRNStatus
from app.services.unit_service import UnitService
from app.services.product_service import ProductService
from app.services.supplier_service import SupplierService
from app.services.purchase_order_service import PurchaseOrderService
from app.services.goods_receipt_service import GoodsReceiptService
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
def confirmed_po(db_session, product, supplier):
    service = PurchaseOrderService(db_session)
    po = service.create_po(
        PurchaseOrderCreate(
            supplier_id=supplier.id,
            order_date="2026-08-03",
            items=[PurchaseOrderItemCreate(product_id=product.id, quantity=500, rate=62.5, gst_rate=18)],
        )
    )
    service.send(po.id, "Priya Sharma")
    return service.confirm(po.id)


def _grn_payload(po, received_quantity=500, **overrides):
    payload = dict(
        po_id=po.id,
        received_by="Ramesh (Store Keeper)",
        items=[GoodsReceiptItemCreate(po_item_id=po.items[0].id, received_quantity=received_quantity)],
    )
    payload.update(overrides)
    return GoodsReceiptCreate(**payload)


# ---------------------------------------------------------------------- #
# Creation
# ---------------------------------------------------------------------- #

def test_create_grn_full_delivery_marks_po_received(db_session, confirmed_po):
    grn = GoodsReceiptService(db_session).create_grn(_grn_payload(confirmed_po, received_quantity=500))
    assert grn.status == GRNStatus.PENDING_QC
    assert grn.grn_number.startswith("GRN-2026-")
    assert grn.items[0].received_quantity == pytest.approx(500)
    assert grn.items[0].variance_quantity == pytest.approx(0)

    db_session.refresh(confirmed_po)
    assert confirmed_po.status == POStatus.RECEIVED
    assert confirmed_po.items[0].line_status == POLineStatus.COMPLETE


def test_create_grn_partial_delivery_marks_po_partially_received(db_session, confirmed_po):
    grn = GoodsReceiptService(db_session).create_grn(_grn_payload(confirmed_po, received_quantity=300))
    assert grn.items[0].variance_quantity == pytest.approx(300 - 500)

    db_session.refresh(confirmed_po)
    assert confirmed_po.status == POStatus.PARTIALLY_RECEIVED
    assert confirmed_po.items[0].line_status == POLineStatus.PARTIAL
    assert confirmed_po.items[0].received_quantity == pytest.approx(300)


def test_second_grn_completes_a_partial_delivery(db_session, confirmed_po):
    service = GoodsReceiptService(db_session)
    service.create_grn(_grn_payload(confirmed_po, received_quantity=300))
    db_session.refresh(confirmed_po)
    second = service.create_grn(_grn_payload(confirmed_po, received_quantity=200))
    assert second.items[0].variance_quantity == pytest.approx(0)

    db_session.refresh(confirmed_po)
    assert confirmed_po.status == POStatus.RECEIVED
    assert confirmed_po.items[0].line_status == POLineStatus.COMPLETE


def test_create_grn_against_non_confirmed_po_raises(db_session, product, supplier):
    po = PurchaseOrderService(db_session).create_po(
        PurchaseOrderCreate(
            supplier_id=supplier.id,
            order_date="2026-08-03",
            items=[PurchaseOrderItemCreate(product_id=product.id, quantity=100, rate=10)],
        )
    )
    with pytest.raises(ConflictError):
        GoodsReceiptService(db_session).create_grn(_grn_payload(po, received_quantity=100))


def test_create_grn_against_invalid_po_raises(db_session):
    with pytest.raises(ValidationError):
        GoodsReceiptService(db_session).create_grn(
            GoodsReceiptCreate(
                po_id=999,
                received_by="Ramesh",
                items=[GoodsReceiptItemCreate(po_item_id=1, received_quantity=10)],
            )
        )


def test_create_grn_with_po_item_from_another_po_raises(db_session, confirmed_po, product, supplier):
    other_service = PurchaseOrderService(db_session)
    other_po = other_service.create_po(
        PurchaseOrderCreate(
            supplier_id=supplier.id,
            order_date="2026-08-03",
            items=[PurchaseOrderItemCreate(product_id=product.id, quantity=50, rate=10)],
        )
    )
    with pytest.raises(ValidationError):
        GoodsReceiptService(db_session).create_grn(
            GoodsReceiptCreate(
                po_id=confirmed_po.id,
                received_by="Ramesh",
                items=[GoodsReceiptItemCreate(po_item_id=other_po.items[0].id, received_quantity=10)],
            )
        )


# ---------------------------------------------------------------------- #
# Close
# ---------------------------------------------------------------------- #

def test_close_grn_blocked_before_qc(db_session, confirmed_po):
    grn = GoodsReceiptService(db_session).create_grn(_grn_payload(confirmed_po))
    with pytest.raises(ConflictError):
        GoodsReceiptService(db_session).close_grn(grn.id)


# ---------------------------------------------------------------------- #
# Queries
# ---------------------------------------------------------------------- #

def test_get_by_status_and_po(db_session, confirmed_po):
    grn = GoodsReceiptService(db_session).create_grn(_grn_payload(confirmed_po))
    service = GoodsReceiptService(db_session)
    assert grn.id in [g.id for g in service.get_by_status(GRNStatus.PENDING_QC)]
    assert grn.id in [g.id for g in service.get_by_po(confirmed_po.id)]
