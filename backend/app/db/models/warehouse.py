from typing import List, TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin, ActiveMixin

if TYPE_CHECKING:
    from app.db.models.rack import Rack
    from app.db.models.location import Location


class Warehouse(Base, IDMixin, TimestampMixin, ActiveMixin):
    """Warehouse master (e.g. WH1, WH3)."""

    __tablename__ = "warehouses"

    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    racks: Mapped[List["Rack"]] = relationship(back_populates="warehouse", cascade="all, delete-orphan")
    locations: Mapped[List["Location"]] = relationship(back_populates="warehouse")

    def __repr__(self) -> str:
        return f"<Warehouse id={self.id} code={self.code}>"
