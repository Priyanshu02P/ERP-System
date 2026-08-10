from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.goods_receipt import GoodsReceipt
from app.db.models.enums import GRNStatus
from app.db.repositories.base_repository import BaseRepository


class GoodsReceiptRepository(BaseRepository[GoodsReceipt]):
    def __init__(self, db: Session):
        super().__init__(GoodsReceipt, db)

    def count_for_year(self, year: int) -> int:
        return (
            self.db.query(func.count(GoodsReceipt.id))
            .filter(GoodsReceipt.grn_number.like(f"GRN-{year}-%"))
            .scalar()
            or 0
        )

    def get_by_status(self, status: GRNStatus) -> List[GoodsReceipt]:
        return self.db.query(GoodsReceipt).filter(GoodsReceipt.status == status).all()

    def get_by_po(self, po_id: int) -> List[GoodsReceipt]:
        return self.db.query(GoodsReceipt).filter(GoodsReceipt.po_id == po_id).all()
