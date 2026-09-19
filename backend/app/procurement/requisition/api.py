from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.shared.enums import PRStatus
from app.procurement.requisition.schemas import (
    PurchaseRequisitionCreate,
    PurchaseRequisitionRead,
    PurchaseRequisitionUpdate,
    PurchaseRequisitionItemCreate,
    PurchaseRequisitionApprove,
    PurchaseRequisitionReject,
)
from app.procurement.requisition.service import PurchaseRequisitionService

router = APIRouter(prefix="/purchase-requisitions", tags=["Purchase Requisitions"])


@router.post("", response_model=PurchaseRequisitionRead, status_code=201)
def create_pr(payload: PurchaseRequisitionCreate, db: Session = Depends(get_db)):
    return PurchaseRequisitionService(db).create_pr(payload)


@router.get("", response_model=List[PurchaseRequisitionRead])
def list_prs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[PRStatus] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db),
):
    service = PurchaseRequisitionService(db)
    if status:
        return service.get_by_status(status)
    if department:
        return service.get_by_department(department)
    return service.get_page(skip=skip, limit=limit)


@router.get("/{pr_id}", response_model=PurchaseRequisitionRead)
def get_pr(pr_id: int, db: Session = Depends(get_db)):
    return PurchaseRequisitionService(db).get(pr_id)


@router.put("/{pr_id}", response_model=PurchaseRequisitionRead)
def update_pr(pr_id: int, payload: PurchaseRequisitionUpdate, db: Session = Depends(get_db)):
    return PurchaseRequisitionService(db).update_pr(pr_id, payload)


@router.delete("/{pr_id}", status_code=204)
def delete_pr(pr_id: int, db: Session = Depends(get_db)):
    PurchaseRequisitionService(db).delete_pr(pr_id)


@router.post("/{pr_id}/items", response_model=PurchaseRequisitionRead, status_code=201)
def add_item(pr_id: int, payload: PurchaseRequisitionItemCreate, db: Session = Depends(get_db)):
    return PurchaseRequisitionService(db).add_item(pr_id, payload)


@router.delete("/{pr_id}/items/{item_id}", response_model=PurchaseRequisitionRead)
def remove_item(pr_id: int, item_id: int, db: Session = Depends(get_db)):
    return PurchaseRequisitionService(db).remove_item(pr_id, item_id)


@router.post("/{pr_id}/submit", response_model=PurchaseRequisitionRead)
def submit_pr(pr_id: int, db: Session = Depends(get_db)):
    return PurchaseRequisitionService(db).submit(pr_id)


@router.post("/{pr_id}/approve", response_model=PurchaseRequisitionRead)
def approve_pr(pr_id: int, payload: PurchaseRequisitionApprove, db: Session = Depends(get_db)):
    return PurchaseRequisitionService(db).approve(pr_id, payload.approved_by)


@router.post("/{pr_id}/reject", response_model=PurchaseRequisitionRead)
def reject_pr(pr_id: int, payload: PurchaseRequisitionReject, db: Session = Depends(get_db)):
    return PurchaseRequisitionService(db).reject(pr_id, payload.rejected_by, payload.rejection_reason)
