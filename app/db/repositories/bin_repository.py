from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.bin import Bin
from app.db.repositories.base_repository import BaseRepository


class BinRepository(BaseRepository[Bin]):
    def __init__(self, db: Session):
        super().__init__(Bin, db)

    def get_by_shelf(self, shelf_id: int) -> List[Bin]:
        return self.db.query(Bin).filter(Bin.shelf_id == shelf_id).all()

    def get_by_code(self, shelf_id: int, code: str) -> Optional[Bin]:
        return self.db.query(Bin).filter(Bin.shelf_id == shelf_id, Bin.code == code).first()

    def exists_in_shelf(self, shelf_id: int, code: str, exclude_id: Optional[int] = None) -> bool:
        query = self.db.query(Bin.id).filter(Bin.shelf_id == shelf_id, Bin.code == code)
        if exclude_id is not None:
            query = query.filter(Bin.id != exclude_id)
        return query.first() is not None
