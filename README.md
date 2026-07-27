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

`frontend/index.html` is a single-file dark-themed inventory control UI
(served at `/` by the FastAPI app, static images at `/assets`):

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
  Products may also carry an `image_url` for display in the UI.
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
  index.html                  # single-file inventory UI
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
- `POST/GET/PUT/DELETE /products`, plus `/activate`, `/deactivate`, `/change-unit/{unit_id}`, `?search=`, `?product_type=`
- `POST/GET/PUT/DELETE /warehouses`, `/racks`, `/shelves`, `/bins`, `/locations` (`GET /locations` lists all)
- `POST/GET/PUT/DELETE /inventory`, plus `/issue`, `/adjust`, `/reserve`, `/release`, `/move`, `/status`
- `GET /inventory/product/{id}/available`, `/inventory/product/{id}/total`
- `GET /logs` — business transaction log (`?action=`, `?entity_id=`, `?search=`, `?limit=`)
- `POST /search/seed?clean=` — seed from `app/data/seed_data.json`
- `POST /search/check-availability`

Full interactive documentation (with request/response schemas) is available
at `/docs` once the app is running.
