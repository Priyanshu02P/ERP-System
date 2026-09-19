from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.quality.inspection.schemas import (
    QualityInspectionCreate,
    QualityInspectionRead,
    QualityInspectionApproveDeviation,
)
from app.quality.inspection.service import QualityInspectionService

router = APIRouter(prefix="/quality-inspections", tags=["Quality Inspections"])


@router.post("", response_model=QualityInspectionRead, status_code=201)
def create_qc(payload: QualityInspectionCreate, db: Session = Depends(get_db)):
    return QualityInspectionService(db).create_qc(payload)


@router.get("", response_model=List[QualityInspectionRead])
def list_qcs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    grn_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    service = QualityInspectionService(db)
    if grn_id:
        result = service.get_by_grn(grn_id)
        return [result] if result else []
    return service.get_page(skip=skip, limit=limit)


@router.get("/{qc_id}", response_model=QualityInspectionRead)
def get_qc(qc_id: int, db: Session = Depends(get_db)):
    return QualityInspectionService(db).get(qc_id)


@router.post("/{qc_id}/approve-deviation", response_model=QualityInspectionRead)
def approve_deviation(qc_id: int, payload: QualityInspectionApproveDeviation, db: Session = Depends(get_db)):
    return QualityInspectionService(db).approve_deviation(qc_id, payload.approved_by)
