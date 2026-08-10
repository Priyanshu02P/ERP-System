from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.db.models.enums import InvoiceStatus
from app.db.schemas.vendor_invoice import (
    VendorInvoiceCreate,
    VendorInvoiceIngest,
    VendorInvoiceRead,
    VendorInvoiceUpdate,
    VendorInvoiceItemUpdate,
    VendorInvoiceMatch,
    VendorInvoiceApprovePayment,
    VendorInvoiceMarkPaid,
)
from app.services.vendor_invoice_service import VendorInvoiceService

router = APIRouter(prefix="/vendor-invoices", tags=["Vendor Invoices"])


@router.post("", response_model=VendorInvoiceRead, status_code=201)
def create_invoice(payload: VendorInvoiceCreate, db: Session = Depends(get_db)):
    return VendorInvoiceService(db).create_manual(payload)


@router.post("/ingest", response_model=VendorInvoiceRead, status_code=201)
def ingest_invoice(payload: VendorInvoiceIngest, db: Session = Depends(get_db)):
    return VendorInvoiceService(db).ingest(payload)


@router.get("", response_model=List[VendorInvoiceRead])
def list_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[InvoiceStatus] = None,
    po_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    service = VendorInvoiceService(db)
    if status:
        return service.get_by_status(status)
    if po_id:
        return service.get_by_po(po_id)
    return service.get_page(skip=skip, limit=limit)


@router.get("/{invoice_id}", response_model=VendorInvoiceRead)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    return VendorInvoiceService(db).get(invoice_id)


@router.put("/{invoice_id}", response_model=VendorInvoiceRead)
def update_invoice(invoice_id: int, payload: VendorInvoiceUpdate, db: Session = Depends(get_db)):
    return VendorInvoiceService(db).update_header(invoice_id, payload)


@router.put("/{invoice_id}/items/{item_id}", response_model=VendorInvoiceRead)
def update_invoice_item(invoice_id: int, item_id: int, payload: VendorInvoiceItemUpdate, db: Session = Depends(get_db)):
    return VendorInvoiceService(db).update_item(invoice_id, item_id, payload)


@router.post("/{invoice_id}/match", response_model=VendorInvoiceRead)
def match_invoice(invoice_id: int, payload: VendorInvoiceMatch, db: Session = Depends(get_db)):
    return VendorInvoiceService(db).match(invoice_id, payload.matched_by)


@router.post("/{invoice_id}/approve-payment", response_model=VendorInvoiceRead)
def approve_invoice_payment(invoice_id: int, payload: VendorInvoiceApprovePayment, db: Session = Depends(get_db)):
    return VendorInvoiceService(db).approve_payment(invoice_id, payload.approved_by)


@router.post("/{invoice_id}/mark-paid", response_model=VendorInvoiceRead)
def mark_invoice_paid(invoice_id: int, payload: VendorInvoiceMarkPaid, db: Session = Depends(get_db)):
    return VendorInvoiceService(db).mark_paid(invoice_id, payload.paid_by)
