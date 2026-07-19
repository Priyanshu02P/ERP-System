from typing import List

from sqlalchemy.orm import Session

from app.db.models.manufacturer import Manufacturer
from app.db.repositories.manufacturer_repository import ManufacturerRepository
from app.db.schemas.manufacturer import ManufacturerCreate, ManufacturerUpdate
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, ReferencedEntityError


class ManufacturerService(BaseService[Manufacturer]):
    def __init__(self, db: Session):
        self.repository: ManufacturerRepository = ManufacturerRepository(db)
        super().__init__(self.repository, entity_name="Manufacturer")

    def create(self, data: ManufacturerCreate) -> Manufacturer:
        if self.repository.exists_code(data.code):
            raise ConflictError(f"Manufacturer code '{data.code}' already exists")
        manufacturer = Manufacturer(**data.model_dump())
        return self.repository.create(manufacturer)

    def update(self, manufacturer_id: int, data: ManufacturerUpdate) -> Manufacturer:
        manufacturer = self.get(manufacturer_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(manufacturer, field, value)
        return self.repository.update(manufacturer)

    def delete(self, manufacturer_id: int) -> None:
        manufacturer = self.get(manufacturer_id)
        if manufacturer.inventories:
            raise ReferencedEntityError("Cannot delete manufacturer: inventory still exists for it")
        self.repository.delete(manufacturer)

    def activate(self, manufacturer_id: int) -> Manufacturer:
        return self.repository.activate(self.get(manufacturer_id))

    def deactivate(self, manufacturer_id: int) -> Manufacturer:
        return self.repository.deactivate(self.get(manufacturer_id))

    def search(self, term: str) -> List[Manufacturer]:
        return self.repository.search(term)
