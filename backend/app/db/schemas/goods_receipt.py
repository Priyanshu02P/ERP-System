from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.db.models.enums import GRNStatus
from app.db.schemas.common import ORMBase


class GoodsReceiptItemCreate(BaseModel):
    po_item_id: int
    received_quantity: float = Field(..., gt=0)
    vendor_batch_number: Optional[str] = Field(None, max_length=50)
    manufacturing_date: Optional[date] = None
    remarks: Optional[str] = Field(None, max_length=255)


class GoodsReceiptItemRead(ORMBase):
    id: int
    po_item_id: int
    received_quantity: float
    variance_quantity: float
    vendor_batch_number: Optional[str] = None
    manufacturing_date: Optional[date] = None
    remarks: Optional[str] = None


class GoodsReceiptCreate(BaseModel):
    po_id: int
    vendor_invoice_ref: Optional[str] = Field(None, max_length=100)
    vehicle_number: Optional[str] = Field(None, max_length=30)
    received_by: str = Field(..., min_length=1, max_length=100)
    overall_condition: Optional[str] = Field(None, max_length=255)
    items: List[GoodsReceiptItemCreate] = Field(..., min_length=1)


class GoodsReceiptRead(ORMBase):
    id: int
    grn_number: str
    po_id: int
    vendor_invoice_ref: Optional[str] = None
    vehicle_number: Optional[str] = None
    received_by: str
    received_at: datetime
    status: GRNStatus
    overall_condition: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[GoodsReceiptItemRead] = []
