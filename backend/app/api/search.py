from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.connection import get_db
from app.db.schemas.search import AvailabilityCheckRequest, AvailabilityCheckResponse, AvailabilityResultItem
from app.db.models.product import Product
from app.services.inventory_service import InventoryService
from app.services.seed_service import seed_synthetic_data

router = APIRouter(prefix="/search", tags=["Search & Utilities"])

@router.post("/check-availability", response_model=AvailabilityCheckResponse)
def check_availability(payload: AvailabilityCheckRequest, db: Session = Depends(get_db)):
    service = InventoryService(db)
    results = []
    all_available = True
    
    for item in payload.items:
        # Check if product exists
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            results.append(
                AvailabilityResultItem(
                    product_id=item.product_id,
                    product_code="N/A",
                    product_name="Unknown Product",
                    requested_quantity=item.quantity,
                    available_quantity=0.0,
                    is_available=False,
                    remarks="Product does not exist"
                )
            )
            all_available = False
            continue
            
        # Get available stock
        available_qty = service.get_available_stock(item.product_id)
        is_avail = available_qty >= item.quantity
        if not is_avail:
            all_available = False
            unit_code = product.unit.code if product.unit else ""
            remarks = f"Insufficient stock (short by {item.quantity - available_qty:.2f} {unit_code})"
        else:
            remarks = "Available"
            
        results.append(
            AvailabilityResultItem(
                product_id=item.product_id,
                product_code=product.code,
                product_name=product.name,
                requested_quantity=item.quantity,
                available_quantity=available_qty,
                is_available=is_avail,
                remarks=remarks
            )
        )
        
    return AvailabilityCheckResponse(results=results, all_available=all_available)

@router.post("/seed")
def seed_database(clean: bool = Query(False), db: Session = Depends(get_db)):
    return seed_synthetic_data(db, clean=clean)
