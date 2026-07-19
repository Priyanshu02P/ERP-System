from typing import List, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.rack import Rack
    from app.db.models.bin import Bin
    from app.db.models.location import Location


class Shelf(Base, IDMixin, TimestampMixin):
    """Shelf within a rack (e.g. '03'). Code is unique per rack, not globally."""

    __tablename__ = "shelves"
    __table_args__ = (UniqueConstraint("rack_id", "code", name="uq_shelf_rack_code"),)

    code: Mapped[str] = mapped_column(String(10), nullable=False)

    rack_id: Mapped[int] = mapped_column(ForeignKey("racks.id"), nullable=False)
    rack: Mapped["Rack"] = relationship(back_populates="shelves")

    bins: Mapped[List["Bin"]] = relationship(back_populates="shelf", cascade="all, delete-orphan")
    locations: Mapped[List["Location"]] = relationship(back_populates="shelf")

    def __repr__(self) -> str:
        return f"<Shelf id={self.id} rack_id={self.rack_id} code={self.code}>"
