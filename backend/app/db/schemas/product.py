from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.db.models.enums import ProductType
from app.db.schemas.common import ORMBase


class ProductBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=255)
    product_type: ProductType
    part_number: Optional[str] = Field(None, max_length=50)
    image_url: Optional[str] = Field(None, max_length=255)
    unit_id: int


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=255)
    product_type: Optional[ProductType] = None
    part_number: Optional[str] = Field(None, max_length=50)
    image_url: Optional[str] = Field(None, max_length=255)
    unit_id: Optional[int] = None


class ProductRead(ORMBase, ProductBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
