from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.rack import Rack
from app.db.repositories.base_repository import BaseRepository


class RackRepository(BaseRepository[Rack]):
    def __init__(self, db: Session):
        super().__init__(Rack, db)

    def get_by_warehouse(self, warehouse_id: int) -> List[Rack]:
        return self.db.query(Rack).filter(Rack.warehouse_id == warehouse_id).all()

    def get_by_code(self, warehouse_id: int, code: str) -> Optional[Rack]:
        return self.db.query(Rack).filter(Rack.warehouse_id == warehouse_id, Rack.code == code).first()

    def exists_in_warehouse(self, warehouse_id: int, code: str, exclude_id: Optional[int] = None) -> bool:
        query = self.db.query(Rack.id).filter(Rack.warehouse_id == warehouse_id, Rack.code == code)
        if exclude_id is not None:
            query = query.filter(Rack.id != exclude_id)
        return query.first() is not None
