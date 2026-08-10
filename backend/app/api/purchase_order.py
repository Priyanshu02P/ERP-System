from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.db.models.enums import POStatus
from app.db.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
    PurchaseOrderSend,
    PurchaseOrderCancel,
)
from app.services.purchase_order_service import PurchaseOrderService

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@router.post("", response_model=PurchaseOrderRead, status_code=201)
def create_po(payload: PurchaseOrderCreate, db: Session = Depends(get_db)):
    return PurchaseOrderService(db).create_po(payload)


@router.get("", response_model=List[PurchaseOrderRead])
def list_pos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[POStatus] = None,
    supplier_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    service = PurchaseOrderService(db)
    if status:
        return service.get_by_status(status)
    if supplier_id:
        return service.get_by_supplier(supplier_id)
    return service.get_page(skip=skip, limit=limit)


@router.get("/{po_id}", response_model=PurchaseOrderRead)
def get_po(po_id: int, db: Session = Depends(get_db)):
    return PurchaseOrderService(db).get(po_id)


@router.put("/{po_id}", response_model=PurchaseOrderRead)
def update_po(po_id: int, payload: PurchaseOrderUpdate, db: Session = Depends(get_db)):
    return PurchaseOrderService(db).update_po(po_id, payload)


@router.post("/{po_id}/send", response_model=PurchaseOrderRead)
def send_po(po_id: int, payload: PurchaseOrderSend, db: Session = Depends(get_db)):
    return PurchaseOrderService(db).send(po_id, payload.approved_by)


@router.post("/{po_id}/confirm", response_model=PurchaseOrderRead)
def confirm_po(po_id: int, db: Session = Depends(get_db)):
    return PurchaseOrderService(db).confirm(po_id)


@router.post("/{po_id}/cancel", response_model=PurchaseOrderRead)
def cancel_po(po_id: int, payload: PurchaseOrderCancel, db: Session = Depends(get_db)):
    return PurchaseOrderService(db).cancel(po_id, payload.cancelled_by, payload.cancellation_reason)
