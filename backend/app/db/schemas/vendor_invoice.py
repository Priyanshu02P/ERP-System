from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.db.models.enums import InvoiceStatus, SourceChannel
from app.db.schemas.common import ORMBase


class VendorInvoiceItemCreate(BaseModel):
    """Human-entry line item: the purchase officer already knows which PO
    line this invoice line is for, so po_item_id is required."""

    po_item_id: int
    description: str = Field(..., min_length=1, max_length=255)
    quantity: float = Field(..., gt=0)
    rate: float = Field(..., ge=0)
    gst_rate: Optional[float] = Field(None, ge=0, le=100)
    amount: Optional[float] = Field(None, ge=0)


class VendorInvoiceItemIngest(BaseModel):
    """Automation-entry line item: only what an OCR/parser can read off a
    document. po_item_id is never accepted here - it's always resolved by
    fuzzy matching against the target PO's own items in the service layer."""

    description: str = Field(..., min_length=1, max_length=255)
    quantity: float = Field(..., gt=0)
    rate: float = Field(..., ge=0)
    gst_rate: Optional[float] = Field(None, ge=0, le=100)
    amount: Optional[float] = Field(None, ge=0)


class VendorInvoiceItemUpdate(BaseModel):
    """Used during review to correct an unmatched or misread line."""

    po_item_id: Optional[int] = None
    description: Optional[str] = Field(None, min_length=1, max_length=255)
    quantity: Optional[float] = Field(None, gt=0)
    rate: Optional[float] = Field(None, ge=0)
    gst_rate: Optional[float] = Field(None, ge=0, le=100)
    amount: Optional[float] = Field(None, ge=0)


class VendorInvoiceItemRead(ORMBase):
    id: int
    po_item_id: Optional[int] = None
    description: str
    quantity: float
    rate: float
    gst_rate: Optional[float] = None
    amount: float
    match_confidence: Optional[float] = None


class VendorInvoiceBase(BaseModel):
    supplier_id: int
    po_id: int
    grn_id: Optional[int] = None
    vendor_invoice_no: Optional[str] = Field(None, max_length=50)
    invoice_date: Optional[date] = None


class VendorInvoiceCreate(VendorInvoiceBase):
    """Manual entry - see POST /vendor-invoices."""

    items: List[VendorInvoiceItemCreate] = Field(..., min_length=1)


class VendorInvoiceIngest(VendorInvoiceBase):
    """Automation entry - see POST /vendor-invoices/ingest."""

    source: SourceChannel = SourceChannel.OCR_BOT
    source_confidence: Optional[float] = Field(None, ge=0, le=1)
    raw_document_url: Optional[str] = Field(None, max_length=500)
    items: List[VendorInvoiceItemIngest] = Field(..., min_length=1)


class VendorInvoiceUpdate(BaseModel):
    """Header fields editable while PENDING_MATCH/MISMATCH - e.g. setting
    grn_id once it's known, or correcting the vendor's own invoice number."""

    grn_id: Optional[int] = None
    vendor_invoice_no: Optional[str] = Field(None, max_length=50)
    invoice_date: Optional[date] = None


class VendorInvoiceMatch(BaseModel):
    matched_by: str = Field(..., min_length=1, max_length=100)


class VendorInvoiceApprovePayment(BaseModel):
    approved_by: str = Field(..., min_length=1, max_length=100)


class VendorInvoiceMarkPaid(BaseModel):
    paid_by: str = Field(..., min_length=1, max_length=100)


class VendorInvoiceRead(ORMBase, VendorInvoiceBase):
    id: int
    status: InvoiceStatus
    subtotal: float
    gst_amount: float
    total_amount: float
    source: SourceChannel
    source_confidence: Optional[float] = None
    raw_document_url: Optional[str] = None
    match_report: Optional[dict[str, Any]] = None
    matched_by: Optional[str] = None
    matched_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    paid_by: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: List[VendorInvoiceItemRead] = []
