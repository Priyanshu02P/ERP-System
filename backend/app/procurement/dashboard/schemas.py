from typing import List, Optional

from pydantic import BaseModel


class ProcurementKPIs(BaseModel):
    """Snapshot counts for a procurement dashboard tile. Everything here is
    a live count re-derived on each request - nothing is cached or stored,
    so it's always consistent with the underlying records."""

    pending_prs: int
    pos_awaiting_grn: int
    grns_awaiting_qc: int
    overdue_deliveries: int
    overdue_purchase_order_ids: List[int]


class ReorderSuggestion(BaseModel):
    """One product whose available (OK-status, unreserved) stock has fallen
    to or below its reorder_level. Nothing here creates a
    PurchaseRequisition automatically - see ProcurementDashboardService's
    docstring for why this stays suggest-only."""

    product_id: int
    product_code: str
    product_name: str
    available_stock: float
    reorder_level: float
    reorder_quantity: Optional[float] = None
    preferred_supplier_id: Optional[int] = None
    preferred_supplier_name: Optional[str] = None
