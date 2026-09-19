from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.quality.inspection.models import QualityInspection
from app.shared.base_repository import BaseRepository


class QualityInspectionRepository(BaseRepository[QualityInspection]):
    def __init__(self, db: Session):
        super().__init__(QualityInspection, db)

    def count_for_year(self, year: int) -> int:
        return (
            self.db.query(func.count(QualityInspection.id))
            .filter(QualityInspection.qc_number.like(f"QC-{year}-%"))
            .scalar()
            or 0
        )

    def get_by_grn(self, grn_id: int) -> Optional[QualityInspection]:
        return self.db.query(QualityInspection).filter(QualityInspection.grn_id == grn_id).first()
