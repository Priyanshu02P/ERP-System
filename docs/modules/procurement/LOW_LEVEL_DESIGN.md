# Low-Level Design — Procurement (`app/procurement/`)

> Part of the module-wise low-level design set. See
> [`../../HIGH_LEVEL_ARCHITECTURE.md`](../../HIGH_LEVEL_ARCHITECTURE.md) for how this fits together,
> and [`../../BUSINESS_DECISIONS.md`](../../BUSINESS_DECISIONS.md) for the "why" behind these rules.
> Foundations these services build on: [shared kernel](../shared/LOW_LEVEL_DESIGN.md).
> Sibling modules: [master_data](../master_data/LOW_LEVEL_DESIGN.md), [wms](../wms/LOW_LEVEL_DESIGN.md),
> [quality](../quality/LOW_LEVEL_DESIGN.md), [platform](../platform/LOW_LEVEL_DESIGN.md). Historical
> build log: [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md).
>
> Convention used throughout: **public methods are the API a router calls** (one router function → one
> service method); **`_private` / `@staticmethod` helpers** are internal building blocks a public
> method composes, never called from a router.

The full buy-side lifecycle: an internal requisition through to paying the vendor. Six of the seven
subdomains are state-machine-driven, each one's terminal action feeding the next — read them in this
order: Supplier (master) → PR → RFQ → Quotation → PO → Invoice. (Goods Receipt and Quality Inspection,
the two steps that sit physically *between* PO and Invoice, live in
[wms](../wms/LOW_LEVEL_DESIGN.md#goods-receipt-appwmsgoods_receipt) and
[quality](../quality/LOW_LEVEL_DESIGN.md) respectively — see
`../../HIGH_LEVEL_ARCHITECTURE.md §5` for the full chain diagram.)

| Subdomain | Files |
|---|---|
| `supplier/` | `models.py`, `schemas.py`, `repository.py`, `service.py` (`SupplierService`), `api.py` |
| `requisition/` | `models.py`, `schemas.py`, `repository.py`, `service.py` (`PurchaseRequisitionService`), `api.py` |
| `rfq/` | `models.py`, `schemas.py`, `repository.py`, `service.py` (`RFQService`), `api.py` |
| `vendor_quotation/` | `models.py`, `schemas.py`, `repository.py`, `service.py` (`VendorQuotationService`), `api.py` |
| `purchase_order/` | `models.py`, `schemas.py`, `repository.py`, `service.py` (`PurchaseOrderService`), `api.py` |
| `vendor_invoice/` | `models.py`, `schemas.py`, `repository.py`, `service.py` (`VendorInvoiceService`), `api.py` |
| `dashboard/` | `schemas.py`, `service.py` (`ProcurementDashboardService`), `api.py` — *no model/repository, aggregates across the above* |

## `SupplierService` (`app/procurement/supplier/service.py`)

Who a product is procured from — carries `category` (`SupplierCategory`) and an optional
`manufacturer_id` link (used by `QualityInspectionService` to default `Inventory.manufacturer_id`).

| Method | Purpose |
|---|---|
| `validate_manufacturer(manufacturer_id)` | Existence check, raises `ValidationError` |
| `create_supplier(data)` | Create, rejecting a duplicate `code`, validating `manufacturer_id` if given |
| `update_supplier(supplier_id, data)` | Partial update, re-validates `manufacturer_id` if changed |
| `delete_supplier(supplier_id)` | Blocked if referenced by `Product.preferred_supplier_id`, any PR/RFQ/Quotation/PO/Invoice |
| `activate_supplier(supplier_id)` / `deactivate_supplier(supplier_id)` | Toggle active flag |
| `search(term)` | Name/code substring search |
| `get_by_category(category)` | Filter by `SupplierCategory` |

## `PurchaseRequisitionService` (`app/procurement/requisition/service.py`)

First step: an internal ask to buy something, before any supplier is involved.
**State machine:** `DRAFT → PENDING_APPROVAL → APPROVED/REJECTED`. (`CONVERTED`/`CLOSED` are reserved
for later phases — nothing sets them yet.)

| Method | Purpose |
|---|---|
| `validate_product(product_id)` | Existence check |
| `_generate_pr_number()` | `PR-{year}-{00001}` |
| `_build_item(item)` | Validates `product_id`, builds a `PurchaseRequisitionItem` |
| `create_pr(data)` | Creates in `DRAFT`, logs `PR_CREATE` |
| `update_pr(pr_id, data)` | Header edit, blocked once not `DRAFT` |
| `delete_pr(pr_id)` | Blocked once not `DRAFT` |
| `add_item(pr_id, item)` / `remove_item(pr_id, item_id)` | Line-item edits, blocked once not `DRAFT` |
| `submit(pr_id)` | `DRAFT → PENDING_APPROVAL`, requires at least one item |
| `approve(pr_id, approved_by)` | `PENDING_APPROVAL → APPROVED`, stamps `approved_by`/`approved_at` |
| `reject(pr_id, rejected_by, rejection_reason)` | `PENDING_APPROVAL → REJECTED` |
| `get_by_status(status)` / `get_by_department(department)` | Filtered list queries |

## `RFQService` (`app/procurement/rfq/service.py`)

Request for Quotation, either from an approved PR (`pr_id` set) or standalone (`pr_id` null).
**State machine:** `DRAFT → SENT → RESPONSES_RECEIVED → CLOSED`. (`CANCELLED` reserved.)

| Method | Purpose |
|---|---|
| `validate_product` / `validate_supplier` / `validate_pr` | Existence checks |
| `_generate_rfq_number()` | `RFQ-{year}-{00001}` |
| `_build_item(item)` | Validates `product_id`, builds an `RFQItem` |
| `create_rfq(data)` | Creates in `DRAFT` (validates `pr_id` if given), logs `RFQ_CREATE` |
| `send(rfq_id, data)` | `DRAFT → SENT`; creates one `RFQSupplier` join row per `data.supplier_ids` with `sent_at`/`sent_channel`/`response_status=SENT` |
| `mark_responded(rfq_id, supplier_id)` | **Called by `VendorQuotationService`**, not a router — flips that supplier's `RFQSupplier.response_status` to `RESPONDED` and moves the RFQ to `RESPONSES_RECEIVED` on its first response, so the status reflects reality without polling |
| `close(rfq_id)` | `SENT`/`RESPONSES_RECEIVED → CLOSED`; any supplier still `SENT` (never responded) is marked `NO_RESPONSE` |
| `get_by_status(status)` | Filtered list query |

## `VendorQuotationService` (`app/procurement/vendor_quotation/service.py`)

A supplier's quoted price — manual entry (nested under an RFQ, or standalone for a routine buy) vs.
automation `ingest`. **State machine:** `PENDING_REVIEW`/`REVIEWED → SELECTED`/`REJECTED`
(`EXPIRED` reserved).

| Method | Purpose |
|---|---|
| `validate_supplier` / `validate_rfq` / `validate_product` | Existence checks |
| `_resolve_amount(quantity, rate, amount)` | `amount` if given, else `round(quantity * rate, 2)` — used on every line so a client can omit `amount` and trust server math |
| `_build_manual_item(item)` | Human entry: `product_id` **required**, no fuzzy matching |
| `_build_ingested_item(item, candidates)` | Automation entry: fuzzy-matches `raw_description` against `candidates` via `best_product_match` (`app/shared/fuzzy_match.py`), stores `match_confidence` |
| `_product_candidates()` | Builds the `ProductMatchCandidate` list from all active products, for ingest to match against |
| `create_manual(rfq_id, data)` | Creates in `REVIEWED` (a human typed it, already trusted); if `rfq_id` set, calls `RFQService.mark_responded` |
| `ingest(data)` | **The only endpoint automation may call.** Always creates in `PENDING_REVIEW`; unmatched lines stay `product_id=NULL`; same `mark_responded` call if `rfq_id` set |
| `update_item(quotation_id, item_id, data)` | Review-queue correction: sets/overrides `product_id` (clearing `match_confidence` — a human override supersedes the fuzzy score), quantity/rate/amount |
| `review(quotation_id, reviewed_by)` | `PENDING_REVIEW → REVIEWED` |
| `select(quotation_id)` | `PENDING_REVIEW`/`REVIEWED → SELECTED`; **blocked while any line has `product_id=NULL`**; auto-rejects every other still-open quotation on the same RFQ (`get_selectable_siblings`) |
| `reject(quotation_id, rejected_by, rejection_reason)` | `PENDING_REVIEW`/`REVIEWED → REJECTED` |
| `get_by_status(status)` / `get_by_rfq(rfq_id)` | Filtered list queries |

## `PurchaseOrderService` (`app/procurement/purchase_order/service.py`)

A commitment to buy — either converted from a `SELECTED` `VendorQuotation` or raised manually for a
routine buy. **State machine:** `DRAFT → SENT → CONFIRMED → PARTIALLY_RECEIVED → RECEIVED` (+`CLOSED`
reserved), with `CANCELLED` reachable from `DRAFT`/`SENT`. No separate approval state — `send()` *is*
the approval, since that's the point real vendor commitment happens.

| Method | Purpose |
|---|---|
| `validate_product` / `validate_supplier` / `validate_pr` | Existence checks |
| `_generate_po_number()` | `PO-{year}-{00001}` |
| `_resolve_amount(quantity, rate, amount)` | Same pattern as the quotation service |
| `_totals(items)` | `(subtotal, gst_amount, total_amount)` computed server-side from line items — **never trusted from the client** |
| `_build_manual_item(item)` | Validates `product_id`, builds a `PurchaseOrderItem` |
| `create_po(data)` | Dispatches to `_create_from_quotation` if `data.quotation_id` set, else `_create_manual` |
| `_create_from_quotation(data)` | Copies every `SELECTED` quotation line into PO lines 1:1, links `quotation_id` (unique — one PO per quotation) |
| `_create_manual(data)` | Builds PO lines directly from `data.items`, no quotation involved |
| `update_po(po_id, data)` | Header edit, blocked once not `DRAFT` |
| `send(po_id, approved_by)` | `DRAFT → SENT`, stamps `approved_by`/`approved_at` — the approval-and-dispatch step |
| `confirm(po_id)` | `SENT → CONFIRMED` — vendor has acknowledged the order |
| `cancel(po_id, cancelled_by, cancellation_reason)` | `DRAFT`/`SENT → CANCELLED` |
| `get_by_status(status)` / `get_by_supplier(supplier_id)` | Filtered list queries |

*(`PARTIALLY_RECEIVED`/`RECEIVED` are set by `GoodsReceiptService` — see
[wms](../wms/LOW_LEVEL_DESIGN.md#goods-receipt-appwmsgoods_receipt).)*

## `VendorInvoiceService` (`app/procurement/vendor_invoice/service.py`)

The 3-way match: PO (what was agreed) vs. GRN (what arrived) vs. Invoice (what's being billed) —
purely financial, never touches `Inventory`. **State machine:** `PENDING_MATCH ⇄ MISMATCH → MATCHED →
APPROVED_FOR_PAYMENT → PAID` (`DISPUTED` reserved, no endpoint). `PENDING_MATCH` doubles as this
module's review-queue state — see `../../BUSINESS_DECISIONS.md`.

| Method | Purpose |
|---|---|
| `_validate_and_load_po(po_id, supplier_id)` | Loads the PO, validates the supplier exists **and matches the PO's own `supplier_id`** (422 on mismatch — an invoice can't claim to be from a different vendor than the PO it bills) |
| `_resolve_grn_id(po_id, explicit_grn_id)` | Explicit value wins (validated); else auto-resolves **only if exactly one `GoodsReceipt` exists for the PO** — ambiguous (multiple) or absent (none) cases left `NULL` |
| `_resolve_amount` / `_totals` | Same server-side-totals pattern as `PurchaseOrderService` |
| `_validate_po_item(po, po_item_id)` | Confirms a line actually belongs to the invoice's own PO |
| `_build_manual_item(po, item)` | Human entry: `po_item_id` **required** |
| `_build_ingested_item(item, candidates)` | Automation entry: fuzzy-matches `description` against the **target PO's own line items** (not the whole product catalog) |
| `_po_item_candidates(po)` *(static)* | Builds `ProductMatchCandidate`s keyed by `po_item.id` (reusing the quotation-matching dataclass generically) |
| `create_manual(data)` | Creates in `PENDING_MATCH`, `grn_id` auto-resolved, logs `INVOICE_CREATE` |
| `ingest(data)` | The only automation entry point; unmatched lines left `po_item_id=NULL`; logs `INVOICE_INGEST` |
| `update_header(invoice_id, data)` | Edits `grn_id`/`vendor_invoice_no`/`invoice_date` while `PENDING_MATCH`/`MISMATCH` |
| `update_item(invoice_id, item_id, data)` | Review-queue line correction (mirrors `VendorQuotationService.update_item`); recomputes totals |
| `_pct_diff(actual, expected)` *(static)* | `abs(actual - expected) / abs(expected) * 100`, guarding division by zero |
| `match(invoice_id, matched_by)` | The 3-way check itself — see `../../BUSINESS_DECISIONS.md §6` for the tolerance numbers and exact comparison logic; stores a full `match_report` JSON; sets `MATCHED`/`MISMATCH`; **re-runnable** from either starting state |
| `approve_payment(invoice_id, approved_by)` | `MATCHED → APPROVED_FOR_PAYMENT` only |
| `mark_paid(invoice_id, paid_by)` | `APPROVED_FOR_PAYMENT → PAID` only |
| `get_by_status(status)` / `get_by_po(po_id)` | Filtered list queries |

## `ProcurementDashboardService` (`app/procurement/dashboard/service.py`)

Read-only aggregation across every subdomain above (plus `wms.inventory` and `wms.goods_receipt`) —
backs `GET /procurement/kpis` and `GET /procurement/reorder-suggestions`. Deliberately **not** a
`BaseService[...]` subclass (owns no single entity) and the one service in this codebase whose methods
never call `log_transaction()` — a dashboard view is a query, not a business event. Nothing here writes
anything; everything is computed live from current rows on each call (no caching/materialization — see
the class docstring for the tradeoff).

| Method | Purpose |
|---|---|
| `_overdue_purchase_orders()` | POs still `CONFIRMED`/`PARTIALLY_RECEIVED` whose `expected_delivery_date` has passed; a PO with no delivery date set, or one that's fully `RECEIVED`, is never counted |
| `get_kpis()` | `pending_prs` (count of `PRStatus.PENDING_APPROVAL`), `pos_awaiting_grn` (`CONFIRMED`+`PARTIALLY_RECEIVED`), `grns_awaiting_qc` (`GRNStatus.PENDING_QC`), `overdue_deliveries` (count + the actual PO ids) |
| `get_reorder_suggestions()` | Every active `Product` with a `reorder_level` set whose available stock (`app.wms.inventory.repository.InventoryRepository.get_available_stock_map()` — OK-status only, reserved quantity excluded, same definition `InventoryService` uses everywhere else) is at or below that threshold; products with no `reorder_level` configured are skipped, not assumed fine. Suggest-only — never creates a `PurchaseRequisition` |

## Repository layer (brief)

Every repository is a thin `BaseRepository[ModelType]` subclass (see
[shared kernel](../shared/LOW_LEVEL_DESIGN.md)). Each concrete repository adds only what its service
actually needs beyond generic CRUD:

| Repository | Extra methods beyond `BaseRepository` |
|---|---|
| `procurement/requisition/repository.py` (`PurchaseRequisitionRepository`) | `count_for_year`, `get_by_status`, `get_by_department` |
| `procurement/rfq/repository.py` (`RFQRepository`) | `count_for_year`, `get_by_status` |
| `procurement/vendor_quotation/repository.py` (`VendorQuotationRepository`) | `get_by_status`, `get_by_rfq`, `get_by_supplier`, `get_selectable_siblings` |
| `procurement/purchase_order/repository.py` (`PurchaseOrderRepository`) | `count_for_year`, `get_by_status`, `get_by_supplier` |
| `procurement/vendor_invoice/repository.py` (`VendorInvoiceRepository`) | `get_by_status`, `get_by_po`, `get_by_supplier` |

No repository contains business rules — every conditional you see above the repository layer belongs
to the service that calls it.
