from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.db.schemas.common import ORMBase


class UnitBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)


class UnitCreate(UnitBase):
    pass


class UnitUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)


class UnitRead(ORMBase, UnitBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
