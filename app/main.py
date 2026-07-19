from fastapi import FastAPI

from app.config import settings
from app.api.error_handlers import register_exception_handlers
from app.api import unit, manufacturer, product, warehouse, inventory

app = FastAPI(title=settings.project_name)

register_exception_handlers(app)

app.include_router(unit.router, prefix=settings.api_v1_prefix)
app.include_router(manufacturer.router, prefix=settings.api_v1_prefix)
app.include_router(product.router, prefix=settings.api_v1_prefix)
app.include_router(warehouse.router, prefix=settings.api_v1_prefix)
app.include_router(inventory.router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
