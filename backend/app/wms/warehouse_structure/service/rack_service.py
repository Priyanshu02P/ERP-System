from sqlalchemy.orm import Session

from app.wms.warehouse_structure.models.rack import Rack
from app.wms.warehouse_structure.models.shelf import Shelf
from app.wms.warehouse_structure.repository.rack_repository import RackRepository
from app.wms.warehouse_structure.repository.warehouse_repository import WarehouseRepository
from app.wms.warehouse_structure.repository.location_repository import LocationRepository
from app.wms.warehouse_structure.schemas import RackCreate
from app.shared.base_service import BaseService
from app.shared.exceptions import ConflictError, ValidationError, ReferencedEntityError


class RackService(BaseService[Rack]):
    """A rack belongs to exactly one Warehouse. add_shelf()/remove_shelf()
    mirror WarehouseService's add_rack()/remove_rack() one level down the
    hierarchy."""

    def __init__(self, db: Session):
        self.repository: RackRepository = RackRepository(db)
        self.warehouse_repository = WarehouseRepository(db)
        self.location_repository = LocationRepository(db)
        super().__init__(self.repository, entity_name="Rack")

    def create(self, data: RackCreate) -> Rack:
        if not self.warehouse_repository.exists(data.warehouse_id):
            raise ValidationError(f"Warehouse with id={data.warehouse_id} does not exist")
        if self.repository.exists_in_warehouse(data.warehouse_id, data.code):
            raise ConflictError(f"Rack code '{data.code}' already exists in this warehouse")
        rack = Rack(**data.model_dump())
        return self.repository.create(rack)

    def delete(self, rack_id: int) -> None:
        rack = self.get(rack_id)
        locations = self.location_repository.find_by_rack(rack_id)
        if any(loc.inventories for loc in locations):
            raise ReferencedEntityError("Cannot delete rack: inventory still exists in it")
        self.repository.delete(rack)

    def add_shelf(self, rack_id: int, code: str) -> Shelf:
        self.get(rack_id)  # ensures rack exists
        shelf = Shelf(rack_id=rack_id, code=code)
        self.repository.db.add(shelf)
        self.repository.db.commit()
        self.repository.db.refresh(shelf)
        return shelf

    def remove_shelf(self, shelf: Shelf) -> None:
        self.repository.db.delete(shelf)
        self.repository.db.commit()
