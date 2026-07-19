from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.warehouse import Warehouse
from app.db.models.rack import Rack
from app.db.repositories.base_repository import BaseRepository


class WarehouseRepository(BaseRepository[Warehouse]):
    def __init__(self, db: Session):
        super().__init__(Warehouse, db)

    def get_by_code(self, code: str) -> Optional[Warehouse]:
        return self.db.query(Warehouse).filter(Warehouse.code == code).first()

    def get_racks(self, warehouse_id: int) -> List[Rack]:
        return self.db.query(Rack).filter(Rack.warehouse_id == warehouse_id).all()

    def exists_code(self, code: str, exclude_id: Optional[int] = None) -> bool:
        query = self.db.query(Warehouse.id).filter(Warehouse.code == code)
        if exclude_id is not None:
            query = query.filter(Warehouse.id != exclude_id)
        return query.first() is not None
