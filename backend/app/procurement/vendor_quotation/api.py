from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.shared.enums import QuotationStatus
from app.procurement.vendor_quotation.schemas import (
    VendorQuotationCreate,
    VendorQuotationIngest,
    VendorQuotationRead,
    VendorQuotationReview,
    VendorQuotationReject,
    QuotationItemUpdate,
)
from app.procurement.vendor_quotation.service import VendorQuotationService

router = APIRouter(tags=["Vendor Quotations"])


# ---------------------------------------------------------------------- #
# Nested under an RFQ - human entry + comparison view
# ---------------------------------------------------------------------- #

@router.post("/rfqs/{rfq_id}/quotations", response_model=VendorQuotationRead, status_code=201)
def create_quotation_for_rfq(rfq_id: int, payload: VendorQuotationCreate, db: Session = Depends(get_db)):
    return VendorQuotationService(db).create_manual(rfq_id, payload)


@router.get("/rfqs/{rfq_id}/quotations", response_model=List[VendorQuotationRead])
def list_quotations_for_rfq(rfq_id: int, db: Session = Depends(get_db)):
    return VendorQuotationService(db).get_by_rfq(rfq_id)


# ---------------------------------------------------------------------- #
# Top-level - manual quotations without an RFQ, automation ingest, review
# ---------------------------------------------------------------------- #

@router.post("/quotations", response_model=VendorQuotationRead, status_code=201)
def create_quotation(payload: VendorQuotationCreate, db: Session = Depends(get_db)):
    return VendorQuotationService(db).create_manual(None, payload)


@router.post("/quotations/ingest", response_model=VendorQuotationRead, status_code=201)
def ingest_quotation(payload: VendorQuotationIngest, db: Session = Depends(get_db)):
    return VendorQuotationService(db).ingest(payload)


@router.get("/quotations", response_model=List[VendorQuotationRead])
def list_quotations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[QuotationStatus] = None,
    db: Session = Depends(get_db),
):
    service = VendorQuotationService(db)
    if status:
        return service.get_by_status(status)
    return service.get_page(skip=skip, limit=limit)


@router.get("/quotations/{quotation_id}", response_model=VendorQuotationRead)
def get_quotation(quotation_id: int, db: Session = Depends(get_db)):
    return VendorQuotationService(db).get(quotation_id)


@router.put("/quotations/{quotation_id}/items/{item_id}", response_model=VendorQuotationRead)
def update_quotation_item(quotation_id: int, item_id: int, payload: QuotationItemUpdate, db: Session = Depends(get_db)):
    return VendorQuotationService(db).update_item(quotation_id, item_id, payload)


@router.post("/quotations/{quotation_id}/review", response_model=VendorQuotationRead)
def review_quotation(quotation_id: int, payload: VendorQuotationReview, db: Session = Depends(get_db)):
    return VendorQuotationService(db).review(quotation_id, payload.reviewed_by)


@router.post("/quotations/{quotation_id}/select", response_model=VendorQuotationRead)
def select_quotation(quotation_id: int, db: Session = Depends(get_db)):
    return VendorQuotationService(db).select(quotation_id)


@router.post("/quotations/{quotation_id}/reject", response_model=VendorQuotationRead)
def reject_quotation(quotation_id: int, payload: VendorQuotationReject, db: Session = Depends(get_db)):
    return VendorQuotationService(db).reject(quotation_id, payload.rejected_by, payload.rejection_reason)
