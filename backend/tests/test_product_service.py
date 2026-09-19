import pytest

from app.master_data.unit.schemas import UnitCreate
from app.master_data.product.schemas import ProductCreate
from app.procurement.supplier.schemas import SupplierCreate
from app.shared.enums import ProductType, SupplierCategory
from app.master_data.unit.service import UnitService
from app.master_data.product.service import ProductService
from app.procurement.supplier.service import SupplierService
from app.shared.exceptions import ConflictError, ValidationError


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
