# High-Level System Architecture

> This is the **master high-level doc** for the whole system. For every HTTP endpoint grouped by
> domain, see [`API.md`](./API.md). For the per-module low-level design (every class and function in a
> given domain), see the module docs under [`modules/`](./modules/):
> [shared kernel](./modules/shared/LOW_LEVEL_DESIGN.md),
> [master_data](./modules/master_data/LOW_LEVEL_DESIGN.md),
> [procurement](./modules/procurement/LOW_LEVEL_DESIGN.md), [wms](./modules/wms/LOW_LEVEL_DESIGN.md),
> [quality](./modules/quality/LOW_LEVEL_DESIGN.md), [platform](./modules/platform/LOW_LEVEL_DESIGN.md).
> For *why* a rule exists rather than *what* it does, see
> [`BUSINESS_DECISIONS.md`](./BUSINESS_DECISIONS.md). This document covers the "what" and "how it fits
> together" system-wide.

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
| API framework | FastAPI (Python), one router per subdomain — see §3 |
| ORM | SQLAlchemy 2.0 (`Mapped[...]` declarative style), models grouped by domain — see §3 |
| Validation / serialization | Pydantic v2 schemas grouped by domain — see §3 |
| Database | PostgreSQL 16 in Docker; **in-memory SQLite** for the test suite (`tests/conftest.py`) |
| Migrations | Alembic, one revision per phase, chained via `down_revision` |
| Automation / bots | n8n (Telegram/WhatsApp/email OCR workflows), calls the API over HTTP only |
| Testing | pytest, `TestClient` for HTTP-level smoke walks |
| Frontend | Static HTML/JS (`frontend/`), served by FastAPI's `StaticFiles` — not a SPA framework |

## 3. Layered architecture

The codebase is organized **by domain first, by layer second** — the opposite of a flat
`app/{api,services,db}` split. Every business capability owns one directory containing all of its own
layers:

```
app/
├── shared/              kernel: base classes, enums, exceptions, transaction log (§4)
├── db/connection.py      SQLAlchemy engine/session/Base (infra, not a domain)
├── master_data/           product, unit, manufacturer
├── procurement/           supplier, requisition, rfq, vendor_quotation, purchase_order,
│                          vendor_invoice, dashboard
├── wms/                   warehouse_structure, inventory, goods_receipt
├── quality/                inspection
└── platform/               search, logs, seed
```

Within each subdomain (e.g. `app/procurement/purchase_order/`), the same four-layer shape from before
still applies top to bottom — it's just packaged together instead of scattered across parallel
top-level folders:

```
┌─────────────────────────────────────────────────────────────────┐
│  API layer            <domain>/<subdomain>/api.py                │
│  FastAPI router. Thin: parse the request into a Pydantic         │
│  schema, call exactly one service method, return its result.     │
│  No business logic here.                                         │
└───────────────────────────────┬─────────────────────────────────┘
                                 │  Pydantic schemas (<domain>/<subdomain>/schemas.py)
                                 │  *Create / *Ingest / *Update / *Read
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Service layer         <domain>/<subdomain>/service.py           │
│  ALL business rules live here: validation, state machines,       │
│  numbering, totals, cross-entity checks, transaction logging.    │
│  Services call repositories, never the ORM/session directly      │
│  (except via a repository), and call OTHER domains' services     │
│  for cross-module operations (e.g. Quality calls WMS's           │
│  InventoryService).                                               │
└───────────────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Repository layer      <domain>/<subdomain>/repository.py        │
│  Plain database access only — no business rules. Generic CRUD    │
│  comes from BaseRepository[ModelType] (app/shared/), each        │
│  concrete repository adds a handful of query methods             │
│  (get_by_status, count_for_year, exists, ...).                   │
└───────────────────────────────┬─────────────────────────────────┘
                                 │  SQLAlchemy ORM
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  Model layer            <domain>/<subdomain>/models.py           │
│  SQLAlchemy declarative models. IDMixin/TimestampMixin/           │
│  ActiveMixin (app/shared/mixins.py) provide                      │
│  id/created_at/updated_at/is_active for free. Shared enums live  │
│  in app/shared/enums.py, imported by whichever domain needs them.│
└─────────────────────────────────────────────────────────────────┘
```

`warehouse_structure` is the one subdomain with more than one entity (`Warehouse`/`Rack`/`Shelf`/
`Bin`/`Location`); there, `models/`, `repository/`, and `service/` are small packages (one file per
entity) rather than single files, since a single API/schema pair already fronts all five.

`app/db/connection.py` (engine, session factory, declarative `Base`) and `app/db/model_registry.py`
(imports every domain's models so `Base.metadata` knows about all of them, for Alembic/`create_all`)
are the only pieces of "db-as-a-layer" left — everything else moved into its owning domain.

**Why this shape:** every layer still has exactly one reason to change, but now every *domain* also has
one place to look. A new validation rule touches only that subdomain's `service.py`. A new query
touches only its `repository.py`. A new field on the wire touches only its `schemas.py`. Onboarding
someone onto "how Procurement works" means pointing at one folder, not five.

## 4. Cross-cutting concerns

### 4.1 Error handling → HTTP status codes

Services raise one of four typed exceptions (`app/shared/exceptions.py`); `app/shared/error_handlers.py`
maps them centrally so no router has to catch anything itself:

| Exception | HTTP status | Raised when |
|---|---|---|
| `NotFoundError` | 404 | `BaseService.get()` can't find the id |
| `ValidationError` | 422 | A business rule about the *shape* of the request fails (unmapped line, missing FK, out-of-range value) |
| `ConflictError` | 409 | A business rule about *state* fails (wrong status for this transition, already-done action) |
| `ReferencedEntityError` | 409 | A delete would orphan something that still points at it |

### 4.2 Transaction log

`app/shared/transaction_logger.py` writes one JSON line per business action to `backend/transaction.log`
(`log_transaction(action, entity_type, entity_id, details)`), read back via `GET /api/v1/logs`
(`?action=`, `?entity_id=`, `?search=`, `?limit=`, exposed through `app/platform/logs/api.py`). Every
state-changing service method calls this — see `TransactionAction` for the full enum of ~40 actions
across every module. This is the audit trail: who did what, when, to which record, without needing a
separate audit table per entity.

### 4.3 The review-queue pattern (human vs. automated input)

Two modules accept both human-entered and bot/OCR-ingested records: **Vendor Quotation** and
**Vendor Invoice**. Both follow the identical shape:

- `create_manual(...)` / `POST /<resource>` — a human already knows the mapping (product, PO line), so
  it's required up front and trusted immediately.
- `ingest(...)` / `POST /<resource>/ingest` — the **only** entry point automation may call. Free-text
  descriptions are fuzzy-matched (`app/shared/fuzzy_match.py`, stdlib `difflib`) against the relevant
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
`app/shared/enums.py` and always enforced in the service (never trusted from client-supplied status
values — there is no generic "set status" endpoint anywhere). See the relevant
[module low-level doc](./modules/) for each one in detail. Several enums intentionally carry a value
with **no endpoint yet** (e.g. `InvoiceStatus.DISPUTED`, `RFQStatus.CANCELLED`) — reserved for a phase
that hasn't been built, not a bug.

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
[`modules/procurement/LOW_LEVEL_DESIGN.md`](./modules/procurement/LOW_LEVEL_DESIGN.md) for what each
KPI actually counts.

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
  HTTP routes end-to-end (see the write-ups in
  [`modules/procurement/IMPLEMENTATION_PLAN.md`](./modules/procurement/IMPLEMENTATION_PLAN.md) §12–§14)
  — this catches router/schema wiring bugs that service-level tests can't.

## 8. Module map (where to find things)

The codebase is grouped by domain, then by layer within each domain — see §3 for the general shape.
Every row below is one directory under `app/`; the low-level doc for each domain lists every class and
function inside it.

| Domain | Subdomains | Low-level doc |
|---|---|---|
| `master_data` | `unit`, `manufacturer`, `product` | [modules/master_data/LOW_LEVEL_DESIGN.md](./modules/master_data/LOW_LEVEL_DESIGN.md) |
| `procurement` | `supplier`, `requisition`, `rfq`, `vendor_quotation`, `purchase_order`, `vendor_invoice`, `dashboard` | [modules/procurement/LOW_LEVEL_DESIGN.md](./modules/procurement/LOW_LEVEL_DESIGN.md) |
| `wms` | `warehouse_structure` (warehouse/rack/shelf/bin/location), `inventory`, `goods_receipt` | [modules/wms/LOW_LEVEL_DESIGN.md](./modules/wms/LOW_LEVEL_DESIGN.md) |
| `quality` | `inspection` | [modules/quality/LOW_LEVEL_DESIGN.md](./modules/quality/LOW_LEVEL_DESIGN.md) |
| `platform` | `search`, `logs`, `seed` | [modules/platform/LOW_LEVEL_DESIGN.md](./modules/platform/LOW_LEVEL_DESIGN.md) |
| `shared` *(kernel, not a business domain)* | `enums`, `mixins`, `schemas_common`, `base_repository`, `base_service`, `exceptions`, `fuzzy_match`, `transaction_logger`, `error_handlers` | [modules/shared/LOW_LEVEL_DESIGN.md](./modules/shared/LOW_LEVEL_DESIGN.md) |
| `db` *(infra, not a business domain)* | `connection.py` (engine/session/Base), `model_registry.py` (registers every domain's models on `Base.metadata`) | — |

Each subdomain folder (e.g. `app/procurement/purchase_order/`) contains its own `models.py`,
`schemas.py`, `repository.py`, `service.py`, and `api.py` — see the low-level doc for that domain for
what each file actually contains.
