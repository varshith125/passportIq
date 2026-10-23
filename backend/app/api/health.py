"""Liveness and readiness health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.core.config import get_settings
from app.ocr.rapidocr_engine import get_ocr_manager
from app.schemas.health import LivenessResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=LivenessResponse)
def health_live() -> LivenessResponse:
    """Indicate that the PassPortIQ backend service process is alive."""
    settings = get_settings()
    return LivenessResponse(
        status="alive",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get("/health/ready", response_model=ReadinessResponse)
def health_ready(response: Response) -> ReadinessResponse:
    """
    Indicate whether required dependencies (including the configured OCR engine) are ready.

    Returns HTTP 200 when ready, or HTTP 503 when the configured OCR engine is unavailable.
    """
    settings = get_settings()
    ocr_status = get_ocr_manager().get_readiness_status(settings=settings)
    if not ocr_status.ready:
        response.status_code = 503

    return ReadinessResponse(
        status="ready" if ocr_status.ready else "degraded",
        ready=ocr_status.ready,
        service=settings.app_name,
        version=settings.app_version,
        ocr=ocr_status,
    )
