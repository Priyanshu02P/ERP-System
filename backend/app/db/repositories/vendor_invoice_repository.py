from typing import List

from sqlalchemy.orm import Session

from app.db.models.vendor_invoice import VendorInvoice
from app.db.models.enums import InvoiceStatus
from app.db.repositories.base_repository import BaseRepository


class VendorInvoiceRepository(BaseRepository[VendorInvoice]):
    def __init__(self, db: Session):
        super().__init__(VendorInvoice, db)

    def get_by_status(self, status: InvoiceStatus) -> List[VendorInvoice]:
        return self.db.query(VendorInvoice).filter(VendorInvoice.status == status).all()

    def get_by_po(self, po_id: int) -> List[VendorInvoice]:
        return self.db.query(VendorInvoice).filter(VendorInvoice.po_id == po_id).all()

    def get_by_supplier(self, supplier_id: int) -> List[VendorInvoice]:
        return self.db.query(VendorInvoice).filter(VendorInvoice.supplier_id == supplier_id).all()
