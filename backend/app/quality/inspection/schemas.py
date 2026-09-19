from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.shared.enums import QCDisposition, QCItemDisposition
from app.shared.schemas_common import ORMBase


class QualityInspectionItemCreate(BaseModel):
    grn_item_id: int
    parameter_results: Optional[List[dict[str, Any]]] = None
    disposition: QCItemDisposition

    # Required (and validated) by the service for ACCEPT/DEVIATION;
    # ignored for REJECT.
    accepted_quantity: Optional[float] = Field(None, ge=0)
    rejected_quantity: Optional[float] = Field(None, ge=0)
    putaway_location_id: Optional[int] = None
    manufacturer_id: Optional[int] = None


class QualityInspectionItemRead(ORMBase):
    id: int
    grn_item_id: int
    parameter_results: Optional[List[dict[str, Any]]] = None
    disposition: QCItemDisposition
    accepted_quantity: float
    rejected_quantity: float
    putaway_location_id: Optional[int] = None
    manufacturer_id: Optional[int] = None
    inventory_id: Optional[int] = None


class QualityInspectionCreate(BaseModel):
    grn_id: int
    inspector: str = Field(..., min_length=1, max_length=100)
    # If a deviation is already approved at the moment of recording (e.g.
    # the inspector's supervisor signs off on the spot), pass it here and
    # Inventory is created for DEVIATION items immediately. Otherwise leave
    # it unset and approve later via POST /quality-inspections/{id}/approve-deviation.
    deviation_approved_by: Optional[str] = Field(None, max_length=100)
    items: List[QualityInspectionItemCreate] = Field(..., min_length=1)


class QualityInspectionApproveDeviation(BaseModel):
    approved_by: str = Field(..., min_length=1, max_length=100)


class QualityInspectionRead(ORMBase):
    id: int
    qc_number: str
    grn_id: int
    inspector: str
    inspected_at: datetime
    overall_disposition: QCDisposition
    deviation_approved_by: Optional[str] = None
    deviation_approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: List[QualityInspectionItemRead] = []
