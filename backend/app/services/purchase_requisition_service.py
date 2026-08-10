from datetime import date
from typing import List

from sqlalchemy.orm import Session

from app.db.models.purchase_requisition import PurchaseRequisition, PurchaseRequisitionItem
from app.db.models.enums import PRStatus
from app.db.models.mixins import utcnow
from app.db.repositories.purchase_requisition_repository import PurchaseRequisitionRepository
from app.db.repositories.product_repository import ProductRepository
from app.db.schemas.purchase_requisition import (
    PurchaseRequisitionCreate,
    PurchaseRequisitionUpdate,
    PurchaseRequisitionItemCreate,
)
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, ValidationError, NotFoundError
from app.services.inventory_service import InventoryService
from app.core.transaction_logger import log_transaction, TransactionAction


class PurchaseRequisitionService(BaseService[PurchaseRequisition]):
    """
    First step of the procurement chain: an internal ask to buy something,
    raised by a department before any supplier is involved (see
    Procurement_Implementation_Plan.md §2.2/§10). Pure manual CRUD +
    approval in this phase - no RFQ/PO automation reads PRStatus.CONVERTED
    yet, PurchaseOrder.pr_id just links back to one for traceability.

    State machine: DRAFT -> PENDING_APPROVAL -> APPROVED/REJECTED.
    CONVERTED/CLOSED are set by later phases (RFQ/PO), not this service.
    """

    def __init__(self, db: Session):
        self.repository: PurchaseRequisitionRepository = PurchaseRequisitionRepository(db)
        self.product_repository = ProductRepository(db)
        self.inventory_service = InventoryService(db)
        super().__init__(self.repository, entity_name="PurchaseRequisition")

    # ------------------------------------------------------------------ #
    # Validation helpers
    # ------------------------------------------------------------------ #

    def validate_product(self, product_id: int) -> None:
        if not self.product_repository.exists(product_id):
            raise ValidationError(f"Product with id={product_id} does not exist")

    def _generate_pr_number(self) -> str:
        year = date.today().year
        count = self.repository.count_for_year(year)
        return f"PR-{year}-{count + 1:05d}"

    def _build_item(self, item: PurchaseRequisitionItemCreate) -> PurchaseRequisitionItem:
        self.validate_product(item.product_id)
        snapshot = self.inventory_service.get_available_stock(item.product_id)
        return PurchaseRequisitionItem(
            product_id=item.product_id,
            quantity=item.quantity,
            notes=item.notes,
            current_stock_snapshot=snapshot,
        )

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def create_pr(self, data: PurchaseRequisitionCreate) -> PurchaseRequisition:
        pr = PurchaseRequisition(
            pr_number=self._generate_pr_number(),
            status=PRStatus.DRAFT,
            priority=data.priority,
            department=data.department,
            raised_by=data.raised_by,
            required_by_date=data.required_by_date,
            reason=data.reason,
            linked_sales_order=data.linked_sales_order,
            source=data.source,
        )
        pr.items = [self._build_item(item) for item in data.items]
        created = self.repository.create(pr)
        log_transaction(
            TransactionAction.PR_CREATE,
            "PurchaseRequisition",
            created.id,
            {"pr_number": created.pr_number, "department": created.department, "item_count": len(created.items),
             "source": created.source.value},
        )
        return created

    def update_pr(self, pr_id: int, data: PurchaseRequisitionUpdate) -> PurchaseRequisition:
        pr = self.get(pr_id)
        if pr.status != PRStatus.DRAFT:
            raise ConflictError("Only a DRAFT purchase requisition can be edited")
        payload = data.model_dump(exclude_unset=True)
        for field, value in payload.items():
            setattr(pr, field, value)
        return self.repository.update(pr)

    def delete_pr(self, pr_id: int) -> None:
        pr = self.get(pr_id)
        if pr.status != PRStatus.DRAFT:
            raise ConflictError(
                f"Cannot delete a PR in status {pr.status.value}; only DRAFT PRs can be deleted "
                "(reject it instead if it's already submitted)"
            )
        log_transaction(TransactionAction.PR_DELETE, "PurchaseRequisition", pr.id, {"pr_number": pr.pr_number})
        self.repository.delete(pr)

    # ------------------------------------------------------------------ #
    # Line items (DRAFT only)
    # ------------------------------------------------------------------ #

    def add_item(self, pr_id: int, item: PurchaseRequisitionItemCreate) -> PurchaseRequisition:
        pr = self.get(pr_id)
        if pr.status != PRStatus.DRAFT:
            raise ConflictError("Items can only be added while the PR is in DRAFT status")
        pr.items.append(self._build_item(item))
        updated = self.repository.update(pr)
        log_transaction(
            TransactionAction.PR_ITEM_ADD, "PurchaseRequisition", pr.id,
            {"pr_number": pr.pr_number, "product_id": item.product_id, "quantity": item.quantity},
        )
        return updated

    def remove_item(self, pr_id: int, item_id: int) -> PurchaseRequisition:
        pr = self.get(pr_id)
        if pr.status != PRStatus.DRAFT:
            raise ConflictError("Items can only be removed while the PR is in DRAFT status")
        item = next((i for i in pr.items if i.id == item_id), None)
        if item is None:
            raise NotFoundError(f"Item id={item_id} not found on PurchaseRequisition id={pr_id}")
        if len(pr.items) <= 1:
            raise ValidationError("A purchase requisition must have at least one item")
        pr.items.remove(item)
        updated = self.repository.update(pr)
        log_transaction(
            TransactionAction.PR_ITEM_REMOVE, "PurchaseRequisition", pr.id,
            {"pr_number": pr.pr_number, "item_id": item_id},
        )
        return updated

    # ------------------------------------------------------------------ #
    # State machine: DRAFT -> PENDING_APPROVAL -> APPROVED / REJECTED
    # ------------------------------------------------------------------ #

    def submit(self, pr_id: int) -> PurchaseRequisition:
        pr = self.get(pr_id)
        if pr.status != PRStatus.DRAFT:
            raise ConflictError(f"Cannot submit a PR in status {pr.status.value}; it must be DRAFT")
        if not pr.items:
            raise ValidationError("Cannot submit a purchase requisition with no items")
        pr.status = PRStatus.PENDING_APPROVAL
        updated = self.repository.update(pr)
        log_transaction(TransactionAction.PR_SUBMIT, "PurchaseRequisition", pr.id, {"pr_number": pr.pr_number})
        return updated

    def approve(self, pr_id: int, approved_by: str) -> PurchaseRequisition:
        pr = self.get(pr_id)
        if pr.status != PRStatus.PENDING_APPROVAL:
            raise ConflictError(
                f"Cannot approve a PR in status {pr.status.value}; it must be PENDING_APPROVAL"
            )
        pr.status = PRStatus.APPROVED
        pr.approved_by = approved_by
        pr.approved_at = utcnow()
        updated = self.repository.update(pr)
        log_transaction(
            TransactionAction.PR_APPROVE, "PurchaseRequisition", pr.id,
            {"pr_number": pr.pr_number, "approved_by": approved_by},
        )
        return updated

    def reject(self, pr_id: int, rejected_by: str, rejection_reason: str) -> PurchaseRequisition:
        pr = self.get(pr_id)
        if pr.status != PRStatus.PENDING_APPROVAL:
            raise ConflictError(
                f"Cannot reject a PR in status {pr.status.value}; it must be PENDING_APPROVAL"
            )
        pr.status = PRStatus.REJECTED
        pr.rejected_by = rejected_by
        pr.rejected_at = utcnow()
        pr.rejection_reason = rejection_reason
        updated = self.repository.update(pr)
        log_transaction(
            TransactionAction.PR_REJECT, "PurchaseRequisition", pr.id,
            {"pr_number": pr.pr_number, "rejected_by": rejected_by, "reason": rejection_reason},
        )
        return updated

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_by_status(self, status: PRStatus) -> List[PurchaseRequisition]:
        return self.repository.get_by_status(status)

    def get_by_department(self, department: str) -> List[PurchaseRequisition]:
        return self.repository.get_by_department(department)
