import pytest

from app.db.schemas.supplier import SupplierCreate, SupplierUpdate
from app.db.schemas.manufacturer import ManufacturerCreate
from app.db.schemas.unit import UnitCreate
from app.db.schemas.product import ProductCreate
from app.db.models.enums import SupplierCategory, ProductType
from app.services.supplier_service import SupplierService
from app.services.manufacturer_service import ManufacturerService
from app.services.unit_service import UnitService
from app.services.product_service import ProductService
from app.services.exceptions import ConflictError, ValidationError, ReferencedEntityError


def _make_supplier(db_session, **overrides):
    payload = dict(code="SUP-001", name="Tata Steel Distributor", category=SupplierCategory.STEEL)
    payload.update(overrides)
    return SupplierService(db_session).create_supplier(SupplierCreate(**payload))


def test_create_supplier_success(db_session):
    supplier = _make_supplier(db_session)
    assert supplier.id is not None
    assert supplier.code == "SUP-001"
    assert supplier.category == SupplierCategory.STEEL
    assert supplier.is_active is True


def test_gstin_normalized_to_uppercase(db_session):
    supplier = _make_supplier(db_session, gstin="24aabct1234m1z5")
    assert supplier.gstin == "24AABCT1234M1Z5"


def test_create_supplier_duplicate_code_raises(db_session):
    _make_supplier(db_session)
    with pytest.raises(ConflictError):
        _make_supplier(db_session, name="Another Vendor")


def test_create_supplier_invalid_manufacturer_raises(db_session):
    with pytest.raises(ValidationError):
        _make_supplier(db_session, manufacturer_id=999)


def test_create_supplier_with_valid_manufacturer_link(db_session):
    manufacturer = ManufacturerService(db_session).create(
        ManufacturerCreate(code="MFG-001", name="Tata Steel")
    )
    supplier = _make_supplier(db_session, manufacturer_id=manufacturer.id)
    assert supplier.manufacturer_id == manufacturer.id


def test_activate_deactivate_supplier(db_session):
    service = SupplierService(db_session)
    supplier = _make_supplier(db_session)
    deactivated = service.deactivate_supplier(supplier.id)
    assert deactivated.is_active is False
    reactivated = service.activate_supplier(supplier.id)
    assert reactivated.is_active is True


def test_update_supplier(db_session):
    service = SupplierService(db_session)
    supplier = _make_supplier(db_session)
    updated = service.update_supplier(supplier.id, SupplierUpdate(default_payment_terms="Net 30"))
    assert updated.default_payment_terms == "Net 30"
    assert updated.code == "SUP-001"  # unchanged


def test_search_supplier_by_name_or_code(db_session):
    _make_supplier(db_session)
    service = SupplierService(db_session)
    assert len(service.search("Tata")) == 1
    assert len(service.search("SUP-001")) == 1
    assert len(service.search("no-match")) == 0


def test_delete_supplier_blocked_when_preferred_by_product(db_session):
    supplier = _make_supplier(db_session)
    unit = UnitService(db_session).create_unit(UnitCreate(code="KG", name="Kilograms"))
    ProductService(db_session).create_product(
        ProductCreate(
            code="RM-CRCA-2MM", name="CRCA Sheet 2mm", product_type=ProductType.RAW,
            unit_id=unit.id, preferred_supplier_id=supplier.id,
        )
    )
    with pytest.raises(ReferencedEntityError):
        SupplierService(db_session).delete_supplier(supplier.id)


def test_get_by_category(db_session):
    _make_supplier(db_session, code="SUP-001", category=SupplierCategory.STEEL)
    _make_supplier(db_session, code="SUP-002", name="Hafele", category=SupplierCategory.HARDWARE)
    assert len(SupplierService(db_session).get_by_category(SupplierCategory.STEEL)) == 1
    assert len(SupplierService(db_session).get_by_category(SupplierCategory.HARDWARE)) == 1
