from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.db.models.enums import InventoryStatus
from app.db.schemas.inventory import (
    InventoryCreate, InventoryRead, InventoryUpdate,
    InventoryAdjustQuantity, InventoryReserve, InventoryMoveLocation, InventoryChangeStatus,
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _to_read(service: InventoryService, inventory) -> dict:
    """Attaches the computed location_path onto the ORM object before schema validation."""
    data = InventoryRead.model_validate(inventory).model_dump()
    data["location_path"] = service.get_location_display(inventory)
    return data


@router.post("", response_model=InventoryRead, status_code=201)
def create_inventory(payload: InventoryCreate, db: Session = Depends(get_db)):
    service = InventoryService(db)
    inventory = service.create_inventory(payload)
    return _to_read(service, inventory)


@router.get("", response_model=List[InventoryRead])
def list_inventory(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    product_id: int | None = None,
    batch_number: str | None = None,
    status: InventoryStatus | None = None,
    location_id: int | None = None,
    manufacturer_id: int | None = None,
    db: Session = Depends(get_db),
):
    service = InventoryService(db)
    if product_id is not None:
        rows = service.get_by_product(product_id)
    elif batch_number is not None:
        rows = service.get_batch_stock(batch_number)
    elif status is not None:
        rows = service.get_by_status(status)
    elif location_id is not None:
        rows = service.get_by_location(location_id)
    elif manufacturer_id is not None:
        rows = service.get_by_manufacturer(manufacturer_id)
    else:
        rows = service.get_page(skip=skip, limit=limit)
    return [_to_read(service, r) for r in rows]


@router.get("/{inventory_id}", response_model=InventoryRead)
def get_inventory(inventory_id: int, db: Session = Depends(get_db)):
    service = InventoryService(db)
    return _to_read(service, service.get(inventory_id))


@router.put("/{inventory_id}", response_model=InventoryRead)
def update_inventory(inventory_id: int, payload: InventoryUpdate, db: Session = Depends(get_db)):
    service = InventoryService(db)
    return _to_read(service, service.update_inventory(inventory_id, payload))


@router.delete("/{inventory_id}", status_code=204)
def delete_inventory(inventory_id: int, db: Session = Depends(get_db)):
    InventoryService(db).delete_inventory(inventory_id)


@router.post("/{inventory_id}/issue", response_model=InventoryRead)
def issue_stock(inventory_id: int, payload: InventoryAdjustQuantity, db: Session = Depends(get_db)):
    service = InventoryService(db)
    inventory = service.issue_stock(inventory_id, abs(payload.quantity_delta))
    return _to_read(service, inventory)


@router.post("/{inventory_id}/adjust", response_model=InventoryRead)
def adjust_quantity(inventory_id: int, payload: InventoryAdjustQuantity, db: Session = Depends(get_db)):
    service = InventoryService(db)
    inventory = service.adjust_quantity(inventory_id, payload.quantity_delta)
    return _to_read(service, inventory)


@router.post("/{inventory_id}/reserve", response_model=InventoryRead)
def reserve_stock(inventory_id: int, payload: InventoryReserve, db: Session = Depends(get_db)):
    service = InventoryService(db)
    inventory = service.reserve_stock(inventory_id, payload.quantity)
    return _to_read(service, inventory)


@router.post("/{inventory_id}/release", response_model=InventoryRead)
def release_stock(inventory_id: int, payload: InventoryReserve, db: Session = Depends(get_db)):
    service = InventoryService(db)
    inventory = service.release_stock(inventory_id, payload.quantity)
    return _to_read(service, inventory)


@router.post("/{inventory_id}/move", response_model=InventoryRead)
def move_stock(inventory_id: int, payload: InventoryMoveLocation, db: Session = Depends(get_db)):
    service = InventoryService(db)
    inventory = service.move_stock(inventory_id, payload.new_location_id)
    return _to_read(service, inventory)


@router.post("/{inventory_id}/status", response_model=InventoryRead)
def change_status(inventory_id: int, payload: InventoryChangeStatus, db: Session = Depends(get_db)):
    service = InventoryService(db)
    inventory = service.change_status(inventory_id, payload.status)
    return _to_read(service, inventory)


@router.get("/product/{product_id}/available", response_model=float)
def get_available_stock(product_id: int, db: Session = Depends(get_db)):
    return InventoryService(db).get_available_stock(product_id)


@router.get("/product/{product_id}/total", response_model=float)
def get_total_stock(product_id: int, db: Session = Depends(get_db)):
    return InventoryService(db).get_total_stock(product_id)
