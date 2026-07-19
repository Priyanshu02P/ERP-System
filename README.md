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

The first time you start it, create the tables (see "Migrations" below).

## Quick start (local, no Docker)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL if needed, e.g. point at a local Postgres
uvicorn app.main:app --reload
```

## Migrations (Alembic)

The `alembic/` scaffold is in place but no migration has been generated yet
(this sandbox has no live Postgres to autogenerate against). Once your
database is up:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

For quick local iteration without migrations, you can also just do:

```python
from app.db.connection import Base, engine
from app.db import models
Base.metadata.create_all(engine)
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
- **Inventory status**: `OK`, `RJC` (rejected), `MIS` (missing), `RET` (returned), `HLD` (on hold), `DMG` (damaged).
- **Location hierarchy**: `Warehouse → Rack → Shelf → Bin`. A shelf can never
  be specified without its rack, and a bin never without its shelf.
  Oversized items may stop at the rack level (e.g. `WH1-A`).
  `SHEET` / `PIPE` are dedicated oversized-item zones, rendered as `SHEET-A` / `PIPE-A`.
- **Composite inventory display string** combines status (or product type,
  when status is `OK`) with the location code, e.g.:
  - `FG-WH1-A-03-05` — finished good, ready to sell, at bin 05 / shelf 03 / rack A / warehouse 1
  - `RET-WH3-A` — returned item, stored at rack A / warehouse 3

## Project layout

```
app/
  config.py                 # pydantic-settings configuration
  main.py                   # FastAPI app + router wiring
  db/
    connection.py            # engine / session / declarative Base
    models/                  # SQLAlchemy ORM models
    schemas/                 # Pydantic request/response schemas
    repositories/             # DB-only query layer
  services/                  # Business rules layer
  api/                        # FastAPI routers
tests/                        # Pytest suite (SQLite in-memory)
alembic/                      # Migration scaffold
docker-compose.yml
Dockerfile
requirements.txt
```

## API overview

All routes are prefixed with `/api/v1`.

- `POST/GET/PUT/DELETE /units`, plus `/activate`, `/deactivate`
- `POST/GET/PUT/DELETE /manufacturers`, plus `/activate`, `/deactivate`, `?search=`
- `POST/GET/PUT/DELETE /products`, plus `/activate`, `/deactivate`, `/change-unit/{unit_id}`, `?search=`, `?product_type=`
- `POST/GET/PUT/DELETE /warehouses`, `/racks`, `/shelves`, `/bins`, `/locations`
- `POST/GET/PUT/DELETE /inventory`, plus `/issue`, `/adjust`, `/reserve`, `/release`, `/move`, `/status`
- `GET /inventory/product/{id}/available`, `/inventory/product/{id}/total`

Full interactive documentation (with request/response schemas) is available
at `/docs` once the app is running.
