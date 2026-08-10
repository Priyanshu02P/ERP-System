from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.db.models.enums import SupplierCategory
from app.db.schemas.common import ORMBase


class SupplierBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)
    gstin: Optional[str] = Field(None, max_length=15)
    address: Optional[str] = Field(None, max_length=255)
    contact_person: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=150)
    category: SupplierCategory
    default_payment_terms: Optional[str] = Field(None, max_length=150)
    manufacturer_id: Optional[int] = None

    @field_validator("gstin")
    @classmethod
    def gstin_uppercase(cls, v: Optional[str]) -> Optional[str]:
        # GSTIN is 15 alphanumeric characters (e.g. 24AABCT1234M1Z5); we don't
        # validate the checksum here, just normalize case for consistent search.
        return v.upper() if v else v


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    gstin: Optional[str] = Field(None, max_length=15)
    address: Optional[str] = Field(None, max_length=255)
    contact_person: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=30)
    email: Optional[str] = Field(None, max_length=150)
    category: Optional[SupplierCategory] = None
    default_payment_terms: Optional[str] = Field(None, max_length=150)
    manufacturer_id: Optional[int] = None


class SupplierRead(ORMBase, SupplierBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
