from sqlalchemy.orm import Session

from app.db.models.bin import Bin
from app.db.repositories.bin_repository import BinRepository
from app.db.repositories.shelf_repository import ShelfRepository
from app.db.repositories.location_repository import LocationRepository
from app.db.schemas.warehouse import BinCreate
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, ValidationError, ReferencedEntityError


class BinService(BaseService[Bin]):
    def __init__(self, db: Session):
        self.repository: BinRepository = BinRepository(db)
        self.shelf_repository = ShelfRepository(db)
        self.location_repository = LocationRepository(db)
        super().__init__(self.repository, entity_name="Bin")

    def create(self, data: BinCreate) -> Bin:
        if not self.shelf_repository.exists(data.shelf_id):
            raise ValidationError(f"Shelf with id={data.shelf_id} does not exist")
        if self.repository.exists_in_shelf(data.shelf_id, data.code):
            raise ConflictError(f"Bin code '{data.code}' already exists in this shelf")
        bin_ = Bin(**data.model_dump())
        return self.repository.create(bin_)

    def delete(self, bin_id: int) -> None:
        bin_ = self.get(bin_id)
        locations = self.location_repository.find_by_bin(bin_id)
        if any(loc.inventories for loc in locations):
            raise ReferencedEntityError("Cannot delete bin: inventory still exists in it")
        self.repository.delete(bin_)
