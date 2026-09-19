from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Date, DateTime, Numeric, Float, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.shared.mixins import IDMixin, TimestampMixin
from app.shared.enums import InvoiceStatus, SourceChannel

if TYPE_CHECKING:
    from app.procurement.purchase_order.models import PurchaseOrder, PurchaseOrderItem
    from app.wms.goods_receipt.models import GoodsReceipt
    from app.procurement.supplier.models import Supplier


class VendorInvoice(Base, IDMixin, TimestampMixin):
    """
    A supplier's bill against a PurchaseOrder - the final leg of the 3-way
    match (PO vs GRN vs Invoice) described in Procurement_Implementation_Plan.md
    §2.9. Human-entered invoices still land in PENDING_MATCH (matching is a
    distinct, deliberate step regardless of who typed the invoice in) but
    require po_item_id on every line up front; AI-parsed ones
    (VendorInvoiceService.ingest) fuzzy-match lines against the target PO's
    own items and can leave lines unmapped for a human to fix during review
    - see InvoiceStatus's docstring for why PENDING_MATCH doubles as the
    review-queue state here.

    subtotal/gst_amount/total_amount are computed server-side from the line
    items, same as PurchaseOrder - never trusted from the client even when
    ingested from an OCR-read document.
    """

    __tablename__ = "vendor_invoices"

    vendor_invoice_no: Mapped[str | None] = mapped_column(String(50), nullable=True)

    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    supplier: Mapped["Supplier"] = relationship()

    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    po: Mapped["PurchaseOrder"] = relationship()

    # Nullable - a service-only invoice (e.g. freight) may have no GRN at
    # all, and even a goods invoice may arrive before a human has pinned
    # down which GRN it's against (see VendorInvoiceService._resolve_grn_id
    # for the one-GRN auto-resolve convenience, and PUT /vendor-invoices/{id}
    # for setting it explicitly). /match requires it to be set.
    grn_id: Mapped[int | None] = mapped_column(ForeignKey("goods_receipts.id"), nullable=True)
    grn: Mapped[Optional["GoodsReceipt"]] = relationship()

    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    gst_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(InvoiceStatus, name="invoice_status"), nullable=False, default=InvoiceStatus.PENDING_MATCH
    )

    # Provenance - deliberately its own Postgres enum type, same reasoning
    # as VendorQuotation.source (see that model's docstring).
    source: Mapped[SourceChannel] = mapped_column(
        SAEnum(SourceChannel, name="invoice_source_channel"), nullable=False, default=SourceChannel.MANUAL
    )
    source_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Populated by VendorInvoiceService.match() - per-line and header
    # tolerance comparisons, see that method's docstring.
    match_report: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    matched_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    paid_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[List["VendorInvoiceItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<VendorInvoice id={self.id} po_id={self.po_id} status={self.status}>"


class VendorInvoiceItem(Base, IDMixin, TimestampMixin):
    __tablename__ = "vendor_invoice_items"

    invoice_id: Mapped[int] = mapped_column(ForeignKey("vendor_invoices.id"), nullable=False)
    invoice: Mapped["VendorInvoice"] = relationship(back_populates="items")

    # Nullable for the same reason QuotationItem.product_id is nullable: an
    # OCR-read invoice line doesn't know our PO line numbering. Resolved by
    # fuzzy-matching the line's description against the target PO's own
    # items on ingest, or left NULL for a human to map - see
    # VendorInvoiceService.update_item(). A manually-entered invoice
    # requires it up front instead (full trust on the mapping).
    po_item_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_order_items.id"), nullable=True)
    po_item: Mapped[Optional["PurchaseOrderItem"]] = relationship()

    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    gst_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    # Fuzzy-match confidence (0-1) against the target PO's item
    # product code/name, set only when po_item_id was resolved
    # automatically on ingest - mirrors QuotationItem.match_confidence.
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<VendorInvoiceItem id={self.id} po_item_id={self.po_item_id} amount={self.amount}>"
