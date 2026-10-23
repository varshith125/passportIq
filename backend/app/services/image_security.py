"""Secure image and document upload validation and safe decoding."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image, ImageOps

from app.core.config import Settings, get_settings
from app.core.errors import ImageValidationError

# Magic-byte file signatures for detection
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_RIFF_MAGIC = b"RIFF"
_WEBP_MAGIC = b"WEBP"
_TIFF_LE_MAGIC = b"II*\x00"
_TIFF_BE_MAGIC = b"MM\x00*"
_PDF_MAGIC = b"%PDF"
_BMP_MAGIC = b"BM"
_GIF_MAGIC = b"GIF8"

SUPPORTED_PIL_FORMATS = {
    "JPEG", "PNG", "WEBP", "TIFF", "BMP", "GIF", "PDF", "ICO", "PPM", "TGA", "AVIF", "HEIC"
}
EXIF_ORIENTATION_TAG = 0x0112  # 274


@dataclass(frozen=True)
class DecodedPassportImage:
    """Safely decoded in-memory image representation and header metadata."""

    rgb_array: np.ndarray
    original_width: int
    original_height: int
    original_format: str
    original_mode: str
    file_size_bytes: int
    exif_orientation_applied: bool
    exif_orientation_tag: Optional[int]


def detect_magic_signature(data: bytes) -> Optional[str]:
    """Inspect raw magic bytes to identify image/document format."""
    if len(data) < 2:
        return None
    if data.startswith(_JPEG_MAGIC):
        return "JPEG"
    if data.startswith(_PNG_MAGIC):
        return "PNG"
    if len(data) >= 12 and data.startswith(_RIFF_MAGIC) and data[8:12] == _WEBP_MAGIC:
        return "WEBP"
    if data.startswith(_TIFF_LE_MAGIC) or data.startswith(_TIFF_BE_MAGIC):
        return "TIFF"
    if data.startswith(_PDF_MAGIC):
        return "PDF"
    if data.startswith(_BMP_MAGIC):
        return "BMP"
    if data.startswith(_GIF_MAGIC):
        return "GIF"
    return None


def validate_and_decode_image(
    raw_bytes: bytes,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> DecodedPassportImage:
    """
    Safely decode uploaded file into an in-memory RGB image.
    Supports any image format, PDF documents, and arbitrary dimensions.
    """
    cfg = settings or get_settings()

    if not raw_bytes:
        raise ImageValidationError(
            code="EMPTY_PAYLOAD",
            message="Uploaded image file is empty (0 bytes).",
            status_code=400,
        )

    file_size = len(raw_bytes)
    if file_size > cfg.max_upload_bytes:
        raise ImageValidationError(
            code="PAYLOAD_TOO_LARGE",
            message=(
                f"Uploaded file size ({file_size} bytes) exceeds maximum allowed limit "
                f"of {cfg.max_upload_bytes} bytes."
            ),
            status_code=413,
            details={"file_size_bytes": file_size, "max_upload_bytes": cfg.max_upload_bytes},
        )

    # 1. Check if the file is a PDF document
    is_pdf = raw_bytes.startswith(_PDF_MAGIC) or bool(
        filename and filename.lower().endswith(".pdf")
    )
    if is_pdf:
        try:
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz

            doc = fitz.open(stream=raw_bytes, filetype="pdf")
            if len(doc) > 0:
                page = doc[0]
                pix = page.get_pixmap(dpi=200)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                rgb_array = np.array(img, dtype=np.uint8, copy=True)
                w, h = pix.width, pix.height
                return DecodedPassportImage(
                    rgb_array=rgb_array,
                    original_width=w,
                    original_height=h,
                    original_format="PDF",
                    original_mode="RGB",
                    file_size_bytes=file_size,
                    exif_orientation_applied=False,
                    exif_orientation_tag=None,
                )
        except Exception:
            pass  # Fall through to PIL/OpenCV decoding

    # 2. General image decoding with Pillow and OpenCV fallback
    previous_max_pixels = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = cfg.max_image_pixels

    decoded_image: Optional[DecodedPassportImage] = None

    try:
        # Step 1: Verify stream integrity if image header is recognized
        try:
            with io.BytesIO(raw_bytes) as verify_stream:
                with Image.open(verify_stream) as verify_img:
                    verify_img.verify()
        except (OSError, SyntaxError, ValueError) as exc:
            # Check if OpenCV can salvage it, otherwise fail as corrupted
            import cv2
            buf = np.frombuffer(raw_bytes, dtype=np.uint8)
            cv_img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            if cv_img is None:
                raise ImageValidationError(
                    code="CORRUPT_IMAGE_DATA",
                    message="Uploaded image file is malformed, truncated, or corrupted.",
                    status_code=400,
                ) from exc

        # Step 2: Open and decode image
        try:
            with io.BytesIO(raw_bytes) as stream:
                with Image.open(stream) as img:
                    original_mode = img.mode
                    detected_format = (
                        img.format or detect_magic_signature(raw_bytes) or "IMAGE"
                    ).upper()

                    exif_orientation: Optional[int] = None
                    try:
                        exif_data = img.getexif()
                        if exif_data and EXIF_ORIENTATION_TAG in exif_data:
                            raw_tag = exif_data.get(EXIF_ORIENTATION_TAG)
                            if isinstance(raw_tag, int):
                                exif_orientation = raw_tag
                    except Exception:
                        exif_orientation = None

                    exif_applied = False
                    if exif_orientation in {2, 3, 4, 5, 6, 7, 8}:
                        transposed = ImageOps.exif_transpose(img)
                        if transposed is not None:
                            img = transposed
                            exif_applied = True

                    w, h = img.size
                    total_pixels = w * h

                    if total_pixels > cfg.max_image_pixels:
                        raise ImageValidationError(
                            code="IMAGE_PIXEL_LIMIT_EXCEEDED",
                            message=(
                                f"Image pixel count ({total_pixels:,} px) exceeds maximum safe limit "
                                f"of {cfg.max_image_pixels:,} pixels."
                            ),
                            status_code=413,
                        )

                    # Ensure pixel integrity is validated
                    img.load()

                    # Only enforce minimum bounds if explicitly set above 1
                    if (cfg.min_image_width > 1 and w < cfg.min_image_width) or (
                        cfg.min_image_height > 1 and h < cfg.min_image_height
                    ):
                        raise ImageValidationError(
                            code="IMAGE_DIMENSIONS_OUT_OF_RANGE",
                            message=(
                                f"Image dimensions ({w}x{h}) are smaller than minimum "
                                f"required ({cfg.min_image_width}x{cfg.min_image_height})."
                            ),
                            status_code=400,
                        )

                    if w > cfg.max_image_width or h > cfg.max_image_height:
                        raise ImageValidationError(
                            code="IMAGE_DIMENSIONS_OUT_OF_RANGE",
                            message=(
                                f"Image dimensions ({w}x{h}) exceed maximum allowed dimensions "
                                f"({cfg.max_image_width}x{cfg.max_image_height})."
                            ),
                            status_code=413,
                        )

                    rgb_img = img.convert("RGB")
                    rgb_array = np.array(rgb_img, dtype=np.uint8, copy=True)
                    rgb_img.close()

                    decoded_image = DecodedPassportImage(
                        rgb_array=rgb_array,
                        original_width=w,
                        original_height=h,
                        original_format=detected_format,
                        original_mode=original_mode,
                        file_size_bytes=file_size,
                        exif_orientation_applied=exif_applied,
                        exif_orientation_tag=exif_orientation,
                    )
        except Image.DecompressionBombError as exc:
            raise ImageValidationError(
                code="DECOMPRESSION_BOMB_DETECTED",
                message="Image rejected due to decompression bomb protection limits.",
                status_code=413,
            ) from exc
        except ImageValidationError:
            raise
        except Exception:
            # OpenCV imdecode fallback
            try:
                import cv2

                buf = np.frombuffer(raw_bytes, dtype=np.uint8)
                cv_img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                if cv_img is not None:
                    h, w = cv_img.shape[:2]
                    rgb_array = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                    decoded_image = DecodedPassportImage(
                        rgb_array=rgb_array,
                        original_width=w,
                        original_height=h,
                        original_format="OPENCV",
                        original_mode="RGB",
                        file_size_bytes=file_size,
                        exif_orientation_applied=False,
                        exif_orientation_tag=None,
                    )
            except Exception:
                pass
    finally:
        Image.MAX_IMAGE_PIXELS = previous_max_pixels

    if decoded_image is None:
        raise ImageValidationError(
            code="CORRUPT_IMAGE_DATA",
            message="Uploaded file could not be parsed or decoded as an image or document.",
            status_code=400,
        )

    return decoded_image
