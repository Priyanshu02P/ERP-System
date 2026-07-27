from datetime import date
from typing import List

from sqlalchemy.orm import Session

from app.db.models.inventory import Inventory
from app.db.models.enums import InventoryStatus
from app.db.repositories.inventory_repository import InventoryRepository
from app.db.repositories.product_repository import ProductRepository
from app.db.repositories.manufacturer_repository import ManufacturerRepository
from app.db.repositories.location_repository import LocationRepository
from app.db.schemas.inventory import InventoryCreate, InventoryUpdate
from app.services.base_service import BaseService
from app.services.exceptions import ValidationError
from app.core.transaction_logger import log_transaction, TransactionAction


class InventoryService(BaseService[Inventory]):
    """
    Owns all stock-movement business rules: receiving, issuing, moving,
    reserving/releasing, adjusting quantity, and changing status/location.
    """

    def __init__(self, db: Session):
        self.repository: InventoryRepository = InventoryRepository(db)
        self.product_repository = ProductRepository(db)
        self.manufacturer_repository = ManufacturerRepository(db)
        self.location_repository = LocationRepository(db)
        super().__init__(self.repository, entity_name="Inventory")

    # ---------- validation ----------

    def validate_product(self, product_id: int) -> None:
        if not self.product_repository.exists(product_id):
            raise ValidationError(f"Product with id={product_id} does not exist")

    def validate_manufacturer(self, manufacturer_id: int) -> None:
        if not self.manufacturer_repository.exists(manufacturer_id):
            raise ValidationError(f"Manufacturer with id={manufacturer_id} does not exist")

    def validate_location(self, location_id: int) -> None:
        if not self.location_repository.exists(location_id):
            raise ValidationError(f"Location with id={location_id} does not exist")

    def validate_quantity(self, quantity: float) -> None:
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than 0")

    def validate_inventory(self, data: InventoryCreate) -> None:
        self.validate_product(data.product_id)
        self.validate_manufacturer(data.manufacturer_id)
        self.validate_location(data.location_id)
        self.validate_quantity(data.quantity)
        if data.manufacturing_date > date.today():
            raise ValidationError("Manufacturing date cannot be in the future")
        if not data.batch_number:
            raise ValidationError("Batch number is required")

    # ---------- location path helper ----------

    def get_location_display(self, inventory: Inventory) -> str:
        """Composite string combining product type/status with the location code, e.g. 'FG-WH1-A-03-05'."""
        prefix = (
            inventory.status.value
            if inventory.status != InventoryStatus.OK
            else inventory.product.product_type.value
        )
        return f"{prefix}-{inventory.location.location_code}"

    # ---------- CRUD ----------

    def create_inventory(self, data: InventoryCreate) -> Inventory:
        self.validate_inventory(data)
        inventory = Inventory(**data.model_dump())
        inventory = self.repository.create(inventory)
        log_transaction(
            TransactionAction.RECEIVE,
            "Inventory",
            inventory.id,
            {
                "product_id": inventory.product_id,
                "manufacturer_id": inventory.manufacturer_id,
                "location_id": inventory.location_id,
                "batch_number": inventory.batch_number,
                "quantity": float(inventory.quantity),
                "status": inventory.status.value,
            },
        )
        return inventory

    def update_inventory(self, inventory_id: int, data: InventoryUpdate) -> Inventory:
        inventory = self.get(inventory_id)
        payload = data.model_dump(exclude_unset=True)
        if "manufacturer_id" in payload:
            self.validate_manufacturer(payload["manufacturer_id"])
        if "location_id" in payload:
            self.validate_location(payload["location_id"])
        if "quantity" in payload:
            self.validate_quantity(payload["quantity"])
        for field, value in payload.items():
            setattr(inventory, field, value)
        return self.repository.update(inventory)

    def delete_inventory(self, inventory_id: int) -> None:
        inventory = self.get(inventory_id)
        details = {
            "product_id": inventory.product_id,
            "batch_number": inventory.batch_number,
            "quantity": float(inventory.quantity),
            "status": inventory.status.value,
        }
        self.repository.delete(inventory)
        log_transaction(TransactionAction.DELETE, "Inventory", inventory_id, details)

    # ---------- stock movement operations ----------

    def receive_stock(self, data: InventoryCreate) -> Inventory:
        """Receive new stock into the warehouse (creates a new inventory record)."""
        return self.create_inventory(data)

    def issue_stock(self, inventory_id: int, quantity: float) -> Inventory:
        """Issue (ship out / consume) stock, deducting from the on-hand quantity."""
        inventory = self.get(inventory_id)
        self.validate_quantity(quantity)
        if quantity > inventory.available_quantity:
            raise ValidationError("Cannot issue more than the available (unreserved) quantity")
        quantity_before = float(inventory.quantity)
        inventory.quantity = quantity_before - quantity
        inventory = self.repository.update(inventory)
        log_transaction(
            TransactionAction.ISSUE,
            "Inventory",
            inventory.id,
            {
                "product_id": inventory.product_id,
                "quantity_issued": quantity,
                "quantity_before": quantity_before,
                "quantity_after": float(inventory.quantity),
            },
        )
        return inventory

    def move_stock(self, inventory_id: int, new_location_id: int) -> Inventory:
        return self.change_location(inventory_id, new_location_id)

    def reserve_stock(self, inventory_id: int, quantity: float) -> Inventory:
        inventory = self.get(inventory_id)
        self.validate_quantity(quantity)
        if quantity > inventory.available_quantity:
            raise ValidationError("Cannot reserve more than the available quantity")
        inventory = self.repository.reserve_stock(inventory, quantity)
        log_transaction(
            TransactionAction.RESERVE,
            "Inventory",
            inventory.id,
            {"product_id": inventory.product_id, "quantity_reserved": quantity,
             "reserved_quantity_after": float(inventory.reserved_quantity)},
        )
        return inventory

    def release_stock(self, inventory_id: int, quantity: float) -> Inventory:
        inventory = self.get(inventory_id)
        self.validate_quantity(quantity)
        inventory = self.repository.release_stock(inventory, quantity)
        log_transaction(
            TransactionAction.RELEASE,
            "Inventory",
            inventory.id,
            {"product_id": inventory.product_id, "quantity_released": quantity,
             "reserved_quantity_after": float(inventory.reserved_quantity)},
        )
        return inventory

    def change_status(self, inventory_id: int, status: InventoryStatus) -> Inventory:
        inventory = self.get(inventory_id)
        status_before = inventory.status.value
        inventory = self.repository.update_status(inventory, status)
        log_transaction(
            TransactionAction.STATUS_CHANGE,
            "Inventory",
            inventory.id,
            {"product_id": inventory.product_id, "status_before": status_before,
             "status_after": inventory.status.value},
        )
        return inventory

    def change_location(self, inventory_id: int, new_location_id: int) -> Inventory:
        inventory = self.get(inventory_id)
        self.validate_location(new_location_id)
        location_before = inventory.location_id
        inventory = self.repository.move_location(inventory, new_location_id)
        log_transaction(
            TransactionAction.MOVE,
            "Inventory",
            inventory.id,
            {"product_id": inventory.product_id, "location_before": location_before,
             "location_after": inventory.location_id},
        )
        return inventory

    def adjust_quantity(self, inventory_id: int, quantity_delta: float) -> Inventory:
        """Positive delta adds stock (e.g. stock-take correction upward), negative deducts."""
        inventory = self.get(inventory_id)
        quantity_before = float(inventory.quantity)
        new_quantity = quantity_before + quantity_delta
        if new_quantity < 0:
            raise ValidationError("Adjustment would result in negative quantity")
        if new_quantity < float(inventory.reserved_quantity):
            raise ValidationError("Adjustment would leave quantity below the reserved amount")
        inventory = self.repository.update_quantity(inventory, new_quantity)
        log_transaction(
            TransactionAction.ADJUST,
            "Inventory",
            inventory.id,
            {"product_id": inventory.product_id, "quantity_delta": quantity_delta,
             "quantity_before": quantity_before, "quantity_after": float(inventory.quantity)},
        )
        return inventory

    # ---------- reads ----------

    def get_stock(self, inventory_id: int) -> Inventory:
        return self.get(inventory_id)

    def get_by_product(self, product_id: int) -> List[Inventory]:
        self.validate_product(product_id)
        return self.repository.get_by_product(product_id)

    def get_by_status(self, status: InventoryStatus) -> List[Inventory]:
        return self.repository.get_by_status(status)

    def get_by_location(self, location_id: int) -> List[Inventory]:
        self.validate_location(location_id)
        return self.repository.get_by_location(location_id)

    def get_by_manufacturer(self, manufacturer_id: int) -> List[Inventory]:
        self.validate_manufacturer(manufacturer_id)
        return self.repository.get_by_manufacturer(manufacturer_id)

    def get_available_stock(self, product_id: int) -> float:
        self.validate_product(product_id)
        return self.repository.get_available_stock(product_id)

    def get_total_stock(self, product_id: int) -> float:
        self.validate_product(product_id)
        return self.repository.get_total_stock(product_id)

    def get_batch_stock(self, batch_number: str) -> List[Inventory]:
        return self.repository.get_by_batch(batch_number)
