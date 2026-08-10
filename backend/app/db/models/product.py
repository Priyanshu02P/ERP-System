from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Numeric, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin, ActiveMixin
from app.db.models.enums import ProductType

if TYPE_CHECKING:
    from app.db.models.unit import Unit
    from app.db.models.inventory import Inventory
    from app.db.models.supplier import Supplier


class Product(Base, IDMixin, TimestampMixin, ActiveMixin):
    """Product master (raw material, WIP, or finished good)."""

    __tablename__ = "products"

    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_type: Mapped[ProductType] = mapped_column(SAEnum(ProductType, name="product_type"), nullable=False)
    part_number: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    image_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Procurement: reorder_level/reorder_quantity are plain thresholds set here.
    # Whether a product is *currently* below reorder level is computed by the
    # procurement module against live Inventory.available_quantity - it isn't
    # stored on Product, since that would need to stay in sync with every
    # stock movement.
    reorder_level: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    reorder_quantity: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)

    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), nullable=False)
    unit: Mapped["Unit"] = relationship(back_populates="products")

    preferred_supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    preferred_supplier: Mapped[Optional["Supplier"]] = relationship(back_populates="preferred_for_products")

    inventories: Mapped[List["Inventory"]] = relationship(back_populates="product")

    def __repr__(self) -> str:
        return f"<Product id={self.id} code={self.code} type={self.product_type}>"
