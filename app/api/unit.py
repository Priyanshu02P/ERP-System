from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.db.schemas.unit import UnitCreate, UnitRead, UnitUpdate
from app.services.unit_service import UnitService

router = APIRouter(prefix="/units", tags=["Units"])


@router.post("", response_model=UnitRead, status_code=201)
def create_unit(payload: UnitCreate, db: Session = Depends(get_db)):
    return UnitService(db).create_unit(payload)


@router.get("", response_model=List[UnitRead])
def list_units(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    service = UnitService(db)
    if active_only:
        return service.repository.get_active()
    return service.get_page(skip=skip, limit=limit)


@router.get("/{unit_id}", response_model=UnitRead)
def get_unit(unit_id: int, db: Session = Depends(get_db)):
    return UnitService(db).get(unit_id)


@router.put("/{unit_id}", response_model=UnitRead)
def update_unit(unit_id: int, payload: UnitUpdate, db: Session = Depends(get_db)):
    return UnitService(db).update_unit(unit_id, payload)


@router.delete("/{unit_id}", status_code=204)
def delete_unit(unit_id: int, db: Session = Depends(get_db)):
    UnitService(db).delete_unit(unit_id)


@router.post("/{unit_id}/activate", response_model=UnitRead)
def activate_unit(unit_id: int, db: Session = Depends(get_db)):
    return UnitService(db).activate(unit_id)


@router.post("/{unit_id}/deactivate", response_model=UnitRead)
def deactivate_unit(unit_id: int, db: Session = Depends(get_db)):
    return UnitService(db).deactivate(unit_id)
