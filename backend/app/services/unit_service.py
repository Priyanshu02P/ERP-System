from sqlalchemy.orm import Session

from app.db.models.unit import Unit
from app.db.repositories.unit_repository import UnitRepository
from app.db.schemas.unit import UnitCreate, UnitUpdate
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, ReferencedEntityError


class UnitService(BaseService[Unit]):
    def __init__(self, db: Session):
        self.repository: UnitRepository = UnitRepository(db)
        super().__init__(self.repository, entity_name="Unit")

    def create_unit(self, data: UnitCreate) -> Unit:
        if self.repository.exists_code(data.code):
            raise ConflictError(f"Unit code '{data.code}' already exists")
        unit = Unit(**data.model_dump())
        return self.repository.create(unit)

    def update_unit(self, unit_id: int, data: UnitUpdate) -> Unit:
        unit = self.get(unit_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(unit, field, value)
        return self.repository.update(unit)

    def delete_unit(self, unit_id: int) -> None:
        unit = self.get(unit_id)
        if unit.products:
            raise ReferencedEntityError("Cannot delete unit: still referenced by products")
        self.repository.delete(unit)

    def activate(self, unit_id: int) -> Unit:
        return self.repository.activate(self.get(unit_id))

    def deactivate(self, unit_id: int) -> Unit:
        return self.repository.deactivate(self.get(unit_id))
