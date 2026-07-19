from typing import List, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.shelf import Shelf
    from app.db.models.location import Location


class Bin(Base, IDMixin, TimestampMixin):
    """Bin within a shelf (e.g. '05'). Code is unique per shelf, not globally."""

    __tablename__ = "bins"
    __table_args__ = (UniqueConstraint("shelf_id", "code", name="uq_bin_shelf_code"),)

    code: Mapped[str] = mapped_column(String(10), nullable=False)

    shelf_id: Mapped[int] = mapped_column(ForeignKey("shelves.id"), nullable=False)
    shelf: Mapped["Shelf"] = relationship(back_populates="bins")

    locations: Mapped[List["Location"]] = relationship(back_populates="bin")

    def __repr__(self) -> str:
        return f"<Bin id={self.id} shelf_id={self.shelf_id} code={self.code}>"
