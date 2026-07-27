from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.inventory import Inventory
from app.db.models.enums import InventoryStatus
from app.db.repositories.base_repository import BaseRepository


class InventoryRepository(BaseRepository[Inventory]):
    def __init__(self, db: Session):
        super().__init__(Inventory, db)

    def get_by_product(self, product_id: int) -> List[Inventory]:
        return self.db.query(Inventory).filter(Inventory.product_id == product_id).all()

    def get_by_batch(self, batch_number: str) -> List[Inventory]:
        return self.db.query(Inventory).filter(Inventory.batch_number == batch_number).all()

    def get_by_status(self, status: InventoryStatus) -> List[Inventory]:
        return self.db.query(Inventory).filter(Inventory.status == status).all()

    def get_by_location(self, location_id: int) -> List[Inventory]:
        return self.db.query(Inventory).filter(Inventory.location_id == location_id).all()

    def get_by_manufacturer(self, manufacturer_id: int) -> List[Inventory]:
        return self.db.query(Inventory).filter(Inventory.manufacturer_id == manufacturer_id).all()

    def get_available_stock(self, product_id: int) -> float:
        """
        Sums (quantity - reserved) across only the OK-status rows for this
        product. Non-OK rows (HLD, DMG, RJC, MIS, RET) are excluded - stock
        on hold, damaged, rejected, missing, or returned is not available
        for reservation/issue even though it's still physically on hand
        (see get_total_stock for the raw physical total across all statuses).
        """
        rows = self.get_by_product(product_id)
        return sum(
            float(r.quantity) - float(r.reserved_quantity)
            for r in rows
            if r.status == InventoryStatus.OK
        )

    def get_total_stock(self, product_id: int) -> float:
        total = (
            self.db.query(func.coalesce(func.sum(Inventory.quantity), 0))
            .filter(Inventory.product_id == product_id)
            .scalar()
        )
        return float(total or 0)

    def update_quantity(self, inventory: Inventory, new_quantity: float) -> Inventory:
        inventory.quantity = new_quantity
        return self.update(inventory)

    def update_status(self, inventory: Inventory, status: InventoryStatus) -> Inventory:
        inventory.status = status
        return self.update(inventory)

    def reserve_stock(self, inventory: Inventory, amount: float) -> Inventory:
        inventory.reserved_quantity = float(inventory.reserved_quantity) + amount
        return self.update(inventory)

    def release_stock(self, inventory: Inventory, amount: float) -> Inventory:
        inventory.reserved_quantity = max(0.0, float(inventory.reserved_quantity) - amount)
        return self.update(inventory)

    def move_location(self, inventory: Inventory, new_location_id: int) -> Inventory:
        inventory.location_id = new_location_id
        return self.update(inventory)
