from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.shared.enums import RFQStatus
from app.procurement.rfq.schemas import RFQCreate, RFQRead, RFQSend
from app.procurement.rfq.service import RFQService

router = APIRouter(prefix="/rfqs", tags=["RFQs"])


@router.post("", response_model=RFQRead, status_code=201)
def create_rfq(payload: RFQCreate, db: Session = Depends(get_db)):
    return RFQService(db).create_rfq(payload)


@router.get("", response_model=List[RFQRead])
def list_rfqs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[RFQStatus] = None,
    db: Session = Depends(get_db),
):
    service = RFQService(db)
    if status:
        return service.get_by_status(status)
    return service.get_page(skip=skip, limit=limit)


@router.get("/{rfq_id}", response_model=RFQRead)
def get_rfq(rfq_id: int, db: Session = Depends(get_db)):
    return RFQService(db).get(rfq_id)


@router.post("/{rfq_id}/send", response_model=RFQRead)
def send_rfq(rfq_id: int, payload: RFQSend, db: Session = Depends(get_db)):
    return RFQService(db).send(rfq_id, payload)


@router.post("/{rfq_id}/close", response_model=RFQRead)
def close_rfq(rfq_id: int, db: Session = Depends(get_db)):
    return RFQService(db).close(rfq_id)
