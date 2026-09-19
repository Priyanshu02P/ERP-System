from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Date, DateTime, Numeric, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.shared.mixins import IDMixin, TimestampMixin
from app.shared.enums import GRNStatus

if TYPE_CHECKING:
    from app.procurement.purchase_order.models import PurchaseOrder, PurchaseOrderItem


class GoodsReceipt(Base, IDMixin, TimestampMixin):
    """
    Records that goods physically arrived against a PurchaseOrder -
    deliberately separate from whether they're usable stock (that's QC's
    call, see QualityInspection) and from Inventory itself (only created
    once a line is QC-accepted). See
    Procurement_Implementation_Plan.md §2.7 and §4.

    A PurchaseOrder can have more than one GoodsReceipt (partial
    deliveries), so there's no uniqueness constraint on po_id.
    """

    __tablename__ = "goods_receipts"

    grn_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)

    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    po: Mapped["PurchaseOrder"] = relationship()

    vendor_invoice_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vehicle_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    received_by: Mapped[str] = mapped_column(String(100), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    status: Mapped[GRNStatus] = mapped_column(
        SAEnum(GRNStatus, name="grn_status"), nullable=False, default=GRNStatus.PENDING_QC
    )
    overall_condition: Mapped[str | None] = mapped_column(String(255), nullable=True)

    items: Mapped[List["GoodsReceiptItem"]] = relationship(back_populates="grn", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<GoodsReceipt id={self.id} grn_number={self.grn_number} status={self.status}>"


class GoodsReceiptItem(Base, IDMixin, TimestampMixin):
    __tablename__ = "goods_receipt_items"

    grn_id: Mapped[int] = mapped_column(ForeignKey("goods_receipts.id"), nullable=False)
    grn: Mapped["GoodsReceipt"] = relationship(back_populates="items")

    po_item_id: Mapped[int] = mapped_column(ForeignKey("purchase_order_items.id"), nullable=False)
    po_item: Mapped["PurchaseOrderItem"] = relationship()

    received_quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)

    # Computed at creation time as received_quantity minus what was still
    # outstanding on the PO line before this GRN (po_item.quantity -
    # po_item.received_quantity, evaluated pre-update) - positive means more
    # arrived than was still expected, negative means a shortfall. See
    # GoodsReceiptService.create_grn().
    variance_quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)

    vendor_batch_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manufacturing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    remarks: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<GoodsReceiptItem id={self.id} po_item_id={self.po_item_id} qty={self.received_quantity}>"
