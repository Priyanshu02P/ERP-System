from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.db.models.enums import LocationCategory
from app.db.schemas.common import ORMBase


# ---------- Warehouse ----------

class WarehouseBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=150)
    address: Optional[str] = Field(None, max_length=255)


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    address: Optional[str] = Field(None, max_length=255)


class WarehouseRead(ORMBase, WarehouseBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------- Rack ----------

class RackBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=10)
    description: Optional[str] = Field(None, max_length=255)
    warehouse_id: int


class RackCreate(RackBase):
    pass


class RackRead(ORMBase, RackBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ---------- Shelf ----------

class ShelfBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=10)
    rack_id: int


class ShelfCreate(ShelfBase):
    pass


class ShelfRead(ORMBase, ShelfBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ---------- Bin ----------

class BinBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=10)
    shelf_id: int


class BinCreate(BinBase):
    pass


class BinRead(ORMBase, BinBase):
    id: int
    created_at: datetime
    updated_at: datetime


# ---------- Location ----------

class LocationCreate(BaseModel):
    """
    Create a location by specifying the hierarchy explicitly.
    Standard locations require warehouse + rack + shelf + bin.
    SHEET/PIPE categories (and oversized items) require only warehouse + rack.
    """

    category: LocationCategory = LocationCategory.STANDARD
    warehouse_id: int
    rack_id: Optional[int] = None
    shelf_id: Optional[int] = None
    bin_id: Optional[int] = None


class LocationRead(ORMBase):
    id: int
    category: LocationCategory
    location_code: str
    warehouse_id: int
    rack_id: Optional[int] = None
    shelf_id: Optional[int] = None
    bin_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
