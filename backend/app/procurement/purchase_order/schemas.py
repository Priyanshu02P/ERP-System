from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.shared.enums import POStatus, POLineStatus
from app.shared.schemas_common import ORMBase


class PurchaseOrderItemCreate(BaseModel):
    """Manual-entry line item. Not used when creating from a quotation -
    items are copied from the quotation's own (already-mapped) lines in
    that case."""

    product_id: int
    quantity: float = Field(..., gt=0)
    rate: float = Field(..., ge=0)
    gst_rate: Optional[float] = Field(None, ge=0, le=100)
    amount: Optional[float] = Field(None, ge=0)


class PurchaseOrderItemRead(ORMBase):
    id: int
    product_id: int
    quantity: float
    rate: float
    gst_rate: Optional[float] = None
    amount: float
    received_quantity: float
    line_status: POLineStatus


class PurchaseOrderBase(BaseModel):
    order_date: date
    expected_delivery_date: Optional[date] = None
    payment_terms: Optional[str] = Field(None, max_length=150)


class PurchaseOrderCreate(PurchaseOrderBase):
    """
    Either:
      - `quotation_id` set: the PO is converted from a SELECTED
        VendorQuotation. `supplier_id`/`items` are ignored if supplied -
        both are taken from the quotation, which is already known-good
        (every line mapped to a product, a single supplier).
      - `quotation_id` omitted: a manual/routine PO. `supplier_id` and
        `items` are then required.
    """

    quotation_id: Optional[int] = None
    pr_id: Optional[int] = None
    supplier_id: Optional[int] = None
    items: Optional[List[PurchaseOrderItemCreate]] = None

    @model_validator(mode="after")
    def _check_manual_requirements(self) -> "PurchaseOrderCreate":
        if self.quotation_id is None:
            if self.supplier_id is None:
                raise ValueError("supplier_id is required when quotation_id is not provided")
            if not self.items:
                raise ValueError("items is required (and must be non-empty) when quotation_id is not provided")
        return self


class PurchaseOrderUpdate(BaseModel):
    """Header-only edit, allowed while the PO is still DRAFT."""

    order_date: Optional[date] = None
    expected_delivery_date: Optional[date] = None
    payment_terms: Optional[str] = Field(None, max_length=150)


class PurchaseOrderSend(BaseModel):
    approved_by: str = Field(..., min_length=1, max_length=100)


class PurchaseOrderCancel(BaseModel):
    cancelled_by: str = Field(..., min_length=1, max_length=100)
    cancellation_reason: str = Field(..., min_length=1, max_length=255)


class PurchaseOrderRead(ORMBase, PurchaseOrderBase):
    id: int
    po_number: str
    quotation_id: Optional[int] = None
    pr_id: Optional[int] = None
    supplier_id: int
    status: POStatus
    subtotal: float
    gst_amount: float
    total_amount: float
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[PurchaseOrderItemRead] = []
