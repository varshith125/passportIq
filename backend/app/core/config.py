"""Application settings and security boundaries for PassPortIQ."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_origins(value: str | None) -> list[str]:
    if not value:
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    return [origin.strip() for origin in value.split(",") if origin.strip()]


@dataclass(frozen=True)
class Settings:
    """Immutable application settings loaded from environment variables."""

    app_name: str = "PassPortIQ"
    app_title: str = "PassPortIQ — Intelligent Passport Data Extraction System"
    app_version: str = "2.0.0"
    env: str = field(default_factory=lambda: os.getenv("PASSPORTIQ_ENV", "development"))
    host: str = field(default_factory=lambda: os.getenv("PASSPORTIQ_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("PASSPORTIQ_PORT", "8000")))
    allowed_origins: list[str] = field(
        default_factory=lambda: _parse_origins(os.getenv("PASSPORTIQ_ALLOWED_ORIGINS"))
    )

    # Image upload & security limits (relaxed to accept any document/image)
    max_upload_bytes: int = field(
        default_factory=lambda: int(os.getenv("PASSPORTIQ_MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))
    )
    min_image_width: int = field(
        default_factory=lambda: int(os.getenv("PASSPORTIQ_MIN_IMAGE_WIDTH", "1"))
    )
    min_image_height: int = field(
        default_factory=lambda: int(os.getenv("PASSPORTIQ_MIN_IMAGE_HEIGHT", "1"))
    )
    max_image_width: int = field(
        default_factory=lambda: int(os.getenv("PASSPORTIQ_MAX_IMAGE_WIDTH", "25000"))
    )
    max_image_height: int = field(
        default_factory=lambda: int(os.getenv("PASSPORTIQ_MAX_IMAGE_HEIGHT", "25000"))
    )
    max_image_pixels: int = field(
        default_factory=lambda: int(os.getenv("PASSPORTIQ_MAX_IMAGE_PIXELS", "100000000"))
    )
    ocr_max_dimension: int = field(
        default_factory=lambda: int(os.getenv("PASSPORTIQ_OCR_MAX_DIMENSION", "3200"))
    )

    # OCR Engine configuration
    # Primary engine is always "rapidocr" unless explicitly configured otherwise.
    # Fallback to Tesseract is disabled by default so engine switches never happen silently.
    ocr_primary_engine: str = field(
        default_factory=lambda: os.getenv("PASSPORTIQ_OCR_PRIMARY_ENGINE", "rapidocr")
        .strip()
        .lower()
    )
    ocr_allow_tesseract_fallback: bool = field(
        default_factory=lambda: _parse_bool(
            os.getenv("PASSPORTIQ_OCR_ALLOW_TESSERACT_FALLBACK"), default=False
        )
    )
    ocr_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("PASSPORTIQ_OCR_TIMEOUT_SECONDS", "30.0"))
    )


def get_settings() -> Settings:
    """Load current settings from environment."""
    return Settings()
