from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base
from app.db.models.mixins import IDMixin, TimestampMixin, ActiveMixin
from app.db.models.enums import SupplierCategory

if TYPE_CHECKING:
    from app.db.models.manufacturer import Manufacturer
    from app.db.models.product import Product


class Supplier(Base, IDMixin, TimestampMixin, ActiveMixin):
    """
    Vendor master: who Purchase Orders are issued to.

    Deliberately separate from Manufacturer. Manufacturer records who made a
    given batch of stock (used on Inventory); Supplier records who we
    actually buy from, which is often a distributor rather than the brand
    itself (e.g. supplier "Tata Steel Distributor" vs manufacturer
    "Tata Steel"). `manufacturer_id` optionally links the two when a
    supplier is known to represent a particular brand.
    """

    __tablename__ = "suppliers"

    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    category: Mapped[SupplierCategory] = mapped_column(
        SAEnum(SupplierCategory, name="supplier_category"), nullable=False
    )
    default_payment_terms: Mapped[str | None] = mapped_column(String(150), nullable=True)

    manufacturer_id: Mapped[int | None] = mapped_column(ForeignKey("manufacturers.id"), nullable=True)
    manufacturer: Mapped[Optional["Manufacturer"]] = relationship(back_populates="suppliers")

    preferred_for_products: Mapped[List["Product"]] = relationship(back_populates="preferred_supplier")

    def __repr__(self) -> str:
        return f"<Supplier id={self.id} code={self.code} name={self.name}>"
