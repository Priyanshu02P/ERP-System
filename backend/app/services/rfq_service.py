from datetime import date
from typing import List

from sqlalchemy.orm import Session

from app.db.models.rfq import RFQ, RFQItem, RFQSupplier
from app.db.models.enums import RFQStatus, RFQResponseStatus
from app.db.models.mixins import utcnow
from app.db.repositories.rfq_repository import RFQRepository
from app.db.repositories.product_repository import ProductRepository
from app.db.repositories.supplier_repository import SupplierRepository
from app.db.repositories.purchase_requisition_repository import PurchaseRequisitionRepository
from app.db.schemas.rfq import RFQCreate, RFQItemCreate, RFQSend
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, ValidationError
from app.core.transaction_logger import log_transaction, TransactionAction


class RFQService(BaseService[RFQ]):
    """
    Request for Quotation - either raised from an approved PurchaseRequisition
    (pr_id set) or standalone for a routine buy (pr_id null). send() dispatches
    to a set of suppliers (RFQSupplier join rows) and mark_responded() is
    called by VendorQuotationService whenever a quotation comes in against
    this RFQ, so RESPONSES_RECEIVED reflects reality without a separate poll.

    State machine: DRAFT -> SENT -> RESPONSES_RECEIVED -> CLOSED. CANCELLED
    is reserved for a future phase (no cancel endpoint yet).
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository: RFQRepository = RFQRepository(db)
        self.product_repository = ProductRepository(db)
        self.supplier_repository = SupplierRepository(db)
        self.pr_repository = PurchaseRequisitionRepository(db)
        super().__init__(self.repository, entity_name="RFQ")

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

    def _generate_rfq_number(self) -> str:
        year = date.today().year
        count = self.repository.count_for_year(year)
        return f"RFQ-{year}-{count + 1:05d}"

    def _build_item(self, item: RFQItemCreate) -> RFQItem:
        self.validate_product(item.product_id)
        return RFQItem(
            product_id=item.product_id,
            quantity=item.quantity,
            required_delivery_date=item.required_delivery_date,
        )

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def create_rfq(self, data: RFQCreate) -> RFQ:
        if data.pr_id is not None:
            self.validate_pr(data.pr_id)
        rfq = RFQ(
            rfq_number=self._generate_rfq_number(),
            status=RFQStatus.DRAFT,
            pr_id=data.pr_id,
            due_date=data.due_date,
            delivery_location=data.delivery_location,
        )
        rfq.items = [self._build_item(item) for item in data.items]
        created = self.repository.create(rfq)
        log_transaction(
            TransactionAction.RFQ_CREATE, "RFQ", created.id,
            {"rfq_number": created.rfq_number, "item_count": len(created.items), "pr_id": created.pr_id},
        )
        return created

    # ------------------------------------------------------------------ #
    # State machine: DRAFT -> SENT -> RESPONSES_RECEIVED -> CLOSED
    # ------------------------------------------------------------------ #

    def send(self, rfq_id: int, data: RFQSend) -> RFQ:
        rfq = self.get(rfq_id)
        if rfq.status != RFQStatus.DRAFT:
            raise ConflictError(f"Cannot send an RFQ in status {rfq.status.value}; it must be DRAFT")

        now = utcnow()
        for supplier_id in data.supplier_ids:
            self.validate_supplier(supplier_id)
            rfq.suppliers.append(
                RFQSupplier(
                    supplier_id=supplier_id,
                    sent_at=now,
                    sent_channel=data.channel,
                    response_status=RFQResponseStatus.SENT,
                )
            )
        rfq.status = RFQStatus.SENT
        updated = self.repository.update(rfq)
        log_transaction(
            TransactionAction.RFQ_SEND, "RFQ", rfq.id,
            {"rfq_number": rfq.rfq_number, "supplier_ids": data.supplier_ids, "channel": data.channel.value},
        )
        return updated

    def mark_responded(self, rfq_id: int, supplier_id: int) -> None:
        """Called by VendorQuotationService when a quotation arrives for a
        supplier on this RFQ - flips that supplier's response tracking and
        moves the RFQ into RESPONSES_RECEIVED on its first response."""
        rfq = self.get(rfq_id)
        link = next((s for s in rfq.suppliers if s.supplier_id == supplier_id), None)
        if link is not None:
            link.response_status = RFQResponseStatus.RESPONDED
        if rfq.status == RFQStatus.SENT:
            rfq.status = RFQStatus.RESPONSES_RECEIVED
        self.repository.update(rfq)

    def close(self, rfq_id: int) -> RFQ:
        rfq = self.get(rfq_id)
        if rfq.status not in (RFQStatus.SENT, RFQStatus.RESPONSES_RECEIVED):
            raise ConflictError(
                f"Cannot close an RFQ in status {rfq.status.value}; it must be SENT or RESPONSES_RECEIVED"
            )
        for link in rfq.suppliers:
            if link.response_status == RFQResponseStatus.SENT:
                link.response_status = RFQResponseStatus.NO_RESPONSE
        rfq.status = RFQStatus.CLOSED
        updated = self.repository.update(rfq)
        log_transaction(TransactionAction.RFQ_CLOSE, "RFQ", rfq.id, {"rfq_number": rfq.rfq_number})
        return updated

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_by_status(self, status: RFQStatus) -> List[RFQ]:
        return self.repository.get_by_status(status)
