"""Health check schemas for liveness and readiness endpoints."""

from __future__ import annotations

from app.schemas.common import SchemaModel


class LivenessResponse(SchemaModel):
    """Response for GET /health/live."""

    status: str
    service: str
    version: str


class OcrDependencyStatus(SchemaModel):
    """Detailed status of the configured OCR engines."""

    primary_engine: str
    primary_available: bool
    primary_status_detail: str
    tesseract_fallback_enabled: bool
    tesseract_available: bool
    active_engine: str | None
    ready: bool


class ReadinessResponse(SchemaModel):
    """Response for GET /health/ready."""

    status: str
    ready: bool
    service: str
    version: str
    ocr: OcrDependencyStatus
