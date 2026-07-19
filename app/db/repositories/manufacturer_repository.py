from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.manufacturer import Manufacturer
from app.db.repositories.base_repository import BaseRepository


class ManufacturerRepository(BaseRepository[Manufacturer]):
    def __init__(self, db: Session):
        super().__init__(Manufacturer, db)

    def get_by_code(self, code: str) -> Optional[Manufacturer]:
        return self.db.query(Manufacturer).filter(Manufacturer.code == code).first()

    def exists_code(self, code: str, exclude_id: Optional[int] = None) -> bool:
        query = self.db.query(Manufacturer.id).filter(Manufacturer.code == code)
        if exclude_id is not None:
            query = query.filter(Manufacturer.id != exclude_id)
        return query.first() is not None

    def search(self, term: str) -> List[Manufacturer]:
        like = f"%{term}%"
        return (
            self.db.query(Manufacturer)
            .filter(or_(Manufacturer.name.ilike(like), Manufacturer.code.ilike(like)))
            .all()
        )

    def get_active(self) -> List[Manufacturer]:
        return self.db.query(Manufacturer).filter(Manufacturer.is_active.is_(True)).all()

    def activate(self, manufacturer: Manufacturer) -> Manufacturer:
        manufacturer.is_active = True
        return self.update(manufacturer)

    def deactivate(self, manufacturer: Manufacturer) -> Manufacturer:
        manufacturer.is_active = False
        return self.update(manufacturer)
