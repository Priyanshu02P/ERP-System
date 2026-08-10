# High-Level System Architecture

> Companion docs: [`LOW_LEVEL_SERVICE_ARCHITECTURE.md`](./LOW_LEVEL_SERVICE_ARCHITECTURE.md) (every
> service, class, and function) and [`BUSINESS_DECISIONS.md`](./BUSINESS_DECISIONS.md) (the "why"
> behind the rules encoded in the code). This document covers the "what" and "how it fits together".

## 1. What this system is

An ERP backend for a small manufacturing business, covering two connected domains:

1. **Inventory & Warehousing** — products, physical storage hierarchy (Warehouse → Rack → Shelf →
   Bin → Location), and stock records (batch/quantity/status at a location).
2. **Procurement** — the full buy-side lifecycle from an internal requisition through to paying the
   vendor: Purchase Requisition → RFQ → Vendor Quotation → Purchase Order → Goods Receipt (GRN) →
   Quality Inspection (QC) → Vendor Invoice (3-way match) → payment.

The two domains meet at exactly one point by design: **QC acceptance calls the same
`InventoryService.create_inventory()` that manual stock entry uses.** Procurement is a *source* of
stock, not a parallel system that happens to also track inventory. See §5.

## 2. Tech stack

| Concern | Choice |
|---|---|
| API framework | FastAPI (Python), routers under `app/api/` |
| ORM | SQLAlchemy 2.0 (`Mapped[...]` declarative style), models under `app/db/models/` |
| Validation / serialization | Pydantic v2 schemas under `app/db/schemas/` |
| Database | PostgreSQL 16 in Docker; **in-memory SQLite** for the test suite (`tests/conftest.py`) |
| Migrations | Alembic, one revision per phase, chained via `down_revision` |
| Automation / bots | n8n (Telegram/WhatsApp/email OCR workflows), calls the API over HTTP only |
| Testing | pytest, `TestClient` for HTTP-level smoke walks |
| Frontend | Static HTML/JS (`frontend/`), served by FastAPI's `StaticFiles` — not a SPA framework |

## 3. Layered architecture

Every domain module (Unit, Product, Purchase Order, Vendor Invoice, ...) follows the same four-layer
shape, top to bottom:

```
┌─────────────────────────────────────────────────────────────────┐
│  API layer            app/api/*.py                              │
│  FastAPI routers. Thin: parse the request into a Pydantic        │
│  schema, call exactly one service method, return its result.    │
│  No business logic here.                                        │
└───────────────────────────────┬─────────────────────────────────┘
                                 │  Pydantic schemas (app/db/schemas/*.py)
                                 │  *Create / *Ingest / *Update / *Read
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Service layer         app/services/*.py                        │
│  ALL business rules live here: validation, state machines,      │
│  numbering, totals, cross-entity checks, transaction logging.   │
│  Services call repositories, never the ORM/session directly     │
│  (except via a repository), and call OTHER services for         │
│  cross-module operations (e.g. QC calls InventoryService).      │
└───────────────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Repository layer      app/db/repositories/*.py                 │
│  Plain database access only — no business rules. Generic CRUD   │
│  comes from BaseRepository[ModelType]; each concrete repository │
│  adds a handful of query methods (get_by_status, count_for_year,│
│  exists, ...).                                                  │
└───────────────────────────────┬─────────────────────────────────┘
                                 │  SQLAlchemy ORM
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Model layer            app/db/models/*.py                      │
│  SQLAlchemy declarative models + the shared enums               │
│  (app/db/models/enums.py). IDMixin/TimestampMixin/ActiveMixin   │
│  provide id/created_at/updated_at/is_active for free.           │
└─────────────────────────────────────────────────────────────────┘
```

**Why this shape:** every layer has exactly one reason to change. A new validation rule touches only
the service. A new query touches only the repository. A new field on the wire touches only the schema.
`BaseService`/`BaseRepository` give every module `get`/`get_all`/`get_page`/`count`/`delete` for free
(with a consistent `NotFoundError`), so a concrete service only ever writes the logic that's actually
specific to it.

## 4. Cross-cutting concerns

### 4.1 Error handling → HTTP status codes

Services raise one of four typed exceptions (`app/services/exceptions.py`); `app/api/error_handlers.py`
maps them centrally so no router has to catch anything itself:

| Exception | HTTP status | Raised when |
|---|---|---|
| `NotFoundError` | 404 | `BaseService.get()` can't find the id |
| `ValidationError` | 422 | A business rule about the *shape* of the request fails (unmapped line, missing FK, out-of-range value) |
| `ConflictError` | 409 | A business rule about *state* fails (wrong status for this transition, already-done action) |
| `ReferencedEntityError` | 409 | A delete would orphan something that still points at it |

### 4.2 Transaction log

`app/core/transaction_logger.py` writes one JSON line per business action to `backend/transaction.log`
(`log_transaction(action, entity_type, entity_id, details)`), read back via `GET /api/v1/logs`
(`?action=`, `?entity_id=`, `?search=`, `?limit=`). Every state-changing service method calls this — see
`TransactionAction` for the full enum of ~40 actions across every module. This is the audit trail: who
did what, when, to which record, without needing a separate audit table per entity.

### 4.3 The review-queue pattern (human vs. automated input)

Two modules accept both human-entered and bot/OCR-ingested records: **Vendor Quotation** and
**Vendor Invoice**. Both follow the identical shape:

- `create_manual(...)` / `POST /<resource>` — a human already knows the mapping (product, PO line), so
  it's required up front and trusted immediately.
- `ingest(...)` / `POST /<resource>/ingest` — the **only** entry point automation may call. Free-text
  descriptions are fuzzy-matched (`app/services/fuzzy_match.py`, stdlib `difflib`) against the relevant
  candidate set; anything below a confidence threshold is left unmapped (`product_id`/`po_item_id =
  NULL`) rather than guessed.
- The record lands in a **review-queue status** (`QuotationStatus.PENDING_REVIEW`,
  `InvoiceStatus.PENDING_MATCH` doing double duty — see `BUSINESS_DECISIONS.md`). A human corrects
  unmapped lines via a `PUT .../items/{item_id}` endpoint.
- The state-changing action that matters downstream (`select()`, `match()`) refuses to run while any
  line is still unmapped.
- **Nothing downstream ever reads an unreviewed record.** A `PENDING_REVIEW` quotation can't become a
  PO; a `PENDING_MATCH` invoice with unmapped lines can't be matched, let alone paid.

This is deliberately the same trust pattern used a third time in QC: an inspector's `DEVIATION`
disposition doesn't create `Inventory` until a human calls `approve_deviation()`.

### 4.4 State machines

Nearly every procurement entity is a state machine, always modelled as a `str, enum.Enum` in
`app/db/models/enums.py` and always enforced in the service (never trusted from client-supplied status
values — there is no generic "set status" endpoint anywhere). See `LOW_LEVEL_SERVICE_ARCHITECTURE.md`
for each one in detail. Several enums intentionally carry a value with **no endpoint yet** (e.g.
`InvoiceStatus.DISPUTED`, `RFQStatus.CANCELLED`) — reserved for a phase that hasn't been built, not a
bug.

### 4.5 Numbering

Every document-like entity gets a human-readable, year-scoped number generated server-side, never
client-supplied: `PR-2026-00001`, `RFQ-2026-00001`, `PO-2026-00001`, `GRN-2026-00001`, `QC-2026-00001`.
Each service's `_generate_..._number()` counts existing rows matching `{PREFIX}-{year}-%` and appends
one, zero-padded to 5 digits.

### 4.6 Provenance (`source` / `source_confidence`)

`VendorQuotation` and `VendorInvoice` both carry `source: SourceChannel` (`MANUAL`, `OCR_BOT`,
`WHATSAPP_BOT`, `TELEGRAM_BOT`, `EMAIL_PARSER`, `API`, `AUTO_REORDER`) and a nullable
`source_confidence: float`. They're deliberately backed by *separate* Postgres enum types
(`quotation_source_channel`, `invoice_source_channel`) even though both use the same Python
`SourceChannel` — see `BUSINESS_DECISIONS.md` for why (`ALTER TYPE ... ADD VALUE` can't run inside the
same migration transaction that adds the value).

## 5. The procurement → inventory seam

This is the one integration point that matters most, so it gets its own diagram. Nothing downstream of
QC touches `Inventory` directly except through `InventoryService`:

```
PurchaseRequisition ──(approve)──▶ RFQ ──(send)──▶ VendorQuotation ──(select)──▶ PurchaseOrder
                                                                                       │
                                                                                (send, confirm)
                                                                                       │
                                                                                       ▼
                                                                              GoodsReceipt (GRN)
                                                                        "physically arrived" — PO's own
                                                                        received_quantity/status update
                                                                        HERE, independent of QC
                                                                                       │
                                                                                       ▼
                                                                            QualityInspection (QC)
                                                                     per line: ACCEPT / REJECT / DEVIATION
                                                                                       │
                                                       ┌───────────────────────────────┼───────────────────┐
                                                       ▼                               ▼                   ▼
                                                    ACCEPT                        DEVIATION              REJECT
                                              InventoryService                 held until a human      no stock,
                                              .create_inventory()              approve_deviation()s     ever
                                              called immediately               it, THEN the same call
                                                       │                               │
                                                       └───────────────┬───────────────┘
                                                                       ▼
                                                                  Inventory
                                                     (the SAME table/service manual stock entry uses)
                                                                       
                                                                       
                                                          VendorInvoice ──(match)──▶ 3-way check:
                                                     invoice qty  vs  GRN received_quantity
                                                     invoice rate vs  PO agreed rate
                                                     invoice total vs PO total
                                                                       │
                                                          MATCHED ──(approve-payment)──▶ APPROVED_FOR_PAYMENT
                                                                       │                        │
                                                                       ▼                   (mark-paid)
                                                                  MISMATCH                       ▼
                                                             (re-matchable after              PAID
                                                              a correction)
```

Key property: **GRN (physically received) and Inventory (usable, accepted stock) are deliberately
different facts.** A GRN can exist with zero Inventory behind it (everything rejected). The PO's own
`received_quantity`/status rolls up at GRN time, not QC time, because "goods arrived" is true regardless
of what QC later decides. See `BUSINESS_DECISIONS.md §4`.

`ProcurementDashboardService` (`GET /procurement/kpis`, `GET /procurement/reorder-suggestions`) sits
*above* this whole chain as a pure, read-only aggregator — it queries every stage above for a live
count/threshold check, never writes anything, and (uniquely among the services in this codebase) never
logs a transaction, since a dashboard view isn't a business event. See
`LOW_LEVEL_SERVICE_ARCHITECTURE.md §4` for what each KPI actually counts.

## 6. Deployment view

`docker-compose.yml` runs three services:

| Service | Image | Purpose |
|---|---|---|
| `postgres` | `postgres:16-alpine` | Application database (`inventory_db`) **and** n8n's own database (`n8n_db`, created by `postgres/init/01-create-n8n-db.sql` on first startup — see below) |
| `app` | built from `./backend` | FastAPI app, `uvicorn --reload`, port 8000 |
| `n8n` | `n8n.io/n8nio/n8n` | Workflow automation — see `n8n/workflows/README.md` for the five workflows shipped (OCR ingest for quotations/invoices, RFQ broadcast, PO confirmation bot, reorder digest). n8n has its **own** database (`n8n_db`, not `inventory_db`) for its internal workflow/execution state; it never touches the app's tables directly — every n8n → app interaction is an `httpRequest` node against `API_BASE_URL` (`http://app:8000/api/v1`), same as any other HTTP client |

**Why `n8n_db` is a separate database, not just separate tables in `inventory_db`:** n8n was originally
pointed at `inventory_db` itself, which would let it create its own tables
(`workflow_entity`, `execution_entity`, ...) inside the application's own database — functionally
harmless (different table names, no collision) but wrong on principle: it blurs a boundary that should
be structural. `postgres/init/01-create-n8n-db.sql` runs once, automatically, the first time the
`pgdata` volume initializes; an existing deployment needs either a fresh volume or a manual
`CREATE DATABASE n8n_db;` — see the script's own comments and the README's Quick Start section.

On `app` startup, `Base.metadata.create_all()` creates any missing tables (idempotent — a fresh
`docker compose up --build` needs no manual migration step). Alembic (`alembic upgrade head`) is the
path for evolving an existing schema afterwards; each phase of this project added exactly one revision.

## 7. Testing strategy

- `tests/conftest.py` provides a `db_session` fixture: a fresh in-memory SQLite database
  (`Base.metadata.create_all` against `sqlite:///:memory:`) per test — fast, fully isolated, no shared
  state between tests.
- One test file per service (`tests/test_<module>_service.py`), calling the service layer directly
  (not through HTTP) — this is where state-machine rules, validation, and cross-entity checks are
  actually verified.
- Integration coverage of full lifecycles (PR → RFQ → Quotation → PO → GRN → QC → Invoice) lives
  inline as fixtures/helper functions within the relevant test files (e.g.
  `_received_and_accepted_po()` in `test_vendor_invoice_service.py`) rather than one giant end-to-end
  test file.
- Each phase's delivery was additionally verified with an ad-hoc `TestClient` walk exercising the real
  HTTP routes end-to-end (see the write-ups in `Procurement_Implementation_Plan.md` §12–§14) — this
  catches router/schema wiring bugs that service-level tests can't.

## 8. Module map (where to find things)

| Domain | Models | Service(s) | Router |
|---|---|---|---|
| Units | `unit.py` | `UnitService` | `unit.py` |
| Manufacturers | `manufacturer.py` | `ManufacturerService` | `manufacturer.py` |
| Suppliers | `supplier.py` | `SupplierService` | `supplier.py` |
| Products | `product.py` | `ProductService` | `product.py` |
| Warehousing | `warehouse.py`, `rack.py`, `shelf.py`, `bin.py`, `location.py` | `WarehouseService`, `RackService`, `ShelfService`, `BinService`, `LocationService` | `warehouse.py` |
| Inventory | `inventory.py` | `InventoryService` | `inventory.py` |
| Purchase Requisition | `purchase_requisition.py` | `PurchaseRequisitionService` | `purchase_requisition.py` |
| RFQ | `rfq.py` | `RFQService` | `rfq.py` |
| Vendor Quotation | `vendor_quotation.py` | `VendorQuotationService` | `vendor_quotation.py` |
| Purchase Order | `purchase_order.py` | `PurchaseOrderService` | `purchase_order.py` |
| Goods Receipt | `goods_receipt.py` | `GoodsReceiptService` | `goods_receipt.py` |
| Quality Inspection | `quality_inspection.py` | `QualityInspectionService` | `quality_inspection.py` |
| Vendor Invoice | `vendor_invoice.py` | `VendorInvoiceService` | `vendor_invoice.py` |
| Procurement Dashboard | *(none — aggregates across the above)* | `ProcurementDashboardService` | `procurement_dashboard.py` |
| Cross-cutting | `enums.py`, `mixins.py` | `base_service.py`, `exceptions.py`, `fuzzy_match.py`, `seed_service.py` | `search.py`, `logs.py`, `error_handlers.py` |

See `LOW_LEVEL_SERVICE_ARCHITECTURE.md` for what every class and function in the Service column
actually does.
