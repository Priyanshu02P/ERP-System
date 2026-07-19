from typing import List

from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.db.repositories.product_repository import ProductRepository
from app.db.repositories.unit_repository import UnitRepository
from app.db.schemas.product import ProductCreate, ProductUpdate
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, ValidationError, ReferencedEntityError


class ProductService(BaseService[Product]):
    def __init__(self, db: Session):
        self.repository: ProductRepository = ProductRepository(db)
        self.unit_repository = UnitRepository(db)
        super().__init__(self.repository, entity_name="Product")

    def validate_product(self, unit_id: int) -> None:
        if not self.unit_repository.exists(unit_id):
            raise ValidationError(f"Unit with id={unit_id} does not exist")

    def create_product(self, data: ProductCreate) -> Product:
        if self.repository.exists_product_code(data.code):
            raise ConflictError(f"Product code '{data.code}' already exists")
        self.validate_product(data.unit_id)
        product = Product(**data.model_dump())
        return self.repository.create(product)

    def update_product(self, product_id: int, data: ProductUpdate) -> Product:
        product = self.get(product_id)
        payload = data.model_dump(exclude_unset=True)
        if "unit_id" in payload:
            self.validate_product(payload["unit_id"])
        for field, value in payload.items():
            setattr(product, field, value)
        return self.repository.update(product)

    def delete_product(self, product_id: int) -> None:
        product = self.get(product_id)
        if product.inventories:
            raise ReferencedEntityError("Cannot delete product: inventory records still reference it")
        self.repository.delete(product)

    def activate_product(self, product_id: int) -> Product:
        return self.repository.activate(self.get(product_id))

    def deactivate_product(self, product_id: int) -> Product:
        return self.repository.deactivate(self.get(product_id))

    def change_unit(self, product_id: int, unit_id: int) -> Product:
        product = self.get(product_id)
        self.validate_product(unit_id)
        product.unit_id = unit_id
        return self.repository.update(product)

    def search_products(self, term: str) -> List[Product]:
        return self.repository.search_by_name(term)
