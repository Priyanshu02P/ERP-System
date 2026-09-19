from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.shared.enums import PRStatus, PRPriority, SourceChannel
from app.shared.schemas_common import ORMBase


class PurchaseRequisitionItemBase(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    notes: Optional[str] = Field(None, max_length=255)


class PurchaseRequisitionItemCreate(PurchaseRequisitionItemBase):
    pass


class PurchaseRequisitionItemRead(ORMBase, PurchaseRequisitionItemBase):
    id: int
    current_stock_snapshot: Optional[float] = None


class PurchaseRequisitionBase(BaseModel):
    department: str = Field(..., min_length=1, max_length=100)
    raised_by: str = Field(..., min_length=1, max_length=100)
    priority: PRPriority = PRPriority.NORMAL
    required_by_date: date
    reason: Optional[str] = Field(None, max_length=255)
    linked_sales_order: Optional[str] = Field(None, max_length=50)


class PurchaseRequisitionCreate(PurchaseRequisitionBase):
    items: List[PurchaseRequisitionItemCreate] = Field(..., min_length=1)
    source: SourceChannel = SourceChannel.MANUAL


class PurchaseRequisitionUpdate(BaseModel):
    department: Optional[str] = Field(None, min_length=1, max_length=100)
    priority: Optional[PRPriority] = None
    required_by_date: Optional[date] = None
    reason: Optional[str] = Field(None, max_length=255)
    linked_sales_order: Optional[str] = Field(None, max_length=50)


class PurchaseRequisitionApprove(BaseModel):
    approved_by: str = Field(..., min_length=1, max_length=100)


class PurchaseRequisitionReject(BaseModel):
    rejected_by: str = Field(..., min_length=1, max_length=100)
    rejection_reason: str = Field(..., min_length=1, max_length=255)


class PurchaseRequisitionRead(ORMBase, PurchaseRequisitionBase):
    id: int
    pr_number: str
    status: PRStatus
    source: SourceChannel
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[PurchaseRequisitionItemRead] = []
