from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Date, DateTime, Numeric, Float, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.shared.mixins import IDMixin, TimestampMixin
from app.shared.enums import QuotationStatus, SourceChannel

if TYPE_CHECKING:
    from app.master_data.product.models import Product
    from app.procurement.supplier.models import Supplier
    from app.procurement.rfq.models import RFQ


class VendorQuotation(Base, IDMixin, TimestampMixin):
    """
    A supplier's quoted price for an RFQ (or a routine buy with no RFQ -
    rfq_id nullable). Human-entered quotations start REVIEWED (a person
    typed it, product_id is already correct); AI-parsed ones start
    PENDING_REVIEW and can't be SELECTED until every line is mapped to a
    product - see VendorQuotationService.
    """

    __tablename__ = "vendor_quotations"

    rfq_id: Mapped[int | None] = mapped_column(ForeignKey("rfqs.id"), nullable=True)
    rfq: Mapped[Optional["RFQ"]] = relationship()

    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    supplier: Mapped["Supplier"] = relationship()

    vendor_quotation_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quotation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    validity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(150), nullable=True)
    delivery_lead_time_days: Mapped[int | None] = mapped_column(nullable=True)

    status: Mapped[QuotationStatus] = mapped_column(
        SAEnum(QuotationStatus, name="quotation_status"), nullable=False, default=QuotationStatus.PENDING_REVIEW
    )

    # Provenance - who/what created this record, and how sure it was.
    # Deliberately a distinct Postgres enum type from PurchaseRequisition.source
    # (both back the same Python SourceChannel, values just differ by list
    # order over time) - reusing the PR module's already-created
    # 'source_channel' type here would require an ALTER TYPE ... ADD VALUE
    # for OCR_BOT that Postgres can't use within the same migration
    # transaction that adds it.
    source: Mapped[SourceChannel] = mapped_column(
        SAEnum(SourceChannel, name="quotation_source_channel"), nullable=False, default=SourceChannel.MANUAL
    )
    source_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rejected_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    items: Mapped[List["QuotationItem"]] = relationship(back_populates="quotation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<VendorQuotation id={self.id} supplier_id={self.supplier_id} status={self.status}>"


class QuotationItem(Base, IDMixin, TimestampMixin):
    __tablename__ = "quotation_items"

    quotation_id: Mapped[int] = mapped_column(ForeignKey("vendor_quotations.id"), nullable=False)
    quotation: Mapped["VendorQuotation"] = relationship(back_populates="items")

    # Nullable: an AI parser reads a line off a vendor PDF/photo before it
    # knows our internal product codes. raw_description is always stored
    # (as extracted); product_id is filled in by fuzzy matching on ingest,
    # or left NULL for a human to map during review.
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    product: Mapped[Optional["Product"]] = relationship()

    raw_description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    gst_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    # Fuzzy-match confidence (0-1) against products.name/code, set only
    # when product_id was resolved automatically on ingest.
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<QuotationItem id={self.id} product_id={self.product_id} rate={self.rate}>"
