from datetime import datetime
from typing import Any, List, Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, DateTime, Numeric, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin
from app.db.models.enums import QCDisposition, QCItemDisposition

if TYPE_CHECKING:
    from app.db.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
    from app.db.models.location import Location
    from app.db.models.manufacturer import Manufacturer
    from app.db.models.inventory import Inventory


class QualityInspection(Base, IDMixin, TimestampMixin):
    """
    QC pass over a single GoodsReceipt. One GoodsReceipt has at most one
    QualityInspection (enforced by a unique constraint on grn_id, same
    "DB unique + service check for a clean error message" pattern as
    PurchaseOrder.quotation_id - see QualityInspectionService.create_qc()).

    deviation_approved_by starts null even when a line is dispositioned
    DEVIATION at creation time - see QCItemDisposition and
    QualityInspectionService.approve_deviation().
    """

    __tablename__ = "quality_inspections"

    qc_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)

    grn_id: Mapped[int] = mapped_column(ForeignKey("goods_receipts.id"), unique=True, nullable=False)
    grn: Mapped["GoodsReceipt"] = relationship()

    inspector: Mapped[str] = mapped_column(String(100), nullable=False)
    inspected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    overall_disposition: Mapped[QCDisposition] = mapped_column(
        SAEnum(QCDisposition, name="qc_disposition"), nullable=False
    )
    deviation_approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deviation_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[List["QualityInspectionItem"]] = relationship(
        back_populates="qc", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<QualityInspection id={self.id} qc_number={self.qc_number} disposition={self.overall_disposition}>"


class QualityInspectionItem(Base, IDMixin, TimestampMixin):
    __tablename__ = "quality_inspection_items"

    qc_id: Mapped[int] = mapped_column(ForeignKey("quality_inspections.id"), nullable=False)
    qc: Mapped["QualityInspection"] = relationship(back_populates="items")

    grn_item_id: Mapped[int] = mapped_column(ForeignKey("goods_receipt_items.id"), nullable=False)
    grn_item: Mapped["GoodsReceiptItem"] = relationship()

    # List of {parameter, spec, observed, result} dicts, matching the sample
    # QC doc's table (Procurement_Implementation_Plan.md §2.8).
    parameter_results: Mapped[Optional[List[dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    disposition: Mapped[QCItemDisposition] = mapped_column(
        SAEnum(QCItemDisposition, name="qc_item_disposition"), nullable=False
    )
    accepted_quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    rejected_quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False, default=0)

    # Required for ACCEPT/DEVIATION (where accepted stock needs somewhere to
    # go), null for REJECT.
    putaway_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    putaway_location: Mapped[Optional["Location"]] = relationship()

    # Defaults from grn.po.supplier.manufacturer_id but overridable - needed
    # because Inventory.manufacturer_id is non-nullable. Null for REJECT.
    manufacturer_id: Mapped[int | None] = mapped_column(ForeignKey("manufacturers.id"), nullable=True)
    manufacturer: Mapped[Optional["Manufacturer"]] = relationship()

    # Set once Inventory is actually created for this line - immediately for
    # ACCEPT, on approval for DEVIATION (see QualityInspectionService), never
    # for REJECT. Nullable FK so a pending-deviation line can exist without one.
    inventory_id: Mapped[int | None] = mapped_column(ForeignKey("inventories.id"), nullable=True)
    inventory: Mapped[Optional["Inventory"]] = relationship()

    def __repr__(self) -> str:
        return f"<QualityInspectionItem id={self.id} grn_item_id={self.grn_item_id} disposition={self.disposition}>"
