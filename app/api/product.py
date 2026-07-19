from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.db.models.enums import ProductType
from app.db.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("", response_model=ProductRead, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    return ProductService(db).create_product(payload)


@router.get("", response_model=List[ProductRead])
def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = None,
    product_type: ProductType | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    service = ProductService(db)
    if search:
        return service.search_products(search)
    if product_type:
        return service.repository.get_by_type(product_type)
    if active_only:
        return service.repository.get_active_products()
    return service.get_page(skip=skip, limit=limit)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: int, db: Session = Depends(get_db)):
    return ProductService(db).get(product_id)


@router.put("/{product_id}", response_model=ProductRead)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)):
    return ProductService(db).update_product(product_id, payload)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    ProductService(db).delete_product(product_id)


@router.post("/{product_id}/activate", response_model=ProductRead)
def activate_product(product_id: int, db: Session = Depends(get_db)):
    return ProductService(db).activate_product(product_id)


@router.post("/{product_id}/deactivate", response_model=ProductRead)
def deactivate_product(product_id: int, db: Session = Depends(get_db)):
    return ProductService(db).deactivate_product(product_id)


@router.post("/{product_id}/change-unit/{unit_id}", response_model=ProductRead)
def change_unit(product_id: int, unit_id: int, db: Session = Depends(get_db)):
    return ProductService(db).change_unit(product_id, unit_id)
