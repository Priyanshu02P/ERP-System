from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.product import Product
from app.db.models.enums import ProductType
from app.db.repositories.base_repository import BaseRepository


class ProductRepository(BaseRepository[Product]):
    def __init__(self, db: Session):
        super().__init__(Product, db)

    def get_by_code(self, code: str) -> Optional[Product]:
        return self.db.query(Product).filter(Product.code == code).first()

    def search_by_name(self, term: str) -> List[Product]:
        return self.db.query(Product).filter(Product.name.ilike(f"%{term}%")).all()

    def get_active_products(self) -> List[Product]:
        return self.db.query(Product).filter(Product.is_active.is_(True)).all()

    def get_by_type(self, product_type: ProductType) -> List[Product]:
        return self.db.query(Product).filter(Product.product_type == product_type).all()

    def get_by_part_number(self, part_number: str) -> List[Product]:
        return self.db.query(Product).filter(Product.part_number == part_number).all()

    def exists_product_code(self, code: str, exclude_id: Optional[int] = None) -> bool:
        query = self.db.query(Product.id).filter(Product.code == code)
        if exclude_id is not None:
            query = query.filter(Product.id != exclude_id)
        return query.first() is not None

    def activate(self, product: Product) -> Product:
        product.is_active = True
        return self.update(product)

    def deactivate(self, product: Product) -> Product:
        product.is_active = False
        return self.update(product)
