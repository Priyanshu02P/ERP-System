from typing import List, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.shared.mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.wms.warehouse_structure.models.warehouse import Warehouse
    from app.wms.warehouse_structure.models.shelf import Shelf
    from app.wms.warehouse_structure.models.location import Location


class Rack(Base, IDMixin, TimestampMixin):
    """Rack within a warehouse (e.g. 'A'). Code is unique per warehouse, not globally."""

    __tablename__ = "racks"
    __table_args__ = (UniqueConstraint("warehouse_id", "code", name="uq_rack_warehouse_code"),)

    code: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    warehouse: Mapped["Warehouse"] = relationship(back_populates="racks")

    shelves: Mapped[List["Shelf"]] = relationship(back_populates="rack", cascade="all, delete-orphan")
    locations: Mapped[List["Location"]] = relationship(back_populates="rack")

    def __repr__(self) -> str:
        return f"<Rack id={self.id} warehouse_id={self.warehouse_id} code={self.code}>"
