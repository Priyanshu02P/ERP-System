# Low-Level Service Architecture

> Every class and function in `app/services/`, grouped by module. For the layer these services sit in
> (and how they relate to routers/repositories/models), see
> [`HIGH_LEVEL_ARCHITECTURE.md`](./HIGH_LEVEL_ARCHITECTURE.md). For *why* a rule exists rather than
> *what* it does, see [`BUSINESS_DECISIONS.md`](./BUSINESS_DECISIONS.md).
>
> Convention used throughout the codebase: **public methods are the API a router calls** (one router
> function → one service method); **`_private` / `@staticmethod` helpers** are internal building blocks
> a public method composes, never called from a router.

---

## 0. Foundations (`app/services/base_service.py`, `exceptions.py`, `fuzzy_match.py`)

### `BaseService[ModelType]` (`base_service.py`)
Generic base every concrete service extends via `super().__init__(self.repository, entity_name=...)`.
Gives every module the same five operations for free, backed by whatever `BaseRepository` subclass the
concrete service constructs:

| Method | Purpose |
|---|---|
| `__init__(repository, entity_name="Entity")` | Stores the repository + a human-readable name used in `NotFoundError` messages |
| `get(id) -> ModelType` | Fetch by id or raise `NotFoundError(f"{entity_name} with id={id} not found")` |
| `get_all() -> List[ModelType]` | Unpaginated full list (small reference tables only) |
| `get_page(skip=0, limit=100) -> List[ModelType]` | Paginated list, used by every `GET /<resource>` list endpoint |
| `count() -> int` | Row count |
| `create(obj) -> ModelType` | Passthrough to `repository.create` |
| `update(obj) -> ModelType` | Passthrough to `repository.update` |
| `delete(id) -> None` | `get()` then `repository.delete()` — concrete services override this when a delete needs a business check first (e.g. `ReferencedEntityError`) |

### Exceptions (`exceptions.py`)
Four typed errors, all extending `ServiceError(message)`. See `HIGH_LEVEL_ARCHITECTURE.md §4.1` for the
HTTP status each maps to. Services never raise raw `Exception`/`HTTPException` — this is the only
vocabulary of failure the service layer speaks, which is what lets `error_handlers.py` map them
centrally instead of every router needing its own try/except.

### Fuzzy matching (`fuzzy_match.py`)
Stdlib-only (`difflib.SequenceMatcher`) first-pass text matcher, shared by `VendorQuotationService` and
`VendorInvoiceService` to route AI-parsed lines into "confidently mapped" vs. "needs human review".

| Symbol | Purpose |
|---|---|
| `ProductMatchCandidate(id, code, name)` | One thing a free-text description could match against — reused for both Products (quotations) and PurchaseOrderItems (invoices, keyed by `po_item.id` instead of a product id) |
| `ProductMatchResult(product_id, confidence)` | The outcome — `product_id` is `None` below threshold even though `confidence` is always populated, so a review UI can show "closest guess: 0.42" |
| `best_product_match(raw_description, candidates, threshold=0.55)` | Scores `raw_description` against every candidate's `name` and `code` (best of the two), returns the single best match; `product_id` only set if `confidence >= threshold` |

---

## 1. Master data services

### `UnitService` (`unit_service.py`)
Measurement units (KG, PCS, MTR...) that every `Product` is expressed in.

| Method | Purpose |
|---|---|
| `create_unit(data)` | Create, rejecting a duplicate `code` (`ConflictError`) |
| `update_unit(unit_id, data)` | Partial update |
| `delete_unit(unit_id)` | Delete, blocked if any `Product` still references it (`ReferencedEntityError`) |
| `activate(unit_id)` / `deactivate(unit_id)` | Toggle `ActiveMixin.is_active` |

### `ManufacturerService` (`manufacturer_service.py`)
"Who actually made this batch of stock" — distinct from `Supplier` (who it was bought from).

| Method | Purpose |
|---|---|
| `create(data)` | Create, rejecting a duplicate `code` |
| `update(manufacturer_id, data)` | Partial update |
| `delete(manufacturer_id)` | Blocked if any `Inventory`/`Supplier` still references it |
| `activate(manufacturer_id)` / `deactivate(manufacturer_id)` | Toggle active flag |
| `search(term)` | Name/code substring search, backs `?search=` on the list endpoint |

### `SupplierService` (`supplier_service.py`)
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

### `ProductService` (`product_service.py`)
Product master (`RAW`/`WIP`/`FG`), `reorder_level`/`reorder_quantity`/`preferred_supplier_id`.

| Method | Purpose |
|---|---|
| `validate_product(unit_id)` | Existence check on `unit_id` (name is a slight misnomer — validates the unit, not the product) |
| `validate_preferred_supplier(supplier_id)` | Existence check |
| `create_product(data)` | Create, rejecting duplicate `code`, validating `unit_id`/`preferred_supplier_id` |
| `update_product(product_id, data)` | Partial update, re-validates any changed FK |
| `delete_product(product_id)` | Blocked if any `Inventory` references it |
| `activate_product(product_id)` / `deactivate_product(product_id)` | Toggle active flag |
| `change_unit(product_id, unit_id)` | Dedicated unit-change endpoint (re-validates) |
| `search_products(term)` | Name/code substring search |

---

## 2. Warehousing services

All four follow the identical "one level of the hierarchy, parent-scoped" shape:
`Warehouse → Rack → Shelf → Bin`, assembled into a `Location` by `LocationService`.

### `WarehouseService` (`warehouse_service.py`)
| Method | Purpose |
|---|---|
| `create(data)` | Create, rejecting duplicate `code` |
| `update(warehouse_id, data)` | Partial update |
| `delete(warehouse_id)` | Blocked if it still has racks/locations |
| `add_rack(warehouse_id, code, description=None)` | Convenience: create a `Rack` scoped to this warehouse in one call |
| `remove_rack(rack)` | Delete a rack (used by `add_rack`'s sibling cleanup paths) |

### `RackService` (`rack_service.py`)
| Method | Purpose |
|---|---|
| `create(data)` | Create, `warehouse_id` required |
| `delete(rack_id)` | Blocked if it still has shelves/locations |
| `add_shelf(rack_id, code)` | Convenience: create a `Shelf` scoped to this rack |
| `remove_shelf(shelf)` | Delete a shelf |

### `ShelfService` (`shelf_service.py`)
| Method | Purpose |
|---|---|
| `create(data)` | Create, `rack_id` required |
| `delete(shelf_id)` | Blocked if it still has bins/locations |
| `add_bin(shelf_id, code)` | Convenience: create a `Bin` scoped to this shelf |
| `remove_bin(bin_)` | Delete a bin |

### `BinService` (`bin_service.py`)
| Method | Purpose |
|---|---|
| `create(data)` | Create, `shelf_id` required |
| `delete(bin_id)` | Blocked if any `Location` still references it |

### `LocationService` (`location_service.py`)
Assembles a `Warehouse`/`Rack`/`Shelf`/`Bin` combination into one addressable `Location`, and is the
only service that knows the hierarchy's validity rules.

| Method | Purpose |
|---|---|
| `validate_hierarchy(data)` | Enforces: a rack must belong to the given warehouse; a shelf must belong to the given rack; a bin must belong to the given shelf; `SHEET`/`PIPE`/`SCRAP` categories stop at rack level (no shelf/bin); oversized items may likewise stop at rack level |
| `get_location_path(data)` | Builds the human-readable path string, e.g. `WH1-A-03-05` or `WH1-A` for a rack-level location |
| `create_location(data)` | Validates hierarchy, rejects a duplicate path, creates |
| `update_location(location_id, data)` | Re-validates hierarchy on the new combination |
| `delete_location(location_id)` | Blocked if any `Inventory` still references it |

---

## 3. Inventory service

### `InventoryService` (`inventory_service.py`)
Owns **every** stock-movement rule. This is the service every procurement module (PR reservation, QC
acceptance) calls into rather than touching `Inventory` rows directly — see
`HIGH_LEVEL_ARCHITECTURE.md §5`.

| Method | Purpose |
|---|---|
| `validate_product(product_id)` / `validate_manufacturer(manufacturer_id)` / `validate_location(location_id)` | Existence checks on the three FKs a stock record needs |
| `validate_quantity(quantity)` | Rejects `<= 0` |
| `validate_inventory(data)` | Runs all of the above against an `InventoryCreate` payload |
| `get_location_display(inventory)` | Human-readable location path for a stock record (delegates to `LocationService`-equivalent logic) |
| `create_inventory(data)` | The seam: validates, creates the row, logs a `RECEIVE` transaction. **Called directly by `QualityInspectionService`** on QC accept/approved-deviation — no parallel "create stock" path exists anywhere else in the codebase |
| `update_inventory(inventory_id, data)` | Partial update of a stock record |
| `delete_inventory(inventory_id)` | Hard delete (no downstream references to check — `Inventory` is a leaf entity) |
| `receive_stock(data)` | Thin alias for `create_inventory` used by manual "receive stock" flows outside procurement |
| `issue_stock(inventory_id, quantity)` | Decrements quantity for an outbound movement, validates sufficient quantity available |
| `move_stock(inventory_id, new_location_id)` | Alias for `change_location` |
| `reserve_stock(inventory_id, quantity)` / `release_stock(inventory_id, quantity)` | Soft-reservation counters (e.g. against a Sales Order, not yet built) without physically moving stock |
| `change_status(inventory_id, status)` | Transitions `InventoryStatus` (`OK`/`RJC`/`MIS`/`RET`/`HLD`/`DMG`) |
| `change_location(inventory_id, new_location_id)` | Validates the new location, moves the record |
| `adjust_quantity(inventory_id, quantity_delta)` | Free-form +/- adjustment (stock count corrections) |
| `get_stock(inventory_id)` | Alias for `get()` |
| `get_by_product(product_id)` / `get_by_status(status)` / `get_by_location(location_id)` / `get_by_manufacturer(manufacturer_id)` | Filtered list queries |
| `get_available_stock(product_id)` | Sum of quantity across all `OK` records for a product (reservations aside) |
| `get_total_stock(product_id)` | Sum of quantity across all records regardless of status |
| `get_batch_stock(batch_number)` | All records sharing a batch number (traceability) |

---

## 4. Procurement chain services

These six services are the buy-side lifecycle, each one state-machine-driven and each one's terminal
action feeding the next service. Read them in this order — PR → RFQ → Quotation → PO → GRN → QC → Invoice.

### `PurchaseRequisitionService` (`purchase_requisition_service.py`)
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

### `RFQService` (`rfq_service.py`)
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

### `VendorQuotationService` (`vendor_quotation_service.py`)
A supplier's quoted price — manual entry (nested under an RFQ, or standalone for a routine buy) vs.
automation `ingest`. **State machine:** `PENDING_REVIEW`/`REVIEWED → SELECTED`/`REJECTED`
(`EXPIRED` reserved).

| Method | Purpose |
|---|---|
| `validate_supplier` / `validate_rfq` / `validate_product` | Existence checks |
| `_resolve_amount(quantity, rate, amount)` | `amount` if given, else `round(quantity * rate, 2)` — used on every line so a client can omit `amount` and trust server math |
| `_build_manual_item(item)` | Human entry: `product_id` **required**, no fuzzy matching |
| `_build_ingested_item(item, candidates)` | Automation entry: fuzzy-matches `raw_description` against `candidates` via `best_product_match`, stores `match_confidence` |
| `_product_candidates()` | Builds the `ProductMatchCandidate` list from all active products, for ingest to match against |
| `create_manual(rfq_id, data)` | Creates in `REVIEWED` (a human typed it, already trusted); if `rfq_id` set, calls `RFQService.mark_responded` |
| `ingest(data)` | **The only endpoint automation may call.** Always creates in `PENDING_REVIEW`; unmatched lines stay `product_id=NULL`; same `mark_responded` call if `rfq_id` set |
| `update_item(quotation_id, item_id, data)` | Review-queue correction: sets/overrides `product_id` (clearing `match_confidence` — a human override supersedes the fuzzy score), quantity/rate/amount |
| `review(quotation_id, reviewed_by)` | `PENDING_REVIEW → REVIEWED` |
| `select(quotation_id)` | `PENDING_REVIEW`/`REVIEWED → SELECTED`; **blocked while any line has `product_id=NULL`**; auto-rejects every other still-open quotation on the same RFQ (`get_selectable_siblings`) |
| `reject(quotation_id, rejected_by, rejection_reason)` | `PENDING_REVIEW`/`REVIEWED → REJECTED` |
| `get_by_status(status)` / `get_by_rfq(rfq_id)` | Filtered list queries |

### `PurchaseOrderService` (`purchase_order_service.py`)
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

*(`PARTIALLY_RECEIVED`/`RECEIVED` are set by `GoodsReceiptService`, not this service — see below.)*

### `GoodsReceiptService` (`goods_receipt_service.py`)
Records goods **physically arriving** against a `CONFIRMED` PO — deliberately independent of QC.
**State machine (`GoodsReceipt`):** `PENDING_QC → QC_IN_PROGRESS → CLOSED`.

| Method | Purpose |
|---|---|
| `_generate_grn_number()` | `GRN-{year}-{00001}` |
| `create_grn(data)` | Requires PO `CONFIRMED`/`PARTIALLY_RECEIVED`; per line, computes `variance_quantity` (received vs. what was still outstanding on that PO line), **updates `PurchaseOrderItem.received_quantity`/`line_status` and rolls `PurchaseOrder.status` to `PARTIALLY_RECEIVED`/`RECEIVED` immediately** — this is the one place PO receiving state actually changes; logs `GRN_CREATE` |
| `close_grn(grn_id)` | `QC_IN_PROGRESS → CLOSED`; requires a `QualityInspection` to already exist (i.e. not still `PENDING_QC`) |
| `get_by_status(status)` / `get_by_po(po_id)` | Filtered list queries |

### `QualityInspectionService` (`quality_inspection_service.py`)
QC pass over a `GoodsReceipt` — **the seam into `InventoryService`**. One GRN has at most one
`QualityInspection` (DB-unique `grn_id` + service check, same belt-and-braces pattern as
`PurchaseOrder.quotation_id`). **Header state (`QCDisposition`):** resolved automatically from line
dispositions, not set directly.

| Method | Purpose |
|---|---|
| `_generate_qc_number()` | `QC-{year}-{00001}` |
| `_resolve_manufacturer_id(grn, explicit_manufacturer_id)` | Explicit value wins; else falls back to `grn.po.supplier.manufacturer_id` |
| `_validate_stock_line(line, manufacturer_id)` | For `ACCEPT`/`DEVIATION` lines: requires `accepted_quantity > 0`, a valid `putaway_location_id`, and a resolvable `manufacturer_id` (422 if the supplier has no manufacturer link and none was passed explicitly) |
| `_create_inventory_for_line(grn, grn_item, qc_item)` | **Calls `InventoryService.create_inventory()`** with `batch_number = grn_item.vendor_batch_number or f"{grn.grn_number}-{grn_item.id}"`, `manufacturing_date = grn_item.manufacturing_date or date.today()`; stamps `qc_item.inventory_id` |
| `_resolve_overall_disposition(dispositions)` *(static)* | All `ACCEPT`→`ACCEPTED`; all `REJECT`→`REJECTED`; any `DEVIATION` with no `REJECT`→`ACCEPTED_WITH_DEVIATION`; any genuine mix→`PARTIAL` |
| `create_qc(data)` | Requires GRN `PENDING_QC` and not already inspected; per line: `ACCEPT` creates `Inventory` immediately; `REJECT` never does; `DEVIATION` only creates it immediately if `data.deviation_approved_by` was already supplied (pre-approved), otherwise **withholds** it; sets `GoodsReceipt.status = QC_IN_PROGRESS`; logs `QC_INSPECT` |
| `approve_deviation(qc_id, approved_by)` | For every still-unapproved `DEVIATION` line, calls `_create_inventory_for_line` now; stamps `deviation_approved_by`/`deviation_approved_at`; blocked if already approved or if there are no `DEVIATION` lines at all; logs `QC_DEVIATION_APPROVE` |
| `get_by_grn(grn_id)` | Lookup (also used internally to enforce the one-QC-per-GRN rule) |

### `VendorInvoiceService` (`vendor_invoice_service.py`)
The 3-way match: PO (what was agreed) vs. GRN (what arrived) vs. Invoice (what's being billed) —
purely financial, never touches `Inventory`. **State machine:** `PENDING_MATCH ⇄ MISMATCH → MATCHED →
APPROVED_FOR_PAYMENT → PAID` (`DISPUTED` reserved, no endpoint). `PENDING_MATCH` doubles as this
module's review-queue state — see `BUSINESS_DECISIONS.md`.

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
| `match(invoice_id, matched_by)` | The 3-way check itself — see `BUSINESS_DECISIONS.md §5` for the tolerance numbers and exact comparison logic; stores a full `match_report` JSON; sets `MATCHED`/`MISMATCH`; **re-runnable** from either starting state |
| `approve_payment(invoice_id, approved_by)` | `MATCHED → APPROVED_FOR_PAYMENT` only |
| `mark_paid(invoice_id, paid_by)` | `APPROVED_FOR_PAYMENT → PAID` only |
| `get_by_status(status)` / `get_by_po(po_id)` | Filtered list queries |

---

## 5. Procurement dashboard service

### `ProcurementDashboardService` (`procurement_dashboard_service.py`)
Read-only aggregation across every module above — backs `GET /procurement/kpis` and
`GET /procurement/reorder-suggestions`. Deliberately **not** a `BaseService[...]` subclass (owns no
single entity) and the one service in this codebase whose methods never call `log_transaction()` — a
dashboard view is a query, not a business event. Nothing here writes anything; everything is computed
live from current rows on each call (no caching/materialization — see the class docstring for the
tradeoff).

| Method | Purpose |
|---|---|
| `_overdue_purchase_orders()` | POs still `CONFIRMED`/`PARTIALLY_RECEIVED` whose `expected_delivery_date` has passed; a PO with no delivery date set, or one that's fully `RECEIVED`, is never counted |
| `get_kpis()` | `pending_prs` (count of `PRStatus.PENDING_APPROVAL`), `pos_awaiting_grn` (`CONFIRMED`+`PARTIALLY_RECEIVED`), `grns_awaiting_qc` (`GRNStatus.PENDING_QC`), `overdue_deliveries` (count + the actual PO ids) |
| `get_reorder_suggestions()` | Every active `Product` with a `reorder_level` set whose available stock (`InventoryRepository.get_available_stock_map()` — OK-status only, reserved quantity excluded, same definition `InventoryService` uses everywhere else) is at or below that threshold; products with no `reorder_level` configured are skipped, not assumed fine. Suggest-only — never creates a `PurchaseRequisition` |

## 6. Utility service

### `seed_service.py`
Not a `BaseService` subclass — a standalone loader that reads `app/data/seed_data.json` (units,
manufacturers, products, the warehouse hierarchy, and inventory records) and inserts them via the
regular services (so seeding goes through the same validation everything else does). Keeps "what data
does a fresh environment start with" out of Python code entirely — edit the JSON, not a script.

---

## 7. Repository layer (brief)

Every repository is a thin `BaseRepository[ModelType]` subclass — see `HIGH_LEVEL_ARCHITECTURE.md §3`.
`BaseRepository` provides `get`, `get_all`, `create`, `update`, `delete`, `exists`, `count`, `paginate`,
`filter`, `bulk_create`. Each concrete repository adds only what its service actually needs beyond that:

| Repository | Extra methods beyond `BaseRepository` |
|---|---|
| `PurchaseRequisitionRepository` | `count_for_year`, `get_by_status`, `get_by_department` |
| `RFQRepository` | `count_for_year`, `get_by_status` |
| `VendorQuotationRepository` | `get_by_status`, `get_by_rfq`, `get_by_supplier`, `get_selectable_siblings` |
| `PurchaseOrderRepository` | `count_for_year`, `get_by_status`, `get_by_supplier` |
| `GoodsReceiptRepository` | `count_for_year`, `get_by_status`, `get_by_po` |
| `QualityInspectionRepository` | `count_for_year`, `get_by_grn` |
| `VendorInvoiceRepository` | `get_by_status`, `get_by_po`, `get_by_supplier` |
| `InventoryRepository` | `get_by_product`, `get_by_status`, `get_by_location`, `get_by_manufacturer`, batch/available-quantity queries, `get_available_stock_map` (single grouped query, `{product_id: available_stock}` for every product — used by `ProcurementDashboardService.get_reorder_suggestions()` to avoid an N+1 query per product) |
| `LocationRepository` | Hierarchy-path lookups used by `LocationService.validate_hierarchy` |

No repository contains business rules — every conditional you see above the repository layer belongs
to the service that calls it.
