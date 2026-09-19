from typing import List, Optional

from sqlalchemy.orm import Session

from app.wms.warehouse_structure.models.shelf import Shelf
from app.shared.base_repository import BaseRepository


class ShelfRepository(BaseRepository[Shelf]):
    def __init__(self, db: Session):
        super().__init__(Shelf, db)

    def get_by_rack(self, rack_id: int) -> List[Shelf]:
        return self.db.query(Shelf).filter(Shelf.rack_id == rack_id).all()

    def get_by_code(self, rack_id: int, code: str) -> Optional[Shelf]:
        return self.db.query(Shelf).filter(Shelf.rack_id == rack_id, Shelf.code == code).first()

    def exists_in_rack(self, rack_id: int, code: str, exclude_id: Optional[int] = None) -> bool:
        query = self.db.query(Shelf.id).filter(Shelf.rack_id == rack_id, Shelf.code == code)
        if exclude_id is not None:
            query = query.filter(Shelf.id != exclude_id)
        return query.first() is not None
