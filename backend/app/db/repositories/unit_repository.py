from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.unit import Unit
from app.db.repositories.base_repository import BaseRepository


class UnitRepository(BaseRepository[Unit]):
    def __init__(self, db: Session):
        super().__init__(Unit, db)

    def get_by_code(self, code: str) -> Optional[Unit]:
        return self.db.query(Unit).filter(Unit.code == code).first()

    def exists_code(self, code: str, exclude_id: Optional[int] = None) -> bool:
        query = self.db.query(Unit.id).filter(Unit.code == code)
        if exclude_id is not None:
            query = query.filter(Unit.id != exclude_id)
        return query.first() is not None

    def get_active(self) -> List[Unit]:
        return self.db.query(Unit).filter(Unit.is_active.is_(True)).all()

    def activate(self, unit: Unit) -> Unit:
        unit.is_active = True
        return self.update(unit)

    def deactivate(self, unit: Unit) -> Unit:
        unit.is_active = False
        return self.update(unit)
