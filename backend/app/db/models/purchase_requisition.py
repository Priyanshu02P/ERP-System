from datetime import date, datetime
from typing import List, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Date, DateTime, Numeric, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin
from app.db.models.enums import PRStatus, PRPriority, SourceChannel

if TYPE_CHECKING:
    from app.db.models.product import Product


class PurchaseRequisition(Base, IDMixin, TimestampMixin):
    """
    Internal request to buy material, raised by Store/Production. Not sent
    to a vendor - it's a demand signal and approval record. Once approved,
    later phases (RFQ/PO) reference it and eventually move it to CONVERTED.
    """

    __tablename__ = "purchase_requisitions"

    pr_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    status: Mapped[PRStatus] = mapped_column(
        SAEnum(PRStatus, name="pr_status"), nullable=False, default=PRStatus.DRAFT
    )
    priority: Mapped[PRPriority] = mapped_column(
        SAEnum(PRPriority, name="pr_priority"), nullable=False, default=PRPriority.NORMAL
    )
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    raised_by: Mapped[str] = mapped_column(String(100), nullable=False)
    required_by_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Free-text on purpose: no Sales Order module exists yet. See
    # docs/Procurement_Implementation_Plan.md "Decisions locked in".
    linked_sales_order: Mapped[str | None] = mapped_column(String(50), nullable=True)

    source: Mapped[SourceChannel] = mapped_column(
        SAEnum(SourceChannel, name="source_channel"), nullable=False, default=SourceChannel.MANUAL
    )

    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    items: Mapped[List["PurchaseRequisitionItem"]] = relationship(
        back_populates="pr", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PurchaseRequisition id={self.id} pr_number={self.pr_number} status={self.status}>"


class PurchaseRequisitionItem(Base, IDMixin, TimestampMixin):
    __tablename__ = "purchase_requisition_items"

    pr_id: Mapped[int] = mapped_column(ForeignKey("purchase_requisitions.id"), nullable=False)
    pr: Mapped["PurchaseRequisition"] = relationship(back_populates="items")

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    product: Mapped["Product"] = relationship()

    quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)

    # Captured at creation time from live Inventory.available_quantity, for
    # audit - "what did we think stock was when this line was raised".
    current_stock_snapshot: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)

    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<PurchaseRequisitionItem id={self.id} product_id={self.product_id} qty={self.quantity}>"
