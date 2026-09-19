from typing import List

from sqlalchemy.orm import Session

from app.procurement.vendor_quotation.models import VendorQuotation
from app.shared.enums import QuotationStatus
from app.shared.base_repository import BaseRepository


class VendorQuotationRepository(BaseRepository[VendorQuotation]):
    def __init__(self, db: Session):
        super().__init__(VendorQuotation, db)

    def get_by_status(self, status: QuotationStatus) -> List[VendorQuotation]:
        return self.db.query(VendorQuotation).filter(VendorQuotation.status == status).all()

    def get_by_rfq(self, rfq_id: int) -> List[VendorQuotation]:
        return self.db.query(VendorQuotation).filter(VendorQuotation.rfq_id == rfq_id).all()

    def get_by_supplier(self, supplier_id: int) -> List[VendorQuotation]:
        return self.db.query(VendorQuotation).filter(VendorQuotation.supplier_id == supplier_id).all()

    def get_selectable_siblings(self, rfq_id: int, exclude_id: int) -> List[VendorQuotation]:
        """Other still-open quotations on the same RFQ, used to auto-reject
        the rest once one is selected."""
        return (
            self.db.query(VendorQuotation)
            .filter(
                VendorQuotation.rfq_id == rfq_id,
                VendorQuotation.id != exclude_id,
                VendorQuotation.status.in_([QuotationStatus.PENDING_REVIEW, QuotationStatus.REVIEWED]),
            )
            .all()
        )
