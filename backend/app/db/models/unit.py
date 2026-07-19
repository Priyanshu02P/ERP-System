from typing import List, TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin, ActiveMixin

if TYPE_CHECKING:
    from app.db.models.product import Product


class Unit(Base, IDMixin, TimestampMixin, ActiveMixin):
    """Unit of measure master (e.g. KG, PCS, MTR)."""

    __tablename__ = "units"

    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    products: Mapped[List["Product"]] = relationship(back_populates="unit")

    def __repr__(self) -> str:
        return f"<Unit id={self.id} code={self.code}>"
