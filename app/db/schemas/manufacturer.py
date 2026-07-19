from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.db.schemas.common import ORMBase


class ManufacturerBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)
    address: Optional[str] = Field(None, max_length=255)
    contact_info: Optional[str] = Field(None, max_length=150)


class ManufacturerCreate(ManufacturerBase):
    pass


class ManufacturerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    address: Optional[str] = Field(None, max_length=255)
    contact_info: Optional[str] = Field(None, max_length=150)


class ManufacturerRead(ORMBase, ManufacturerBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
