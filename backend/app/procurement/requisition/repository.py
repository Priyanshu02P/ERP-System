from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.procurement.requisition.models import PurchaseRequisition
from app.shared.enums import PRStatus
from app.shared.base_repository import BaseRepository


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
