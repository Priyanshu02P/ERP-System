from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.db.schemas.procurement_dashboard import ProcurementKPIs, ReorderSuggestion
from app.services.procurement_dashboard_service import ProcurementDashboardService

router = APIRouter(prefix="/procurement", tags=["Procurement Dashboard"])


@router.get("/kpis", response_model=ProcurementKPIs)
def get_procurement_kpis(db: Session = Depends(get_db)):
    return ProcurementDashboardService(db).get_kpis()


@router.get("/reorder-suggestions", response_model=List[ReorderSuggestion])
def get_reorder_suggestions(db: Session = Depends(get_db)):
    return ProcurementDashboardService(db).get_reorder_suggestions()
