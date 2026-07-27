"""
Seeds the database from the bundled `app/data/seed_data.json` fixture.

The fixture is a plain, human-editable JSON file describing units,
manufacturers, products, the warehouse/rack/shelf/bin/location hierarchy,
and inventory records. This keeps the "what data do we start with" concern
out of Python code entirely - to change the seed data, edit the JSON file.

Cross-references inside the JSON are by human-readable code (e.g. a rack
references its warehouse by `warehouse_code`, an inventory record
references its product by `product_code`) rather than by database id,
since ids aren't known until rows are inserted.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.unit import Unit
from app.db.models.manufacturer import Manufacturer
from app.db.models.product import Product
from app.db.models.warehouse import Warehouse
from app.db.models.rack import Rack
from app.db.models.shelf import Shelf
from app.db.models.bin import Bin
from app.db.models.location import Location
from app.db.models.inventory import Inventory
from app.db.models.enums import ProductType, InventoryStatus, LocationCategory
from app.core.transaction_logger import log_transaction, TransactionAction

SEED_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "seed_data.json"


def _load_seed_data() -> dict[str, Any]:
    with open(SEED_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_synthetic_data(db: Session, clean: bool = False) -> dict:
    if clean:
        # Delete existing data in reverse dependency order
        db.query(Inventory).delete()
        db.query(Location).delete()
        db.query(Bin).delete()
        db.query(Shelf).delete()
        db.query(Rack).delete()
        db.query(Warehouse).delete()
        db.query(Product).delete()
        db.query(Manufacturer).delete()
        db.query(Unit).delete()
        db.commit()

    # Check if we already have data
    if db.query(Product).first() is not None:
        return {"status": "skipped", "message": "Database already contains product records. Use clean=true to re-seed."}

    data = _load_seed_data()

    # ---------- 1. Units ----------
    units_by_code: dict[str, Unit] = {}
    for u in data.get("units", []):
        unit = Unit(code=u["code"], name=u["name"], description=u.get("description"), is_active=u.get("is_active", True))
        db.add(unit)
        units_by_code[u["code"]] = unit
    db.commit()
    for unit in units_by_code.values():
        db.refresh(unit)

    # ---------- 2. Manufacturers ----------
    manufacturers_by_code: dict[str, Manufacturer] = {}
    for m in data.get("manufacturers", []):
        mfg = Manufacturer(
            code=m["code"], name=m["name"], address=m.get("address"),
            contact_info=m.get("contact_info"), is_active=m.get("is_active", True),
        )
        db.add(mfg)
        manufacturers_by_code[m["code"]] = mfg
    db.commit()
    for mfg in manufacturers_by_code.values():
        db.refresh(mfg)

    # ---------- 3. Products ----------
    products_by_code: dict[str, Product] = {}
    for p in data.get("products", []):
        product = Product(
            code=p["code"],
            name=p["name"],
            description=p.get("description"),
            product_type=ProductType(p["product_type"]),
            part_number=p.get("part_number"),
            image_url=p.get("image_url"),
            unit_id=units_by_code[p["unit_code"]].id,
            is_active=p.get("is_active", True),
        )
        db.add(product)
        products_by_code[p["code"]] = product
    db.commit()
    for product in products_by_code.values():
        db.refresh(product)

    # ---------- 4. Warehouses ----------
    warehouses_by_code: dict[str, Warehouse] = {}
    for w in data.get("warehouses", []):
        warehouse = Warehouse(code=w["code"], name=w["name"], address=w.get("address"), is_active=w.get("is_active", True))
        db.add(warehouse)
        warehouses_by_code[w["code"]] = warehouse
    db.commit()
    for warehouse in warehouses_by_code.values():
        db.refresh(warehouse)

    # ---------- 5. Racks (keyed by warehouse_code + code, since rack codes repeat across warehouses) ----------
    racks_by_key: dict[tuple[str, str], Rack] = {}
    for r in data.get("racks", []):
        rack = Rack(
            code=r["code"],
            description=r.get("description"),
            warehouse_id=warehouses_by_code[r["warehouse_code"]].id,
        )
        db.add(rack)
        racks_by_key[(r["warehouse_code"], r["code"])] = rack
    db.commit()
    for rack in racks_by_key.values():
        db.refresh(rack)

    # ---------- 6. Shelves (keyed by warehouse_code + rack_code + code) ----------
    shelves_by_key: dict[tuple[str, str, str], Shelf] = {}
    for s in data.get("shelves", []):
        rack = racks_by_key[(s["warehouse_code"], s["rack_code"])]
        shelf = Shelf(code=s["code"], rack_id=rack.id)
        db.add(shelf)
        shelves_by_key[(s["warehouse_code"], s["rack_code"], s["code"])] = shelf
    db.commit()
    for shelf in shelves_by_key.values():
        db.refresh(shelf)

    # ---------- 7. Bins (keyed by warehouse_code + rack_code + shelf_code + code) ----------
    bins_by_key: dict[tuple[str, str, str, str], Bin] = {}
    for b in data.get("bins", []):
        shelf = shelves_by_key[(b["warehouse_code"], b["rack_code"], b["shelf_code"])]
        bin_ = Bin(code=b["code"], shelf_id=shelf.id)
        db.add(bin_)
        bins_by_key[(b["warehouse_code"], b["rack_code"], b["shelf_code"], b["code"])] = bin_
    db.commit()
    for bin_ in bins_by_key.values():
        db.refresh(bin_)

    # ---------- 8. Locations ----------
    # STANDARD locations use the full warehouse->rack->shelf->bin hierarchy.
    # SHEET / PIPE / SCRAP locations are rack-level-only zones.
    locations_by_code: dict[str, Location] = {}
    for loc in data.get("locations", []):
        warehouse = warehouses_by_code[loc["warehouse_code"]]
        rack = racks_by_key.get((loc["warehouse_code"], loc["rack_code"])) if loc.get("rack_code") else None
        shelf = (
            shelves_by_key.get((loc["warehouse_code"], loc["rack_code"], loc["shelf_code"]))
            if loc.get("shelf_code")
            else None
        )
        bin_ = (
            bins_by_key.get((loc["warehouse_code"], loc["rack_code"], loc["shelf_code"], loc["bin_code"]))
            if loc.get("bin_code")
            else None
        )
        location = Location(
            category=LocationCategory(loc["category"]),
            location_code=loc["location_code"],
            warehouse_id=warehouse.id,
            rack_id=rack.id if rack else None,
            shelf_id=shelf.id if shelf else None,
            bin_id=bin_.id if bin_ else None,
        )
        db.add(location)
        locations_by_code[loc["location_code"]] = location
    db.commit()
    for location in locations_by_code.values():
        db.refresh(location)

    # ---------- 9. Inventories ----------
    inventory_rows = []
    for inv in data.get("inventories", []):
        manufacturing_date = date.today() - timedelta(days=inv.get("manufacturing_date_offset_days", 0))
        row = Inventory(
            product_id=products_by_code[inv["product_code"]].id,
            manufacturer_id=manufacturers_by_code[inv["manufacturer_code"]].id,
            location_id=locations_by_code[inv["location_code"]].id,
            batch_number=inv["batch_number"],
            manufacturing_date=manufacturing_date,
            quantity=inv["quantity"],
            reserved_quantity=inv.get("reserved_quantity", 0.0),
            status=InventoryStatus(inv.get("status", "OK")),
        )
        db.add(row)
        inventory_rows.append(row)
    db.commit()
    for row in inventory_rows:
        db.refresh(row)

    counts = {
        "units": len(units_by_code),
        "manufacturers": len(manufacturers_by_code),
        "products": len(products_by_code),
        "warehouses": len(warehouses_by_code),
        "racks": len(racks_by_key),
        "shelves": len(shelves_by_key),
        "bins": len(bins_by_key),
        "locations": len(locations_by_code),
        "inventories": len(inventory_rows),
    }

    log_transaction(TransactionAction.SEED, "Database", None, counts)

    return {"status": "success", "message": "Database seeded from seed_data.json successfully.", "counts": counts}
