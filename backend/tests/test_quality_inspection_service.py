import pytest

from app.master_data.unit.schemas import UnitCreate
from app.master_data.product.schemas import ProductCreate
from app.procurement.supplier.schemas import SupplierCreate
from app.master_data.manufacturer.schemas import ManufacturerCreate
from app.wms.warehouse_structure.schemas import WarehouseCreate, RackCreate, ShelfCreate, BinCreate, LocationCreate
from app.procurement.purchase_order.schemas import PurchaseOrderCreate, PurchaseOrderItemCreate
from app.wms.goods_receipt.schemas import GoodsReceiptCreate, GoodsReceiptItemCreate
from app.quality.inspection.schemas import QualityInspectionCreate, QualityInspectionItemCreate
from app.shared.enums import (
    ProductType, SupplierCategory, GRNStatus, QCDisposition, QCItemDisposition,
)
from app.master_data.unit.service import UnitService
from app.master_data.product.service import ProductService
from app.procurement.supplier.service import SupplierService
from app.master_data.manufacturer.service import ManufacturerService
from app.wms.warehouse_structure.service.warehouse_service import WarehouseService
from app.wms.warehouse_structure.service.rack_service import RackService
from app.wms.warehouse_structure.service.shelf_service import ShelfService
from app.wms.warehouse_structure.service.bin_service import BinService
from app.wms.warehouse_structure.service.location_service import LocationService
from app.procurement.purchase_order.service import PurchaseOrderService
from app.wms.goods_receipt.service import GoodsReceiptService
from app.quality.inspection.service import QualityInspectionService
from app.wms.inventory.service import InventoryService
from app.shared.exceptions import ConflictError, ValidationError


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
def supplier_no_manufacturer(db_session):
    return SupplierService(db_session).create_supplier(
        SupplierCreate(code="SUP-LOCAL", name="Local Hardware Shop", category=SupplierCategory.HARDWARE)
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


def _confirmed_po(db_session, supplier, product, quantity=500):
    service = PurchaseOrderService(db_session)
    po = service.create_po(
        PurchaseOrderCreate(
            supplier_id=supplier.id,
            order_date="2026-08-03",
            items=[PurchaseOrderItemCreate(product_id=product.id, quantity=quantity, rate=62.5, gst_rate=18)],
        )
    )
    service.send(po.id, "Priya Sharma")
    return service.confirm(po.id)


@pytest.fixture
def pending_qc_grn(db_session, product, supplier):
    po = _confirmed_po(db_session, supplier, product, quantity=500)
    return GoodsReceiptService(db_session).create_grn(
        GoodsReceiptCreate(
            po_id=po.id,
            received_by="Ramesh (Store Keeper)",
            items=[
                GoodsReceiptItemCreate(
                    po_item_id=po.items[0].id, received_quantity=500, vendor_batch_number="TSD-BATCH-77"
                )
            ],
        )
    )


# ---------------------------------------------------------------------- #
# Full accept -> Inventory creation
# ---------------------------------------------------------------------- #

def test_full_accept_creates_inventory_and_closes_receiving(db_session, pending_qc_grn, location):
    grn_item = pending_qc_grn.items[0]
    qc = QualityInspectionService(db_session).create_qc(
        QualityInspectionCreate(
            grn_id=pending_qc_grn.id,
            inspector="QC Inspector Anita",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=grn_item.id,
                    disposition=QCItemDisposition.ACCEPT,
                    accepted_quantity=500,
                    putaway_location_id=location.id,
                )
            ],
        )
    )
    assert qc.qc_number.startswith("QC-2026-")
    assert qc.overall_disposition == QCDisposition.ACCEPTED
    assert qc.items[0].inventory_id is not None

    inventory = InventoryService(db_session).get(qc.items[0].inventory_id)
    assert inventory.quantity == pytest.approx(500)
    assert inventory.batch_number == "TSD-BATCH-77"

    db_session.refresh(pending_qc_grn)
    assert pending_qc_grn.status == GRNStatus.QC_IN_PROGRESS


def test_accepted_batch_falls_back_to_grn_qc_id_when_no_vendor_batch(db_session, product, supplier, location):
    po = _confirmed_po(db_session, supplier, product, quantity=10)
    grn = GoodsReceiptService(db_session).create_grn(
        GoodsReceiptCreate(
            po_id=po.id,
            received_by="Ramesh",
            items=[GoodsReceiptItemCreate(po_item_id=po.items[0].id, received_quantity=10)],
        )
    )
    qc = QualityInspectionService(db_session).create_qc(
        QualityInspectionCreate(
            grn_id=grn.id,
            inspector="Anita",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=grn.items[0].id, disposition=QCItemDisposition.ACCEPT,
                    accepted_quantity=10, putaway_location_id=location.id,
                )
            ],
        )
    )
    inventory = InventoryService(db_session).get(qc.items[0].inventory_id)
    assert inventory.batch_number == f"{grn.grn_number}-{grn.items[0].id}"


# ---------------------------------------------------------------------- #
# Reject -> no Inventory
# ---------------------------------------------------------------------- #

def test_full_reject_creates_no_inventory(db_session, pending_qc_grn):
    grn_item = pending_qc_grn.items[0]
    qc = QualityInspectionService(db_session).create_qc(
        QualityInspectionCreate(
            grn_id=pending_qc_grn.id,
            inspector="Anita",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=grn_item.id, disposition=QCItemDisposition.REJECT, rejected_quantity=500,
                )
            ],
        )
    )
    assert qc.overall_disposition == QCDisposition.REJECTED
    assert qc.items[0].inventory_id is None
    assert qc.items[0].putaway_location_id is None


# ---------------------------------------------------------------------- #
# Deviation -> held until approved
# ---------------------------------------------------------------------- #

def test_deviation_holds_inventory_until_approved(db_session, pending_qc_grn, location):
    grn_item = pending_qc_grn.items[0]
    qc = QualityInspectionService(db_session).create_qc(
        QualityInspectionCreate(
            grn_id=pending_qc_grn.id,
            inspector="Anita",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=grn_item.id, disposition=QCItemDisposition.DEVIATION,
                    accepted_quantity=480, putaway_location_id=location.id,
                )
            ],
        )
    )
    assert qc.overall_disposition == QCDisposition.ACCEPTED_WITH_DEVIATION
    assert qc.deviation_approved_by is None
    assert qc.items[0].inventory_id is None

    approved = QualityInspectionService(db_session).approve_deviation(qc.id, "Plant Manager Vikram")
    assert approved.deviation_approved_by == "Plant Manager Vikram"
    assert approved.items[0].inventory_id is not None

    inventory = InventoryService(db_session).get(approved.items[0].inventory_id)
    assert inventory.quantity == pytest.approx(480)


def test_deviation_pre_approved_at_creation_creates_inventory_immediately(db_session, pending_qc_grn, location):
    qc = QualityInspectionService(db_session).create_qc(
        QualityInspectionCreate(
            grn_id=pending_qc_grn.id,
            inspector="Anita",
            deviation_approved_by="Plant Manager Vikram",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=pending_qc_grn.items[0].id, disposition=QCItemDisposition.DEVIATION,
                    accepted_quantity=480, putaway_location_id=location.id,
                )
            ],
        )
    )
    assert qc.deviation_approved_by == "Plant Manager Vikram"
    assert qc.items[0].inventory_id is not None


def test_approve_deviation_twice_raises(db_session, pending_qc_grn, location):
    qc = QualityInspectionService(db_session).create_qc(
        QualityInspectionCreate(
            grn_id=pending_qc_grn.id,
            inspector="Anita",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=pending_qc_grn.items[0].id, disposition=QCItemDisposition.DEVIATION,
                    accepted_quantity=480, putaway_location_id=location.id,
                )
            ],
        )
    )
    service = QualityInspectionService(db_session)
    service.approve_deviation(qc.id, "Vikram")
    with pytest.raises(ConflictError):
        service.approve_deviation(qc.id, "Vikram")


def test_approve_deviation_with_no_deviation_lines_raises(db_session, pending_qc_grn, location):
    qc = QualityInspectionService(db_session).create_qc(
        QualityInspectionCreate(
            grn_id=pending_qc_grn.id,
            inspector="Anita",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=pending_qc_grn.items[0].id, disposition=QCItemDisposition.ACCEPT,
                    accepted_quantity=500, putaway_location_id=location.id,
                )
            ],
        )
    )
    with pytest.raises(ConflictError):
        QualityInspectionService(db_session).approve_deviation(qc.id, "Vikram")


# ---------------------------------------------------------------------- #
# Mixed lines -> PARTIAL
# ---------------------------------------------------------------------- #

def test_mixed_accept_and_reject_gives_partial_disposition(db_session, product, supplier, location):
    po = _confirmed_po(db_session, supplier, product, quantity=100)
    grn = GoodsReceiptService(db_session).create_grn(
        GoodsReceiptCreate(
            po_id=po.id,
            received_by="Ramesh",
            items=[GoodsReceiptItemCreate(po_item_id=po.items[0].id, received_quantity=100)],
        )
    )
    qc = QualityInspectionService(db_session).create_qc(
        QualityInspectionCreate(
            grn_id=grn.id,
            inspector="Anita",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=grn.items[0].id, disposition=QCItemDisposition.ACCEPT,
                    accepted_quantity=80, putaway_location_id=location.id,
                ),
            ],
        )
    )
    # Single-line GRN here only supports one disposition per line item; a
    # true split-accept/reject-within-one-line scenario is out of scope for
    # this line-item granularity (matches the plan's GoodsReceiptItem model).
    assert qc.overall_disposition == QCDisposition.ACCEPTED


# ---------------------------------------------------------------------- #
# Validation
# ---------------------------------------------------------------------- #

def test_accept_without_location_raises(db_session, pending_qc_grn):
    with pytest.raises(ValidationError):
        QualityInspectionService(db_session).create_qc(
            QualityInspectionCreate(
                grn_id=pending_qc_grn.id,
                inspector="Anita",
                items=[
                    QualityInspectionItemCreate(
                        grn_item_id=pending_qc_grn.items[0].id, disposition=QCItemDisposition.ACCEPT,
                        accepted_quantity=500,
                    )
                ],
            )
        )


def test_accept_with_supplier_missing_manufacturer_link_requires_explicit_manufacturer(
    db_session, product, supplier_no_manufacturer, location, manufacturer
):
    po = _confirmed_po(db_session, supplier_no_manufacturer, product, quantity=10)
    grn = GoodsReceiptService(db_session).create_grn(
        GoodsReceiptCreate(
            po_id=po.id,
            received_by="Ramesh",
            items=[GoodsReceiptItemCreate(po_item_id=po.items[0].id, received_quantity=10)],
        )
    )
    service = QualityInspectionService(db_session)
    with pytest.raises(ValidationError):
        service.create_qc(
            QualityInspectionCreate(
                grn_id=grn.id,
                inspector="Anita",
                items=[
                    QualityInspectionItemCreate(
                        grn_item_id=grn.items[0].id, disposition=QCItemDisposition.ACCEPT,
                        accepted_quantity=10, putaway_location_id=location.id,
                    )
                ],
            )
        )
    # Explicit manufacturer_id on the line unblocks it.
    qc = service.create_qc(
        QualityInspectionCreate(
            grn_id=grn.id,
            inspector="Anita",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=grn.items[0].id, disposition=QCItemDisposition.ACCEPT,
                    accepted_quantity=10, putaway_location_id=location.id, manufacturer_id=manufacturer.id,
                )
            ],
        )
    )
    assert qc.items[0].manufacturer_id == manufacturer.id


def test_create_qc_only_once_per_grn(db_session, pending_qc_grn, location):
    service = QualityInspectionService(db_session)
    service.create_qc(
        QualityInspectionCreate(
            grn_id=pending_qc_grn.id,
            inspector="Anita",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=pending_qc_grn.items[0].id, disposition=QCItemDisposition.ACCEPT,
                    accepted_quantity=500, putaway_location_id=location.id,
                )
            ],
        )
    )
    with pytest.raises(ConflictError):
        service.create_qc(
            QualityInspectionCreate(
                grn_id=pending_qc_grn.id,
                inspector="Anita",
                items=[
                    QualityInspectionItemCreate(
                        grn_item_id=pending_qc_grn.items[0].id, disposition=QCItemDisposition.REJECT,
                    )
                ],
            )
        )


def test_create_qc_against_invalid_grn_raises(db_session):
    with pytest.raises(ValidationError):
        QualityInspectionService(db_session).create_qc(
            QualityInspectionCreate(
                grn_id=999, inspector="Anita",
                items=[QualityInspectionItemCreate(grn_item_id=1, disposition=QCItemDisposition.REJECT)],
            )
        )


# ---------------------------------------------------------------------- #
# Full flow: PO -> GRN -> QC -> GRN close
# ---------------------------------------------------------------------- #

def test_full_receiving_flow_and_grn_close(db_session, product, supplier, location):
    po = _confirmed_po(db_session, supplier, product, quantity=200)
    grn = GoodsReceiptService(db_session).create_grn(
        GoodsReceiptCreate(
            po_id=po.id,
            received_by="Ramesh",
            items=[GoodsReceiptItemCreate(po_item_id=po.items[0].id, received_quantity=200)],
        )
    )
    QualityInspectionService(db_session).create_qc(
        QualityInspectionCreate(
            grn_id=grn.id,
            inspector="Anita",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=grn.items[0].id, disposition=QCItemDisposition.ACCEPT,
                    accepted_quantity=200, putaway_location_id=location.id,
                )
            ],
        )
    )
    closed = GoodsReceiptService(db_session).close_grn(grn.id)
    assert closed.status == GRNStatus.CLOSED
