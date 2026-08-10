import pytest

from app.db.schemas.unit import UnitCreate
from app.db.schemas.product import ProductCreate
from app.db.schemas.purchase_requisition import (
    PurchaseRequisitionCreate,
    PurchaseRequisitionUpdate,
    PurchaseRequisitionItemCreate,
)
from app.db.models.enums import ProductType, PRStatus, PRPriority, SourceChannel
from app.services.unit_service import UnitService
from app.services.product_service import ProductService
from app.services.purchase_requisition_service import PurchaseRequisitionService
from app.services.exceptions import ConflictError, ValidationError, NotFoundError


@pytest.fixture
def product(db_session):
    unit = UnitService(db_session).create_unit(UnitCreate(code="KG", name="Kilograms"))
    return ProductService(db_session).create_product(
        ProductCreate(code="RM-CRCA-2MM", name="CRCA Sheet 2mm", product_type=ProductType.RAW, unit_id=unit.id)
    )


def _make_pr(db_session, product, **overrides):
    payload = dict(
        department="Production Planning",
        raised_by="Rakesh Patel",
        required_by_date="2026-08-10",
        items=[PurchaseRequisitionItemCreate(product_id=product.id, quantity=1200)],
    )
    payload.update(overrides)
    return PurchaseRequisitionService(db_session).create_pr(PurchaseRequisitionCreate(**payload))


def test_create_pr_success(db_session, product):
    pr = _make_pr(db_session, product)
    assert pr.status == PRStatus.DRAFT
    assert pr.pr_number.startswith("PR-2026-")
    assert pr.pr_number.endswith("00001")
    assert len(pr.items) == 1
    assert pr.items[0].current_stock_snapshot == 0  # no inventory exists yet


def test_pr_number_increments(db_session, product):
    pr1 = _make_pr(db_session, product)
    pr2 = _make_pr(db_session, product)
    assert pr1.pr_number != pr2.pr_number
    assert pr2.pr_number.endswith("00002")


def test_create_pr_with_invalid_product_raises(db_session):
    with pytest.raises(ValidationError):
        _make_pr(db_session, product=type("P", (), {"id": 999})())


def test_create_pr_requires_at_least_one_item(db_session, product):
    with pytest.raises(Exception):
        # min_length=1 on items is enforced by Pydantic itself (ValidationError from pydantic,
        # not our ValidationError) - either way, creation must fail.
        PurchaseRequisitionCreate(
            department="Production Planning", raised_by="Rakesh Patel",
            required_by_date="2026-08-10", items=[],
        )


def test_default_priority_and_source(db_session, product):
    pr = _make_pr(db_session, product)
    assert pr.priority == PRPriority.NORMAL
    assert pr.source == SourceChannel.MANUAL


def test_urgent_priority_and_auto_reorder_source(db_session, product):
    pr = _make_pr(db_session, product, priority=PRPriority.URGENT, source=SourceChannel.AUTO_REORDER)
    assert pr.priority == PRPriority.URGENT
    assert pr.source == SourceChannel.AUTO_REORDER


def test_add_item_only_while_draft(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    updated = service.add_item(pr.id, PurchaseRequisitionItemCreate(product_id=product.id, quantity=50))
    assert len(updated.items) == 2

    service.submit(pr.id)
    with pytest.raises(ConflictError):
        service.add_item(pr.id, PurchaseRequisitionItemCreate(product_id=product.id, quantity=10))


def test_remove_item_blocks_when_only_one_left(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    with pytest.raises(ValidationError):
        service.remove_item(pr.id, pr.items[0].id)


def test_remove_item_not_found_raises(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    service.add_item(pr.id, PurchaseRequisitionItemCreate(product_id=product.id, quantity=50))
    with pytest.raises(NotFoundError):
        service.remove_item(pr.id, 9999)


def test_submit_moves_draft_to_pending_approval(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    submitted = service.submit(pr.id)
    assert submitted.status == PRStatus.PENDING_APPROVAL


def test_submit_twice_raises_conflict(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    service.submit(pr.id)
    with pytest.raises(ConflictError):
        service.submit(pr.id)


def test_approve_requires_pending_approval_status(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    with pytest.raises(ConflictError):
        service.approve(pr.id, "Purchase Manager")  # still DRAFT


def test_approve_sets_status_and_audit_fields(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    service.submit(pr.id)
    approved = service.approve(pr.id, "Purchase Manager")
    assert approved.status == PRStatus.APPROVED
    assert approved.approved_by == "Purchase Manager"
    assert approved.approved_at is not None


def test_reject_sets_status_and_reason(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    service.submit(pr.id)
    rejected = service.reject(pr.id, "Purchase Manager", "Budget exceeded this month")
    assert rejected.status == PRStatus.REJECTED
    assert rejected.rejected_by == "Purchase Manager"
    assert rejected.rejection_reason == "Budget exceeded this month"


def test_reject_requires_pending_approval_status(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    with pytest.raises(ConflictError):
        service.reject(pr.id, "Purchase Manager", "not applicable yet")


def test_update_blocked_once_submitted(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    service.submit(pr.id)
    with pytest.raises(ConflictError):
        service.update_pr(pr.id, PurchaseRequisitionUpdate(reason="changed my mind"))


def test_update_allowed_while_draft(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    updated = service.update_pr(pr.id, PurchaseRequisitionUpdate(reason="Reorder level breached"))
    assert updated.reason == "Reorder level breached"


def test_delete_blocked_once_submitted(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    service.submit(pr.id)
    with pytest.raises(ConflictError):
        service.delete_pr(pr.id)


def test_delete_allowed_while_draft(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr = _make_pr(db_session, product)
    service.delete_pr(pr.id)
    with pytest.raises(NotFoundError):
        service.get(pr.id)


def test_get_by_status(db_session, product):
    service = PurchaseRequisitionService(db_session)
    pr1 = _make_pr(db_session, product)
    pr2 = _make_pr(db_session, product)
    service.submit(pr2.id)
    assert len(service.get_by_status(PRStatus.DRAFT)) == 1
    assert len(service.get_by_status(PRStatus.PENDING_APPROVAL)) == 1


def test_get_by_department(db_session, product):
    service = PurchaseRequisitionService(db_session)
    _make_pr(db_session, product, department="Production Planning")
    _make_pr(db_session, product, department="Store")
    assert len(service.get_by_department("Production Planning")) == 1
    assert len(service.get_by_department("Store")) == 1


def test_stock_snapshot_reflects_available_inventory(db_session, product):
    from datetime import date as _date

    from app.db.schemas.manufacturer import ManufacturerCreate
    from app.db.schemas.warehouse import WarehouseCreate, RackCreate, ShelfCreate, BinCreate, LocationCreate
    from app.db.schemas.inventory import InventoryCreate
    from app.services.manufacturer_service import ManufacturerService
    from app.services.warehouse_service import WarehouseService
    from app.services.rack_service import RackService
    from app.services.shelf_service import ShelfService
    from app.services.bin_service import BinService
    from app.services.location_service import LocationService
    from app.services.inventory_service import InventoryService

    manufacturer = ManufacturerService(db_session).create(ManufacturerCreate(code="MFG-1", name="Tata Steel"))
    warehouse = WarehouseService(db_session).create(WarehouseCreate(code="WH1", name="Main Warehouse"))
    rack = RackService(db_session).create(RackCreate(code="A", warehouse_id=warehouse.id))
    shelf = ShelfService(db_session).create(ShelfCreate(code="03", rack_id=rack.id))
    bin_ = BinService(db_session).create(BinCreate(code="05", shelf_id=shelf.id))
    location = LocationService(db_session).create_location(
        LocationCreate(warehouse_id=warehouse.id, rack_id=rack.id, shelf_id=shelf.id, bin_id=bin_.id)
    )
    InventoryService(db_session).receive_stock(
        InventoryCreate(
            product_id=product.id, manufacturer_id=manufacturer.id, location_id=location.id,
            batch_number="B-001", manufacturing_date=_date(2026, 1, 1), quantity=180,
        )
    )

    pr = _make_pr(db_session, product)
    assert float(pr.items[0].current_stock_snapshot) == 180
