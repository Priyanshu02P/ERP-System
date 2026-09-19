from datetime import date
from typing import List

from sqlalchemy.orm import Session

from app.shared.enums import PRStatus, POStatus, GRNStatus
from app.procurement.requisition.repository import PurchaseRequisitionRepository
from app.procurement.purchase_order.repository import PurchaseOrderRepository
from app.wms.goods_receipt.repository import GoodsReceiptRepository
from app.master_data.product.repository import ProductRepository
from app.wms.inventory.repository import InventoryRepository
from app.procurement.dashboard.schemas import ProcurementKPIs, ReorderSuggestion

# A PO in either of these states has been dispatched to (and acknowledged
# by) the vendor but isn't fully received yet - see POStatus's docstring.
# CLOSED is deliberately excluded even though it's not built yet (see
# BUSINESS_DECISIONS.md), since a closed PO is done, not "awaiting" anything.
_PO_OPEN_STATUSES = (POStatus.CONFIRMED, POStatus.PARTIALLY_RECEIVED)


class ProcurementDashboardService:
    """
    Read-only aggregation across the procurement chain for §3's dashboard
    endpoints (GET /procurement/kpis, GET /procurement/reorder-suggestions).
    Deliberately NOT a BaseService[...] subclass - there's no single entity
    this service owns, and every method here is a query, never a state
    change, so (unlike every other service in this codebase) nothing here
    calls log_transaction: the transaction log records business EVENTS,
    and looking at a dashboard isn't one - see transaction_logger's
    "every write endpoint logs" convention in HIGH_LEVEL_ARCHITECTURE.md §4.2.

    Every number here is computed live from the current rows each time it's
    called - nothing is cached, materialized, or stored, so there's no
    staleness/invalidation problem to manage. This is a deliberate
    simplification: fine at this system's scale, and the first thing to
    revisit (e.g. a materialized view or a scheduled snapshot table) if the
    dashboard is ever called often enough for the live joins to matter.
    """

    def __init__(self, db: Session):
        self.db = db
        self.pr_repository = PurchaseRequisitionRepository(db)
        self.po_repository = PurchaseOrderRepository(db)
        self.grn_repository = GoodsReceiptRepository(db)
        self.product_repository = ProductRepository(db)
        self.inventory_repository = InventoryRepository(db)

    # ------------------------------------------------------------------ #
    # KPIs
    # ------------------------------------------------------------------ #

    def _overdue_purchase_orders(self) -> List:
        """POs that are dispatched/confirmed, still not fully received, and
        past their own expected_delivery_date. A PO with no
        expected_delivery_date set is never counted as overdue - there's
        nothing to be overdue against."""
        today = date.today()
        overdue = []
        for status in _PO_OPEN_STATUSES:
            for po in self.po_repository.get_by_status(status):
                if po.expected_delivery_date is not None and po.expected_delivery_date < today:
                    overdue.append(po)
        return overdue

    def get_kpis(self) -> ProcurementKPIs:
        pending_prs = len(self.pr_repository.get_by_status(PRStatus.PENDING_APPROVAL))
        pos_awaiting_grn = sum(len(self.po_repository.get_by_status(s)) for s in _PO_OPEN_STATUSES)
        grns_awaiting_qc = len(self.grn_repository.get_by_status(GRNStatus.PENDING_QC))
        overdue = self._overdue_purchase_orders()

        return ProcurementKPIs(
            pending_prs=pending_prs,
            pos_awaiting_grn=pos_awaiting_grn,
            grns_awaiting_qc=grns_awaiting_qc,
            overdue_deliveries=len(overdue),
            overdue_purchase_order_ids=[po.id for po in overdue],
        )

    # ------------------------------------------------------------------ #
    # Reorder suggestions
    # ------------------------------------------------------------------ #

    def get_reorder_suggestions(self) -> List[ReorderSuggestion]:
        """
        Every active product whose available (OK-status, unreserved) stock
        has fallen to or below its own reorder_level. Products with no
        reorder_level set are skipped entirely - "no threshold configured"
        is not the same thing as "always needs reordering". This mirrors
        Product.reorder_level's own docstring: whether a product is
        *currently* below threshold is computed here against live
        Inventory, never stored on Product itself.

        This is intentionally suggest-only: it never creates a
        PurchaseRequisition. The (future) n8n reorder-digest workflow reads
        this endpoint and lets a human turn a suggestion into a PR via
        POST /purchase-requisitions with source=AUTO_REORDER - see
        BUSINESS_DECISIONS.md §1 on why nothing in this codebase
        auto-creates a procurement document without a human action.
        """
        available_by_product = self.inventory_repository.get_available_stock_map()

        suggestions = []
        for product in self.product_repository.get_all():
            if not product.is_active or product.reorder_level is None:
                continue
            available = available_by_product.get(product.id, 0.0)
            if available > float(product.reorder_level):
                continue
            suggestions.append(
                ReorderSuggestion(
                    product_id=product.id,
                    product_code=product.code,
                    product_name=product.name,
                    available_stock=available,
                    reorder_level=float(product.reorder_level),
                    reorder_quantity=(
                        float(product.reorder_quantity) if product.reorder_quantity is not None else None
                    ),
                    preferred_supplier_id=product.preferred_supplier_id,
                    preferred_supplier_name=(
                        product.preferred_supplier.name if product.preferred_supplier else None
                    ),
                )
            )
        return suggestions
