"""Passport extraction endpoint with bounded upload reading and transient handling."""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from app.core.config import get_settings
from app.core.errors import ImageValidationError
from app.ocr.rapidocr_engine import get_ocr_manager
from app.pipeline.orchestrator import run_extraction_pipeline
from app.schemas.extraction import PassportExtractionResponse

router = APIRouter(prefix="/api/passports", tags=["passports"])

_READ_CHUNK_SIZE = 64 * 1024  # 64 KB chunks


@router.post("/extract", response_model=PassportExtractionResponse)
async def extract_passport_data(
    file: UploadFile = File(..., description="Passport image file (JPEG, PNG, WEBP, or TIFF)"),
) -> PassportExtractionResponse:
    """
    Accept an uploaded passport image, validate file signatures and safety limits,
    run OCR + MRZ + VIZ extraction and reconciliation, and return structured results.
    """
    settings = get_settings()
    max_bytes = settings.max_upload_bytes
    buffer = bytearray()

    try:
        while True:
            chunk = await file.read(_READ_CHUNK_SIZE)
            if not chunk:
                break
            buffer.extend(chunk)
            if len(buffer) > max_bytes:
                raise ImageValidationError(
                    code="PAYLOAD_TOO_LARGE",
                    message=(
                        f"Uploaded file exceeds maximum allowed size of {max_bytes} bytes "
                        f"({max_bytes // (1024 * 1024)} MB)."
                    ),
                    status_code=413,
                    details={"max_upload_bytes": max_bytes},
                )
        raw_bytes = bytes(buffer)
    finally:
        buffer.clear()
        await file.close()

    from app.services.image_security import detect_magic_signature

    if detect_magic_signature(raw_bytes) is None:
        raise ImageValidationError(
            code="INVALID_FILE_SIGNATURE",
            message="Uploaded file signature does not match any supported document or image format.",
            status_code=415,
            details={"filename": file.filename, "content_type": file.content_type},
        )

    return run_extraction_pipeline(
        raw_bytes=raw_bytes,
        filename=file.filename,
        content_type=file.content_type,
        settings=settings,
        ocr_manager=get_ocr_manager(),
    )
