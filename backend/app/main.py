import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.config import settings
from app.api.error_handlers import register_exception_handlers
from app.api import unit, manufacturer, product, warehouse, inventory, search

app = FastAPI(title=settings.project_name)

register_exception_handlers(app)

app.include_router(unit.router, prefix=settings.api_v1_prefix)
app.include_router(manufacturer.router, prefix=settings.api_v1_prefix)
app.include_router(product.router, prefix=settings.api_v1_prefix)
app.include_router(warehouse.router, prefix=settings.api_v1_prefix)
app.include_router(inventory.router, prefix=settings.api_v1_prefix)
app.include_router(search.router, prefix=settings.api_v1_prefix)


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
