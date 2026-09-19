from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.enums import RFQStatus, SendChannel, RFQResponseStatus
from app.shared.schemas_common import ORMBase


class RFQItemBase(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    required_delivery_date: Optional[date] = None


class RFQItemCreate(RFQItemBase):
    pass


class RFQItemRead(ORMBase, RFQItemBase):
    id: int


class RFQSupplierRead(ORMBase):
    id: int
    supplier_id: int
    sent_at: Optional[datetime] = None
    sent_channel: Optional[SendChannel] = None
    response_status: RFQResponseStatus


class RFQBase(BaseModel):
    due_date: date
    delivery_location: Optional[str] = Field(None, max_length=255)
    pr_id: Optional[int] = None


class RFQCreate(RFQBase):
    items: List[RFQItemCreate] = Field(..., min_length=1)


class RFQSend(BaseModel):
    supplier_ids: List[int] = Field(..., min_length=1)
    channel: SendChannel = SendChannel.API


class RFQRead(ORMBase, RFQBase):
    id: int
    rfq_number: str
    status: RFQStatus
    created_at: datetime
    updated_at: datetime
    items: List[RFQItemRead] = []
    suppliers: List[RFQSupplierRead] = []
