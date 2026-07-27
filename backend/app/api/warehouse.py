from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.db.schemas.warehouse import (
    WarehouseCreate, WarehouseRead, WarehouseUpdate,
    RackCreate, RackRead,
    ShelfCreate, ShelfRead,
    BinCreate, BinRead,
    LocationCreate, LocationRead,
)
from app.services.warehouse_service import WarehouseService
from app.services.rack_service import RackService
from app.services.shelf_service import ShelfService
from app.services.bin_service import BinService
from app.services.location_service import LocationService

router = APIRouter(tags=["Warehouse Hierarchy"])


# ---------- Warehouse ----------

@router.post("/warehouses", response_model=WarehouseRead, status_code=201)
def create_warehouse(payload: WarehouseCreate, db: Session = Depends(get_db)):
    return WarehouseService(db).create(payload)


@router.get("/warehouses", response_model=List[WarehouseRead])
def list_warehouses(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return WarehouseService(db).get_page(skip=skip, limit=limit)


@router.get("/warehouses/{warehouse_id}", response_model=WarehouseRead)
def get_warehouse(warehouse_id: int, db: Session = Depends(get_db)):
    return WarehouseService(db).get(warehouse_id)


@router.put("/warehouses/{warehouse_id}", response_model=WarehouseRead)
def update_warehouse(warehouse_id: int, payload: WarehouseUpdate, db: Session = Depends(get_db)):
    return WarehouseService(db).update(warehouse_id, payload)


@router.delete("/warehouses/{warehouse_id}", status_code=204)
def delete_warehouse(warehouse_id: int, db: Session = Depends(get_db)):
    WarehouseService(db).delete(warehouse_id)


@router.get("/warehouses/{warehouse_id}/racks", response_model=List[RackRead])
def list_warehouse_racks(warehouse_id: int, db: Session = Depends(get_db)):
    return WarehouseService(db).repository.get_racks(warehouse_id)


# ---------- Rack ----------

@router.post("/racks", response_model=RackRead, status_code=201)
def create_rack(payload: RackCreate, db: Session = Depends(get_db)):
    return RackService(db).create(payload)


@router.get("/racks/{rack_id}", response_model=RackRead)
def get_rack(rack_id: int, db: Session = Depends(get_db)):
    return RackService(db).get(rack_id)


@router.delete("/racks/{rack_id}", status_code=204)
def delete_rack(rack_id: int, db: Session = Depends(get_db)):
    RackService(db).delete(rack_id)


# ---------- Shelf ----------

@router.post("/shelves", response_model=ShelfRead, status_code=201)
def create_shelf(payload: ShelfCreate, db: Session = Depends(get_db)):
    return ShelfService(db).create(payload)


@router.get("/shelves/{shelf_id}", response_model=ShelfRead)
def get_shelf(shelf_id: int, db: Session = Depends(get_db)):
    return ShelfService(db).get(shelf_id)


@router.delete("/shelves/{shelf_id}", status_code=204)
def delete_shelf(shelf_id: int, db: Session = Depends(get_db)):
    ShelfService(db).delete(shelf_id)


# ---------- Bin ----------

@router.post("/bins", response_model=BinRead, status_code=201)
def create_bin(payload: BinCreate, db: Session = Depends(get_db)):
    return BinService(db).create(payload)


@router.get("/bins/{bin_id}", response_model=BinRead)
def get_bin(bin_id: int, db: Session = Depends(get_db)):
    return BinService(db).get(bin_id)


@router.delete("/bins/{bin_id}", status_code=204)
def delete_bin(bin_id: int, db: Session = Depends(get_db)):
    BinService(db).delete(bin_id)


# ---------- Location ----------

@router.post("/locations", response_model=LocationRead, status_code=201)
def create_location(payload: LocationCreate, db: Session = Depends(get_db)):
    return LocationService(db).create_location(payload)


@router.get("/locations", response_model=List[LocationRead])
def list_locations(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return LocationService(db).get_page(skip=skip, limit=limit)


@router.get("/locations/{location_id}", response_model=LocationRead)
def get_location(location_id: int, db: Session = Depends(get_db)):
    return LocationService(db).get(location_id)


@router.put("/locations/{location_id}", response_model=LocationRead)
def update_location(location_id: int, payload: LocationCreate, db: Session = Depends(get_db)):
    return LocationService(db).update_location(location_id, payload)


@router.delete("/locations/{location_id}", status_code=204)
def delete_location(location_id: int, db: Session = Depends(get_db)):
    LocationService(db).delete_location(location_id)
