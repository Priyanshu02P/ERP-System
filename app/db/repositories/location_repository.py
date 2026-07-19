from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.location import Location
from app.db.repositories.base_repository import BaseRepository


class LocationRepository(BaseRepository[Location]):
    def __init__(self, db: Session):
        super().__init__(Location, db)

    def find(
        self,
        warehouse_id: int,
        rack_id: Optional[int] = None,
        shelf_id: Optional[int] = None,
        bin_id: Optional[int] = None,
    ) -> Optional[Location]:
        return (
            self.db.query(Location)
            .filter(
                Location.warehouse_id == warehouse_id,
                Location.rack_id == rack_id,
                Location.shelf_id == shelf_id,
                Location.bin_id == bin_id,
            )
            .first()
        )

    def get_complete_location(self, location_id: int) -> Optional[Location]:
        return self.db.query(Location).filter(Location.id == location_id).first()

    def exists_location(self, location_code: str) -> bool:
        return self.db.query(Location.id).filter(Location.location_code == location_code).first() is not None

    def find_by_bin(self, bin_id: int) -> List[Location]:
        return self.db.query(Location).filter(Location.bin_id == bin_id).all()

    def find_by_shelf(self, shelf_id: int) -> List[Location]:
        return self.db.query(Location).filter(Location.shelf_id == shelf_id).all()

    def find_by_rack(self, rack_id: int) -> List[Location]:
        return self.db.query(Location).filter(Location.rack_id == rack_id).all()

    def find_by_warehouse(self, warehouse_id: int) -> List[Location]:
        return self.db.query(Location).filter(Location.warehouse_id == warehouse_id).all()
