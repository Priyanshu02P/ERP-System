from datetime import date

import pytest

from app.db.schemas.unit import UnitCreate
from app.db.schemas.product import ProductCreate
from app.db.schemas.manufacturer import ManufacturerCreate
from app.db.schemas.warehouse import WarehouseCreate, RackCreate, ShelfCreate, BinCreate, LocationCreate
from app.db.schemas.inventory import InventoryCreate
from app.db.models.enums import ProductType, InventoryStatus, LocationCategory

from app.services.unit_service import UnitService
from app.services.product_service import ProductService
from app.services.manufacturer_service import ManufacturerService
from app.services.warehouse_service import WarehouseService
from app.services.rack_service import RackService
from app.services.shelf_service import ShelfService
from app.services.bin_service import BinService
from app.services.location_service import LocationService
from app.services.inventory_service import InventoryService
from app.services.exceptions import ValidationError


def _make_base_entities(db_session):
    unit = UnitService(db_session).create_unit(UnitCreate(code="PCS", name="Pieces"))
    product = ProductService(db_session).create_product(
        ProductCreate(code="FG-001", name="Widget", product_type=ProductType.FG, unit_id=unit.id)
    )
    manufacturer = ManufacturerService(db_session).create(
        ManufacturerCreate(code="MFG-1", name="Acme Corp")
    )
    warehouse = WarehouseService(db_session).create(WarehouseCreate(code="WH1", name="Main Warehouse"))
    rack = RackService(db_session).create(RackCreate(code="A", warehouse_id=warehouse.id))
    shelf = ShelfService(db_session).create(ShelfCreate(code="03", rack_id=rack.id))
    bin_ = BinService(db_session).create(BinCreate(code="05", shelf_id=shelf.id))
    location = LocationService(db_session).create_location(
        LocationCreate(warehouse_id=warehouse.id, rack_id=rack.id, shelf_id=shelf.id, bin_id=bin_.id)
    )
    return product, manufacturer, location


def test_location_code_matches_expected_format(db_session):
    _, _, location = _make_base_entities(db_session)
    assert location.location_code == "WH1-A-03-05"


def test_shelf_without_rack_is_rejected(db_session):
    warehouse = WarehouseService(db_session).create(WarehouseCreate(code="WH3", name="Overflow"))
    with pytest.raises(ValidationError):
        LocationService(db_session).validate_hierarchy(
            LocationCreate(warehouse_id=warehouse.id, shelf_id=1)
        )


def test_receive_stock_and_location_display(db_session):
    product, manufacturer, location = _make_base_entities(db_session)
    service = InventoryService(db_session)
    inventory = service.receive_stock(
        InventoryCreate(
            product_id=product.id,
            manufacturer_id=manufacturer.id,
            location_id=location.id,
            batch_number="B-100",
            manufacturing_date=date(2026, 1, 1),
            quantity=50,
            status=InventoryStatus.OK,
        )
    )
    assert service.get_location_display(inventory) == "FG-WH1-A-03-05"


def test_reserve_cannot_exceed_available(db_session):
    product, manufacturer, location = _make_base_entities(db_session)
    service = InventoryService(db_session)
    inventory = service.receive_stock(
        InventoryCreate(
            product_id=product.id,
            manufacturer_id=manufacturer.id,
            location_id=location.id,
            batch_number="B-100",
            manufacturing_date=date(2026, 1, 1),
            quantity=10,
        )
    )
    with pytest.raises(ValidationError):
        service.reserve_stock(inventory.id, 20)


def test_issue_stock_reduces_quantity(db_session):
    product, manufacturer, location = _make_base_entities(db_session)
    service = InventoryService(db_session)
    inventory = service.receive_stock(
        InventoryCreate(
            product_id=product.id,
            manufacturer_id=manufacturer.id,
            location_id=location.id,
            batch_number="B-100",
            manufacturing_date=date(2026, 1, 1),
            quantity=10,
        )
    )
    updated = service.issue_stock(inventory.id, 4)
    assert float(updated.quantity) == 6
