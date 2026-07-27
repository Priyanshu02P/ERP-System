import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.error_handlers import register_exception_handlers
from app.api import unit, manufacturer, product, warehouse, inventory, search, logs
from app.db.connection import Base, engine
from app.db import models  # noqa: F401 - importing registers every model on Base.metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates any tables that don't exist yet. This is idempotent (it never
    # touches tables that already exist), so it's safe to run on every
    # startup - a fresh `docker compose up --build` works immediately
    # without a manual `alembic upgrade head` step. Once the schema is
    # established, use Alembic migrations for further changes.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.project_name, lifespan=lifespan)

register_exception_handlers(app)

app.include_router(unit.router, prefix=settings.api_v1_prefix)
app.include_router(manufacturer.router, prefix=settings.api_v1_prefix)
app.include_router(product.router, prefix=settings.api_v1_prefix)
app.include_router(warehouse.router, prefix=settings.api_v1_prefix)
app.include_router(inventory.router, prefix=settings.api_v1_prefix)
app.include_router(search.router, prefix=settings.api_v1_prefix)
app.include_router(logs.router, prefix=settings.api_v1_prefix)


def _resolve_dir(candidates: list[str]) -> str | None:
    for p in candidates:
        if os.path.isdir(p):
            return p
    return None


_assets_dir = _resolve_dir([
    "frontend/assets",
    "../frontend/assets",
    "../../frontend/assets",
    "/code/frontend/assets",
])
if _assets_dir:
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_ui():
    paths = [
        "frontend/index.html",
        "../frontend/index.html",
        "../../frontend/index.html",
        "/code/frontend/index.html"
    ]
    for p in paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="<h1>ERP System UI</h1><p>index.html not found. Please ensure it exists in the frontend/ folder.</p>",
        status_code=404
    )


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
