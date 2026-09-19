from typing import List

from sqlalchemy.orm import Session

from app.master_data.product.models import Product
from app.master_data.product.repository import ProductRepository
from app.master_data.unit.repository import UnitRepository
from app.procurement.supplier.repository import SupplierRepository
from app.master_data.product.schemas import ProductCreate, ProductUpdate
from app.shared.base_service import BaseService
from app.shared.exceptions import ConflictError, ValidationError, ReferencedEntityError


class ProductService(BaseService[Product]):
    """Product master (RAW/WIP/FG). Carries reorder_level/reorder_quantity
    and an optional preferred_supplier_id, which the (future) reorder-digest
    workflow reads to decide what to raise a PurchaseRequisition for."""

    def __init__(self, db: Session):
        self.repository: ProductRepository = ProductRepository(db)
        self.unit_repository = UnitRepository(db)
        self.supplier_repository = SupplierRepository(db)
        super().__init__(self.repository, entity_name="Product")

    def validate_product(self, unit_id: int) -> None:
        if not self.unit_repository.exists(unit_id):
            raise ValidationError(f"Unit with id={unit_id} does not exist")

    def validate_preferred_supplier(self, supplier_id: int) -> None:
        if not self.supplier_repository.exists(supplier_id):
            raise ValidationError(f"Supplier with id={supplier_id} does not exist")

    def create_product(self, data: ProductCreate) -> Product:
        if self.repository.exists_product_code(data.code):
            raise ConflictError(f"Product code '{data.code}' already exists")
        self.validate_product(data.unit_id)
        if data.preferred_supplier_id is not None:
            self.validate_preferred_supplier(data.preferred_supplier_id)
        product = Product(**data.model_dump())
        return self.repository.create(product)

    def update_product(self, product_id: int, data: ProductUpdate) -> Product:
        product = self.get(product_id)
        payload = data.model_dump(exclude_unset=True)
        if "unit_id" in payload:
            self.validate_product(payload["unit_id"])
        if "preferred_supplier_id" in payload and payload["preferred_supplier_id"] is not None:
            self.validate_preferred_supplier(payload["preferred_supplier_id"])
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
