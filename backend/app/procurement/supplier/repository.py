from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.procurement.supplier.models import Supplier
from app.shared.enums import SupplierCategory
from app.shared.base_repository import BaseRepository


class SupplierRepository(BaseRepository[Supplier]):
    def __init__(self, db: Session):
        super().__init__(Supplier, db)

    def get_by_code(self, code: str) -> Optional[Supplier]:
        return self.db.query(Supplier).filter(Supplier.code == code).first()

    def exists_code(self, code: str, exclude_id: Optional[int] = None) -> bool:
        query = self.db.query(Supplier.id).filter(Supplier.code == code)
        if exclude_id is not None:
            query = query.filter(Supplier.id != exclude_id)
        return query.first() is not None

    def search(self, term: str) -> List[Supplier]:
        like = f"%{term}%"
        return (
            self.db.query(Supplier)
            .filter(or_(Supplier.name.ilike(like), Supplier.code.ilike(like), Supplier.gstin.ilike(like)))
            .all()
        )

    def get_by_category(self, category: SupplierCategory) -> List[Supplier]:
        return self.db.query(Supplier).filter(Supplier.category == category).all()

    def get_active(self) -> List[Supplier]:
        return self.db.query(Supplier).filter(Supplier.is_active.is_(True)).all()

    def activate(self, supplier: Supplier) -> Supplier:
        supplier.is_active = True
        return self.update(supplier)

    def deactivate(self, supplier: Supplier) -> Supplier:
        supplier.is_active = False
        return self.update(supplier)
