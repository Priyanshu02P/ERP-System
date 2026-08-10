from typing import List

from sqlalchemy.orm import Session

from app.db.models.supplier import Supplier
from app.db.models.enums import SupplierCategory
from app.db.repositories.supplier_repository import SupplierRepository
from app.db.repositories.manufacturer_repository import ManufacturerRepository
from app.db.schemas.supplier import SupplierCreate, SupplierUpdate
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, ValidationError, ReferencedEntityError


class SupplierService(BaseService[Supplier]):
    def __init__(self, db: Session):
        self.repository: SupplierRepository = SupplierRepository(db)
        self.manufacturer_repository = ManufacturerRepository(db)
        super().__init__(self.repository, entity_name="Supplier")

    def validate_manufacturer(self, manufacturer_id: int) -> None:
        if not self.manufacturer_repository.exists(manufacturer_id):
            raise ValidationError(f"Manufacturer with id={manufacturer_id} does not exist")

    def create_supplier(self, data: SupplierCreate) -> Supplier:
        if self.repository.exists_code(data.code):
            raise ConflictError(f"Supplier code '{data.code}' already exists")
        if data.manufacturer_id is not None:
            self.validate_manufacturer(data.manufacturer_id)
        supplier = Supplier(**data.model_dump())
        return self.repository.create(supplier)

    def update_supplier(self, supplier_id: int, data: SupplierUpdate) -> Supplier:
        supplier = self.get(supplier_id)
        payload = data.model_dump(exclude_unset=True)
        if "manufacturer_id" in payload and payload["manufacturer_id"] is not None:
            self.validate_manufacturer(payload["manufacturer_id"])
        for field, value in payload.items():
            setattr(supplier, field, value)
        return self.repository.update(supplier)

    def delete_supplier(self, supplier_id: int) -> None:
        supplier = self.get(supplier_id)
        if supplier.preferred_for_products:
            raise ReferencedEntityError(
                "Cannot delete supplier: it is set as the preferred supplier on one or more products"
            )
        self.repository.delete(supplier)

    def activate_supplier(self, supplier_id: int) -> Supplier:
        return self.repository.activate(self.get(supplier_id))

    def deactivate_supplier(self, supplier_id: int) -> Supplier:
        return self.repository.deactivate(self.get(supplier_id))

    def search(self, term: str) -> List[Supplier]:
        return self.repository.search(term)

    def get_by_category(self, category: SupplierCategory) -> List[Supplier]:
        return self.repository.get_by_category(category)
