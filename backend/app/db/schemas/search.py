from pydantic import BaseModel, Field
from typing import List

class ProductQuantityItem(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0, description="Quantity requested")

class AvailabilityCheckRequest(BaseModel):
    items: List[ProductQuantityItem]

class AvailabilityResultItem(BaseModel):
    product_id: int
    product_code: str
    product_name: str
    requested_quantity: float
    available_quantity: float
    is_available: bool
    remarks: str

class AvailabilityCheckResponse(BaseModel):
    results: List[AvailabilityResultItem]
    all_available: bool
