from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.procurement.purchase_order.models import PurchaseOrder
from app.shared.enums import POStatus
from app.shared.base_repository import BaseRepository


class PurchaseOrderRepository(BaseRepository[PurchaseOrder]):
    def __init__(self, db: Session):
        super().__init__(PurchaseOrder, db)

    def count_for_year(self, year: int) -> int:
        return (
            self.db.query(func.count(PurchaseOrder.id))
            .filter(PurchaseOrder.po_number.like(f"PO-{year}-%"))
            .scalar()
            or 0
        )

    def get_by_status(self, status: POStatus) -> List[PurchaseOrder]:
        return self.db.query(PurchaseOrder).filter(PurchaseOrder.status == status).all()

    def get_by_supplier(self, supplier_id: int) -> List[PurchaseOrder]:
        return self.db.query(PurchaseOrder).filter(PurchaseOrder.supplier_id == supplier_id).all()

    def get_by_quotation(self, quotation_id: int) -> Optional[PurchaseOrder]:
        return (
            self.db.query(PurchaseOrder)
            .filter(PurchaseOrder.quotation_id == quotation_id)
            .first()
        )
