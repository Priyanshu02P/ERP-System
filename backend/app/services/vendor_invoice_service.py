from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models.vendor_invoice import VendorInvoice, VendorInvoiceItem
from app.db.models.purchase_order import PurchaseOrderItem
from app.db.models.enums import InvoiceStatus
from app.db.models.mixins import utcnow
from app.db.repositories.vendor_invoice_repository import VendorInvoiceRepository
from app.db.repositories.purchase_order_repository import PurchaseOrderRepository
from app.db.repositories.goods_receipt_repository import GoodsReceiptRepository
from app.db.repositories.supplier_repository import SupplierRepository
from app.db.schemas.vendor_invoice import (
    VendorInvoiceCreate,
    VendorInvoiceIngest,
    VendorInvoiceItemCreate,
    VendorInvoiceItemIngest,
    VendorInvoiceItemUpdate,
    VendorInvoiceUpdate,
)
from app.services.base_service import BaseService
from app.services.exceptions import ConflictError, ValidationError, NotFoundError
from app.services.fuzzy_match import best_product_match, ProductMatchCandidate
from app.core.transaction_logger import log_transaction, TransactionAction

# Deliberate simplification (not specified numerically in the plan): a line
# is MATCHED if both its quantity and its rate are within this percentage
# of the GRN's received quantity / the PO's agreed rate. Loose enough to
# tolerate rounding/OCR noise, tight enough to catch a real discrepancy.
QUANTITY_TOLERANCE_PCT = 2.0
RATE_TOLERANCE_PCT = 1.0

_EDITABLE_STATUSES = (InvoiceStatus.PENDING_MATCH, InvoiceStatus.MISMATCH)


class VendorInvoiceService(BaseService[VendorInvoice]):
    """
    The 3-way match: a VendorInvoice line is only trustworthy once it's
    checked against what was actually ordered (PurchaseOrderItem.rate) and
    what actually arrived (GoodsReceiptItem.received_quantity) - see
    match(). Nothing here creates or touches Inventory; that already
    happened at QC (Phase 5). This module's job is purely financial:
    deciding whether an invoice is safe to pay.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository: VendorInvoiceRepository = VendorInvoiceRepository(db)
        self.po_repository = PurchaseOrderRepository(db)
        self.grn_repository = GoodsReceiptRepository(db)
        self.supplier_repository = SupplierRepository(db)
        super().__init__(self.repository, entity_name="VendorInvoice")

    # ------------------------------------------------------------------ #
    # Validation / resolution helpers
    # ------------------------------------------------------------------ #

    def _validate_and_load_po(self, po_id: int, supplier_id: int):
        po = self.po_repository.get(po_id)
        if po is None:
            raise ValidationError(f"PurchaseOrder with id={po_id} does not exist")
        if not self.supplier_repository.exists(supplier_id):
            raise ValidationError(f"Supplier with id={supplier_id} does not exist")
        if po.supplier_id != supplier_id:
            raise ValidationError(
                f"Supplier id={supplier_id} does not match PO id={po_id}'s supplier (id={po.supplier_id})"
            )
        return po

    def _resolve_grn_id(self, po_id: int, explicit_grn_id: Optional[int]) -> Optional[int]:
        """Convenience auto-resolve: if the caller didn't say which GRN this
        invoice is against but exactly one exists for the PO, use it.
        Ambiguous (multiple GRNs, e.g. partial deliveries) or absent (none
        yet) cases are left NULL - set explicitly later via PUT."""
        if explicit_grn_id is not None:
            if not self.grn_repository.exists(explicit_grn_id):
                raise ValidationError(f"GoodsReceipt with id={explicit_grn_id} does not exist")
            return explicit_grn_id
        grns = self.grn_repository.get_by_po(po_id)
        return grns[0].id if len(grns) == 1 else None

    @staticmethod
    def _resolve_amount(quantity: float, rate: float, amount: Optional[float]) -> float:
        return amount if amount is not None else round(float(quantity) * float(rate), 2)

    @staticmethod
    def _totals(items: List[VendorInvoiceItem]) -> tuple[float, float, float]:
        subtotal = round(sum(float(i.amount) for i in items), 2)
        gst_amount = round(
            sum(float(i.amount) * float(i.gst_rate) / 100 for i in items if i.gst_rate is not None), 2
        )
        return subtotal, gst_amount, round(subtotal + gst_amount, 2)

    def _validate_po_item(self, po, po_item_id: int) -> PurchaseOrderItem:
        po_item = next((i for i in po.items if i.id == po_item_id), None)
        if po_item is None:
            raise ValidationError(f"PurchaseOrderItem id={po_item_id} does not belong to PO id={po.id}")
        return po_item

    def _build_manual_item(self, po, item: VendorInvoiceItemCreate) -> VendorInvoiceItem:
        self._validate_po_item(po, item.po_item_id)
        return VendorInvoiceItem(
            po_item_id=item.po_item_id,
            description=item.description,
            quantity=item.quantity,
            rate=item.rate,
            gst_rate=item.gst_rate,
            amount=self._resolve_amount(item.quantity, item.rate, item.amount),
            match_confidence=None,
        )

    def _build_ingested_item(
        self, item: VendorInvoiceItemIngest, candidates: List[ProductMatchCandidate]
    ) -> VendorInvoiceItem:
        match = best_product_match(item.description, candidates)
        return VendorInvoiceItem(
            po_item_id=match.product_id,  # candidate.id carries the po_item_id here, see _po_item_candidates
            description=item.description,
            quantity=item.quantity,
            rate=item.rate,
            gst_rate=item.gst_rate,
            amount=self._resolve_amount(item.quantity, item.rate, item.amount),
            match_confidence=match.confidence,
        )

    @staticmethod
    def _po_item_candidates(po) -> List[ProductMatchCandidate]:
        """Candidates for fuzzy-matching an ingested invoice line: the
        target PO's own items, keyed by po_item.id (reusing
        ProductMatchCandidate/best_product_match as a generic
        description-vs-code/name matcher, not specifically product-bound)."""
        return [
            ProductMatchCandidate(id=item.id, code=item.product.code, name=item.product.name)
            for item in po.items
        ]

    # ------------------------------------------------------------------ #
    # Creation - manual (human) vs ingest (automation)
    # ------------------------------------------------------------------ #

    def create_manual(self, data: VendorInvoiceCreate) -> VendorInvoice:
        po = self._validate_and_load_po(data.po_id, data.supplier_id)

        invoice = VendorInvoice(
            supplier_id=data.supplier_id,
            po_id=data.po_id,
            grn_id=self._resolve_grn_id(data.po_id, data.grn_id),
            vendor_invoice_no=data.vendor_invoice_no,
            invoice_date=data.invoice_date,
            status=InvoiceStatus.PENDING_MATCH,
        )
        invoice.items = [self._build_manual_item(po, item) for item in data.items]
        invoice.subtotal, invoice.gst_amount, invoice.total_amount = self._totals(invoice.items)
        created = self.repository.create(invoice)

        log_transaction(
            TransactionAction.INVOICE_CREATE, "VendorInvoice", created.id,
            {"po_id": created.po_id, "supplier_id": created.supplier_id, "item_count": len(created.items)},
        )
        return created

    def ingest(self, data: VendorInvoiceIngest) -> VendorInvoice:
        """The only entry point automation may call - see
        Procurement_Implementation_Plan.md §5. Always lands in
        PENDING_MATCH with unmatched lines left po_item_id=NULL, the same
        review-queue role PENDING_REVIEW plays for quotations."""
        po = self._validate_and_load_po(data.po_id, data.supplier_id)

        candidates = self._po_item_candidates(po)
        invoice = VendorInvoice(
            supplier_id=data.supplier_id,
            po_id=data.po_id,
            grn_id=self._resolve_grn_id(data.po_id, data.grn_id),
            vendor_invoice_no=data.vendor_invoice_no,
            invoice_date=data.invoice_date,
            status=InvoiceStatus.PENDING_MATCH,
            source=data.source,
            source_confidence=data.source_confidence,
            raw_document_url=data.raw_document_url,
        )
        invoice.items = [self._build_ingested_item(item, candidates) for item in data.items]
        invoice.subtotal, invoice.gst_amount, invoice.total_amount = self._totals(invoice.items)
        created = self.repository.create(invoice)

        unmatched = sum(1 for i in created.items if i.po_item_id is None)
        log_transaction(
            TransactionAction.INVOICE_INGEST, "VendorInvoice", created.id,
            {
                "po_id": created.po_id, "supplier_id": created.supplier_id, "source": data.source.value,
                "item_count": len(created.items), "unmatched_item_count": unmatched,
            },
        )
        return created

    # ------------------------------------------------------------------ #
    # Header edit / review queue
    # ------------------------------------------------------------------ #

    def update_header(self, invoice_id: int, data: VendorInvoiceUpdate) -> VendorInvoice:
        invoice = self.get(invoice_id)
        if invoice.status not in _EDITABLE_STATUSES:
            raise ConflictError(f"Cannot edit a vendor invoice in status {invoice.status.value}")
        payload = data.model_dump(exclude_unset=True)
        if "grn_id" in payload and payload["grn_id"] is not None:
            if not self.grn_repository.exists(payload["grn_id"]):
                raise ValidationError(f"GoodsReceipt with id={payload['grn_id']} does not exist")
        for field, value in payload.items():
            setattr(invoice, field, value)
        return self.repository.update(invoice)

    def update_item(self, invoice_id: int, item_id: int, data: VendorInvoiceItemUpdate) -> VendorInvoice:
        invoice = self.get(invoice_id)
        if invoice.status not in _EDITABLE_STATUSES:
            raise ConflictError(f"Cannot edit line items on a vendor invoice in status {invoice.status.value}")
        item = next((i for i in invoice.items if i.id == item_id), None)
        if item is None:
            raise NotFoundError(f"Item id={item_id} not found on VendorInvoice id={invoice_id}")

        payload = data.model_dump(exclude_unset=True)
        if "po_item_id" in payload and payload["po_item_id"] is not None:
            self._validate_po_item(invoice.po, payload["po_item_id"])
            item.match_confidence = None  # human override supersedes the fuzzy-match score
        for field, value in payload.items():
            setattr(item, field, value)
        if "quantity" in payload or "rate" in payload:
            if "amount" not in payload:
                item.amount = self._resolve_amount(item.quantity, item.rate, None)

        invoice.subtotal, invoice.gst_amount, invoice.total_amount = self._totals(invoice.items)
        updated = self.repository.update(invoice)
        log_transaction(
            TransactionAction.INVOICE_ITEM_UPDATE, "VendorInvoice", invoice.id,
            {"item_id": item_id, "fields": list(payload.keys())},
        )
        return updated

    # ------------------------------------------------------------------ #
    # 3-way match
    # ------------------------------------------------------------------ #

    @staticmethod
    def _pct_diff(actual: float, expected: float) -> float:
        if expected == 0:
            return 0.0 if actual == 0 else 100.0
        return round(abs(actual - expected) / abs(expected) * 100, 2)

    def match(self, invoice_id: int, matched_by: str) -> VendorInvoice:
        invoice = self.get(invoice_id)
        if invoice.status not in _EDITABLE_STATUSES:
            raise ConflictError(
                f"Cannot match a vendor invoice in status {invoice.status.value}; it must be "
                "PENDING_MATCH (or MISMATCH, to re-attempt after a correction)"
            )
        if invoice.grn_id is None:
            raise ValidationError(
                "Cannot match: no GoodsReceipt is linked to this invoice yet. Set grn_id via "
                "PUT /vendor-invoices/{id} first."
            )
        unmapped = [i.id for i in invoice.items if i.po_item_id is None]
        if unmapped:
            raise ValidationError(
                f"Cannot match: item(s) {unmapped} are not mapped to a PO line. Correct them via "
                "PUT /vendor-invoices/{id}/items/{item_id} first."
            )

        po = invoice.po
        grn = invoice.grn
        grn_items_by_po_item = {gi.po_item_id: gi for gi in grn.items}

        line_reports = []
        all_lines_ok = True
        for item in invoice.items:
            po_item = next(i for i in po.items if i.id == item.po_item_id)
            grn_item = grn_items_by_po_item.get(item.po_item_id)

            if grn_item is None:
                line_reports.append({
                    "invoice_item_id": item.id, "po_item_id": item.po_item_id, "ok": False,
                    "reason": "No line for this PO item on the linked GRN",
                })
                all_lines_ok = False
                continue

            qty_diff_pct = self._pct_diff(float(item.quantity), float(grn_item.received_quantity))
            rate_diff_pct = self._pct_diff(float(item.rate), float(po_item.rate))
            line_ok = qty_diff_pct <= QUANTITY_TOLERANCE_PCT and rate_diff_pct <= RATE_TOLERANCE_PCT
            all_lines_ok = all_lines_ok and line_ok

            line_reports.append({
                "invoice_item_id": item.id, "po_item_id": item.po_item_id, "ok": line_ok,
                "invoice_quantity": float(item.quantity), "grn_received_quantity": float(grn_item.received_quantity),
                "quantity_diff_pct": qty_diff_pct,
                "invoice_rate": float(item.rate), "po_rate": float(po_item.rate), "rate_diff_pct": rate_diff_pct,
            })

        header_diff_pct = self._pct_diff(float(invoice.total_amount), float(po.total_amount))
        # Header tolerance is the looser of the two line tolerances - it's a
        # sanity check on the overall bill, not a re-check of every line.
        header_ok = header_diff_pct <= QUANTITY_TOLERANCE_PCT
        overall_ok = all_lines_ok and header_ok

        invoice.match_report = {
            "tolerance_pct": {"quantity": QUANTITY_TOLERANCE_PCT, "rate": RATE_TOLERANCE_PCT},
            "lines": line_reports,
            "header": {
                "invoice_total_amount": float(invoice.total_amount), "po_total_amount": float(po.total_amount),
                "diff_pct": header_diff_pct, "ok": header_ok,
            },
            "result": "MATCHED" if overall_ok else "MISMATCH",
        }
        invoice.status = InvoiceStatus.MATCHED if overall_ok else InvoiceStatus.MISMATCH
        invoice.matched_by = matched_by
        invoice.matched_at = utcnow()
        updated = self.repository.update(invoice)

        log_transaction(
            TransactionAction.INVOICE_MATCH, "VendorInvoice", invoice.id,
            {"matched_by": matched_by, "result": invoice.match_report["result"]},
        )
        return updated

    # ------------------------------------------------------------------ #
    # Payment
    # ------------------------------------------------------------------ #

    def approve_payment(self, invoice_id: int, approved_by: str) -> VendorInvoice:
        invoice = self.get(invoice_id)
        if invoice.status != InvoiceStatus.MATCHED:
            raise ConflictError(
                f"Cannot approve payment on a vendor invoice in status {invoice.status.value}; "
                "it must be MATCHED"
            )
        invoice.status = InvoiceStatus.APPROVED_FOR_PAYMENT
        invoice.approved_by = approved_by
        invoice.approved_at = utcnow()
        updated = self.repository.update(invoice)
        log_transaction(
            TransactionAction.INVOICE_APPROVE_PAYMENT, "VendorInvoice", invoice.id, {"approved_by": approved_by}
        )
        return updated

    def mark_paid(self, invoice_id: int, paid_by: str) -> VendorInvoice:
        invoice = self.get(invoice_id)
        if invoice.status != InvoiceStatus.APPROVED_FOR_PAYMENT:
            raise ConflictError(
                f"Cannot mark a vendor invoice paid in status {invoice.status.value}; it must be "
                "APPROVED_FOR_PAYMENT"
            )
        invoice.status = InvoiceStatus.PAID
        invoice.paid_by = paid_by
        invoice.paid_at = utcnow()
        updated = self.repository.update(invoice)
        log_transaction(TransactionAction.INVOICE_MARK_PAID, "VendorInvoice", invoice.id, {"paid_by": paid_by})
        return updated

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_by_status(self, status: InvoiceStatus) -> List[VendorInvoice]:
        return self.repository.get_by_status(status)

    def get_by_po(self, po_id: int) -> List[VendorInvoice]:
        return self.repository.get_by_po(po_id)
