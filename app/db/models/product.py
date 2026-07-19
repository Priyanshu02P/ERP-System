from typing import List, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin, ActiveMixin
from app.db.models.enums import ProductType

if TYPE_CHECKING:
    from app.db.models.unit import Unit
    from app.db.models.inventory import Inventory


class Product(Base, IDMixin, TimestampMixin, ActiveMixin):
    """Product master (raw material, WIP, or finished good)."""

    __tablename__ = "products"

    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_type: Mapped[ProductType] = mapped_column(SAEnum(ProductType, name="product_type"), nullable=False)
    part_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    unit: Mapped["Unit"] = relationship(back_populates="products")

    inventories: Mapped[List["Inventory"]] = relationship(back_populates="product")

    def __repr__(self) -> str:
        return f"<Product id={self.id} code={self.code} type={self.product_type}>"
