"""Unit tests for secure image validation, signature verification, limits, EXIF, and privacy redaction."""

from __future__ import annotations

import unittest

from app.core.config import Settings
from app.core.errors import ImageValidationError
from app.core.logging import redact_sensitive_text
from app.services.image_security import detect_magic_signature, validate_and_decode_image
from tests.fixtures.synthetic_passports import make_image_bytes


class ImageSecurityTests(unittest.TestCase):
    """Verify strict file signature, dimension, pixel, decompression bomb, and EXIF handling."""

    def test_valid_formats_accepted(self) -> None:
        for fmt in ("PNG", "JPEG", "WEBP", "TIFF"):
            raw = make_image_bytes(width=640, height=420, fmt=fmt)
            self.assertEqual(detect_magic_signature(raw), fmt)
            decoded = validate_and_decode_image(raw, filename=f"sample.{fmt.lower()}")
            self.assertEqual(decoded.original_width, 640)
            self.assertEqual(decoded.original_height, 420)
            self.assertEqual(decoded.original_format, fmt)
            self.assertEqual(decoded.rgb_array.shape, (420, 640, 3))

    def test_empty_payload_rejected(self) -> None:
        with self.assertRaises(ImageValidationError) as ctx:
            validate_and_decode_image(b"")
        self.assertEqual(ctx.exception.code, "EMPTY_PAYLOAD")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_arbitrary_image_formats_accepted(self) -> None:
        for fmt in ("PNG", "JPEG", "WEBP", "TIFF", "BMP"):
            raw = make_image_bytes(width=640, height=420, fmt=fmt)
            decoded = validate_and_decode_image(raw, filename=f"sample.{fmt.lower()}")
            self.assertEqual(decoded.original_width, 640)
            self.assertEqual(decoded.original_height, 420)
            self.assertEqual(decoded.rgb_array.shape, (420, 640, 3))

    def test_undersized_dimensions_accepted_by_default(self) -> None:
        tiny = make_image_bytes(width=180, height=120, fmt="PNG")
        decoded = validate_and_decode_image(tiny)
        self.assertEqual(decoded.original_width, 180)
        self.assertEqual(decoded.original_height, 120)

    def test_undersized_dimensions_rejected_only_when_strict_settings(self) -> None:
        tiny = make_image_bytes(width=180, height=120, fmt="PNG")
        strict_settings = Settings(min_image_width=300, min_image_height=200)
        with self.assertRaises(ImageValidationError) as ctx:
            validate_and_decode_image(tiny, settings=strict_settings)
        self.assertEqual(ctx.exception.code, "IMAGE_DIMENSIONS_OUT_OF_RANGE")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_unparseable_non_image_bytes_rejected(self) -> None:
        garbage = b"NOT_A_VALID_IMAGE_OR_PDF_GARBAGE_PAYLOAD_9999"
        with self.assertRaises(ImageValidationError) as ctx:
            validate_and_decode_image(garbage)
        self.assertEqual(ctx.exception.code, "CORRUPT_IMAGE_DATA")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_oversized_file_bytes_rejected(self) -> None:
        raw = make_image_bytes(width=500, height=400, fmt="PNG")
        strict_settings = Settings(max_upload_bytes=100)
        with self.assertRaises(ImageValidationError) as ctx:
            validate_and_decode_image(raw, settings=strict_settings)
        self.assertEqual(ctx.exception.code, "PAYLOAD_TOO_LARGE")
        self.assertEqual(ctx.exception.status_code, 413)

    def test_oversized_dimensions_rejected(self) -> None:
        raw = make_image_bytes(width=900, height=600, fmt="PNG")
        strict_settings = Settings(max_image_width=800, max_image_height=800)
        with self.assertRaises(ImageValidationError) as ctx:
            validate_and_decode_image(raw, settings=strict_settings)
        self.assertEqual(ctx.exception.code, "IMAGE_DIMENSIONS_OUT_OF_RANGE")
        self.assertEqual(ctx.exception.status_code, 413)

    def test_pixel_count_and_decompression_bomb_limit_enforced(self) -> None:
        raw = make_image_bytes(width=800, height=600, fmt="PNG")  # 480,000 px
        strict_settings = Settings(max_image_pixels=250_000)
        with self.assertRaises(ImageValidationError) as ctx:
            validate_and_decode_image(raw, settings=strict_settings)
        self.assertIn(
            ctx.exception.code,
            {"IMAGE_PIXEL_LIMIT_EXCEEDED", "DECOMPRESSION_BOMB_DETECTED"},
        )
        self.assertEqual(ctx.exception.status_code, 413)

    def test_corrupted_image_stream_rejected(self) -> None:
        valid_png = make_image_bytes(width=500, height=400, fmt="PNG")
        corrupted = valid_png[:48] + b"\x00\xff\x00\xffcorrupt_stream"
        with self.assertRaises(ImageValidationError) as ctx:
            validate_and_decode_image(corrupted)
        self.assertEqual(ctx.exception.code, "CORRUPT_IMAGE_DATA")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_exif_orientation_transposed_correctly(self) -> None:
        # Create a 400x600 JPEG with EXIF Orientation=6 (Rotate 90 CW -> becomes 600x400)
        raw = make_image_bytes(width=400, height=600, fmt="JPEG", exif_orientation=6)
        decoded = validate_and_decode_image(raw)
        self.assertTrue(decoded.exif_orientation_applied)
        self.assertEqual(decoded.exif_orientation_tag, 6)
        self.assertEqual(decoded.original_width, 600)
        self.assertEqual(decoded.original_height, 400)

    def test_privacy_log_redaction_strips_mrz_and_pii(self) -> None:
        raw_log = (
            "Debug passport_number=L898902C3 surname=ERIKSSON "
            "line=P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
        )
        sanitized = redact_sensitive_text(raw_log)
        self.assertNotIn("L898902C3", sanitized)
        self.assertNotIn("ERIKSSON", sanitized)
        self.assertIn("[REDACTED]", sanitized)
        self.assertIn("[REDACTED_MRZ]", sanitized)


if __name__ == "__main__":
    unittest.main()
