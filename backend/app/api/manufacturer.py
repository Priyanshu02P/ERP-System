from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.db.schemas.manufacturer import ManufacturerCreate, ManufacturerRead, ManufacturerUpdate
from app.services.manufacturer_service import ManufacturerService

router = APIRouter(prefix="/manufacturers", tags=["Manufacturers"])


@router.post("", response_model=ManufacturerRead, status_code=201)
def create_manufacturer(payload: ManufacturerCreate, db: Session = Depends(get_db)):
    return ManufacturerService(db).create(payload)


@router.get("", response_model=List[ManufacturerRead])
def list_manufacturers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = None,
    db: Session = Depends(get_db),
):
    service = ManufacturerService(db)
    if search:
        return service.search(search)
    return service.get_page(skip=skip, limit=limit)


@router.get("/{manufacturer_id}", response_model=ManufacturerRead)
def get_manufacturer(manufacturer_id: int, db: Session = Depends(get_db)):
    return ManufacturerService(db).get(manufacturer_id)


@router.put("/{manufacturer_id}", response_model=ManufacturerRead)
def update_manufacturer(manufacturer_id: int, payload: ManufacturerUpdate, db: Session = Depends(get_db)):
    return ManufacturerService(db).update(manufacturer_id, payload)


@router.delete("/{manufacturer_id}", status_code=204)
def delete_manufacturer(manufacturer_id: int, db: Session = Depends(get_db)):
    ManufacturerService(db).delete(manufacturer_id)


@router.post("/{manufacturer_id}/activate", response_model=ManufacturerRead)
def activate_manufacturer(manufacturer_id: int, db: Session = Depends(get_db)):
    return ManufacturerService(db).activate(manufacturer_id)


@router.post("/{manufacturer_id}/deactivate", response_model=ManufacturerRead)
def deactivate_manufacturer(manufacturer_id: int, db: Session = Depends(get_db)):
    return ManufacturerService(db).deactivate(manufacturer_id)
