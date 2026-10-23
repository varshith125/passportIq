"""FastAPI application entry point for PassPortIQ v2."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.passports import router as passports_router
from app.core.config import Settings, get_settings
from app.core.errors import PassPortIQError
from app.core.logging import get_privacy_logger
from app.schemas.extraction import ApiErrorDetail, ApiErrorResponse

logger = get_privacy_logger("passportiq.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the PassPortIQ FastAPI application instance."""
    cfg = settings or get_settings()

    app = FastAPI(
        title=cfg.app_title,
        description="Accurate Passport Data Extraction with OCR & MRZ Validation",
        version=cfg.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure narrow CORS for intended frontend origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
        max_age=600,
    )

    @app.exception_handler(PassPortIQError)
    async def handle_passportiq_error(request: Request, exc: PassPortIQError) -> JSONResponse:
        logger.warning(
            "Controlled request error: path=%s code=%s status=%d",
            request.url.path,
            exc.code,
            exc.status_code,
        )
        payload = ApiErrorResponse(
            error=ApiErrorDetail(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            )
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("Request validation error on path=%s", request.url.path)
        payload = ApiErrorResponse(
            error=ApiErrorDetail(
                code="INVALID_REQUEST_PARAMETERS",
                message="Request parameters or multipart form fields are invalid or missing.",
                details={"field_errors_count": len(exc.errors())},
            )
        )
        return JSONResponse(status_code=422, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Never expose internal stack traces or raw exception messages to clients
        logger.error("Unhandled internal error on path=%s: %s", request.url.path, type(exc).__name__)
        payload = ApiErrorResponse(
            error=ApiErrorDetail(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected internal error occurred while processing the request.",
                details={},
            )
        )
        return JSONResponse(status_code=500, content=payload.model_dump())

    app.include_router(health_router)
    app.include_router(passports_router)

    # Mount frontend static distribution if available (bundled in PyInstaller or built locally)
    import os
    import sys
    from fastapi.staticfiles import StaticFiles

    candidate_dist_dirs = [
        os.path.join(getattr(sys, "_MEIPASS", ""), "frontend_dist") if getattr(sys, "_MEIPASS", None) else None,
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")),
        os.path.abspath(os.path.join(os.getcwd(), "frontend", "dist")),
    ]
    for dist_dir in candidate_dist_dirs:
        if dist_dir and os.path.isdir(dist_dir) and os.path.exists(os.path.join(dist_dir, "index.html")):
            logger.info("Serving frontend static assets from: %s", dist_dir)
            app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static_frontend")
            break

    return app


app = create_app()
