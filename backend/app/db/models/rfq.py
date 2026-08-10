from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Date, DateTime, Numeric, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin
from app.db.models.enums import RFQStatus, SendChannel, RFQResponseStatus

if TYPE_CHECKING:
    from app.db.models.product import Product
    from app.db.models.supplier import Supplier
    from app.db.models.purchase_requisition import PurchaseRequisition


class RFQ(Base, IDMixin, TimestampMixin):
    """
    Request for Quotation sent to one or more suppliers for a set of
    products. May originate from an approved PurchaseRequisition, or be
    raised directly for routine buys (pr_id nullable - see
    Procurement_Implementation_Plan.md \u00a72.4).
    """

    __tablename__ = "rfqs"

    rfq_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    pr_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_requisitions.id"), nullable=True)
    pr: Mapped[Optional["PurchaseRequisition"]] = relationship()

    status: Mapped[RFQStatus] = mapped_column(
        SAEnum(RFQStatus, name="rfq_status"), nullable=False, default=RFQStatus.DRAFT
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    delivery_location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    items: Mapped[List["RFQItem"]] = relationship(back_populates="rfq", cascade="all, delete-orphan")
    suppliers: Mapped[List["RFQSupplier"]] = relationship(back_populates="rfq", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<RFQ id={self.id} rfq_number={self.rfq_number} status={self.status}>"


class RFQItem(Base, IDMixin, TimestampMixin):
    __tablename__ = "rfq_items"

    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id"), nullable=False)
    rfq: Mapped["RFQ"] = relationship(back_populates="items")

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    product: Mapped["Product"] = relationship()

    quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    required_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    def __repr__(self) -> str:
        return f"<RFQItem id={self.id} product_id={self.product_id} qty={self.quantity}>"


class RFQSupplier(Base, IDMixin, TimestampMixin):
    """
    Join table: which suppliers an RFQ was sent to, over which channel, and
    whether they've responded yet. Rows are created when the RFQ is sent
    (see RFQService.send), not at RFQ creation time.
    """

    __tablename__ = "rfq_suppliers"

    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id"), nullable=False)
    rfq: Mapped["RFQ"] = relationship(back_populates="suppliers")

    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    supplier: Mapped["Supplier"] = relationship()

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_channel: Mapped[SendChannel | None] = mapped_column(
        SAEnum(SendChannel, name="send_channel"), nullable=True
    )
    response_status: Mapped[RFQResponseStatus] = mapped_column(
        SAEnum(RFQResponseStatus, name="rfq_response_status"),
        nullable=False,
        default=RFQResponseStatus.SENT,
    )

    def __repr__(self) -> str:
        return f"<RFQSupplier rfq_id={self.rfq_id} supplier_id={self.supplier_id} status={self.response_status}>"
