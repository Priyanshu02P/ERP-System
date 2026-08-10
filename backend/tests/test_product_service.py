import pytest

from app.db.schemas.unit import UnitCreate
from app.db.schemas.product import ProductCreate
from app.db.schemas.supplier import SupplierCreate
from app.db.models.enums import ProductType, SupplierCategory
from app.services.unit_service import UnitService
from app.services.product_service import ProductService
from app.services.supplier_service import SupplierService
from app.services.exceptions import ConflictError, ValidationError


def test_create_product_success(db_session):
    unit = UnitService(db_session).create_unit(UnitCreate(code="PCS", name="Pieces"))
    product = ProductService(db_session).create_product(
        ProductCreate(code="PRD-001", name="Bolt", product_type=ProductType.RAW, unit_id=unit.id)
    )
    assert product.id is not None
    assert product.code == "PRD-001"


def test_create_product_duplicate_code_raises(db_session):
    unit = UnitService(db_session).create_unit(UnitCreate(code="PCS", name="Pieces"))
    service = ProductService(db_session)
    service.create_product(ProductCreate(code="PRD-001", name="Bolt", product_type=ProductType.RAW, unit_id=unit.id))
    with pytest.raises(ConflictError):
        service.create_product(
            ProductCreate(code="PRD-001", name="Other", product_type=ProductType.RAW, unit_id=unit.id)
        )


def test_create_product_missing_unit_raises(db_session):
    service = ProductService(db_session)
    with pytest.raises(ValidationError):
        service.create_product(
            ProductCreate(code="PRD-002", name="Bolt", product_type=ProductType.RAW, unit_id=999)
        )


def test_create_product_with_reorder_fields(db_session):
    unit = UnitService(db_session).create_unit(UnitCreate(code="KG", name="Kilograms"))
    product = ProductService(db_session).create_product(
        ProductCreate(
            code="RM-CRCA-2MM", name="CRCA Sheet 2mm", product_type=ProductType.RAW,
            unit_id=unit.id, reorder_level=300, reorder_quantity=1200,
        )
    )
    assert float(product.reorder_level) == 300
    assert float(product.reorder_quantity) == 1200
    assert product.preferred_supplier_id is None


def test_create_product_invalid_preferred_supplier_raises(db_session):
    unit = UnitService(db_session).create_unit(UnitCreate(code="KG", name="Kilograms"))
    with pytest.raises(ValidationError):
        ProductService(db_session).create_product(
            ProductCreate(
                code="RM-CRCA-2MM", name="CRCA Sheet 2mm", product_type=ProductType.RAW,
                unit_id=unit.id, preferred_supplier_id=999,
            )
        )


def test_create_product_with_valid_preferred_supplier(db_session):
    unit = UnitService(db_session).create_unit(UnitCreate(code="KG", name="Kilograms"))
    supplier = SupplierService(db_session).create_supplier(
        SupplierCreate(code="SUP-001", name="Tata Steel Distributor", category=SupplierCategory.STEEL)
    )
    product = ProductService(db_session).create_product(
        ProductCreate(
            code="RM-CRCA-2MM", name="CRCA Sheet 2mm", product_type=ProductType.RAW,
            unit_id=unit.id, preferred_supplier_id=supplier.id,
        )
    )
    assert product.preferred_supplier_id == supplier.id
