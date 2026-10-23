"""Structured domain errors and HTTP status mappings for PassPortIQ."""

from __future__ import annotations


class PassPortIQError(Exception):
    """Base exception for controlled application errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ImageValidationError(PassPortIQError):
    """Raised when an uploaded file fails security, signature, or dimension validation."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, status_code=status_code, details=details)


class OcrEngineUnavailableError(PassPortIQError):
    """Raised when the configured OCR engine cannot be initialized or executed."""

    def __init__(
        self,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            code="OCR_ENGINE_UNAVAILABLE",
            message=message,
            status_code=503,
            details=details,
        )


class OcrProcessingTimeoutError(PassPortIQError):
    """Raised when OCR execution exceeds the configured timeout."""

    def __init__(
        self,
        message: str = "OCR processing timed out within configured resource limits.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            code="OCR_PROCESSING_TIMEOUT",
            message=message,
            status_code=504,
            details=details,
        )
