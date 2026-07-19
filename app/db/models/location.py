from typing import List, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin
from app.db.models.enums import LocationCategory

if TYPE_CHECKING:
    from app.db.models.warehouse import Warehouse
    from app.db.models.rack import Rack
    from app.db.models.shelf import Shelf
    from app.db.models.bin import Bin
    from app.db.models.inventory import Inventory


class Location(Base, IDMixin, TimestampMixin):
    """
    A physical storage location.

    Normally a full hierarchy: warehouse -> rack -> shelf -> bin
    (e.g. WH1-A-03-05). Oversized items may skip lower levels
    (e.g. WH1-A, warehouse + rack only), and special categories
    (SHEET, PIPE) are always stored at the warehouse + rack level.

    `location_code` is a denormalized, human-readable string
    (e.g. "WH1-A-03-05") kept in sync by LocationService for fast
    lookups and display; it is not the source of truth for the
    hierarchy relationships themselves.
    """

    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("location_code", name="uq_location_code"),)

    category: Mapped[LocationCategory] = mapped_column(
        SAEnum(LocationCategory, name="location_category"),
        default=LocationCategory.STANDARD,
        nullable=False,
    )
    location_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    rack_id: Mapped[int | None] = mapped_column(ForeignKey("racks.id"), nullable=True)
    shelf_id: Mapped[int | None] = mapped_column(ForeignKey("shelves.id"), nullable=True)
    bin_id: Mapped[int | None] = mapped_column(ForeignKey("bins.id"), nullable=True)

    warehouse: Mapped["Warehouse"] = relationship(back_populates="locations")
    rack: Mapped["Rack | None"] = relationship(back_populates="locations")
    shelf: Mapped["Shelf | None"] = relationship(back_populates="locations")
    bin: Mapped["Bin | None"] = relationship(back_populates="locations")

    inventories: Mapped[List["Inventory"]] = relationship(back_populates="location")

    def __repr__(self) -> str:
        return f"<Location id={self.id} code={self.location_code}>"
