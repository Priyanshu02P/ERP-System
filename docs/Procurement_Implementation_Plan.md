# Procurement Module — Implementation Plan

**Project:** 26-07-19-ERP-System (Apex Precision Fabricators reference profile)
**Builds on:** existing Inventory/Warehouse module (FastAPI + SQLAlchemy + Postgres, layered `Router → Service → Repository → Model`)
**Core constraint from you:** n8n (and any other automation) must **never** touch Postgres directly. Every write/read — human or bot — goes through the same FastAPI `/api/v1` surface.

---

## 0. What this builds on (from your repo)

| Piece | What exists today |
|---|---|
| Pattern | `app/api` (routers) → `app/services` (business rules) → `app/db/repositories` (queries) → `app/db/models` (SQLAlchemy) → `app/db/schemas` (Pydantic) |
| Generics | `BaseRepository[ModelType]`, `BaseService[ModelType]` — CRUD + `NotFoundError` for free |
| Mixins | `IDMixin`, `TimestampMixin`, `ActiveMixin` |
| Audit log | `app/core/transaction_logger.py` → `backend/transaction.log`, one JSON line per business action, read via `GET /api/v1/logs` |
| Errors | `NotFoundError` (404), `ConflictError`/`ReferencedEntityError` (409), `ValidationError` (422) — centrally handled |
| Existing masters | `Unit`, `Manufacturer` (code/name/address/contact_info — currently used as "who made this batch" on `Inventory`), `Product` (RAW/WIP/FG), `Warehouse→Rack→Shelf→Bin→Location` |
| Auth | **None.** Every route is open. |
| n8n | `docker-compose.yml` gives n8n its own tables in `inventory_db` for n8n's *internal* state (workflow defs/executions) — that's normal and fine. The Telegram invoice-OCR workflow itself only does Telegram → Mistral OCR → reply-to-Telegram right now; it never calls your API or DB. |

Two decisions worth flagging before the data model, because they shape everything below:

1. **`Manufacturer` ≠ `Supplier`.** In your schema, `Manufacturer` is wired to `Inventory` as "who made this batch" (e.g. Tata Steel). In procurement, a Purchase Order goes to a *vendor* (e.g. "Tata Steel Distributor"), which may not be the same entity — exactly like the company profile's vendor list (`Tata Steel Distributor`, `JSW Steel`, `Steel Authority Dealer`). So this plan introduces a new `Supplier` master rather than overloading `Manufacturer`, with an optional link between them.
2. **Automation identity, not just automation transport.** "Use APIs instead of DB" solves *how* n8n talks to the system. It doesn't solve *who* n8n is when it does. Since there's currently zero auth, I'm adding a minimal API-key gate as part of this module — procurement is the first place real money and vendor commitments show up, so it's the right place to stop being wide open.

---

## 1. Architecture rule: API-first for automation

```
Human (browser, frontend/index.html)  ─┐
                                        ├──►  FastAPI /api/v1  ──►  Service layer  ──►  Postgres
n8n workflows (Telegram/WhatsApp/OCR) ─┘         (validation, transaction_logger,
                                                   state transitions all live here)
```

Concrete rules to enforce this, not just state it:

- **n8n gets its own database, not `inventory_db`.** Today's `docker-compose.yml` sets n8n's `DB_TYPE: postgresdb` pointing at `inventory_db`. Change this to either (a) a separate `n8n_db` database on the same Postgres server, or (b) simplest for your scale — drop the `DB_TYPE`/`DB_POSTGRESDB_*` block entirely so n8n falls back to its bundled SQLite for its own internal state. Either way, **no n8n credential in the n8n UI should ever point at `inventory_db`.**
- **Every n8n workflow node that reads/writes procurement data is an `httpRequest` node hitting `/api/v1/...`.** Never a Postgres/Supabase node. This is the enforceable version of your instruction — a code-review rule for any workflow JSON you add.
- **The API is the only place business rules live.** State transitions (e.g. "can't approve a PO that's already CLOSED"), quantity math, and transaction logging happen once, in the service layer — so a PR created by a purchase manager in the UI and a PR auto-raised by a reorder-level bot are validated identically.
- **Ingest endpoints for AI-parsed data are explicitly separate from human-entry endpoints**, and land in a `PENDING_REVIEW` state (see §5) — an OCR misread should never silently become a real PO or real stock.

---

## 2. New domain model

Text ERD (new entities only; arrows show FK direction):

```
Supplier ──┬──────────────────────────────────────────────────────────────┐
           │                                                               │
Product ───┼── PurchaseRequisitionItem ── PurchaseRequisition              │
           │                                        │                     │
           │                                    (approved)                │
           │                                        ▼                     │
           ├── RFQItem ── RFQ ── RFQSupplier ───────────────────────────► Supplier
           │                       │
           │                       ▼
           ├── QuotationItem ── VendorQuotation ─────────────────────────► Supplier
           │                       │ (selected)
           │                       ▼
           ├── PurchaseOrderItem ── PurchaseOrder ────────────────────────► Supplier
           │                       │
           │                       ▼
           │                 GoodsReceiptItem ── GoodsReceipt
           │                       │
           │                       ▼
           │              QualityInspectionItem ── QualityInspection
           │                       │ (accepted)
           │                       ▼
           └────────────────►  Inventory   (existing table — reused, not duplicated)

VendorInvoiceItem ── VendorInvoice ──► PurchaseOrder, GoodsReceipt, Supplier
```

### 2.1 `Supplier` (new master)

Mirrors `Manufacturer`'s style, extended for procurement:

- `code`, `name`, `gstin`, `address`, `contact_person`, `phone`, `email`
- `category` (string or enum: STEEL / HARDWARE / POWDER_COATING / PACKAGING / LOGISTICS / CONSUMABLES / OTHER)
- `default_payment_terms` (string, e.g. "30% Advance, 70% on Delivery")
- `manufacturer_id` (nullable FK → `manufacturers.id`) — links a distributor to the brand it represents, when relevant
- `is_active` (`ActiveMixin`)

### 2.2 `Product` — two additive columns

To support "automatic purchase suggestions from reorder levels" (from your AI features list):

- `reorder_level: float | None`
- `reorder_quantity: float | None`
- `preferred_supplier_id: int | None` (FK → `suppliers.id`)

### 2.3 Purchase Requisition

- **`PurchaseRequisition`**: `pr_number` (unique, e.g. `PR-2026-00847`), `status` (`PRStatus`), `priority` (`NORMAL`/`URGENT`), `department`, `raised_by`, `required_by_date`, `reason`, `source` (`SourceChannel`), `approved_by`, `approved_at`
- **`PurchaseRequisitionItem`**: `pr_id`, `product_id`, `quantity`, `current_stock_snapshot` (captured at creation, for audit — mirrors the "current stock" column in the sample PR doc), `notes`

### 2.4 RFQ

- **`RFQ`**: `rfq_number`, `pr_id` (nullable — routine buys may skip PR), `status` (`RFQStatus`), `due_date`, `delivery_location`
- **`RFQItem`**: `rfq_id`, `product_id`, `quantity`, `required_delivery_date`
- **`RFQSupplier`** (join table): `rfq_id`, `supplier_id`, `sent_at`, `sent_channel` (`EMAIL`/`WHATSAPP`/`TELEGRAM`/`API`), `response_status` (`SENT`/`RESPONDED`/`NO_RESPONSE`)

### 2.5 Vendor Quotation

- **`VendorQuotation`**: `rfq_id` (nullable), `supplier_id`, `vendor_quotation_no`, `quotation_date`, `validity_date`, `payment_terms`, `delivery_lead_time_days`, `status` (`QuotationStatus`), **`source`** (`MANUAL`/`OCR_BOT`/`WHATSAPP_BOT`/`EMAIL_PARSER`), **`source_confidence`** (float, nullable), `raw_document_url`, `reviewed_by`, `reviewed_at`
- **`QuotationItem`**: `quotation_id`, `product_id` (**nullable**), `raw_description` (always stored, as extracted), `quantity`, `rate`, `gst_rate`, `amount`, `match_confidence`

  **Why `product_id` is nullable:** an AI parser reads "CRCA Sheet 2mmx1250x2500" off a vendor PDF — it doesn't know your internal product codes. The ingest endpoint does a first-pass fuzzy match against `products.name`/`code`; anything unmatched or below a confidence threshold stays `product_id = NULL` and shows up in a "needs mapping" review queue. A quotation can't be `SELECTED` (→ converted to a PO) until every line is mapped.

### 2.6 Purchase Order

- **`PurchaseOrder`**: `po_number`, `quotation_id` (nullable), `pr_id` (nullable), `supplier_id`, `status` (`POStatus`), `order_date`, `expected_delivery_date`, `payment_terms`, `subtotal`, `gst_amount`, `total_amount`, `approved_by`, `approved_at`
- **`PurchaseOrderItem`**: `po_id`, `product_id`, `quantity`, `rate`, `gst_rate`, `amount`, `received_quantity` (running total, updated on each GRN), `line_status` (`PENDING`/`PARTIAL`/`COMPLETE`)

### 2.7 Goods Receipt Note (GRN)

- **`GoodsReceipt`**: `grn_number`, `po_id`, `vendor_invoice_ref`, `vehicle_number`, `received_by`, `received_at`, `status` (`GRNStatus`), `overall_condition`
- **`GoodsReceiptItem`**: `grn_id`, `po_item_id`, `received_quantity`, `variance_quantity` (computed), `vendor_batch_number` (nullable), `manufacturing_date` (nullable — see §4), `remarks`

### 2.8 Quality Inspection (QC)

- **`QualityInspection`**: `qc_number`, `grn_id`, `inspector`, `inspected_at`, `overall_disposition` (`QCDisposition`), `deviation_approved_by` (nullable)
- **`QualityInspectionItem`**: `qc_id`, `grn_item_id`, `parameter_results` (JSON — list of `{parameter, spec, observed, result}`, matches the sample QC doc's table), `disposition` (`ACCEPT`/`REJECT`/`DEVIATION`), `accepted_quantity`, `rejected_quantity`, `putaway_location_id` (FK → `locations.id`), `manufacturer_id` (FK → `manufacturers.id`, defaults from `supplier.manufacturer_id` but overridable — needed because `Inventory.manufacturer_id` is non-nullable)

### 2.9 Vendor Invoice (3-way match)

- **`VendorInvoice`**: `vendor_invoice_no`, `supplier_id`, `po_id`, `grn_id` (nullable), `invoice_date`, `subtotal`, `gst_amount`, `total_amount`, `status` (`InvoiceStatus`), `source`, `source_confidence`, `raw_document_url`, `match_report` (JSON), `matched_by`, `matched_at`
- **`VendorInvoiceItem`**: `invoice_id`, `po_item_id` (nullable), `description`, `quantity`, `rate`, `gst_rate`, `amount`

### 2.10 New enums (add to `app/db/models/enums.py`)

```python
class PRStatus(str, enum.Enum):
    DRAFT = "DRAFT"; PENDING_APPROVAL = "PENDING_APPROVAL"; APPROVED = "APPROVED"
    REJECTED = "REJECTED"; CONVERTED = "CONVERTED"; CLOSED = "CLOSED"

class PRPriority(str, enum.Enum):
    NORMAL = "NORMAL"; URGENT = "URGENT"

class RFQStatus(str, enum.Enum):
    DRAFT = "DRAFT"; SENT = "SENT"; RESPONSES_RECEIVED = "RESPONSES_RECEIVED"
    CLOSED = "CLOSED"; CANCELLED = "CANCELLED"

class QuotationStatus(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"; REVIEWED = "REVIEWED"
    SELECTED = "SELECTED"; REJECTED = "REJECTED"; EXPIRED = "EXPIRED"

class POStatus(str, enum.Enum):
    DRAFT = "DRAFT"; SENT = "SENT"; CONFIRMED = "CONFIRMED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"; RECEIVED = "RECEIVED"
    CLOSED = "CLOSED"; CANCELLED = "CANCELLED"

class GRNStatus(str, enum.Enum):
    PENDING_QC = "PENDING_QC"; QC_IN_PROGRESS = "QC_IN_PROGRESS"; CLOSED = "CLOSED"

class QCDisposition(str, enum.Enum):
    ACCEPTED = "ACCEPTED"; ACCEPTED_WITH_DEVIATION = "ACCEPTED_WITH_DEVIATION"
    REJECTED = "REJECTED"; PARTIAL = "PARTIAL"

class InvoiceStatus(str, enum.Enum):
    PENDING_MATCH = "PENDING_MATCH"; MATCHED = "MATCHED"; MISMATCH = "MISMATCH"
    APPROVED_FOR_PAYMENT = "APPROVED_FOR_PAYMENT"; PAID = "PAID"; DISPUTED = "DISPUTED"

class SourceChannel(str, enum.Enum):
    MANUAL = "MANUAL"; WHATSAPP_BOT = "WHATSAPP_BOT"; TELEGRAM_BOT = "TELEGRAM_BOT"
    EMAIL_PARSER = "EMAIL_PARSER"; API = "API"; AUTO_REORDER = "AUTO_REORDER"
```

Migration: one Alembic revision adding all new tables + the two `products` columns, following your existing `alembic revision --autogenerate -m "add procurement tables"` flow (you already have two prior revisions, so this is just the next one).

---

## 3. API surface (all under `/api/v1`, same router style as today)

| Resource | Endpoints |
|---|---|
| Suppliers | `POST/GET/PUT/DELETE /suppliers`, `/{id}/activate`, `/{id}/deactivate`, `?search=`, `?category=`, `GET /suppliers/{id}/scorecard` |
| Purchase Requisitions | `POST/GET/PUT /purchase-requisitions`, `/{id}/submit`, `/{id}/approve`, `/{id}/reject`, `?status=&department=` |
| RFQs | `POST/GET /rfqs`, `/{id}/send`, `/{id}/close` |
| Quotations | `POST /rfqs/{id}/quotations` (human entry), **`POST /quotations/ingest`** (automation entry — see §5), `GET /rfqs/{id}/quotations` (comparison view), `/{id}/select`, `/{id}/reject` |
| Purchase Orders | `POST/GET/PUT /purchase-orders`, `/{id}/send`, `/{id}/confirm`, `/{id}/cancel` |
| Goods Receipts | `POST/GET /goods-receipts`, `/{id}/close` |
| Quality Inspections | `POST/GET /quality-inspections`, `/{id}/approve-deviation` |
| Vendor Invoices | `POST /vendor-invoices` (manual), **`POST /vendor-invoices/ingest`** (automation), `/{id}/match`, `/{id}/approve-payment`, `/{id}/mark-paid` |
| Dashboard ✅ | `GET /procurement/kpis` (pending PRs, POs awaiting GRN, GRNs awaiting QC, overdue deliveries), `GET /procurement/reorder-suggestions` — **delivered**, see §15 below |

Every write endpoint logs to `transaction_logger` with new `TransactionAction` values (`PR_CREATE`, `PR_APPROVE`, `RFQ_SENT`, `QUOTATION_INGEST`, `PO_ISSUED`, `PO_CONFIRMED`, `GRN_RECEIVED`, `QC_INSPECTED`, `INVOICE_MATCHED`, ...), same JSON-lines pattern as today, so `/api/v1/logs` and the future Activity Logs UI tab pick it up for free.

---

## 4. GRN/QC → Inventory integration (the important seam)

Rather than a second "create stock" code path, QC acceptance calls into the **existing** `InventoryService`:

```python
# in a new QualityInspectionService, on an ACCEPT/ACCEPTED_WITH_DEVIATION line:
inventory_data = InventoryCreate(
    product_id=grn_item.po_item.product_id,
    manufacturer_id=qc_item.manufacturer_id,          # resolved from supplier link or set explicitly
    location_id=qc_item.putaway_location_id,
    batch_number=grn_item.vendor_batch_number or f"{grn.grn_number}-{grn_item.id}",
    manufacturing_date=grn_item.manufacturing_date or date.today(),
    quantity=qc_item.accepted_quantity,
    status=InventoryStatus.OK,
)
inventory = InventoryService(self.db).create_inventory(inventory_data)
```

This reuses your existing validation, `RECEIVE` transaction log entry, and available-quantity logic untouched — procurement becomes a *source* of stock, not a parallel system. Rejected/deviation-pending lines simply don't call this, keeping "physically received" (GRN) separate from "usable stock" (Inventory), exactly like your current `OK`/`HLD`/`DMG` status split already implies.

---

## 5. Human input vs. automated input — the review-queue pattern

Since AI-parsed quotations and invoices can misread a number, they never write directly into an authoritative record:

- `POST /quotations/ingest` and `POST /vendor-invoices/ingest` are the **only** endpoints n8n calls to create these records. They accept the same shape as the human-entry endpoints plus `source` and `source_confidence`, and always create the record in `PENDING_REVIEW`.
- A purchase officer reviews via `GET /quotations?status=PENDING_REVIEW` (or a "Needs Review" tab in the UI), corrects any unmatched `product_id`/amounts, then calls `/quotations/{id}/select` (or the invoice equivalent) — which is the point business rules (state transitions, matching) actually apply.
- Nothing downstream (PO generation, inventory, payment approval) ever reads a `PENDING_REVIEW` record.

This is the same pattern your QC module already uses for `ACCEPTED_WITH_DEVIATION` (machine/inspector flags it, a human approves) — so it's consistent with how the rest of the app already handles "trust but verify."

---

## Decisions locked in

- **Approval:** manual approve/reject only on PR and PO — no value-threshold auto-approval for now.
- **Supplier vs. Manufacturer:** kept fully separate, as designed in §2.1.
- **Sales order link:** `PurchaseRequisition.linked_sales_order` stays a free-text field — no FK, since a Sales Order module isn't built yet.
- **Auth (§6, original plan):** out of scope for this module. RBAC is planned separately later; nothing here should assume or block on it. The `/ingest` endpoints (§5) are still separated from human-entry endpoints and land in `PENDING_REVIEW` — that review-queue pattern is about data trust, not access control, so it stands regardless of when auth lands.

---

## 6. n8n workflow changes ✅ (delivered, see §15 below)

- **Fix `docker-compose.yml` first** (§1) — remove n8n's `DB_TYPE: postgresdb` block pointing at `inventory_db`, or give it a separate `n8n_db`.
- **Extend the existing invoice-OCR workflow**: after its `Parse Final Invoice JSON` node, add an `httpRequest` node → `POST {API_BASE_URL}/api/v1/vendor-invoices/ingest`, alongside (not instead of) the current Telegram reply — so the human still sees the OCR result in chat, and it also lands in the review queue.
- **New workflow — Quotation OCR**: same Telegram/WhatsApp-trigger + Mistral-OCR pattern, posting to `POST /quotations/ingest` instead.
- **New workflow — RFQ broadcast**: triggered by `POST /rfqs/{id}/send` (or n8n polls `GET /rfqs?status=DRAFT` on a schedule) → sends WhatsApp/Telegram/email to each `RFQSupplier`.
- **New workflow — vendor PO confirmation bot**: vendor replies "confirmed" on WhatsApp/Telegram → `httpRequest` → `POST /purchase-orders/{id}/confirm`.
- **New workflow — reorder digest**: scheduled trigger → `GET /procurement/reorder-suggestions` → WhatsApp/Telegram digest to the purchase manager; a reply/button can call `POST /purchase-requisitions` with `source=AUTO_REORDER`.

Every one of these has exactly one shape of "database access": an `httpRequest` node against your API. That's the rule to hold every future workflow to. No API-key gate is being added yet (see decisions above), but the `/ingest` vs. human-entry endpoint split stays regardless.

---

## 7. Testing

Mirrors `backend/tests/` conventions (in-memory SQLite via `conftest.py`'s `db_session` fixture):

- `test_procurement_service.py` — PR/RFQ/PO state-transition rules (e.g. can't approve an already-approved PR, can't send an RFQ with no line items)
- `test_grn_qc_flow.py` — integration test: PR → RFQ → quotation → select → PO → GRN → QC accept → assert an `Inventory` row now exists with the right qty/location, and that a rejected line does **not** create one
- `test_invoice_matching.py` — 3-way match logic: matching PO/GRN/invoice → `MATCHED`; quantity mismatch beyond tolerance → `MISMATCH`
- `test_quotation_ingest.py` — ingest endpoint creates `PENDING_REVIEW` records; unmatched line descriptions stay `product_id=None`; `/select` blocked while any line is unmapped

---

## 8. Suggested build order — Phases 1–6 done ✅

| Phase | Scope |
|---|---|
| **1** ✅ | `Supplier` master + `Product.reorder_level/reorder_quantity/preferred_supplier_id` + Alembic migration — **delivered**, see §9 below |
| **2** ✅ | PR module (model, service, API, tests) — pure manual CRUD + approval, no automation yet — **delivered**, see §10 below |
| **3** ✅ | RFQ + Vendor Quotation (manual entry first), including the review-queue pattern and fuzzy product matching — **delivered**, see §11 below |
| **4** ✅ | Purchase Order lifecycle (from selected quotation or manual), state machine + transaction logging — **delivered**, see §12 below |
| **5** ✅ | GRN + QC, wired into `InventoryService.create_inventory` (§4) — this is the phase that actually connects procurement to your existing inventory module — **delivered**, see §13 below |
| **6** ✅ | Vendor Invoice + 3-way match — **delivered**, see §14 below |
| **7** | Fix `docker-compose.yml` for n8n's own DB (§6) |
| **8** | n8n workflows: extend invoice-OCR to call `/vendor-invoices/ingest`, add quotation-OCR, RFQ-broadcast, PO-confirmation, reorder-digest workflows |
| **9** | `GET /procurement/kpis` + a "Procurement" tab in `frontend/index.html`, following the existing Inventory tab's structure (stats cards, filterable table, action modals) — same API endpoints the bots use, so this is mostly UI work by this point |

Phases 1–6 can be built and tested with zero n8n involvement (Postman/curl, same as your current setup) — automation only gets layered on in 7–8, once the underlying API is solid. That ordering also means the "no DB access for n8n" rule is easy to enforce: there's simply nothing for n8n to call until the API exists.

---

## 9. Phase 1 — what was actually built

All following your existing `Router → Service → Repository → Model` pattern exactly, with tests in the same in-memory-SQLite style as `tests/conftest.py`.

**New files:**
- `app/db/models/supplier.py` — `Supplier` model
- `app/db/repositories/supplier_repository.py`
- `app/services/supplier_service.py`
- `app/db/schemas/supplier.py`
- `app/api/supplier.py`
- `alembic/versions/3eb23937e4f0_add_suppliers_and_product_reorder_fields.py`
- `tests/test_supplier_service.py`

**Modified files:**
- `app/db/models/enums.py` — added `SupplierCategory`
- `app/db/models/__init__.py` — registered `Supplier`
- `app/db/models/manufacturer.py` — added reverse `suppliers` relationship
- `app/db/models/product.py` — added `reorder_level`, `reorder_quantity`, `preferred_supplier_id` + relationship
- `app/db/schemas/product.py` — exposed the new fields
- `app/services/product_service.py` — validates `preferred_supplier_id` against the `Supplier` table
- `app/main.py` — registered the supplier router
- `tests/test_product_service.py` — added reorder-field and preferred-supplier tests
- `README.md` — API overview + a domain-model note on Supplier vs. Manufacturer

**Verified, not just written:** full `pytest` run (23/23 passing, including all pre-existing tests), plus a live `TestClient` smoke test hitting the actual HTTP endpoints — create manufacturer → create supplier linked to it → create product with `reorder_level`/`preferred_supplier_id` → category filter → search → delete blocked by `ReferencedEntityError` (409) → invalid `manufacturer_id` rejected (422).

**Deliberately not done in Phase 1** (belongs to later phases per the table above): the actual "which products are below reorder level" query — that needs to join `Product.reorder_level` against live `Inventory.available_quantity`, which is PR-module territory (Phase 2), not supplier-master territory. The columns are in place and validated; the reorder-suggestion logic gets built on top of them next.

---

## 10. Phase 2 — what was actually built

**New files:**
- `app/db/models/purchase_requisition.py` — `PurchaseRequisition` + `PurchaseRequisitionItem`
- `app/db/repositories/purchase_requisition_repository.py`
- `app/services/purchase_requisition_service.py` — the state machine lives here
- `app/db/schemas/purchase_requisition.py`
- `app/api/purchase_requisition.py`
- `alembic/versions/590830d22a78_add_purchase_requisition_tables.py`
- `tests/test_purchase_requisition_service.py`

**Modified files:**
- `app/db/models/enums.py` — added `PRStatus`, `PRPriority`, `SourceChannel`
- `app/db/models/__init__.py` — registered the two new models
- `app/core/transaction_logger.py` — added `PR_CREATE`, `PR_ITEM_ADD`, `PR_ITEM_REMOVE`, `PR_SUBMIT`, `PR_APPROVE`, `PR_REJECT`, `PR_DELETE`
- `app/main.py` — registered the router

**State machine implemented:** `DRAFT → PENDING_APPROVAL → APPROVED / REJECTED`, manual approval only (per your decision — no value threshold). `CONVERTED` and `CLOSED` stay unused until Phase 3/4 (RFQ/PO) exist to set them — the enum values are there so those phases don't need a migration to add them later.

**Business rules enforced by the service, not just the schema:**
- `pr_number` auto-generated as `PR-{year}-{00001}`, sequential per year
- Every line item's `current_stock_snapshot` is captured live from `InventoryService.get_available_stock()` at creation/add time — this is the existing Inventory module being *read from*, same principle as §4's GRN/QC write-path
- Items can only be added/removed while `DRAFT`; a PR can't be submitted with zero items; the last remaining item can't be removed
- Header fields (`department`, `priority`, `required_by_date`, etc.) can only be edited while `DRAFT`
- Delete is only allowed while `DRAFT` — once submitted, the audit trail is `reject`, not delete
- `approve`/`reject` both require `PENDING_APPROVAL` status and record who + when (`approved_by`/`approved_at` or `rejected_by`/`rejected_at`/`rejection_reason`)

**Verified:** 45/45 `pytest` passing (23 from Phase 1 + 22 new, nothing broken), plus an HTTP-level `TestClient` walk through the full lifecycle — create → reject-before-submit blocked (409) → add item → submit → edit-after-submit blocked (409) → approve → filter by status → a second PR through the reject path → confirmed every step landed in `transaction.log` under its own `PR_*` action.

---

## 11. Phase 3 — what was actually built

**New files:**
- `app/db/models/rfq.py` — `RFQ`, `RFQItem`, `RFQSupplier` (the send/response-tracking join table)
- `app/db/models/vendor_quotation.py` — `VendorQuotation`, `QuotationItem`
- `app/db/repositories/rfq_repository.py`, `app/db/repositories/vendor_quotation_repository.py`
- `app/services/rfq_service.py` — RFQ state machine
- `app/services/vendor_quotation_service.py` — manual entry, ingest, review queue, select/reject
- `app/services/fuzzy_match.py` — stdlib-`difflib` best-match helper used by ingest (no new dependency)
- `app/db/schemas/rfq.py`, `app/db/schemas/vendor_quotation.py`
- `app/api/rfq.py`, `app/api/vendor_quotation.py`
- `alembic/versions/6f1a2d9c4e57_add_rfq_and_vendor_quotation_tables.py`
- `tests/test_rfq_service.py`, `tests/test_vendor_quotation_service.py`, `tests/test_quotation_ingest.py`

**Modified files:**
- `app/db/models/enums.py` — added `RFQStatus`, `SendChannel`, `RFQResponseStatus`, `QuotationStatus`; added `OCR_BOT` to `SourceChannel`
- `app/db/models/__init__.py` — registered the four new models
- `app/core/transaction_logger.py` — added `RFQ_CREATE`, `RFQ_SEND`, `RFQ_CLOSE`, `QUOTATION_CREATE`, `QUOTATION_INGEST`, `QUOTATION_ITEM_UPDATE`, `QUOTATION_REVIEW`, `QUOTATION_SELECT`, `QUOTATION_REJECT`
- `app/main.py` — registered both routers
- `README.md` — API overview extended for PR (missed in Phase 2) + RFQ/Quotation, plus a domain-model note on the review-queue pattern

**State machines implemented:**
- **RFQ:** `DRAFT → SENT → RESPONSES_RECEIVED → CLOSED`. `RFQSupplier` rows (who it was sent to, over which channel) are created at `/send`, not at RFQ creation — a DRAFT RFQ is just items with no recipients yet. `mark_responded()` is called internally whenever a quotation is created against an RFQ, flipping that supplier's `response_status` to `RESPONDED` and advancing the RFQ to `RESPONSES_RECEIVED` on the first response. `/close` sweeps any suppliers still sitting at `SENT` to `NO_RESPONSE`. `CANCELLED` stays unused for now, same reasoning as `PRStatus.CONVERTED/CLOSED` in Phase 2.
- **VendorQuotation:** human entry (`POST /rfqs/{id}/quotations` or `POST /quotations`) starts `REVIEWED` directly — a person already picked the `product_id`, so there's nothing to review. Automation entry (`POST /quotations/ingest`, the *only* endpoint n8n may call per §5) always starts `PENDING_REVIEW`. `/{id}/review` moves `PENDING_REVIEW → REVIEWED`. `/{id}/select` is blocked with a `ValidationError` if any line still has `product_id = NULL`, and on success auto-rejects every other open (`PENDING_REVIEW`/`REVIEWED`) quotation on the same RFQ. `/{id}/reject` is available from either open state.

**Fuzzy matching (the §5 review-queue mechanism, concretely):**
- `app/services/fuzzy_match.best_product_match()` scores an ingested line's `raw_description` against every active product's `name` and `code` using `difflib.SequenceMatcher`, taking the best of the two per candidate. Deliberately stdlib-only — this is a first-pass filter to route lines into "confidently mapped" vs. "needs a human," not a production search index.
- Above the default 0.55 confidence threshold, `product_id` is set and `match_confidence` is recorded; below it, `product_id` stays `NULL` and the (still-recorded) confidence lets a review UI show "closest guess: 0.42" instead of nothing.
- A human corrects an unmatched or misread line via `PUT /quotations/{id}/items/{item_id}` (`QuotationItemUpdate`); supplying a `product_id` there clears `match_confidence`, since it's now a human decision, not a machine guess.

**A design deviation worth flagging:** the plan's `VendorQuotation.source` enum was going to reuse the PR module's existing `source_channel` Postgres type. Adding `OCR_BOT` to that type in-place would need `ALTER TYPE ... ADD VALUE`, and Postgres won't let a migration use a newly added enum value within the same transaction that added it — so the same migration that adds `OCR_BOT` couldn't also create a table using it. Rather than split this into two migrations, `VendorQuotation.source` uses its own Postgres enum type (`quotation_source_channel`, same Python values) — a cheap way to sidestep a real Postgres constraint. Noted in both the model and the migration.

**Verified:** 71/71 `pytest` passing (45 from Phases 1–2 + 26 new, nothing broken), plus an HTTP-level `TestClient` walk through the full lifecycle — create RFQ → send to a supplier → manual quotation entry (starts `REVIEWED`) → automation ingest with a fuzzy-matched line (`confidence 0.7`, mapped automatically) → filter the review queue by `PENDING_REVIEW` → select the manual quotation → confirmed the RFQ flipped to `RESPONSES_RECEIVED` and the supplier's response status to `RESPONDED` → re-`/send` blocked (409, already past `DRAFT`) → confirmed every step landed in `transaction.log` under its own `RFQ_*`/`QUOTATION_*` action.

**Deliberately not done in Phase 3** (belongs to Phase 4 per the table above): converting a `SELECTED` quotation into a `PurchaseOrder`. `VendorQuotationService.select()` stops at marking the quotation `SELECTED` and auto-rejecting its siblings — it doesn't create anything downstream, since `PurchaseOrder`/`PurchaseOrderItem` don't exist yet. That seam (`quotation_id` → new PO) is exactly what Phase 4 builds on top of.

---

## 12. Phase 4 — what was actually built

**New files:**
- `app/db/models/purchase_order.py` — `PurchaseOrder`, `PurchaseOrderItem`
- `app/db/repositories/purchase_order_repository.py`
- `app/services/purchase_order_service.py` — the state machine + quotation→PO conversion logic lives here
- `app/db/schemas/purchase_order.py`
- `app/api/purchase_order.py`
- `alembic/versions/b4d8e1a9f2c3_add_purchase_order_tables.py`
- `tests/test_purchase_order_service.py`

**Modified files:**
- `app/db/models/enums.py` — added `POStatus`, `POLineStatus`
- `app/db/models/__init__.py` — registered the two new models
- `app/core/transaction_logger.py` — added `PO_CREATE`, `PO_UPDATE`, `PO_SEND`, `PO_CONFIRM`, `PO_CANCEL`
- `app/main.py` — registered the router
- `README.md` — API overview extended for Purchase Orders

**State machine implemented:** `DRAFT → SENT → CONFIRMED`, plus `CANCELLED` from either `DRAFT` or `SENT`. `PARTIALLY_RECEIVED`/`RECEIVED`/`CLOSED` stay unused until the GRN module (Phase 5) exists to set them as goods are received against the PO — same reasoning as `PRStatus.CONVERTED/CLOSED` and `RFQStatus.CANCELLED` before it. `PurchaseOrderItem.received_quantity`/`line_status` are likewise present but untouched (`0`/`PENDING`) until then.

**A deliberate simplification of the approval model:** unlike `PurchaseRequisition`, `POStatus` has no separate `PENDING_APPROVAL` state, so there's no standalone `/approve` endpoint (matching §3's endpoint list, which only lists `/send`, `/confirm`, `/cancel`). Instead, `/send` *is* the approval step — it requires an `approved_by` and moves `DRAFT → SENT` in one action, recording `approved_by`/`approved_at`. This still satisfies the "manual approve... on PR **and PO**" decision from §"Decisions locked in" without inventing an unlisted state: sending a PO to a vendor is the point real money and vendor commitment happen, so approval and dispatch being the same action is a closer match to how procurement actually works here than a separate pending-approval queue would be.

**Business rules enforced by the service, not just the schema:**
- `po_number` auto-generated as `PO-{year}-{00001}`, sequential per year, same pattern as `PR-`/`RFQ-`
- `POST /purchase-orders` branches on `quotation_id`:
  - **From a quotation**: the quotation must be `SELECTED` (409 otherwise) and not already converted (409 on a second attempt — enforced both by a DB-level unique constraint on `purchase_orders.quotation_id` and a service-level check for a clean error message); `supplier_id` and all line items (`product_id`/`quantity`/`rate`/`gst_rate`/`amount`) are copied from the quotation's own (already-mapped) lines; `payment_terms` defaults from the quotation's `payment_terms` unless overridden; `pr_id` is auto-derived from `quotation.rfq.pr_id` when the quotation traces back to an RFQ raised from a PR, unless explicitly overridden
  - **Manual**: `supplier_id` and `items` are required (schema-level validator), each `product_id` is checked against the product master
- `subtotal`/`gst_amount`/`total_amount` are computed server-side from the line items (`amount = quantity × rate` per line unless supplied; `gst_amount` summed per-line at each line's own `gst_rate`) — never trusted from the client
- Header fields (`order_date`, `expected_delivery_date`, `payment_terms`) can only be edited via `PUT /purchase-orders/{id}` while `DRAFT`
- `/send` requires at least one item and `DRAFT` status; `/confirm` requires `SENT`; `/cancel` requires `DRAFT` or `SENT` (once `CONFIRMED` or receiving has started, cancellation is blocked — a GRN-aware cancel/return path is Phase 5+ territory)

**Verified:** 89/89 `pytest` passing (71 from Phases 1–3 + 18 new, nothing broken), plus an HTTP-level `TestClient` walk through the full lifecycle — manual quotation → select → PO created from quotation (supplier/payment terms/line items/totals all copied correctly) → second conversion attempt from the same quotation blocked (409) → header edit while `DRAFT` → `/send` (approval + dispatch, `approved_by` recorded) → edit-after-send blocked (409) → `/confirm` → `/cancel` blocked once `CONFIRMED` (409) → a separate manual PO created and cancelled from `DRAFT` → invalid `supplier_id` rejected (422) → `?status=` filter → confirmed `PO_SEND` landed in `transaction.log`.

**Deliberately not done in Phase 4** (belongs to Phase 5 per the table above): anything that updates `PurchaseOrderItem.received_quantity`/`line_status` or moves a PO to `PARTIALLY_RECEIVED`/`RECEIVED`/`CLOSED`. That's the GRN module's job — `GoodsReceipt`/`GoodsReceiptItem` don't exist yet, and per §4 of this plan, GRN/QC acceptance is what will eventually call into `InventoryService.create_inventory()` to turn a received, QC-accepted line into real stock.



---

## 13. Phase 5 — what was actually built

**New files:**
- `app/db/models/goods_receipt.py` — `GoodsReceipt`, `GoodsReceiptItem`
- `app/db/models/quality_inspection.py` — `QualityInspection`, `QualityInspectionItem`
- `app/db/repositories/goods_receipt_repository.py`
- `app/db/repositories/quality_inspection_repository.py`
- `app/services/goods_receipt_service.py` — GRN creation, PO receiving rollup, GRN close
- `app/services/quality_inspection_service.py` — QC dispositions, deviation approval, the `InventoryService.create_inventory()` seam described in §4
- `app/db/schemas/goods_receipt.py`
- `app/db/schemas/quality_inspection.py`
- `app/api/goods_receipt.py`
- `app/api/quality_inspection.py`
- `alembic/versions/cf937838efc5_add_grn_and_qc_tables.py`
- `tests/test_goods_receipt_service.py`
- `tests/test_quality_inspection_service.py`

**Modified files:**
- `app/db/models/enums.py` — added `GRNStatus`, `QCDisposition` (header rollup), `QCItemDisposition` (per-line ACCEPT/REJECT/DEVIATION — narrower than the header-level `QCDisposition`, since a single QC record can mix dispositions across its lines)
- `app/db/models/__init__.py` — registered the four new models
- `app/core/transaction_logger.py` — added `GRN_CREATE`, `GRN_CLOSE`, `QC_INSPECT`, `QC_DEVIATION_APPROVE`
- `app/main.py` — registered both routers

**State machines implemented:**
- `GRNStatus`: `PENDING_QC → QC_IN_PROGRESS` (automatic, the moment a `QualityInspection` is recorded against the GRN) `→ CLOSED` (explicit `POST /goods-receipts/{id}/close`, so a purchase officer can review the QC outcome — including any still-pending deviation approval — before the GRN is considered fully settled).
- `POStatus`/`POLineStatus`: finally driven, as flagged as outstanding at the end of §12. `GoodsReceiptService.create_grn()` updates `PurchaseOrderItem.received_quantity`/`line_status` and rolls `PurchaseOrder.status` up to `PARTIALLY_RECEIVED` or `RECEIVED` **immediately** on receipt — deliberately independent of QC, matching §4's framing that "physically received" (GRN) is a different fact from "usable stock" (Inventory). A PO can have more than one GRN against it (partial deliveries), so `po_id` isn't unique on `GoodsReceipt` the way `quotation_id` is on `PurchaseOrder`.
- `QCDisposition` (header): resolved automatically from the set of line-item `QCItemDisposition` values — all `ACCEPT` → `ACCEPTED`; all `REJECT` → `REJECTED`; any `DEVIATION` with no `REJECT` present → `ACCEPTED_WITH_DEVIATION`; anything else (a genuine mix) → `PARTIAL`.

**The deviation-approval trust pattern (the main design decision this phase):** §5 of this plan draws an explicit parallel — "this is the same pattern your QC module already uses for `ACCEPTED_WITH_DEVIATION` (machine/inspector flags it, a human approves)." That pattern is implemented literally:
- `disposition: ACCEPT` on a line → `InventoryService.create_inventory()` is called **immediately** inside `create_qc()`.
- `disposition: REJECT` → inventory is never created for that line.
- `disposition: DEVIATION` → inventory creation is **withheld**. If `QualityInspectionCreate.deviation_approved_by` is already set at creation time (e.g. a supervisor signs off on the spot), the DEVIATION lines get their inventory immediately too. Otherwise the line sits with `inventory_id = NULL` until `POST /quality-inspections/{id}/approve-deviation` is called, which then creates inventory for every still-unapproved `DEVIATION` line and stamps `deviation_approved_by`/`deviation_approved_at`. Approving twice is blocked (409), as is approving a QC record with no `DEVIATION` lines.

**The `InventoryService.create_inventory()` seam, exactly as specified in §4:**
```python
InventoryCreate(
    product_id=grn_item.po_item.product_id,
    manufacturer_id=qc_item.manufacturer_id,
    location_id=qc_item.putaway_location_id,
    batch_number=grn_item.vendor_batch_number or f"{grn.grn_number}-{grn_item.id}",
    manufacturing_date=grn_item.manufacturing_date or date.today(),
    quantity=qc_item.accepted_quantity,
    status=InventoryStatus.OK,
)
```
No parallel "create stock" path exists — every unit of stock procurement ever produces goes through the same `InventoryService` validation, `RECEIVE` transaction log entry, and available-quantity logic as manual stock entry.

**`manufacturer_id` resolution** (needed because `Inventory.manufacturer_id` is non-nullable, per §2.8): defaults to `grn.po.supplier.manufacturer_id`, overridable per QC line. If the PO's supplier has no linked manufacturer *and* the line doesn't supply one explicitly, the line is rejected (422) rather than silently guessing — this only applies to `ACCEPT`/`DEVIATION` lines; `REJECT` lines need no manufacturer or location at all.

**Business rules enforced by the service, not just the schema:**
- `grn_number`/`qc_number` auto-generated as `GRN-{year}-{00001}`/`QC-{year}-{00001}`, same pattern as `PR-`/`RFQ-`/`PO-`
- `POST /goods-receipts` requires the PO to be `CONFIRMED` or already `PARTIALLY_RECEIVED` (409 otherwise); every `po_item_id` on the payload must belong to the PO being received against (422 otherwise)
- `GoodsReceiptItem.variance_quantity` is computed server-side as `received_quantity − (po_item.quantity − po_item.received_quantity)` at the moment of creation — i.e. relative to what was *still outstanding* on that PO line, so it reads correctly across multiple partial GRNs, not just against the PO's original full quantity
- `POST /quality-inspections` requires the GRN to be `PENDING_QC` (409 otherwise) and blocks a second QC against the same GRN (409 — enforced both by a DB-level unique constraint on `quality_inspections.grn_id` and a service-level check, the same belt-and-braces pattern as `PurchaseOrder.quotation_id`)
- `/goods-receipts/{id}/close` requires `QC_IN_PROGRESS` (i.e. a QC has already been recorded)

**Verified:** 110/110 `pytest` passing (89 from Phases 1–4 + 21 new, nothing broken), plus an HTTP-level `TestClient` walk through the full lifecycle — PO confirmed → first (partial) GRN → PO rolls to `PARTIALLY_RECEIVED` → second GRN completes the line → PO rolls to `RECEIVED` → QC `ACCEPT` on the first GRN creates `Inventory` immediately → QC `DEVIATION` on the second GRN withholds `Inventory` → `approve-deviation` creates it → both GRNs closed → total `Inventory` quantity for the product matches the accepted quantities exactly (300 + 195) → a second QC attempt against an already-inspected GRN blocked (409) → `GRN_CREATE`/`GRN_CLOSE`/`QC_INSPECT`/`QC_DEVIATION_APPROVE` all landed in `transaction.log`.

**Deliberately not done in Phase 5** (belongs to Phase 6 per the table above): Vendor Invoice / 3-way match. `VendorInvoice`/`VendorInvoiceItem` don't exist yet — per §2.9 and §9 (Phase 6 scope), that's the module that will match a vendor's invoice against this phase's `PurchaseOrder` and `GoodsReceipt` records (quantity/rate/amount within tolerance) before approving payment.

---

## 14. Phase 6 — what was actually built

**New files:**
- `app/db/models/vendor_invoice.py` — `VendorInvoice`, `VendorInvoiceItem`
- `app/db/repositories/vendor_invoice_repository.py`
- `app/services/vendor_invoice_service.py` — manual/ingest entry, review-queue item mapping, the 3-way match, payment lifecycle
- `app/db/schemas/vendor_invoice.py`
- `app/api/vendor_invoice.py`
- `alembic/versions/7a2e2f74aa57_add_vendor_invoice_tables.py`
- `tests/test_vendor_invoice_service.py`

**Modified files:**
- `app/db/models/enums.py` — added `InvoiceStatus`
- `app/db/models/__init__.py` — registered the two new models
- `app/core/transaction_logger.py` — added `INVOICE_CREATE`, `INVOICE_INGEST`, `INVOICE_ITEM_UPDATE`, `INVOICE_MATCH`, `INVOICE_APPROVE_PAYMENT`, `INVOICE_MARK_PAID`
- `app/main.py` — registered the router

**State machine implemented — `InvoiceStatus`:**
`PENDING_MATCH → MATCHED/MISMATCH` (via `POST /vendor-invoices/{id}/match`, re-runnable from either state so a correction can flip a `MISMATCH` to `MATCHED`) `→ APPROVED_FOR_PAYMENT` (only reachable from `MATCHED`) `→ PAID`. `DISPUTED` has no endpoint yet, deliberately — the plan's own API surface table (§3) never lists one, so it's left reserved for a future phase, the same way `RFQStatus.CANCELLED` and `POStatus.CLOSED` were left unused until their phases arrived.

**Reconciling §2.10's `InvoiceStatus` enum with §5's review-queue narrative:** §5 says ingested records "always create the record in `PENDING_REVIEW`", but `InvoiceStatus` (as specified) has no `PENDING_REVIEW` value. The resolution: **`PENDING_MATCH` plays that role for invoices.** There's no separate "reviewed, not yet matched" state the way quotations have `REVIEWED` before `SELECTED` — matching *is* the trust gate here, so both manual and ingested invoices land in `PENDING_MATCH`, and `match()` itself refuses to run while any line is still unmapped to a `PurchaseOrderItem` (422), forcing a human through `PUT /vendor-invoices/{id}/items/{item_id}` first — functionally identical to `VendorQuotationService.select()` blocking on unmapped `product_id`.

**Human vs. automated entry, mirroring the quotation module exactly:**
- `POST /vendor-invoices` (manual): `po_item_id` **required** on every line — the purchase officer already knows which PO line this bills against, so no fuzzy matching runs.
- `POST /vendor-invoices/ingest` (automation): `po_item_id` **never accepted** — each line's free-text `description` is fuzzy-matched (reusing `fuzzy_match.best_product_match`, the same stdlib-`difflib` first-pass matcher from Phase 3) against the *target PO's own line items* (by their product code/name), not the whole product catalog — since an invoice line can only possibly refer to something that was actually ordered on that PO. Unmatched lines stay `po_item_id = NULL` for a human to fix.
- `source`/`source_confidence`/`raw_document_url` follow the same provenance pattern as `VendorQuotation`, deliberately on their own Postgres enum type (`invoice_source_channel`) for the same "can't `ALTER TYPE ... ADD VALUE` mid-migration" reason documented on `VendorQuotation.source`.

**`grn_id` resolution — the one genuinely new wrinkle this phase (invoices reference a GRN, which quotations never had to deal with):** `VendorInvoice.grn_id` is nullable because a PO can have more than one `GoodsReceipt` (Phase 5's partial-delivery support) and an invoice might arrive before anyone has pinned down which delivery it's for, or might have no GRN at all (a pure service/freight invoice). On both `create_manual` and `ingest`, the service auto-resolves `grn_id` as a convenience **only when exactly one `GoodsReceipt` exists for that PO** — ambiguous (multiple GRNs) or absent (none yet) cases are left `NULL`, settable afterwards via `PUT /vendor-invoices/{id}`. `match()` refuses to run at all with `grn_id = NULL` (422, telling the caller to set it first) — there is deliberately no "guess the GRN" fallback for the ambiguous case, since silently picking one of several deliveries to match a whole invoice against is exactly the kind of guess that belongs to a human, not the matcher.

**The 3-way match itself (`VendorInvoiceService.match()`), per line:**
- **Quantity check:** invoice line `quantity` vs. that `PurchaseOrderItem`'s corresponding `GoodsReceiptItem.received_quantity` **on the linked GRN specifically** (not the PO's cumulative `received_quantity` across all GRNs) — matching what this one invoice is actually billing for against what physically arrived in that one delivery.
- **Rate check:** invoice line `rate` vs. the agreed `PurchaseOrderItem.rate` — this is checked against the PO, not the GRN, since a GRN records quantity received but never re-states price.
- **Header check:** invoice `total_amount` (computed server-side from its own lines, same as `PurchaseOrder.total_amount` — never trusted from the client, even on ingest) vs. `PurchaseOrder.total_amount`, as an overall sanity check rather than a re-check of each line.
- **Tolerance (a deliberate simplification, not numerically specified in the plan):** quantity and header within **2%**, rate within **1%** — loose enough to absorb rounding/OCR noise, tight enough to catch a real discrepancy. Both constants (`QUANTITY_TOLERANCE_PCT`, `RATE_TOLERANCE_PCT`) live at the top of `vendor_invoice_service.py` for easy tuning later.
- A line whose `po_item_id` has no corresponding line on the linked GRN (e.g. a two-line PO where only one line was ever received) fails that line with an explicit `"reason"` in the report rather than silently passing or crashing.
- The full `match_report` (per-line diffs, header diff, tolerances used, overall result) is stored as JSON on the invoice — enough for a finance reviewer to see *why* something mismatched without re-deriving it.

**Nothing here touches Inventory.** Phase 5 already created stock at QC acceptance; this module's entire job is financial — deciding whether an invoice is safe to approve for payment. `approve_payment()` is hard-gated on `status == MATCHED` (409 otherwise) precisely so a `MISMATCH`ed invoice can never be paid without either a correction-and-rematch or (in a future phase) an explicit override/dispute path.

**Verified:** 130/130 `pytest` passing (110 from Phases 1–5 + 20 new, nothing broken), plus an HTTP-level `TestClient` walk covering both entry paths: a manual invoice with `grn_id` auto-resolved → `match` → `MATCHED` → `approve-payment` → `mark-paid` → `PAID`; and a separate ingested invoice with an intentionally-unmatchable description → `match` blocked (422) while unmapped → `PUT .../items/{id}` maps it → `match` → `MATCHED` — with `INVOICE_CREATE`/`INVOICE_INGEST`/`INVOICE_ITEM_UPDATE`/`INVOICE_MATCH`/`INVOICE_APPROVE_PAYMENT`/`INVOICE_MARK_PAID` all landing in `transaction.log`.

**Deliberately not done in Phase 6:** a `/dispute` endpoint for `InvoiceStatus.DISPUTED` (not in §3's API surface — reserved, see above); a value-threshold auto-approval path for payment (consistent with the "Decisions locked in" section's manual-only approval stance for PR/PO); and RBAC/auth on any of these endpoints (out of scope for this module per that same section). This closes out every phase in the original build-order table (§8) — dashboard/KPI endpoints (`GET /procurement/kpis`, `GET /procurement/reorder-suggestions`, §3) and the n8n workflow wiring (§6) remain as natural next steps whenever you're ready to pick those up.

---

## 15. Dashboard/KPIs (§3) and n8n workflows (§6) — what was actually built

### Dashboard/KPI endpoints

**New files:**
- `app/services/procurement_dashboard_service.py` — `ProcurementDashboardService`
- `app/db/schemas/procurement_dashboard.py` — `ProcurementKPIs`, `ReorderSuggestion`
- `app/api/procurement_dashboard.py` — `GET /procurement/kpis`, `GET /procurement/reorder-suggestions`
- `tests/test_procurement_dashboard_service.py`

**Modified files:**
- `app/db/repositories/inventory_repository.py` — added `get_available_stock_map()`, a single grouped
  query returning `{product_id: available_stock}` for every product, so `get_reorder_suggestions()`
  doesn't run one query per product (N+1) when checking every active product against its threshold
- `app/main.py` — registered the router

**Design notes:**
- `ProcurementDashboardService` is deliberately **not** a `BaseService[...]` subclass — there's no
  single entity it owns, every method is a read, and (unlike every other service in this codebase)
  nothing here calls `log_transaction()`: the transaction log records business *events*, and looking at
  a dashboard isn't one.
- **Everything is computed live on each request** — no caching, no materialized view, no stored
  snapshot. Deliberate simplification at this system's scale; the first thing to revisit if the
  dashboard is ever called often enough for the live joins to matter (see the service's own docstring).
- **`pending_prs`** counts `PRStatus.PENDING_APPROVAL` only — a `DRAFT` PR isn't "pending" anyone else's
  action yet, it's still being written.
- **`pos_awaiting_grn`** counts `POStatus.CONFIRMED` + `PARTIALLY_RECEIVED` — dispatched and
  acknowledged by the vendor, but not yet fully received.
- **`grns_awaiting_qc`** counts `GRNStatus.PENDING_QC` directly.
- **`overdue_deliveries`** — a PO counts as overdue only if it's still `CONFIRMED`/`PARTIALLY_RECEIVED`
  **and** has an `expected_delivery_date` in the past; a PO with no delivery date set is never counted
  (nothing to be overdue against), and a fully `RECEIVED` PO is never counted even if its date has
  passed (it's done, not "awaiting" anything). Also returns the actual `overdue_purchase_order_ids`, not
  just a count, so a caller (dashboard UI or the reorder-digest-style workflow) can act on it directly.
- **`get_reorder_suggestions()`** is deliberately **suggest-only** — it never creates a
  `PurchaseRequisition`. It checks every active product with a `reorder_level` set (products with no
  threshold configured are skipped, not treated as "always fine") against
  `InventoryRepository.get_available_stock_map()` — the same OK-status-only, reserved-quantity-excluded
  definition of "available" used everywhere else in `InventoryService`, so a product showing as low here
  matches what a warehouse operator would see if they checked stock by hand.

**Verified:** 140/140 `pytest` passing (130 from Phases 1–6 + 10 new), plus an HTTP-level `TestClient`
walk (a PR submitted → `pending_prs: 1`; a product below its `reorder_level` → appears in
`reorder-suggestions` with its preferred supplier attached).

### n8n workflows

**New files (`n8n/workflows/`):**
- `vendor-invoice-ocr-ingest.json` — extends the existing invoice-OCR Telegram workflow with a new
  branch calling `POST /vendor-invoices/ingest` alongside (not instead of) the existing Telegram reply
- `vendor-quotation-ocr-ingest.json` — same OCR pattern for quotations, resolving the RFQ from the
  chat message's caption before calling `POST /quotations/ingest`
- `rfq-broadcast.json` — polls `GET /rfqs?status=SENT`, delivers to each `RFQSupplier` over their
  preferred channel (WhatsApp/Telegram/Email)
- `po-confirmation-bot.json` — a vendor's chat reply ("confirmed PO-2026-00042") →
  `POST /purchase-orders/{id}/confirm`
- `reorder-digest.json` — scheduled digest from the new `GET /procurement/reorder-suggestions`, with a
  reply path that calls `POST /purchase-requisitions` with `source=AUTO_REORDER`
- `n8n/workflows/README.md` — import instructions, the credential names each workflow expects, and the
  environment variables they read

**Modified files:**
- `docker-compose.yml`:
  - **Fixed the bug §6 flagged:** n8n now gets its own database (`n8n_db`, created by a new
    `postgres/init/01-create-n8n-db.sql` init script mounted into postgres's
    `docker-entrypoint-initdb.d`) instead of writing its internal workflow/execution tables into
    `inventory_db`. This is the "or give it a separate `n8n_db`" option from §6 — chosen over dropping
    Postgres persistence entirely, since losing n8n's own workflow history on every restart would be a
    worse trade.
  - **Also fixed a separate, previously-unnoticed bug while in this file:** the `app` service's
    `DATABASE_URL` pointed at `postgres:5431` — the *host-side* port mapping — instead of `postgres:5432`,
    postgres's actual in-network listening port (the `"5431:5432"` mapping under `ports:` only matters
    for connections from *outside* the compose network, e.g. a local DB client on the host machine). Left
    uncorrected, the `app` container could never have reached its own database inside `docker compose
    up`. Fixing it was necessary for this task's own scope: the n8n workflows above assume `app` is
    actually reachable via `API_BASE_URL=http://app:8000/api/v1`, which requires `app` to have started
    successfully in the first place.
  - Added `API_BASE_URL` (read by every workflow's `httpRequest` nodes) and
    `PURCHASE_MANAGER_TELEGRAM_CHAT_ID` (read by the reorder digest) to n8n's environment.
- `postgres/init/01-create-n8n-db.sql` — new file, documents the migration path for an existing
  deployment (the init script only runs on a fresh volume).

**Design notes:**
- **One rule held without exception across every workflow:** the only shape of "database access" any
  workflow has is an `httpRequest` node against this application's own API — never Postgres directly.
  This is now structurally true, not just conventional, since n8n's own database is separate from
  `inventory_db`.
- **No workflow ever sets a status field directly.** Every write is a normal call to an action endpoint
  (`/confirm`, `/select`'s equivalent via `/quotations/ingest` landing in the review queue, `/match`,
  `POST /purchase-requisitions`) — so the same `ConflictError`/`ValidationError` responses that protect a
  human clicking the wrong button in the UI protect these workflows too. `po-confirmation-bot.json`'s
  confirmation call, for instance, has no separate "is this PO actually SENT" guard of its own — it
  relies entirely on `PurchaseOrderService.confirm()` to reject anything else with 409.
- **The reorder digest's reply path deliberately doesn't skip approval.** `source=AUTO_REORDER` only
  records provenance on the resulting `PurchaseRequisition` (`SourceChannel.AUTO_REORDER`, a value that
  already existed on the model from Phase 2 — see `LOW_LEVEL_SERVICE_ARCHITECTURE.md`); the PR still
  starts in `DRAFT` and needs `submit()`/`approve()` through the normal flow. This matches
  `BUSINESS_DECISIONS.md §1`: no value-threshold or automation-sourced auto-approval exists anywhere in
  this codebase.
- **GRN and QC recording were deliberately left out of workflow automation.** There's no
  `httpRequest`-to-`/goods-receipts` or `/quality-inspections` workflow — physically receiving goods and
  passing/failing inspection are judgment calls made standing in front of a delivery, not something a
  chat message should trigger. See `n8n/workflows/README.md`'s "What's deliberately not here" section.
- Every workflow JSON is a syntactically valid n8n export (checked with `json.load` — this environment
  has no running n8n instance to import into and verify against, so treat that as syntax validation, not
  a substitute for an actual test-import before relying on these in production) and ships `"active":
  false`, since each references named credentials (Telegram bot tokens, WhatsApp/SMTP, Mistral OCR) that
  don't exist until configured in a real n8n instance.

**Deliberately not done:** an actual running n8n instance to execute these workflows against (out of
reach of this environment); a webhook-based alternative to the RFQ-broadcast poll (the app has no
outbound-webhook mechanism by design — see `HIGH_LEVEL_ARCHITECTURE.md §6` — so polling is the
correct shape here, not a shortcut); and any change to `InventoryService`/procurement services
themselves, since these workflows are purely API *clients* — nothing about calling an existing endpoint
from n8n instead of curl/the UI changes what that endpoint does.
