from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.db.models.enums import QuotationStatus, SourceChannel
from app.db.schemas.common import ORMBase


class QuotationItemCreate(BaseModel):
    """Human-entry line item: the purchase officer already knows the
    product, so product_id is required and no fuzzy matching happens."""

    product_id: int
    raw_description: Optional[str] = Field(None, max_length=255)
    quantity: float = Field(..., gt=0)
    rate: float = Field(..., ge=0)
    gst_rate: Optional[float] = Field(None, ge=0, le=100)
    amount: Optional[float] = Field(None, ge=0)


class QuotationItemIngest(BaseModel):
    """Automation-entry line item: only what an OCR/parser can read off a
    document. product_id is never accepted here - it's always resolved by
    fuzzy matching in the service layer."""

    raw_description: str = Field(..., min_length=1, max_length=255)
    quantity: float = Field(..., gt=0)
    rate: float = Field(..., ge=0)
    gst_rate: Optional[float] = Field(None, ge=0, le=100)
    amount: Optional[float] = Field(None, ge=0)


class QuotationItemUpdate(BaseModel):
    """Used during review to correct an unmatched or misread line."""

    product_id: Optional[int] = None
    quantity: Optional[float] = Field(None, gt=0)
    rate: Optional[float] = Field(None, ge=0)
    gst_rate: Optional[float] = Field(None, ge=0, le=100)
    amount: Optional[float] = Field(None, ge=0)


class QuotationItemRead(ORMBase):
    id: int
    product_id: Optional[int] = None
    raw_description: str
    quantity: float
    rate: float
    gst_rate: Optional[float] = None
    amount: float
    match_confidence: Optional[float] = None


class VendorQuotationBase(BaseModel):
    supplier_id: int
    vendor_quotation_no: Optional[str] = Field(None, max_length=50)
    quotation_date: Optional[date] = None
    validity_date: Optional[date] = None
    payment_terms: Optional[str] = Field(None, max_length=150)
    delivery_lead_time_days: Optional[int] = Field(None, ge=0)


class VendorQuotationCreate(VendorQuotationBase):
    """Manual entry, nested under an RFQ - see POST /rfqs/{id}/quotations."""

    items: List[QuotationItemCreate] = Field(..., min_length=1)


class VendorQuotationIngest(VendorQuotationBase):
    """Automation entry - see POST /quotations/ingest. rfq_id is optional
    here (top-level, not path-nested) since a bot may not know which RFQ a
    forwarded quotation belongs to."""

    rfq_id: Optional[int] = None
    source: SourceChannel = SourceChannel.OCR_BOT
    source_confidence: Optional[float] = Field(None, ge=0, le=1)
    raw_document_url: Optional[str] = Field(None, max_length=500)
    items: List[QuotationItemIngest] = Field(..., min_length=1)


class VendorQuotationReview(BaseModel):
    reviewed_by: str = Field(..., min_length=1, max_length=100)


class VendorQuotationReject(BaseModel):
    rejected_by: str = Field(..., min_length=1, max_length=100)
    rejection_reason: str = Field(..., min_length=1, max_length=255)


class VendorQuotationRead(ORMBase, VendorQuotationBase):
    id: int
    rfq_id: Optional[int] = None
    status: QuotationStatus
    source: SourceChannel
    source_confidence: Optional[float] = None
    raw_document_url: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[QuotationItemRead] = []
