from datetime import date

from sqlalchemy import String, ForeignKey, Numeric, Date, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin
from app.db.models.enums import InventoryStatus

if TYPE_CHECKING:
    from app.db.models.product import Product
    from app.db.models.manufacturer import Manufacturer
    from app.db.models.location import Location


class Inventory(Base, IDMixin, TimestampMixin):
    """
    A stock record: a quantity of a product, from a manufacturer, in a batch,
    sitting in a specific location with a given status.
    """

    __tablename__ = "inventories"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    manufacturer_id: Mapped[int] = mapped_column(ForeignKey("manufacturers.id"), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)

    batch_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    manufacturing_date: Mapped[date] = mapped_column(Date, nullable=False)

    quantity: Mapped[float] = mapped_column(Numeric(14, 3), nullable=False)
    reserved_quantity: Mapped[float] = mapped_column(Numeric(14, 3), default=0, nullable=False)

    status: Mapped[InventoryStatus] = mapped_column(SAEnum(InventoryStatus, name="inventory_status"), nullable=False)

    product: Mapped["Product"] = relationship(back_populates="inventories")
    manufacturer: Mapped["Manufacturer"] = relationship(back_populates="inventories")
    location: Mapped["Location"] = relationship(back_populates="inventories")

    @property
    def available_quantity(self) -> float:
        return float(self.quantity) - float(self.reserved_quantity)

    def __repr__(self) -> str:
        return f"<Inventory id={self.id} product_id={self.product_id} batch={self.batch_number}>"
