import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.shared.error_handlers import register_exception_handlers

# Each domain owns its own api module. Grouping the imports by domain here
# mirrors the folder layout under app/ (master_data, procurement, wms, quality,
# platform) - see docs/HIGH_LEVEL_ARCHITECTURE.md for the full domain map.
from app.master_data.unit import api as unit_api
from app.master_data.manufacturer import api as manufacturer_api
from app.master_data.product import api as product_api

from app.procurement.supplier import api as supplier_api
from app.procurement.requisition import api as requisition_api
from app.procurement.rfq import api as rfq_api
from app.procurement.vendor_quotation import api as vendor_quotation_api
from app.procurement.purchase_order import api as purchase_order_api
from app.procurement.vendor_invoice import api as vendor_invoice_api
from app.procurement.dashboard import api as procurement_dashboard_api

from app.wms.warehouse_structure import api as warehouse_api
from app.wms.inventory import api as inventory_api
from app.wms.goods_receipt import api as goods_receipt_api

from app.quality.inspection import api as quality_inspection_api

from app.platform.search import api as search_api
from app.platform.logs import api as logs_api

from app.db.connection import Base, engine
from app.db import model_registry  # noqa: F401 - importing registers every model on Base.metadata


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

# master_data
app.include_router(unit_api.router, prefix=settings.api_v1_prefix)
app.include_router(manufacturer_api.router, prefix=settings.api_v1_prefix)
app.include_router(product_api.router, prefix=settings.api_v1_prefix)

# procurement
app.include_router(supplier_api.router, prefix=settings.api_v1_prefix)
app.include_router(requisition_api.router, prefix=settings.api_v1_prefix)
app.include_router(rfq_api.router, prefix=settings.api_v1_prefix)
app.include_router(vendor_quotation_api.router, prefix=settings.api_v1_prefix)
app.include_router(purchase_order_api.router, prefix=settings.api_v1_prefix)
app.include_router(vendor_invoice_api.router, prefix=settings.api_v1_prefix)
app.include_router(procurement_dashboard_api.router, prefix=settings.api_v1_prefix)

# wms
app.include_router(warehouse_api.router, prefix=settings.api_v1_prefix)
app.include_router(inventory_api.router, prefix=settings.api_v1_prefix)
app.include_router(goods_receipt_api.router, prefix=settings.api_v1_prefix)

# quality
app.include_router(quality_inspection_api.router, prefix=settings.api_v1_prefix)

# platform
app.include_router(search_api.router, prefix=settings.api_v1_prefix)
app.include_router(logs_api.router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


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
    # Product images (e.g. /assets/products/PROD-001.png), unrelated to the
    # React build output below.
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

# The React frontend (built via `npm run build` in frontend/web, see
# frontend/web/vite.config.js) is emitted to frontend/dist. Its JS/CSS
# bundles live under /app/ (configured via vite's build.assetsDir) so they
# never collide with the /assets mount above. Mounting it last, with
# html=True, means it also serves dist/index.html for "/".
_dist_dir = _resolve_dir([
    "frontend/dist",
    "../frontend/dist",
    "../../frontend/dist",
    "/code/frontend/dist",
])
if _dist_dir:
    app.mount("/", StaticFiles(directory=_dist_dir, html=True), name="frontend")
