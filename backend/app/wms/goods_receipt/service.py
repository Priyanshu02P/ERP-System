from datetime import date
from typing import List

from sqlalchemy.orm import Session

from app.wms.goods_receipt.models import GoodsReceipt, GoodsReceiptItem
from app.shared.enums import GRNStatus, POStatus, POLineStatus
from app.shared.mixins import utcnow
from app.wms.goods_receipt.repository import GoodsReceiptRepository
from app.procurement.purchase_order.repository import PurchaseOrderRepository
from app.wms.goods_receipt.schemas import GoodsReceiptCreate
from app.shared.base_service import BaseService
from app.shared.exceptions import ConflictError, ValidationError
from app.shared.transaction_logger import log_transaction, TransactionAction


class GoodsReceiptService(BaseService[GoodsReceipt]):
    """
    Records goods physically arriving against a PurchaseOrder. This is
    deliberately the "physically received" step, independent of QC - see
    Procurement_Implementation_Plan.md §4. A GRN starts PENDING_QC and stays
    that way until a QualityInspection is recorded against it
    (GoodsReceiptService itself never touches Inventory).

    PurchaseOrderItem.received_quantity/line_status and PurchaseOrder.status
    (-> PARTIALLY_RECEIVED/RECEIVED) are updated here, immediately, since
    "goods arrived" is true regardless of what QC later decides about them.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository: GoodsReceiptRepository = GoodsReceiptRepository(db)
        self.po_repository = PurchaseOrderRepository(db)
        super().__init__(self.repository, entity_name="GoodsReceipt")

    # ------------------------------------------------------------------ #
    # Numbering
    # ------------------------------------------------------------------ #

    def _generate_grn_number(self) -> str:
        year = date.today().year
        count = self.repository.count_for_year(year)
        return f"GRN-{year}-{count + 1:05d}"

    # ------------------------------------------------------------------ #
    # Creation
    # ------------------------------------------------------------------ #

    def create_grn(self, data: GoodsReceiptCreate) -> GoodsReceipt:
        po = self.po_repository.get(data.po_id)
        if po is None:
            raise ValidationError(f"PurchaseOrder with id={data.po_id} does not exist")
        if po.status not in (POStatus.CONFIRMED, POStatus.PARTIALLY_RECEIVED):
            raise ConflictError(
                f"Cannot record a goods receipt against a PO in status {po.status.value}; "
                "it must be CONFIRMED (or already PARTIALLY_RECEIVED, for a further delivery "
                "against the same PO)"
            )

        po_items_by_id = {item.id: item for item in po.items}
        grn_items: List[GoodsReceiptItem] = []
        for line in data.items:
            po_item = po_items_by_id.get(line.po_item_id)
            if po_item is None:
                raise ValidationError(
                    f"PurchaseOrderItem id={line.po_item_id} does not belong to PO id={po.id}"
                )
            remaining_expected = float(po_item.quantity) - float(po_item.received_quantity)
            grn_items.append(
                GoodsReceiptItem(
                    po_item_id=po_item.id,
                    received_quantity=line.received_quantity,
                    variance_quantity=round(float(line.received_quantity) - remaining_expected, 3),
                    vendor_batch_number=line.vendor_batch_number,
                    manufacturing_date=line.manufacturing_date,
                    remarks=line.remarks,
                )
            )
            # Physically received, independent of QC outcome - see class docstring.
            po_item.received_quantity = float(po_item.received_quantity) + float(line.received_quantity)
            if po_item.received_quantity <= 0:
                po_item.line_status = POLineStatus.PENDING
            elif po_item.received_quantity >= float(po_item.quantity):
                po_item.line_status = POLineStatus.COMPLETE
            else:
                po_item.line_status = POLineStatus.PARTIAL

        grn = GoodsReceipt(
            grn_number=self._generate_grn_number(),
            po_id=po.id,
            vendor_invoice_ref=data.vendor_invoice_ref,
            vehicle_number=data.vehicle_number,
            received_by=data.received_by,
            received_at=utcnow(),
            status=GRNStatus.PENDING_QC,
            overall_condition=data.overall_condition,
        )
        grn.items = grn_items
        created = self.repository.create(grn)

        # Roll the PO's own status up from its lines' receiving progress.
        po.status = (
            POStatus.RECEIVED
            if all(item.line_status == POLineStatus.COMPLETE for item in po.items)
            else POStatus.PARTIALLY_RECEIVED
        )
        self.po_repository.update(po)

        log_transaction(
            TransactionAction.GRN_CREATE, "GoodsReceipt", created.id,
            {
                "grn_number": created.grn_number, "po_id": po.id, "po_number": po.po_number,
                "item_count": len(created.items), "po_status": po.status.value,
            },
        )
        return created

    # ------------------------------------------------------------------ #
    # Close (after QC has been recorded)
    # ------------------------------------------------------------------ #

    def close_grn(self, grn_id: int) -> GoodsReceipt:
        grn = self.get(grn_id)
        if grn.status != GRNStatus.QC_IN_PROGRESS:
            raise ConflictError(
                f"Cannot close a GRN in status {grn.status.value}; a quality inspection must be "
                "recorded first (POST /quality-inspections)"
            )
        grn.status = GRNStatus.CLOSED
        updated = self.repository.update(grn)
        log_transaction(TransactionAction.GRN_CLOSE, "GoodsReceipt", grn.id, {"grn_number": grn.grn_number})
        return updated

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_by_status(self, status: GRNStatus) -> List[GoodsReceipt]:
        return self.repository.get_by_status(status)

    def get_by_po(self, po_id: int) -> List[GoodsReceipt]:
        return self.repository.get_by_po(po_id)
