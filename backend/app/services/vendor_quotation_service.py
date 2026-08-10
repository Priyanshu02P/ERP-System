from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.vendor_quotation import VendorQuotation, QuotationItem
from app.db.models.enums import QuotationStatus
from app.db.models.mixins import utcnow
from app.db.repositories.vendor_quotation_repository import VendorQuotationRepository
from app.db.repositories.rfq_repository import RFQRepository
from app.db.repositories.supplier_repository import SupplierRepository
from app.db.repositories.product_repository import ProductRepository
from app.db.schemas.vendor_quotation import (
    VendorQuotationCreate,
    VendorQuotationIngest,
    QuotationItemCreate,
    QuotationItemIngest,
    QuotationItemUpdate,
)
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, ValidationError, NotFoundError
from app.services.fuzzy_match import best_product_match, ProductMatchCandidate
from app.services.rfq_service import RFQService
from app.core.transaction_logger import log_transaction, TransactionAction


class VendorQuotationService(BaseService[VendorQuotation]):
    def __init__(self, db: Session):
        self.db = db
        self.repository: VendorQuotationRepository = VendorQuotationRepository(db)
        self.rfq_repository = RFQRepository(db)
        self.supplier_repository = SupplierRepository(db)
        self.product_repository = ProductRepository(db)
        super().__init__(self.repository, entity_name="VendorQuotation")

    # ------------------------------------------------------------------ #
    # Validation helpers
    # ------------------------------------------------------------------ #

    def validate_supplier(self, supplier_id: int) -> None:
        if not self.supplier_repository.exists(supplier_id):
            raise ValidationError(f"Supplier with id={supplier_id} does not exist")

    def validate_rfq(self, rfq_id: int) -> None:
        if not self.rfq_repository.exists(rfq_id):
            raise ValidationError(f"RFQ with id={rfq_id} does not exist")

    def validate_product(self, product_id: int) -> None:
        if not self.product_repository.exists(product_id):
            raise ValidationError(f"Product with id={product_id} does not exist")

    @staticmethod
    def _resolve_amount(quantity: float, rate: float, amount: Optional[float]) -> float:
        return amount if amount is not None else round(quantity * rate, 2)

    def _build_manual_item(self, item: QuotationItemCreate) -> QuotationItem:
        self.validate_product(item.product_id)
        product = self.product_repository.get(item.product_id)
        return QuotationItem(
            product_id=item.product_id,
            raw_description=item.raw_description or product.name,
            quantity=item.quantity,
            rate=item.rate,
            gst_rate=item.gst_rate,
            amount=self._resolve_amount(item.quantity, item.rate, item.amount),
            match_confidence=None,
        )

    def _build_ingested_item(self, item: QuotationItemIngest, candidates: List[ProductMatchCandidate]) -> QuotationItem:
        match = best_product_match(item.raw_description, candidates)
        return QuotationItem(
            product_id=match.product_id,
            raw_description=item.raw_description,
            quantity=item.quantity,
            rate=item.rate,
            gst_rate=item.gst_rate,
            amount=self._resolve_amount(item.quantity, item.rate, item.amount),
            match_confidence=match.confidence,
        )

    def _product_candidates(self) -> List[ProductMatchCandidate]:
        return [
            ProductMatchCandidate(id=p.id, code=p.code, name=p.name)
            for p in self.product_repository.get_active_products()
        ]

    # ------------------------------------------------------------------ #
    # Creation - manual (human, nested under an RFQ) vs ingest (automation)
    # ------------------------------------------------------------------ #

    def create_manual(self, rfq_id: Optional[int], data: VendorQuotationCreate) -> VendorQuotation:
        self.validate_supplier(data.supplier_id)
        if rfq_id is not None:
            self.validate_rfq(rfq_id)

        quotation = VendorQuotation(
            rfq_id=rfq_id,
            supplier_id=data.supplier_id,
            vendor_quotation_no=data.vendor_quotation_no,
            quotation_date=data.quotation_date,
            validity_date=data.validity_date,
            payment_terms=data.payment_terms,
            delivery_lead_time_days=data.delivery_lead_time_days,
            status=QuotationStatus.REVIEWED,
        )
        quotation.items = [self._build_manual_item(item) for item in data.items]
        created = self.repository.create(quotation)

        if rfq_id is not None:
            RFQService(self.db).mark_responded(rfq_id, data.supplier_id)

        log_transaction(
            TransactionAction.QUOTATION_CREATE, "VendorQuotation", created.id,
            {"supplier_id": created.supplier_id, "rfq_id": rfq_id, "item_count": len(created.items)},
        )
        return created

    def ingest(self, data: VendorQuotationIngest) -> VendorQuotation:
        """The only entry point automation may call - see
        Procurement_Implementation_Plan.md \u00a75. Always lands in
        PENDING_REVIEW; unmatched lines stay product_id=NULL."""
        self.validate_supplier(data.supplier_id)
        if data.rfq_id is not None:
            self.validate_rfq(data.rfq_id)

        candidates = self._product_candidates()
        quotation = VendorQuotation(
            rfq_id=data.rfq_id,
            supplier_id=data.supplier_id,
            vendor_quotation_no=data.vendor_quotation_no,
            quotation_date=data.quotation_date,
            validity_date=data.validity_date,
            payment_terms=data.payment_terms,
            delivery_lead_time_days=data.delivery_lead_time_days,
            status=QuotationStatus.PENDING_REVIEW,
            source=data.source,
            source_confidence=data.source_confidence,
            raw_document_url=data.raw_document_url,
        )
        quotation.items = [self._build_ingested_item(item, candidates) for item in data.items]
        created = self.repository.create(quotation)

        if data.rfq_id is not None:
            RFQService(self.db).mark_responded(data.rfq_id, data.supplier_id)

        unmatched = sum(1 for i in created.items if i.product_id is None)
        log_transaction(
            TransactionAction.QUOTATION_INGEST, "VendorQuotation", created.id,
            {
                "supplier_id": created.supplier_id, "rfq_id": data.rfq_id,
                "source": data.source.value, "item_count": len(created.items),
                "unmatched_item_count": unmatched,
            },
        )
        return created

    # ------------------------------------------------------------------ #
    # Review queue
    # ------------------------------------------------------------------ #

    def update_item(self, quotation_id: int, item_id: int, data: QuotationItemUpdate) -> VendorQuotation:
        quotation = self.get(quotation_id)
        if quotation.status not in (QuotationStatus.PENDING_REVIEW, QuotationStatus.REVIEWED):
            raise ConflictError(
                f"Cannot edit line items on a quotation in status {quotation.status.value}"
            )
        item = next((i for i in quotation.items if i.id == item_id), None)
        if item is None:
            raise NotFoundError(f"Item id={item_id} not found on VendorQuotation id={quotation_id}")

        payload = data.model_dump(exclude_unset=True)
        if "product_id" in payload and payload["product_id"] is not None:
            self.validate_product(payload["product_id"])
            item.match_confidence = None  # human override supersedes the fuzzy-match score
        for field, value in payload.items():
            setattr(item, field, value)
        if "quantity" in payload or "rate" in payload:
            if "amount" not in payload:
                item.amount = self._resolve_amount(item.quantity, item.rate, None)

        updated = self.repository.update(quotation)
        log_transaction(
            TransactionAction.QUOTATION_ITEM_UPDATE, "VendorQuotation", quotation.id,
            {"item_id": item_id, "fields": list(payload.keys())},
        )
        return updated

    def review(self, quotation_id: int, reviewed_by: str) -> VendorQuotation:
        quotation = self.get(quotation_id)
        if quotation.status != QuotationStatus.PENDING_REVIEW:
            raise ConflictError(
                f"Cannot review a quotation in status {quotation.status.value}; it must be PENDING_REVIEW"
            )
        quotation.status = QuotationStatus.REVIEWED
        quotation.reviewed_by = reviewed_by
        quotation.reviewed_at = utcnow()
        updated = self.repository.update(quotation)
        log_transaction(
            TransactionAction.QUOTATION_REVIEW, "VendorQuotation", quotation.id, {"reviewed_by": reviewed_by}
        )
        return updated

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #

    def select(self, quotation_id: int) -> VendorQuotation:
        quotation = self.get(quotation_id)
        if quotation.status not in (QuotationStatus.PENDING_REVIEW, QuotationStatus.REVIEWED):
            raise ConflictError(
                f"Cannot select a quotation in status {quotation.status.value}"
            )
        unmapped = [i.id for i in quotation.items if i.product_id is None]
        if unmapped:
            raise ValidationError(
                f"Cannot select: item(s) {unmapped} are not mapped to a product. "
                "Correct them via PUT /quotations/{id}/items/{item_id} first."
            )
        quotation.status = QuotationStatus.SELECTED
        updated = self.repository.update(quotation)

        if quotation.rfq_id is not None:
            for sibling in self.repository.get_selectable_siblings(quotation.rfq_id, quotation.id):
                sibling.status = QuotationStatus.REJECTED
                sibling.rejection_reason = "Another quotation on this RFQ was selected"
                self.repository.update(sibling)

        log_transaction(TransactionAction.QUOTATION_SELECT, "VendorQuotation", quotation.id, {"rfq_id": quotation.rfq_id})
        return updated

    def reject(self, quotation_id: int, rejected_by: str, rejection_reason: str) -> VendorQuotation:
        quotation = self.get(quotation_id)
        if quotation.status not in (QuotationStatus.PENDING_REVIEW, QuotationStatus.REVIEWED):
            raise ConflictError(
                f"Cannot reject a quotation in status {quotation.status.value}"
            )
        quotation.status = QuotationStatus.REJECTED
        quotation.rejected_by = rejected_by
        quotation.rejected_at = utcnow()
        quotation.rejection_reason = rejection_reason
        updated = self.repository.update(quotation)
        log_transaction(
            TransactionAction.QUOTATION_REJECT, "VendorQuotation", quotation.id,
            {"rejected_by": rejected_by, "reason": rejection_reason},
        )
        return updated

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_by_status(self, status: QuotationStatus) -> List[VendorQuotation]:
        return self.repository.get_by_status(status)

    def get_by_rfq(self, rfq_id: int) -> List[VendorQuotation]:
        return self.repository.get_by_rfq(rfq_id)
