from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.db.models.enums import InventoryStatus
from app.db.schemas.common import ORMBase


class InventoryBase(BaseModel):
    product_id: int
    manufacturer_id: int
    location_id: int
    batch_number: str = Field(..., min_length=1, max_length=50)
    manufacturing_date: date
    quantity: float = Field(..., gt=0)
    status: InventoryStatus = InventoryStatus.OK

    @field_validator("manufacturing_date")
    @classmethod
    def manufacturing_date_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("manufacturing_date cannot be in the future")
        return v


class InventoryCreate(InventoryBase):
    pass


class InventoryUpdate(BaseModel):
    manufacturer_id: Optional[int] = None
    location_id: Optional[int] = None
    batch_number: Optional[str] = Field(None, min_length=1, max_length=50)
    manufacturing_date: Optional[date] = None
    quantity: Optional[float] = Field(None, gt=0)
    status: Optional[InventoryStatus] = None


class InventoryAdjustQuantity(BaseModel):
    quantity_delta: float = Field(..., description="Positive to add stock, negative to deduct stock")


class InventoryReserve(BaseModel):
    quantity: float = Field(..., gt=0)


class InventoryMoveLocation(BaseModel):
    new_location_id: int


class InventoryChangeStatus(BaseModel):
    status: InventoryStatus


class InventoryRead(ORMBase, InventoryBase):
    id: int
    reserved_quantity: float
    available_quantity: float
    created_at: datetime
    updated_at: datetime
    location_path: Optional[str] = Field(
        None, description="Computed composite string, e.g. 'FG-WH1-A-03-05'"
    )
