from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.purchase_requisition import PurchaseRequisition
from app.db.models.enums import PRStatus
from app.db.repositories.base_repository import BaseRepository


class PurchaseRequisitionRepository(BaseRepository[PurchaseRequisition]):
    def __init__(self, db: Session):
        super().__init__(PurchaseRequisition, db)

    def count_for_year(self, year: int) -> int:
        return (
            self.db.query(func.count(PurchaseRequisition.id))
            .filter(PurchaseRequisition.pr_number.like(f"PR-{year}-%"))
            .scalar()
            or 0
        )

    def get_by_status(self, status: PRStatus) -> List[PurchaseRequisition]:
        return self.db.query(PurchaseRequisition).filter(PurchaseRequisition.status == status).all()

    def get_by_department(self, department: str) -> List[PurchaseRequisition]:
        return self.db.query(PurchaseRequisition).filter(PurchaseRequisition.department == department).all()
