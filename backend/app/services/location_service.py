from sqlalchemy.orm import Session

from app.db.models.location import Location
from app.db.models.enums import LocationCategory
from app.db.repositories.location_repository import LocationRepository
from app.db.repositories.warehouse_repository import WarehouseRepository
from app.db.repositories.rack_repository import RackRepository
from app.db.repositories.shelf_repository import ShelfRepository
from app.db.repositories.bin_repository import BinRepository
from app.db.schemas.warehouse import LocationCreate
from app.services.base_service import BaseService
from app.services.exceptions import ValidationError, ConflictError, ReferencedEntityError


class LocationService(BaseService[Location]):
    """
    Builds and validates physical storage locations.

    Hierarchy rules:
      - A rack must belong to the given warehouse.
      - A shelf must belong to the given rack (so a shelf can never be
        specified without its rack - e.g. "WH3-03" is not a valid location).
      - A bin must belong to the given shelf.
      - Oversized items may stop at the rack level (e.g. "WH1-A").
      - SHEET / PIPE / SCRAP categories are dedicated rack-level-only zones
        and are always expressed at the warehouse + rack level, rendered as
        "SHEET-A" / "PIPE-A" / "SCRAP-A" rather than the standard "WH1-A" form.
    """

    # Categories that are always expressed at the warehouse + rack level only
    RACK_LEVEL_CATEGORIES = (LocationCategory.SHEET, LocationCategory.PIPE, LocationCategory.SCRAP)

    def __init__(self, db: Session):
        self.repository: LocationRepository = LocationRepository(db)
        self.warehouse_repository = WarehouseRepository(db)
        self.rack_repository = RackRepository(db)
        self.shelf_repository = ShelfRepository(db)
        self.bin_repository = BinRepository(db)
        super().__init__(self.repository, entity_name="Location")

    def validate_hierarchy(self, data: LocationCreate) -> None:
        warehouse = self.warehouse_repository.get(data.warehouse_id)
        if warehouse is None:
            raise ValidationError(f"Warehouse with id={data.warehouse_id} does not exist")

        if data.shelf_id is not None and data.rack_id is None:
            raise ValidationError("A shelf cannot be specified without its rack")
        if data.bin_id is not None and data.shelf_id is None:
            raise ValidationError("A bin cannot be specified without its shelf")

        rack = None
        if data.rack_id is not None:
            rack = self.rack_repository.get(data.rack_id)
            if rack is None:
                raise ValidationError(f"Rack with id={data.rack_id} does not exist")
            if rack.warehouse_id != data.warehouse_id:
                raise ValidationError("Rack does not belong to the given warehouse")

        shelf = None
        if data.shelf_id is not None:
            shelf = self.shelf_repository.get(data.shelf_id)
            if shelf is None:
                raise ValidationError(f"Shelf with id={data.shelf_id} does not exist")
            if shelf.rack_id != data.rack_id:
                raise ValidationError("Shelf does not belong to the given rack")

        if data.bin_id is not None:
            bin_ = self.bin_repository.get(data.bin_id)
            if bin_ is None:
                raise ValidationError(f"Bin with id={data.bin_id} does not exist")
            if bin_.shelf_id != data.shelf_id:
                raise ValidationError("Bin does not belong to the given shelf")

        if data.category in self.RACK_LEVEL_CATEGORIES and rack is None:
            raise ValidationError(f"{data.category.value} locations require at least a rack")

    def get_location_path(self, data: LocationCreate) -> str:
        """Builds the human-readable composite location string."""
        warehouse = self.warehouse_repository.get(data.warehouse_id)
        rack = self.rack_repository.get(data.rack_id) if data.rack_id else None
        shelf = self.shelf_repository.get(data.shelf_id) if data.shelf_id else None
        bin_ = self.bin_repository.get(data.bin_id) if data.bin_id else None

        if data.category in self.RACK_LEVEL_CATEGORIES:
            return f"{data.category.value}-{rack.code}"

        parts = [warehouse.code]
        if rack:
            parts.append(rack.code)
        if shelf:
            parts.append(shelf.code)
        if bin_:
            parts.append(bin_.code)
        return "-".join(parts)

    def create_location(self, data: LocationCreate) -> Location:
        self.validate_hierarchy(data)
        location_code = self.get_location_path(data)
        if self.repository.exists_location(location_code):
            raise ConflictError(f"Location '{location_code}' already exists")
        location = Location(
            category=data.category,
            location_code=location_code,
            warehouse_id=data.warehouse_id,
            rack_id=data.rack_id,
            shelf_id=data.shelf_id,
            bin_id=data.bin_id,
        )
        return self.repository.create(location)

    def update_location(self, location_id: int, data: LocationCreate) -> Location:
        self.validate_hierarchy(data)
        location = self.get(location_id)
        location_code = self.get_location_path(data)
        if location_code != location.location_code and self.repository.exists_location(location_code):
            raise ConflictError(f"Location '{location_code}' already exists")
        location.category = data.category
        location.location_code = location_code
        location.warehouse_id = data.warehouse_id
        location.rack_id = data.rack_id
        location.shelf_id = data.shelf_id
        location.bin_id = data.bin_id
        return self.repository.update(location)

    def delete_location(self, location_id: int) -> None:
        location = self.get(location_id)
        if location.inventories:
            raise ReferencedEntityError("Cannot delete location: inventory still exists in it")
        self.repository.delete(location)
