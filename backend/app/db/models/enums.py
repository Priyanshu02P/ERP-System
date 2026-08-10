import enum


class ProductType(str, enum.Enum):
    """Where a product sits in the manufacturing lifecycle."""

    RAW = "RAW"   # Raw material
    WIP = "WIP"   # Work in progress
    FG = "FG"     # Finished good


class InventoryStatus(str, enum.Enum):
    """Current disposition of a stock record."""

    OK = "OK"     # Good / ready to sell (shown together with product type, e.g. "FG")
    RJC = "RJC"   # Rejected
    MIS = "MIS"   # Missing
    RET = "RET"   # Returned
    HLD = "HLD"   # On hold
    DMG = "DMG"   # Damaged


class LocationCategory(str, enum.Enum):
    """Distinguishes normal rack/shelf/bin storage from special oversized-item zones."""

    STANDARD = "STANDARD"  # Normal WHx-Rack-Shelf-Bin hierarchy
    SHEET = "SHEET"        # Oversized flat stock, stored at warehouse+rack level only
    PIPE = "PIPE"          # Oversized pipe stock, stored at warehouse+rack level only
    SCRAP = "SCRAP"        # Scrap / rejected-goods yard, stored at warehouse+rack level only


class SupplierCategory(str, enum.Enum):
    """What a supplier/vendor is approved to sell. Distinct from Manufacturer,
    which records who made a given batch of stock rather than who it was
    procured from (e.g. supplier 'Tata Steel Distributor' vs manufacturer
    'Tata Steel')."""

    STEEL = "STEEL"
    STAINLESS_STEEL = "STAINLESS_STEEL"
    ALUMINIUM = "ALUMINIUM"
    HARDWARE = "HARDWARE"
    POWDER_COATING = "POWDER_COATING"
    PACKAGING = "PACKAGING"
    LOGISTICS = "LOGISTICS"
    CONSUMABLES = "CONSUMABLES"
    OTHER = "OTHER"


class PRStatus(str, enum.Enum):
    """Purchase Requisition lifecycle. CONVERTED/CLOSED are set by later
    procurement phases (RFQ/PO) once they exist - the PR module itself only
    drives DRAFT -> PENDING_APPROVAL -> APPROVED/REJECTED."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CONVERTED = "CONVERTED"
    CLOSED = "CLOSED"


class PRPriority(str, enum.Enum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"


class SourceChannel(str, enum.Enum):
    """Who/what created a procurement record. Used to distinguish manual
    human entry from bot/automation-originated records (e.g. an n8n
    reorder-level digest raising a PR automatically)."""

    MANUAL = "MANUAL"
    WHATSAPP_BOT = "WHATSAPP_BOT"
    TELEGRAM_BOT = "TELEGRAM_BOT"
    EMAIL_PARSER = "EMAIL_PARSER"
    OCR_BOT = "OCR_BOT"
    API = "API"
    AUTO_REORDER = "AUTO_REORDER"


class RFQStatus(str, enum.Enum):
    """RFQ lifecycle. CANCELLED is reserved for a future phase (no cancel
    endpoint yet, same as PRStatus.CONVERTED/CLOSED in the PR module)."""

    DRAFT = "DRAFT"
    SENT = "SENT"
    RESPONSES_RECEIVED = "RESPONSES_RECEIVED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class SendChannel(str, enum.Enum):
    """Channel an RFQ was actually dispatched through to a given supplier."""

    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    TELEGRAM = "TELEGRAM"
    API = "API"


class RFQResponseStatus(str, enum.Enum):
    """Per-supplier response tracking on an RFQ. SENT is the state from
    dispatch until either a quotation arrives (-> RESPONDED) or the RFQ is
    closed with nothing received (-> NO_RESPONSE)."""

    SENT = "SENT"
    RESPONDED = "RESPONDED"
    NO_RESPONSE = "NO_RESPONSE"


class QuotationStatus(str, enum.Enum):
    """Vendor quotation lifecycle. AI-parsed quotations land in
    PENDING_REVIEW and can never be SELECTED until every line item is
    mapped to a product - see VendorQuotationService.select()."""

    PENDING_REVIEW = "PENDING_REVIEW"
    REVIEWED = "REVIEWED"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class POStatus(str, enum.Enum):
    """Purchase Order lifecycle. This module (Phase 4) drives
    DRAFT -> SENT -> CONFIRMED, plus CANCELLED from either DRAFT or SENT.
    PARTIALLY_RECEIVED/RECEIVED/CLOSED are set by the GRN module once it
    exists (Phase 5) as goods are received against the PO - same reasoning
    as PRStatus.CONVERTED/CLOSED and RFQStatus.CANCELLED before it: the
    enum values are here now so that phase doesn't need a migration to add
    them later."""

    DRAFT = "DRAFT"
    SENT = "SENT"
    CONFIRMED = "CONFIRMED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class POLineStatus(str, enum.Enum):
    """Per-line receiving progress on a PurchaseOrderItem. Stays PENDING
    until the GRN module (Phase 5) starts posting received_quantity against
    it - present now so that phase's migration only needs to add GRN
    tables, not touch this one."""

    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"


class GRNStatus(str, enum.Enum):
    """Goods Receipt Note lifecycle. PENDING_QC -> QC_IN_PROGRESS happens as
    soon as a QualityInspection is recorded against the GRN (see
    QualityInspectionService.create_qc) - QC_IN_PROGRESS -> CLOSED is a
    separate explicit step (POST /goods-receipts/{id}/close) so a purchase
    officer can review the QC outcome (including any pending deviation
    approval) before the GRN is considered fully settled."""

    PENDING_QC = "PENDING_QC"
    QC_IN_PROGRESS = "QC_IN_PROGRESS"
    CLOSED = "CLOSED"


class QCDisposition(str, enum.Enum):
    """Header-level rollup of a QualityInspection's line-item dispositions -
    see QualityInspectionService._resolve_overall_disposition()."""

    ACCEPTED = "ACCEPTED"
    ACCEPTED_WITH_DEVIATION = "ACCEPTED_WITH_DEVIATION"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"


class QCItemDisposition(str, enum.Enum):
    """Per-line QC call. ACCEPT creates Inventory immediately. REJECT never
    does. DEVIATION holds off creating Inventory until a human approves it
    via POST /quality-inspections/{id}/approve-deviation - the same
    "machine/inspector flags it, a human approves" trust pattern used for
    AI-parsed quotations landing in PENDING_REVIEW (see plan §5)."""

    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    DEVIATION = "DEVIATION"


class InvoiceStatus(str, enum.Enum):
    """Vendor Invoice / 3-way-match lifecycle. PENDING_MATCH is also this
    module's review-queue state (see VendorInvoiceService.ingest): an
    ingested invoice with unmapped lines can't be matched until a human
    maps every line to a PurchaseOrderItem, the same way a quotation can't
    be SELECTED with unmapped product_ids.

    /match can be re-run from either PENDING_MATCH or MISMATCH (e.g. after
    a correction), landing on MATCHED or MISMATCH. APPROVED_FOR_PAYMENT only
    reachable from MATCHED - see approve_payment(). DISPUTED has no
    endpoint yet - reserved for a future phase, same pattern as
    RFQStatus.CANCELLED and POStatus.CLOSED before it."""

    PENDING_MATCH = "PENDING_MATCH"
    MATCHED = "MATCHED"
    MISMATCH = "MISMATCH"
    APPROVED_FOR_PAYMENT = "APPROVED_FOR_PAYMENT"
    PAID = "PAID"
    DISPUTED = "DISPUTED"
