from datetime import date, timedelta

import pytest

from app.master_data.unit.schemas import UnitCreate
from app.master_data.product.schemas import ProductCreate, ProductUpdate
from app.procurement.supplier.schemas import SupplierCreate
from app.master_data.manufacturer.schemas import ManufacturerCreate
from app.wms.warehouse_structure.schemas import WarehouseCreate, RackCreate, ShelfCreate, BinCreate, LocationCreate
from app.wms.inventory.schemas import InventoryCreate
from app.procurement.requisition.schemas import PurchaseRequisitionCreate, PurchaseRequisitionItemCreate
from app.procurement.purchase_order.schemas import PurchaseOrderCreate, PurchaseOrderItemCreate
from app.wms.goods_receipt.schemas import GoodsReceiptCreate, GoodsReceiptItemCreate
from app.quality.inspection.schemas import QualityInspectionCreate, QualityInspectionItemCreate
from app.shared.enums import ProductType, SupplierCategory, InventoryStatus, QCItemDisposition
from app.master_data.unit.service import UnitService
from app.master_data.product.service import ProductService
from app.procurement.supplier.service import SupplierService
from app.master_data.manufacturer.service import ManufacturerService
from app.wms.warehouse_structure.service.warehouse_service import WarehouseService
from app.wms.warehouse_structure.service.rack_service import RackService
from app.wms.warehouse_structure.service.shelf_service import ShelfService
from app.wms.warehouse_structure.service.bin_service import BinService
from app.wms.warehouse_structure.service.location_service import LocationService
from app.wms.inventory.service import InventoryService
from app.procurement.requisition.service import PurchaseRequisitionService
from app.procurement.purchase_order.service import PurchaseOrderService
from app.wms.goods_receipt.service import GoodsReceiptService
from app.quality.inspection.service import QualityInspectionService
from app.procurement.dashboard.service import ProcurementDashboardService


@pytest.fixture
def unit(db_session):
    return UnitService(db_session).create_unit(UnitCreate(code="KG", name="Kilograms"))


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
def location(db_session):
    warehouse = WarehouseService(db_session).create(WarehouseCreate(code="WH1", name="Main Warehouse"))
    rack = RackService(db_session).create(RackCreate(code="A", warehouse_id=warehouse.id))
    shelf = ShelfService(db_session).create(ShelfCreate(code="03", rack_id=rack.id))
    bin_ = BinService(db_session).create(BinCreate(code="05", shelf_id=shelf.id))
    return LocationService(db_session).create_location(
        LocationCreate(warehouse_id=warehouse.id, rack_id=rack.id, shelf_id=shelf.id, bin_id=bin_.id)
    )


def _confirmed_po(db_session, supplier, product, quantity=500, expected_delivery_date=None):
    service = PurchaseOrderService(db_session)
    po = service.create_po(
        PurchaseOrderCreate(
            supplier_id=supplier.id, order_date="2026-08-03", expected_delivery_date=expected_delivery_date,
            items=[PurchaseOrderItemCreate(product_id=product.id, quantity=quantity, rate=62.5, gst_rate=18)],
        )
    )
    service.send(po.id, "Priya Sharma")
    return service.confirm(po.id)


# ---------------------------------------------------------------------- #
# KPIs
# ---------------------------------------------------------------------- #

def test_pending_prs_counts_only_pending_approval(db_session, unit, product=None):
    product = ProductService(db_session).create_product(
        ProductCreate(code="RM-1", name="Raw 1", product_type=ProductType.RAW, unit_id=unit.id)
    )
    pr_service = PurchaseRequisitionService(db_session)
    draft_pr = pr_service.create_pr(
        PurchaseRequisitionCreate(
            department="Production", raised_by="Store Keeper", required_by_date="2026-09-01",
            items=[PurchaseRequisitionItemCreate(product_id=product.id, quantity=10)],
        )
    )
    submitted_pr = pr_service.create_pr(
        PurchaseRequisitionCreate(
            department="Production", raised_by="Store Keeper", required_by_date="2026-09-01",
            items=[PurchaseRequisitionItemCreate(product_id=product.id, quantity=20)],
        )
    )
    pr_service.submit(submitted_pr.id)

    kpis = ProcurementDashboardService(db_session).get_kpis()
    assert kpis.pending_prs == 1  # only the submitted one, draft_pr doesn't count
    assert draft_pr.id  # keep draft_pr referenced/used


def test_pos_awaiting_grn_counts_confirmed_and_partially_received(db_session, supplier, unit, location):
    product = ProductService(db_session).create_product(
        ProductCreate(code="RM-2", name="Raw 2", product_type=ProductType.RAW, unit_id=unit.id)
    )
    po1 = _confirmed_po(db_session, supplier, product, quantity=100)  # stays CONFIRMED
    po2 = _confirmed_po(db_session, supplier, product, quantity=200)  # will become PARTIALLY_RECEIVED

    GoodsReceiptService(db_session).create_grn(
        GoodsReceiptCreate(
            po_id=po2.id, received_by="Ramesh",
            items=[GoodsReceiptItemCreate(po_item_id=po2.items[0].id, received_quantity=100)],
        )
    )

    kpis = ProcurementDashboardService(db_session).get_kpis()
    assert kpis.pos_awaiting_grn == 2  # one CONFIRMED, one PARTIALLY_RECEIVED


def test_grns_awaiting_qc_counts_pending_qc_only(db_session, supplier, unit, location):
    product = ProductService(db_session).create_product(
        ProductCreate(code="RM-3", name="Raw 3", product_type=ProductType.RAW, unit_id=unit.id)
    )
    po = _confirmed_po(db_session, supplier, product, quantity=100)
    grn = GoodsReceiptService(db_session).create_grn(
        GoodsReceiptCreate(
            po_id=po.id, received_by="Ramesh",
            items=[GoodsReceiptItemCreate(po_item_id=po.items[0].id, received_quantity=100)],
        )
    )
    assert ProcurementDashboardService(db_session).get_kpis().grns_awaiting_qc == 1

    QualityInspectionService(db_session).create_qc(
        QualityInspectionCreate(
            grn_id=grn.id, inspector="Anita",
            items=[
                QualityInspectionItemCreate(
                    grn_item_id=grn.items[0].id, disposition=QCItemDisposition.ACCEPT,
                    accepted_quantity=100, putaway_location_id=location.id,
                )
            ],
        )
    )
    assert ProcurementDashboardService(db_session).get_kpis().grns_awaiting_qc == 0


def test_overdue_deliveries(db_session, supplier, unit):
    product = ProductService(db_session).create_product(
        ProductCreate(code="RM-4", name="Raw 4", product_type=ProductType.RAW, unit_id=unit.id)
    )
    past = (date.today() - timedelta(days=5)).isoformat()
    future = (date.today() + timedelta(days=5)).isoformat()

    overdue_po = _confirmed_po(db_session, supplier, product, quantity=50, expected_delivery_date=past)
    _confirmed_po(db_session, supplier, product, quantity=50, expected_delivery_date=future)  # not overdue
    _confirmed_po(db_session, supplier, product, quantity=50, expected_delivery_date=None)  # no date, not overdue

    kpis = ProcurementDashboardService(db_session).get_kpis()
    assert kpis.overdue_deliveries == 1
    assert kpis.overdue_purchase_order_ids == [overdue_po.id]


def test_fully_received_po_is_not_overdue_even_if_date_passed(db_session, supplier, unit, location):
    product = ProductService(db_session).create_product(
        ProductCreate(code="RM-5", name="Raw 5", product_type=ProductType.RAW, unit_id=unit.id)
    )
    past = (date.today() - timedelta(days=5)).isoformat()
    po = _confirmed_po(db_session, supplier, product, quantity=50, expected_delivery_date=past)
    GoodsReceiptService(db_session).create_grn(
        GoodsReceiptCreate(
            po_id=po.id, received_by="Ramesh",
            items=[GoodsReceiptItemCreate(po_item_id=po.items[0].id, received_quantity=50)],
        )
    )
    kpis = ProcurementDashboardService(db_session).get_kpis()
    assert kpis.overdue_deliveries == 0  # RECEIVED, no longer "awaiting"


# ---------------------------------------------------------------------- #
# Reorder suggestions
# ---------------------------------------------------------------------- #

def test_reorder_suggestion_when_stock_at_or_below_threshold(db_session, unit, supplier):
    product = ProductService(db_session).create_product(
        ProductCreate(
            code="RM-LOW", name="Low Stock Item", product_type=ProductType.RAW, unit_id=unit.id,
            reorder_level=100, reorder_quantity=500, preferred_supplier_id=supplier.id,
        )
    )
    suggestions = ProcurementDashboardService(db_session).get_reorder_suggestions()
    matching = [s for s in suggestions if s.product_id == product.id]
    assert len(matching) == 1
    suggestion = matching[0]
    assert suggestion.available_stock == 0
    assert suggestion.reorder_level == 100
    assert suggestion.reorder_quantity == 500
    assert suggestion.preferred_supplier_id == supplier.id
    assert suggestion.preferred_supplier_name == supplier.name


def test_no_reorder_suggestion_when_stock_above_threshold(db_session, unit, location, manufacturer):
    product = ProductService(db_session).create_product(
        ProductCreate(
            code="RM-OK", name="Well Stocked Item", product_type=ProductType.RAW, unit_id=unit.id,
            reorder_level=50,
        )
    )
    InventoryService(db_session).create_inventory(
        InventoryCreate(
            product_id=product.id, manufacturer_id=manufacturer.id, location_id=location.id,
            batch_number="B1", manufacturing_date="2026-01-01", quantity=200, status=InventoryStatus.OK,
        )
    )
    suggestions = ProcurementDashboardService(db_session).get_reorder_suggestions()
    assert product.id not in [s.product_id for s in suggestions]


def test_no_reorder_suggestion_without_reorder_level_set(db_session, unit):
    product = ProductService(db_session).create_product(
        ProductCreate(code="RM-NOLEVEL", name="No Threshold Item", product_type=ProductType.RAW, unit_id=unit.id)
    )
    suggestions = ProcurementDashboardService(db_session).get_reorder_suggestions()
    assert product.id not in [s.product_id for s in suggestions]


def test_no_reorder_suggestion_for_inactive_product(db_session, unit):
    product = ProductService(db_session).create_product(
        ProductCreate(code="RM-INACTIVE", name="Inactive Item", product_type=ProductType.RAW, unit_id=unit.id, reorder_level=10)
    )
    ProductService(db_session).deactivate_product(product.id)
    suggestions = ProcurementDashboardService(db_session).get_reorder_suggestions()
    assert product.id not in [s.product_id for s in suggestions]


def test_non_ok_status_stock_does_not_count_toward_available(db_session, unit, location, manufacturer):
    product = ProductService(db_session).create_product(
        ProductCreate(code="RM-DMG", name="Damaged Stock Item", product_type=ProductType.RAW, unit_id=unit.id, reorder_level=50)
    )
    InventoryService(db_session).create_inventory(
        InventoryCreate(
            product_id=product.id, manufacturer_id=manufacturer.id, location_id=location.id,
            batch_number="B1", manufacturing_date="2026-01-01", quantity=500, status=InventoryStatus.DMG,
        )
    )
    suggestions = ProcurementDashboardService(db_session).get_reorder_suggestions()
    matching = [s for s in suggestions if s.product_id == product.id]
    assert len(matching) == 1
    assert matching[0].available_stock == 0  # DMG stock doesn't count as available
