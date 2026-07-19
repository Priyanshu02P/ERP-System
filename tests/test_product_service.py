import pytest

from app.db.schemas.unit import UnitCreate
from app.db.schemas.product import ProductCreate
from app.db.models.enums import ProductType
from app.services.unit_service import UnitService
from app.services.product_service import ProductService
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
