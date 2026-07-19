from sqlalchemy.orm import Session

from app.db.models.warehouse import Warehouse
from app.db.models.rack import Rack
from app.db.repositories.warehouse_repository import WarehouseRepository
from app.db.repositories.location_repository import LocationRepository
from app.db.schemas.warehouse import WarehouseCreate, WarehouseUpdate
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, ReferencedEntityError


class WarehouseService(BaseService[Warehouse]):
    def __init__(self, db: Session):
        self.repository: WarehouseRepository = WarehouseRepository(db)
        self.location_repository = LocationRepository(db)
        super().__init__(self.repository, entity_name="Warehouse")

    def create(self, data: WarehouseCreate) -> Warehouse:
        if self.repository.exists_code(data.code):
            raise ConflictError(f"Warehouse code '{data.code}' already exists")
        warehouse = Warehouse(**data.model_dump())
        return self.repository.create(warehouse)

    def update(self, warehouse_id: int, data: WarehouseUpdate) -> Warehouse:
        warehouse = self.get(warehouse_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(warehouse, field, value)
        return self.repository.update(warehouse)

    def delete(self, warehouse_id: int) -> None:
        warehouse = self.get(warehouse_id)
        locations = self.location_repository.find_by_warehouse(warehouse_id)
        if any(loc.inventories for loc in locations):
            raise ReferencedEntityError("Cannot delete warehouse: inventory still exists in it")
        self.repository.delete(warehouse)

    def add_rack(self, warehouse_id: int, code: str, description: str | None = None) -> Rack:
        self.get(warehouse_id)  # ensures warehouse exists
        rack = Rack(warehouse_id=warehouse_id, code=code, description=description)
        self.repository.db.add(rack)
        self.repository.db.commit()
        self.repository.db.refresh(rack)
        return rack

    def remove_rack(self, rack: Rack) -> None:
        self.repository.db.delete(rack)
        self.repository.db.commit()
