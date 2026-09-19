from sqlalchemy.orm import Session

from app.wms.warehouse_structure.models.bin import Bin
from app.wms.warehouse_structure.repository.bin_repository import BinRepository
from app.wms.warehouse_structure.repository.shelf_repository import ShelfRepository
from app.wms.warehouse_structure.repository.location_repository import LocationRepository
from app.wms.warehouse_structure.schemas import BinCreate
from app.shared.base_service import BaseService
from app.shared.exceptions import ConflictError, ValidationError, ReferencedEntityError


class BinService(BaseService[Bin]):
    """A bin belongs to exactly one Shelf and is the lowest level of the
    STANDARD storage hierarchy - a Location is a specific bin (or, for
    oversized SHEET/PIPE/SCRAP categories, a rack). See LocationService for
    how the hierarchy is validated and assembled into a Location."""

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
