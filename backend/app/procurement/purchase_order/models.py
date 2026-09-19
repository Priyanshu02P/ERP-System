from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Date, DateTime, Numeric, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.shared.mixins import IDMixin, TimestampMixin
from app.shared.enums import POStatus, POLineStatus

if TYPE_CHECKING:
    from app.master_data.product.models import Product
    from app.procurement.supplier.models import Supplier
    from app.procurement.requisition.models import PurchaseRequisition
    from app.procurement.vendor_quotation.models import VendorQuotation


class PurchaseOrder(Base, IDMixin, TimestampMixin):
    """
    A commitment to buy from a Supplier - either converted from a SELECTED
    VendorQuotation (quotation_id set, the common path) or raised directly
    for a routine buy with no RFQ/quotation on file (quotation_id null,
    supplier_id + items supplied manually). See
    Procurement_Implementation_Plan.md \u00a72.6 and \u00a711 ("Deliberately not
    done in Phase 3").

    There is no separate PENDING_APPROVAL state (unlike PurchaseRequisition):
    approval and dispatch are a single action here - see
    PurchaseOrderService.send(), which requires approved_by and moves
    DRAFT -> SENT in one step, since sending a PO is the point real money
    and vendor commitment happen.
    """

    __tablename__ = "purchase_orders"

    po_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)

    quotation_id: Mapped[int | None] = mapped_column(
        ForeignKey("vendor_quotations.id"), unique=True, nullable=True
    )
    quotation: Mapped[Optional["VendorQuotation"]] = relationship()

    pr_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_requisitions.id"), nullable=True)
    pr: Mapped[Optional["PurchaseRequisition"]] = relationship()

    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    supplier: Mapped["Supplier"] = relationship()

    status: Mapped[POStatus] = mapped_column(
        SAEnum(POStatus, name="po_status"), nullable=False, default=POStatus.DRAFT
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(String(150), nullable=True)

    subtotal: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    gst_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cancelled_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    items: Mapped[List["PurchaseOrderItem"]] = relationship(back_populates="po", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<PurchaseOrder id={self.id} po_number={self.po_number} status={self.status}>"


class PurchaseOrderItem(Base, IDMixin, TimestampMixin):
    __tablename__ = "purchase_order_items"

    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), nullable=False)
    po: Mapped["PurchaseOrder"] = relationship(back_populates="items")

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    product: Mapped["Product"] = relationship()

    quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    gst_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    # Updated by the GRN module (Phase 5) as goods are received against
    # this line - untouched (stays 0 / PENDING) until then, same pattern as
    # PRStatus.CONVERTED/CLOSED being unused until later phases exist to
    # set them.
    received_quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    line_status: Mapped[POLineStatus] = mapped_column(
        SAEnum(POLineStatus, name="po_line_status"), nullable=False, default=POLineStatus.PENDING
    )

    def __repr__(self) -> str:
        return f"<PurchaseOrderItem id={self.id} product_id={self.product_id} qty={self.quantity}>"
