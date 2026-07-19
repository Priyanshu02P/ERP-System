from sqlalchemy.orm import Session

from app.db.models.shelf import Shelf
from app.db.models.bin import Bin
from app.db.repositories.shelf_repository import ShelfRepository
from app.db.repositories.rack_repository import RackRepository
from app.db.repositories.location_repository import LocationRepository
from app.db.schemas.warehouse import ShelfCreate
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, ValidationError, ReferencedEntityError


class ShelfService(BaseService[Shelf]):
    def __init__(self, db: Session):
        self.repository: ShelfRepository = ShelfRepository(db)
        self.rack_repository = RackRepository(db)
        self.location_repository = LocationRepository(db)
        super().__init__(self.repository, entity_name="Shelf")

    def create(self, data: ShelfCreate) -> Shelf:
        if not self.rack_repository.exists(data.rack_id):
            raise ValidationError(f"Rack with id={data.rack_id} does not exist")
        if self.repository.exists_in_rack(data.rack_id, data.code):
            raise ConflictError(f"Shelf code '{data.code}' already exists in this rack")
        shelf = Shelf(**data.model_dump())
        return self.repository.create(shelf)

    def delete(self, shelf_id: int) -> None:
        shelf = self.get(shelf_id)
        locations = self.location_repository.find_by_shelf(shelf_id)
        if any(loc.inventories for loc in locations):
            raise ReferencedEntityError("Cannot delete shelf: inventory still exists in it")
        self.repository.delete(shelf)

    def add_bin(self, shelf_id: int, code: str) -> Bin:
        self.get(shelf_id)  # ensures shelf exists
        bin_ = Bin(shelf_id=shelf_id, code=code)
        self.repository.db.add(bin_)
        self.repository.db.commit()
        self.repository.db.refresh(bin_)
        return bin_

    def remove_bin(self, bin_: Bin) -> None:
        self.repository.db.delete(bin_)
        self.repository.db.commit()
