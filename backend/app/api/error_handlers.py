from fastapi import Request
from fastapi.responses import JSONResponse

from app.services.exceptions import (
    NotFoundError,
    ConflictError,
    ValidationError,
    ReferencedEntityError,
)


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.message})


async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.message})


async def referenced_entity_handler(request: Request, exc: ReferencedEntityError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": exc.message})


def register_exception_handlers(app) -> None:
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(ConflictError, conflict_handler)
    app.add_exception_handler(ValidationError, validation_handler)
    app.add_exception_handler(ReferencedEntityError, referenced_entity_handler)
