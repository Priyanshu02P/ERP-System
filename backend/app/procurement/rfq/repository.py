from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.procurement.rfq.models import RFQ
from app.shared.enums import RFQStatus
from app.shared.base_repository import BaseRepository


class RFQRepository(BaseRepository[RFQ]):
    def __init__(self, db: Session):
        super().__init__(RFQ, db)

    def count_for_year(self, year: int) -> int:
        return (
            self.db.query(func.count(RFQ.id))
            .filter(RFQ.rfq_number.like(f"RFQ-{year}-%"))
            .scalar()
            or 0
        )

    def get_by_status(self, status: RFQStatus) -> List[RFQ]:
        return self.db.query(RFQ).filter(RFQ.status == status).all()
