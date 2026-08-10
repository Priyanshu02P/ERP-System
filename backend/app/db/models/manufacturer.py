from typing import List, TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin, ActiveMixin

if TYPE_CHECKING:
    from app.db.models.inventory import Inventory
    from app.db.models.supplier import Supplier


class Manufacturer(Base, IDMixin, TimestampMixin, ActiveMixin):
    """
    Manufacturer / brand master - records who made a given batch of stock
    (see Inventory.manufacturer_id). Distinct from Supplier, which records
    who a Purchase Order is actually issued to; a Supplier may optionally
    link back here via Supplier.manufacturer_id when it represents this brand.
    """

    __tablename__ = "manufacturers"

    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_info: Mapped[str | None] = mapped_column(String(150), nullable=True)

    inventories: Mapped[List["Inventory"]] = relationship(back_populates="manufacturer")
    suppliers: Mapped[List["Supplier"]] = relationship(back_populates="manufacturer")

    def __repr__(self) -> str:
        return f"<Manufacturer id={self.id} code={self.code}>"
