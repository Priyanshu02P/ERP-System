from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.db.models.enums import POStatus, QuotationStatus
from app.db.models.mixins import utcnow
from app.db.repositories.purchase_order_repository import PurchaseOrderRepository
from app.db.repositories.product_repository import ProductRepository
from app.db.repositories.supplier_repository import SupplierRepository
from app.db.repositories.purchase_requisition_repository import PurchaseRequisitionRepository
from app.db.repositories.vendor_quotation_repository import VendorQuotationRepository
from app.db.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderItemCreate
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, ValidationError, NotFoundError
from app.core.transaction_logger import log_transaction, TransactionAction


class PurchaseOrderService(BaseService[PurchaseOrder]):
    def __init__(self, db: Session):
        self.db = db
        self.repository: PurchaseOrderRepository = PurchaseOrderRepository(db)
        self.product_repository = ProductRepository(db)
        self.supplier_repository = SupplierRepository(db)
        self.pr_repository = PurchaseRequisitionRepository(db)
        self.quotation_repository = VendorQuotationRepository(db)
        super().__init__(self.repository, entity_name="PurchaseOrder")

    # ------------------------------------------------------------------ #
    # Validation helpers
    # ------------------------------------------------------------------ #

    def validate_product(self, product_id: int) -> None:
        if not self.product_repository.exists(product_id):
            raise ValidationError(f"Product with id={product_id} does not exist")

    def validate_supplier(self, supplier_id: int) -> None:
        if not self.supplier_repository.exists(supplier_id):
            raise ValidationError(f"Supplier with id={supplier_id} does not exist")

    def validate_pr(self, pr_id: int) -> None:
        if not self.pr_repository.exists(pr_id):
            raise ValidationError(f"PurchaseRequisition with id={pr_id} does not exist")

    def _generate_po_number(self) -> str:
        year = date.today().year
        count = self.repository.count_for_year(year)
        return f"PO-{year}-{count + 1:05d}"

    @staticmethod
    def _resolve_amount(quantity: float, rate: float, amount: Optional[float]) -> float:
        return amount if amount is not None else round(float(quantity) * float(rate), 2)

    @staticmethod
    def _totals(items: List[PurchaseOrderItem]) -> tuple[float, float, float]:
        subtotal = round(sum(float(i.amount) for i in items), 2)
        gst_amount = round(
            sum(float(i.amount) * float(i.gst_rate) / 100 for i in items if i.gst_rate is not None), 2
        )
        return subtotal, gst_amount, round(subtotal + gst_amount, 2)

    def _build_manual_item(self, item: PurchaseOrderItemCreate) -> PurchaseOrderItem:
        self.validate_product(item.product_id)
        return PurchaseOrderItem(
            product_id=item.product_id,
            quantity=item.quantity,
            rate=item.rate,
            gst_rate=item.gst_rate,
            amount=self._resolve_amount(item.quantity, item.rate, item.amount),
        )

    # ------------------------------------------------------------------ #
    # Creation - from a SELECTED quotation, or manual/routine
    # ------------------------------------------------------------------ #

    def create_po(self, data: PurchaseOrderCreate) -> PurchaseOrder:
        if data.quotation_id is not None:
            return self._create_from_quotation(data)
        return self._create_manual(data)

    def _create_from_quotation(self, data: PurchaseOrderCreate) -> PurchaseOrder:
        quotation = self.quotation_repository.get(data.quotation_id)
        if quotation is None:
            raise ValidationError(f"VendorQuotation with id={data.quotation_id} does not exist")
        if quotation.status != QuotationStatus.SELECTED:
            raise ConflictError(
                f"Cannot create a PO from a quotation in status {quotation.status.value}; "
                "it must be SELECTED first (POST /quotations/{id}/select)"
            )
        if self.repository.get_by_quotation(quotation.id) is not None:
            raise ConflictError(f"A Purchase Order has already been created from quotation id={quotation.id}")

        pr_id = data.pr_id
        if pr_id is None and quotation.rfq is not None:
            pr_id = quotation.rfq.pr_id
        if pr_id is not None:
            self.validate_pr(pr_id)

        payment_terms = data.payment_terms if data.payment_terms is not None else quotation.payment_terms

        po = PurchaseOrder(
            po_number=self._generate_po_number(),
            quotation_id=quotation.id,
            pr_id=pr_id,
            supplier_id=quotation.supplier_id,
            status=POStatus.DRAFT,
            order_date=data.order_date,
            expected_delivery_date=data.expected_delivery_date,
            payment_terms=payment_terms,
        )
        po.items = [
            PurchaseOrderItem(
                product_id=qi.product_id,
                quantity=qi.quantity,
                rate=qi.rate,
                gst_rate=qi.gst_rate,
                amount=qi.amount,
            )
            for qi in quotation.items
        ]
        po.subtotal, po.gst_amount, po.total_amount = self._totals(po.items)
        created = self.repository.create(po)
        log_transaction(
            TransactionAction.PO_CREATE, "PurchaseOrder", created.id,
            {
                "po_number": created.po_number, "quotation_id": quotation.id,
                "supplier_id": created.supplier_id, "item_count": len(created.items),
                "total_amount": float(created.total_amount),
            },
        )
        return created

    def _create_manual(self, data: PurchaseOrderCreate) -> PurchaseOrder:
        self.validate_supplier(data.supplier_id)
        if data.pr_id is not None:
            self.validate_pr(data.pr_id)

        po = PurchaseOrder(
            po_number=self._generate_po_number(),
            quotation_id=None,
            pr_id=data.pr_id,
            supplier_id=data.supplier_id,
            status=POStatus.DRAFT,
            order_date=data.order_date,
            expected_delivery_date=data.expected_delivery_date,
            payment_terms=data.payment_terms,
        )
        po.items = [self._build_manual_item(item) for item in data.items]
        po.subtotal, po.gst_amount, po.total_amount = self._totals(po.items)
        created = self.repository.create(po)
        log_transaction(
            TransactionAction.PO_CREATE, "PurchaseOrder", created.id,
            {
                "po_number": created.po_number, "quotation_id": None,
                "supplier_id": created.supplier_id, "item_count": len(created.items),
                "total_amount": float(created.total_amount),
            },
        )
        return created

    # ------------------------------------------------------------------ #
    # Header edit (DRAFT only)
    # ------------------------------------------------------------------ #

    def update_po(self, po_id: int, data: PurchaseOrderUpdate) -> PurchaseOrder:
        po = self.get(po_id)
        if po.status != POStatus.DRAFT:
            raise ConflictError("Only a DRAFT purchase order can be edited")
        payload = data.model_dump(exclude_unset=True)
        for field, value in payload.items():
            setattr(po, field, value)
        updated = self.repository.update(po)
        log_transaction(TransactionAction.PO_UPDATE, "PurchaseOrder", po.id, {"po_number": po.po_number})
        return updated

    # ------------------------------------------------------------------ #
    # State machine: DRAFT -> SENT -> CONFIRMED ; DRAFT/SENT -> CANCELLED
    # ------------------------------------------------------------------ #

    def send(self, po_id: int, approved_by: str) -> PurchaseOrder:
        """Approval and dispatch happen together: there's no separate
        PENDING_APPROVAL state for a PO (see model docstring), so sending
        a DRAFT PO *is* the approval step."""
        po = self.get(po_id)
        if po.status != POStatus.DRAFT:
            raise ConflictError(f"Cannot send a PO in status {po.status.value}; it must be DRAFT")
        if not po.items:
            raise ValidationError("Cannot send a purchase order with no items")
        po.status = POStatus.SENT
        po.approved_by = approved_by
        po.approved_at = utcnow()
        updated = self.repository.update(po)
        log_transaction(
            TransactionAction.PO_SEND, "PurchaseOrder", po.id,
            {"po_number": po.po_number, "approved_by": approved_by},
        )
        return updated

    def confirm(self, po_id: int) -> PurchaseOrder:
        """Vendor confirmed the order - e.g. via the n8n PO-confirmation
        bot replying 'confirmed' on WhatsApp/Telegram."""
        po = self.get(po_id)
        if po.status != POStatus.SENT:
            raise ConflictError(f"Cannot confirm a PO in status {po.status.value}; it must be SENT")
        po.status = POStatus.CONFIRMED
        updated = self.repository.update(po)
        log_transaction(TransactionAction.PO_CONFIRM, "PurchaseOrder", po.id, {"po_number": po.po_number})
        return updated

    def cancel(self, po_id: int, cancelled_by: str, cancellation_reason: str) -> PurchaseOrder:
        po = self.get(po_id)
        if po.status not in (POStatus.DRAFT, POStatus.SENT):
            raise ConflictError(
                f"Cannot cancel a PO in status {po.status.value}; it must be DRAFT or SENT "
                "(once CONFIRMED or receiving has started, it can no longer be cancelled outright)"
            )
        po.status = POStatus.CANCELLED
        po.cancelled_by = cancelled_by
        po.cancelled_at = utcnow()
        po.cancellation_reason = cancellation_reason
        updated = self.repository.update(po)
        log_transaction(
            TransactionAction.PO_CANCEL, "PurchaseOrder", po.id,
            {"po_number": po.po_number, "cancelled_by": cancelled_by, "reason": cancellation_reason},
        )
        return updated

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_by_status(self, status: POStatus) -> List[PurchaseOrder]:
        return self.repository.get_by_status(status)

    def get_by_supplier(self, supplier_id: int) -> List[PurchaseOrder]:
        return self.repository.get_by_supplier(supplier_id)
