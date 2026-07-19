from datetime import date, timedelta
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

    # 1. Seed Units
    pcs = Unit(code="PCS", name="Pieces", description="Individual items", is_active=True)
    kg = Unit(code="KG", name="Kilograms", description="Weight measurement", is_active=True)
    mtr = Unit(code="MTR", name="Meters", description="Length measurement", is_active=True)
    lit = Unit(code="LIT", name="Liters", description="Volume measurement", is_active=True)
    db.add_all([pcs, kg, mtr, lit])
    db.commit()

    # Refresh to get IDs
    db.refresh(pcs)
    db.refresh(kg)
    db.refresh(mtr)
    db.refresh(lit)

    # 2. Seed Manufacturers
    mfg1 = Manufacturer(code="MFG-001", name="Apex Industries", address="123 Industrial Parkway", contact_info="sales@apex.com", is_active=True)
    mfg2 = Manufacturer(code="MFG-002", name="Global Tech Parts", address="456 Tech Blvd", contact_info="support@globaltech.com", is_active=True)
    mfg3 = Manufacturer(code="MFG-003", name="Eco Materials Corp", address="789 Green Rd", contact_info="info@ecomaterials.com", is_active=True)
    db.add_all([mfg1, mfg2, mfg3])
    db.commit()

    db.refresh(mfg1)
    db.refresh(mfg2)
    db.refresh(mfg3)

    # 3. Seed Products
    # RAW
    p1 = Product(code="PROD-001", name="Steel Rod 10mm", description="High-tensile structural steel rod", product_type=ProductType.RAW, part_number="SR-10", unit_id=mtr.id, is_active=True)
    p2 = Product(code="PROD-002", name="Copper Wire 2mm", description="Conductive copper wiring", product_type=ProductType.RAW, part_number="CW-02", unit_id=mtr.id, is_active=True)
    p7 = Product(code="PROD-007", name="Hydraulic Fluid", description="Premium ISO 46 hydraulic oil", product_type=ProductType.RAW, part_number="HF-46", unit_id=lit.id, is_active=True)
    # WIP
    p3 = Product(code="PROD-003", name="Sub-assembly Alpha", description="Pre-wired mechanical sub-assembly", product_type=ProductType.WIP, part_number="SA-ALPHA", unit_id=pcs.id, is_active=True)
    p4 = Product(code="PROD-004", name="Control Board v2", description="Microcontroller logic board", product_type=ProductType.WIP, part_number="CB-V2", unit_id=pcs.id, is_active=True)
    # FG
    p5 = Product(code="PROD-005", name="Industrial Widget", description="Complete heavy duty widget assembly", product_type=ProductType.FG, part_number="IW-5000", unit_id=pcs.id, is_active=True)
    p6 = Product(code="PROD-006", name="Heavy Duty Gearbox", description="10:1 ratio industrial gearbox", product_type=ProductType.FG, part_number="GB-HD-10", unit_id=pcs.id, is_active=True)

    db.add_all([p1, p2, p3, p4, p5, p6, p7])
    db.commit()

    db.refresh(p1)
    db.refresh(p2)
    db.refresh(p3)
    db.refresh(p4)
    db.refresh(p5)
    db.refresh(p6)
    db.refresh(p7)

    # 4. Seed Warehouses
    wh1 = Warehouse(code="WH1", name="Main Warehouse", address="100 Logistics Way", is_active=True)
    wh2 = Warehouse(code="WH2", name="Overflow Warehouse", address="200 Warehouse Row", is_active=True)
    db.add_all([wh1, wh2])
    db.commit()

    db.refresh(wh1)
    db.refresh(wh2)

    # 5. Seed Racks
    rack_a = Rack(code="A", description="Rack A (Main Aisle)", warehouse_id=wh1.id)
    rack_b = Rack(code="B", description="Rack B (Secondary Aisle)", warehouse_id=wh1.id)
    rack_c = Rack(code="C", description="Rack C (Overflow Area)", warehouse_id=wh2.id)
    db.add_all([rack_a, rack_b, rack_c])
    db.commit()

    db.refresh(rack_a)
    db.refresh(rack_b)
    db.refresh(rack_c)

    # 6. Seed Shelves
    shelf_a01 = Shelf(code="01", rack_id=rack_a.id)
    shelf_a02 = Shelf(code="02", rack_id=rack_a.id)
    shelf_b01 = Shelf(code="01", rack_id=rack_b.id)
    shelf_c01 = Shelf(code="01", rack_id=rack_c.id)
    db.add_all([shelf_a01, shelf_a02, shelf_b01, shelf_c01])
    db.commit()

    db.refresh(shelf_a01)
    db.refresh(shelf_a02)
    db.refresh(shelf_b01)
    db.refresh(shelf_c01)

    # 7. Seed Bins
    bin_a0101 = Bin(code="01", shelf_id=shelf_a01.id)
    bin_a0102 = Bin(code="02", shelf_id=shelf_a01.id)
    bin_a0201 = Bin(code="01", shelf_id=shelf_a02.id)
    bin_b0101 = Bin(code="01", shelf_id=shelf_b01.id)
    bin_c0101 = Bin(code="01", shelf_id=shelf_c01.id)
    db.add_all([bin_a0101, bin_a0102, bin_a0201, bin_b0101, bin_c0101])
    db.commit()

    db.refresh(bin_a0101)
    db.refresh(bin_a0102)
    db.refresh(bin_a0201)
    db.refresh(bin_b0101)
    db.refresh(bin_c0101)

    # 8. Seed Locations
    # Standard locations
    loc1 = Location(category=LocationCategory.STANDARD, location_code="WH1-A-01-01", warehouse_id=wh1.id, rack_id=rack_a.id, shelf_id=shelf_a01.id, bin_id=bin_a0101.id)
    loc2 = Location(category=LocationCategory.STANDARD, location_code="WH1-A-01-02", warehouse_id=wh1.id, rack_id=rack_a.id, shelf_id=shelf_a01.id, bin_id=bin_a0102.id)
    loc3 = Location(category=LocationCategory.STANDARD, location_code="WH1-A-02-01", warehouse_id=wh1.id, rack_id=rack_a.id, shelf_id=shelf_a02.id, bin_id=bin_a0201.id)
    loc4 = Location(category=LocationCategory.STANDARD, location_code="WH1-B-01-01", warehouse_id=wh1.id, rack_id=rack_b.id, shelf_id=shelf_b01.id, bin_id=bin_b0101.id)
    loc5 = Location(category=LocationCategory.STANDARD, location_code="WH2-C-01-01", warehouse_id=wh2.id, rack_id=rack_c.id, shelf_id=shelf_c01.id, bin_id=bin_c0101.id)

    # Special category locations (warehouse + rack level only)
    loc_sheet = Location(category=LocationCategory.SHEET, location_code="SHEET-A", warehouse_id=wh1.id, rack_id=rack_a.id)
    loc_pipe = Location(category=LocationCategory.PIPE, location_code="PIPE-B", warehouse_id=wh1.id, rack_id=rack_b.id)

    db.add_all([loc1, loc2, loc3, loc4, loc5, loc_sheet, loc_pipe])
    db.commit()

    db.refresh(loc1)
    db.refresh(loc2)
    db.refresh(loc3)
    db.refresh(loc4)
    db.refresh(loc5)
    db.refresh(loc_sheet)
    db.refresh(loc_pipe)

    # 9. Seed Inventories
    # Steel Rod: 120 units in PIPE-B, 15 reserved, status OK (available: 105)
    inv1 = Inventory(product_id=p1.id, manufacturer_id=mfg3.id, location_id=loc_pipe.id, batch_number="B-ST-099", manufacturing_date=date.today() - timedelta(days=30), quantity=120.0, reserved_quantity=15.0, status=InventoryStatus.OK)
    
    # Copper Wire: 50 units in WH1-A-01-01, 0 reserved, status OK (available: 50)
    inv2 = Inventory(product_id=p2.id, manufacturer_id=mfg2.id, location_id=loc1.id, batch_number="B-CW-204", manufacturing_date=date.today() - timedelta(days=15), quantity=50.0, reserved_quantity=0.0, status=InventoryStatus.OK)
    
    # Sub-assembly Alpha: 10 units in WH1-A-01-02, 2 reserved, status OK (available: 8)
    inv3 = Inventory(product_id=p3.id, manufacturer_id=mfg1.id, location_id=loc2.id, batch_number="B-SA-501", manufacturing_date=date.today() - timedelta(days=10), quantity=10.0, reserved_quantity=2.0, status=InventoryStatus.OK)
    
    # Control Board v2: 15 units in WH1-A-02-01, 5 reserved, status HLD (On Hold) -> available quantity is 10, total qty is 15.
    inv4 = Inventory(product_id=p4.id, manufacturer_id=mfg1.id, location_id=loc3.id, batch_number="B-CB-302", manufacturing_date=date.today() - timedelta(days=5), quantity=15.0, reserved_quantity=5.0, status=InventoryStatus.HLD)
    
    # Industrial Widget: 25 units in WH1-A-02-01, 5 reserved, status OK (available: 20)
    inv5 = Inventory(product_id=p5.id, manufacturer_id=mfg1.id, location_id=loc3.id, batch_number="B-IW-801", manufacturing_date=date.today() - timedelta(days=20), quantity=25.0, reserved_quantity=5.0, status=InventoryStatus.OK)
    
    # Industrial Widget: 5 units in WH2-C-01-01, 0 reserved, status OK (available: 5). Total Industrial Widget: 20 + 5 = 25.
    inv6 = Inventory(product_id=p5.id, manufacturer_id=mfg1.id, location_id=loc5.id, batch_number="B-IW-802", manufacturing_date=date.today() - timedelta(days=21), quantity=5.0, reserved_quantity=0.0, status=InventoryStatus.OK)

    # Heavy Duty Gearbox: 2 units in WH1-B-01-01, 2 reserved, status OK (available: 0)
    inv7 = Inventory(product_id=p6.id, manufacturer_id=mfg2.id, location_id=loc4.id, batch_number="B-GB-700", manufacturing_date=date.today() - timedelta(days=45), quantity=2.0, reserved_quantity=2.0, status=InventoryStatus.OK)

    # Hydraulic Fluid: 80 units in SHEET-A, manufactured by MFG-003, batch B-HF-01, qty 80, reserved 0, status OK (available: 80)
    inv8 = Inventory(product_id=p7.id, manufacturer_id=mfg3.id, location_id=loc_sheet.id, batch_number="B-HF-01", manufacturing_date=date.today() - timedelta(days=60), quantity=80.0, reserved_quantity=0.0, status=InventoryStatus.OK)

    db.add_all([inv1, inv2, inv3, inv4, inv5, inv6, inv7, inv8])
    db.commit()

    return {"status": "success", "message": "Database seeded with synthetic data successfully."}
