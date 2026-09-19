from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.shared.enums import SupplierCategory
from app.procurement.supplier.schemas import SupplierCreate, SupplierRead, SupplierUpdate
from app.procurement.supplier.service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.post("", response_model=SupplierRead, status_code=201)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)):
    return SupplierService(db).create_supplier(payload)


@router.get("", response_model=List[SupplierRead])
def list_suppliers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = None,
    category: SupplierCategory | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    service = SupplierService(db)
    if search:
        return service.search(search)
    if category:
        return service.get_by_category(category)
    if active_only:
        return service.repository.get_active()
    return service.get_page(skip=skip, limit=limit)


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: int, db: Session = Depends(get_db)):
    return SupplierService(db).get(supplier_id)


@router.put("/{supplier_id}", response_model=SupplierRead)
def update_supplier(supplier_id: int, payload: SupplierUpdate, db: Session = Depends(get_db)):
    return SupplierService(db).update_supplier(supplier_id, payload)


@router.delete("/{supplier_id}", status_code=204)
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    SupplierService(db).delete_supplier(supplier_id)


@router.post("/{supplier_id}/activate", response_model=SupplierRead)
def activate_supplier(supplier_id: int, db: Session = Depends(get_db)):
    return SupplierService(db).activate_supplier(supplier_id)


@router.post("/{supplier_id}/deactivate", response_model=SupplierRead)
def deactivate_supplier(supplier_id: int, db: Session = Depends(get_db)):
    return SupplierService(db).deactivate_supplier(supplier_id)
