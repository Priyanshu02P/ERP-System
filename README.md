# Inventory Management System

FastAPI + SQLAlchemy + Pydantic + PostgreSQL backend, following a strict
layered architecture:

```
Client → FastAPI Router → Service Layer → Repository Layer → SQLAlchemy Models → PostgreSQL
```

| Layer | Responsibility |
|---|---|
| Router (`app/api`) | HTTP requests/responses |
| Service (`app/services`) | Business rules |
| Repository (`app/db/repositories`) | Database queries |
| Model (`app/db/models`) | Database schema |
| Schema (`app/db/schemas`) | Request/response validation |

## Documentation

- [`docs/HIGH_LEVEL_ARCHITECTURE.md`](docs/HIGH_LEVEL_ARCHITECTURE.md) — system architecture, layering,
  cross-cutting concerns, deployment view
- [`docs/LOW_LEVEL_SERVICE_ARCHITECTURE.md`](docs/LOW_LEVEL_SERVICE_ARCHITECTURE.md) — every service
  class and function, grouped by module
- [`docs/BUSINESS_DECISIONS.md`](docs/BUSINESS_DECISIONS.md) — the reasoning behind every non-obvious
  rule in the code, organized by theme
- [`docs/Procurement_Implementation_Plan.md`](docs/Procurement_Implementation_Plan.md) — the original
  phase-by-phase build log and spec
- [`n8n/workflows/README.md`](n8n/workflows/README.md) — importable n8n workflows for the automation
  touchpoints (OCR ingest, RFQ broadcast, PO confirmation bot, reorder digest)

## Quick start (Docker)

```bash
docker compose up --build
```

This starts Postgres on `localhost:5432` and the API on `localhost:8000`.
Interactive docs: http://localhost:8000/docs
The inventory UI is served at http://localhost:8000/ (see "Frontend" below).

Tables are created automatically on startup (see "Migrations" below), so
this works immediately on a fresh database - no manual step needed. Seed
sample data either via the UI's "Seed sample data" button or
`POST /api/v1/search/seed`.

`docker-compose.yml` also starts n8n (`localhost:5678`) for the workflow
automation touchpoints — see [`n8n/workflows/README.md`](n8n/workflows/README.md)
for what to import and how. n8n has its **own** database (`n8n_db`,
created by `postgres/init/01-create-n8n-db.sql` on first startup) —
it never touches `inventory_db` directly; every n8n ↔ app interaction is
an HTTP call against the API, same as any other client. If you have an
existing `pgdata` volume from before this split (n8n previously wrote its
internal tables into `inventory_db`), either run `docker compose down -v`
for a clean start, or manually `CREATE DATABASE n8n_db;` against the
running postgres container and restart n8n.

For telegram bot to work you have to use cloudflared tunnel.

And set Webhook url and n8n host url in env file.

## Quick start (local, no Docker)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL if needed, e.g. point at a local Postgres
uvicorn app.main:app --reload
```

## Frontend

`frontend/web` is a React app (Vite) — a dark-themed inventory & procurement
control UI, built to `frontend/dist` and served at `/` by the FastAPI app
(static images at `/assets`). `docker compose up --build` builds it
automatically; see `frontend/README.md` for the dev/build workflow.

Pages:

- **Dashboard** — stock-wide stats and a recent-activity feed.
- **Inventory** — every stock record with its product image, manufacturer,
  batch, location, quantity/reserved/available, and status. Supports
  free-text search (product name/code, record ID, manufacturer, batch,
  manufacturing date, date loaded), filters (status, product type,
  warehouse, manufacturer), and sorting. Actions per record: **Receive**
  (add new stock), **Dispatch** (issue/ship out), **Change status**, and a
  **Manage** panel for Reserve / Release / Move / Adjust / Delete.
- **Products** — a searchable image gallery of the product catalog.
- **Activity logs** — a live view over `backend/transaction.log`
  (see below), filterable by action and free-text search.

## Business transaction logging

Every stock-movement action — `RECEIVE`, `ISSUE`, `MOVE`, `RESERVE`,
`RELEASE`, `STATUS_CHANGE`, `ADJUST`, `DELETE`, `SEED` — is written as a
single-line structured JSON entry to `backend/transaction.log`
(`app/core/transaction_logger.py`). This is a business audit trail, kept
separate from ordinary application/error logs. Read it back via
`GET /api/v1/logs` (supports `?action=`, `?entity_id=`, `?search=`, `?limit=`).

## Seeding

`POST /api/v1/search/seed?clean=false` seeds the database from
`app/data/seed_data.json` — a plain JSON fixture describing units,
manufacturers, products (including `image_url`), the warehouse/rack/shelf/
bin/location hierarchy, and inventory records. Edit that file to change
what gets seeded; no Python changes required. Pass `clean=true` to wipe
existing data and reseed. A `SEED` entry is written to the transaction log
each time it runs.



## Migrations (Alembic)

On startup, the app automatically runs `Base.metadata.create_all()`, which
creates any tables that don't exist yet (and never touches ones that do).
That's enough for local development and for this Docker Compose setup - a
fresh `docker compose up --build` works immediately, no manual step needed.

For tracked, reviewable schema changes over time (the production-grade
path), use Alembic instead:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

## Running tests

Tests use an in-memory SQLite database (see `tests/conftest.py`), so no
Postgres instance is required:

```bash
pip install -r requirements.txt
pytest -v
```

## Domain model notes

- **Product types**: `RAW`, `WIP`, `FG` (raw material / work-in-progress / finished good).
  Products may also carry an `image_url` for display in the UI, and optional
  `reorder_level` / `reorder_quantity` / `preferred_supplier_id` for procurement.
- **Supplier vs. Manufacturer**: `Manufacturer` records who *made* a given
  batch of stock (`Inventory.manufacturer_id`). `Supplier` records who a
  Purchase Order is actually issued to — often a distributor rather than the
  brand itself (e.g. supplier "Tata Steel Distributor" vs manufacturer
  "Tata Steel"). The two are kept as separate masters; `Supplier.manufacturer_id`
  optionally links a supplier to the brand it represents.
- **Inventory status**: `OK`, `RJC` (rejected), `MIS` (missing), `RET` (returned), `HLD` (on hold), `DMG` (damaged).
  Only `OK`-status stock counts toward a product's *available* quantity
  (`GET /inventory/product/{id}/available`); other statuses are still
  physically on hand but excluded from what can be reserved or issued.
- **Location hierarchy**: `Warehouse → Rack → Shelf → Bin`. A shelf can never
  be specified without its rack, and a bin never without its shelf.
  Oversized items may stop at the rack level (e.g. `WH1-A`).
  `SHEET` / `PIPE` / `SCRAP` are dedicated rack-level-only zones, rendered as
  `SHEET-A` / `PIPE-A` / `SCRAP-A`.
- **Composite inventory display string** combines status (or product type,
  when status is `OK`) with the location code, e.g.:
  - `FG-WH1-A-03-05` — finished good, ready to sell, at bin 05 / shelf 03 / rack A / warehouse 1
  - `RET-WH3-A` — returned item, stored at rack A / warehouse 3
- **RFQ → Vendor Quotation review queue**: an RFQ tracks per-supplier send
  status (`RFQSupplier.response_status`: `SENT` → `RESPONDED`/`NO_RESPONSE`).
  Human-entered quotations (`POST /rfqs/{id}/quotations`) start `REVIEWED`
  since a person already knows the product. AI/automation-parsed quotations
  (`POST /quotations/ingest`) always start `PENDING_REVIEW`: each line's
  free-text description is fuzzy-matched against the product master
  (`app/services/fuzzy_match.py`, stdlib `difflib`), and any line below the
  confidence threshold is left `product_id = NULL` for a human to map via
  `PUT /quotations/{id}/items/{item_id}`. A quotation can never be
  `/select`-ed while any line is unmapped. Selecting one quotation on an
  RFQ auto-rejects the RFQ's other open quotations.

## Project layout

```
app/
  config.py                 # pydantic-settings configuration
  main.py                   # FastAPI app + router wiring
  core/
    transaction_logger.py    # writes/reads backend/transaction.log
  data/
    seed_data.json            # editable seed fixture
  db/
    connection.py            # engine / session / declarative Base
    models/                  # SQLAlchemy ORM models
    schemas/                 # Pydantic request/response schemas
    repositories/             # DB-only query layer
  services/                  # Business rules layer
  api/                        # FastAPI routers
tests/                        # Pytest suite (SQLite in-memory)
alembic/                      # Migration scaffold
frontend/
  web/                         # React source (Vite) - edit here
  dist/                        # built output, served at "/" (generated)
  assets/products/*.png       # product images
docker-compose.yml
Dockerfile
requirements.txt
transaction.log                # business audit log (created at runtime)
```

## API overview

All routes are prefixed with `/api/v1`.

- `POST/GET/PUT/DELETE /units`, plus `/activate`, `/deactivate`
- `POST/GET/PUT/DELETE /manufacturers`, plus `/activate`, `/deactivate`, `?search=`
- `POST/GET/PUT/DELETE /suppliers`, plus `/activate`, `/deactivate`, `?search=`, `?category=`, `?active_only=`
- `POST/GET/PUT/DELETE /products`, plus `/activate`, `/deactivate`, `/change-unit/{unit_id}`, `?search=`, `?product_type=`
- `POST/GET/PUT/DELETE /warehouses`, `/racks`, `/shelves`, `/bins`, `/locations` (`GET /locations` lists all)
- `POST/GET/PUT/DELETE /inventory`, plus `/issue`, `/adjust`, `/reserve`, `/release`, `/move`, `/status`
- `GET /inventory/product/{id}/available`, `/inventory/product/{id}/total`
- `POST/GET/PUT /purchase-requisitions`, plus `/{id}/submit`, `/{id}/approve`, `/{id}/reject`,
  `/{id}/items` (add), `/{id}/items/{item_id}` (remove), `?status=`, `?department=`
- `POST/GET /rfqs`, plus `/{id}/send`, `/{id}/close`, `?status=`
- `POST /rfqs/{id}/quotations` (human entry), `GET /rfqs/{id}/quotations` (comparison view)
- `POST /quotations` (manual, no RFQ), `POST /quotations/ingest` (automation entry — always lands in
  `PENDING_REVIEW`), `GET /quotations` (`?status=`), `PUT /quotations/{id}/items/{item_id}` (correct a line
  during review), `/{id}/review`, `/{id}/select`, `/{id}/reject`
- `POST/GET/PUT /purchase-orders` (`POST` either converts a `SELECTED` quotation via `quotation_id`, or
  creates a manual/routine PO from `supplier_id` + `items`), plus `/{id}/send` (approve + dispatch in one
  step), `/{id}/confirm` (vendor confirmed), `/{id}/cancel`, `?status=`, `?supplier_id=`
- `POST/GET /goods-receipts` (record goods physically received against a `CONFIRMED` PO — rolls the PO's
  own status up to `PARTIALLY_RECEIVED`/`RECEIVED` immediately), plus `/{id}/close` (after QC is recorded),
  `?status=`, `?po_id=`
- `POST/GET /quality-inspections` (per-line `ACCEPT`/`REJECT`/`DEVIATION` disposition against a GRN —
  `ACCEPT` creates real `Inventory` immediately via the existing `InventoryService`, `DEVIATION` withholds
  it until approved), plus `/{id}/approve-deviation` (creates `Inventory` for any still-pending `DEVIATION`
  lines), `?grn_id=`
- `POST /vendor-invoices` (manual entry, `po_item_id` required per line), **`POST /vendor-invoices/ingest`**
  (automation entry — fuzzy-matches each line's description against the target PO's own items, leaving
  unmatched lines for review), `PUT /vendor-invoices/{id}` (set `grn_id` etc. while unmatched),
  `PUT /vendor-invoices/{id}/items/{item_id}` (map/correct a line), `/{id}/match` (the 3-way PO/GRN/invoice
  check — re-runnable after a correction), `/{id}/approve-payment` (`MATCHED` only), `/{id}/mark-paid`,
  `?status=`, `?po_id=`
- `GET /procurement/kpis` (pending PRs, POs awaiting GRN, GRNs awaiting QC, overdue deliveries),
  `GET /procurement/reorder-suggestions` (active products at/below `reorder_level`, live-computed, never
  auto-creates a PR)
- `GET /logs` — business transaction log (`?action=`, `?entity_id=`, `?search=`, `?limit=`)
- `POST /search/seed?clean=` — seed from `app/data/seed_data.json`
- `POST /search/check-availability`

Full interactive documentation (with request/response schemas) is available
at `/docs` once the app is running.
