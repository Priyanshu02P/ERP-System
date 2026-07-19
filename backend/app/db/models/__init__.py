"""
Import every model here so that:
  1. `Base.metadata` is aware of all tables (needed for Alembic autogenerate
     and for `Base.metadata.create_all()`), and
  2. string-based relationship references (e.g. "Product") resolve correctly.
"""

from app.db.models.unit import Unit
from app.db.models.manufacturer import Manufacturer
from app.db.models.product import Product
from app.db.models.warehouse import Warehouse
from app.db.models.rack import Rack
from app.db.models.shelf import Shelf
from app.db.models.bin import Bin
from app.db.models.location import Location
from app.db.models.inventory import Inventory

__all__ = [
    "Unit",
    "Manufacturer",
    "Product",
    "Warehouse",
    "Rack",
    "Shelf",
    "Bin",
    "Location",
    "Inventory",
]
