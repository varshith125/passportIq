"""End-to-end API tests for POST /api/passports/extract."""

from __future__ import annotations

import shutil
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.ocr.base import OcrEngineResult
from app.ocr.rapidocr_engine import RapidOcrEngineManager
from tests.fixtures.synthetic_passports import (
    make_image_bytes,
    make_synthetic_ocr_blocks,
    make_synthetic_passport_image_bytes,
)


class PassportExtractionApiTests(unittest.TestCase):
    """Verify full API extraction lifecycle, error envelopes, and live OCR fallback."""

    def setUp(self) -> None:
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_extract_passport_complete_success_with_rapidocr_blocks(self) -> None:
        img_bytes = make_image_bytes(width=900, height=600, fmt="PNG")
        mock_ocr_result = OcrEngineResult(
            requested_engine="rapidocr",
            active_engine="rapidocr_onnxruntime",
            fallback_used=False,
            fallback_reason=None,
            blocks=make_synthetic_ocr_blocks(),
            duration_ms=18.4,
        )
        with patch("app.api.passports.get_ocr_manager") as mock_get_mgr:
            mock_get_mgr.return_value.extract_text_blocks.return_value = mock_ocr_result
            response = self.client.post(
                "/api/passports/extract",
                files={"file": ("passport.png", img_bytes, "image/png")},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["document_classification"], "passport_td3")
        self.assertEqual(data["fields"]["passport_number"]["value"], "L898902C3")
        self.assertEqual(data["fields"]["surname"]["value"], "ERIKSSON")
        self.assertEqual(data["fields"]["given_names"]["value"], "ANNA MARIA")
        self.assertEqual(data["fields"]["date_of_birth"]["value"], "1974-08-12")
        self.assertEqual(data["fields"]["date_of_expiry"]["value"], "2030-04-15")
        self.assertEqual(data["fields"]["place_of_birth"]["value"], "STOCKHOLM")
        self.assertTrue(data["mrz"]["detected"])
        self.assertTrue(data["mrz"]["all_check_digits_valid"])
        self.assertEqual(data["reconciliation"]["overall_status"], "matched")
        self.assertEqual(data["ocr_metadata"]["active_engine"], "rapidocr_onnxruntime")
        self.assertFalse(data["ocr_metadata"]["fallback_used"])

    def test_extract_unlabelled_document_without_mrz_extracts_viz_and_returns_diagnostics(self) -> None:
        """Verify API extraction when OCR detects values without labels and without MRZ."""
        from app.ocr.base import OcrTextBlock

        img_bytes = make_image_bytes(width=900, height=600, fmt="PNG")
        unlabelled_blocks = [
            OcrTextBlock("PASSPORT", 0.99, ((300.0, 50.0), (500.0, 50.0), (500.0, 80.0), (300.0, 80.0))),
            OcrTextBlock("UNITED STATES OF AMERICA", 0.98, ((200.0, 90.0), (600.0, 90.0), (600.0, 120.0), (200.0, 120.0))),
            OcrTextBlock("LOPEZ", 0.99, ((250.0, 150.0), (350.0, 150.0), (350.0, 180.0), (250.0, 180.0))),
            OcrTextBlock("JOSHUA", 0.98, ((250.0, 190.0), (380.0, 190.0), (380.0, 220.0), (250.0, 220.0))),
            OcrTextBlock("USA", 0.99, ((250.0, 230.0), (310.0, 230.0), (310.0, 250.0), (250.0, 250.0))),
            OcrTextBlock("08SEP1973", 0.97, ((250.0, 260.0), (400.0, 260.0), (400.0, 280.0), (250.0, 280.0))),
            OcrTextBlock("NEWYORK.USA", 0.92, ((250.0, 290.0), (450.0, 290.0), (450.0, 310.0), (250.0, 310.0))),
            OcrTextBlock("06JAN2024", 0.98, ((250.0, 320.0), (400.0, 320.0), (400.0, 340.0), (250.0, 340.0))),
            OcrTextBlock("06JAN2034", 0.98, ((250.0, 350.0), (400.0, 350.0), (400.0, 370.0), (250.0, 370.0))),
            OcrTextBlock("K38542916", 0.98, ((600.0, 80.0), (780.0, 80.0), (780.0, 110.0), (600.0, 110.0))),
        ]
        mock_ocr_result = OcrEngineResult(
            requested_engine="rapidocr",
            active_engine="rapidocr_onnxruntime",
            fallback_used=False,
            fallback_reason=None,
            blocks=unlabelled_blocks,
            duration_ms=45.2,
        )
        with patch("app.api.passports.get_ocr_manager") as mock_get_mgr:
            mock_get_mgr.return_value.extract_text_blocks.return_value = mock_ocr_result
            response = self.client.post(
                "/api/passports/extract",
                files={"file": ("passport_male2.jpg", img_bytes, "image/jpeg")},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "partial")
        self.assertFalse(data["mrz"]["detected"])
        self.assertEqual(data["fields"]["surname"]["value"], "LOPEZ")
        self.assertEqual(data["fields"]["surname"]["source"], "viz")
        self.assertEqual(data["fields"]["given_names"]["value"], "JOSHUA")
        self.assertEqual(data["fields"]["full_name"]["value"], "JOSHUA LOPEZ")
        self.assertEqual(data["fields"]["nationality"]["value"], "USA")
        self.assertEqual(data["fields"]["passport_number"]["value"], "K38542916")
        self.assertEqual(data["fields"]["date_of_birth"]["value"], "1973-09-08")
        self.assertEqual(data["fields"]["place_of_birth"]["value"], "NEWYORK, USA")
        self.assertEqual(data["fields"]["date_of_issue"]["value"], "2024-01-06")
        self.assertEqual(data["fields"]["date_of_expiry"]["value"], "2034-01-06")
        self.assertIsNone(data["fields"]["personal_number"]["value"])
        self.assertEqual(data["reconciliation"]["overall_status"], "insufficient_data")
        self.assertEqual(data["ocr_metadata"]["detected_blocks_count"], 10)
        self.assertIsNotNone(data["ocr_metadata"]["mean_ocr_confidence"])
        self.assertIn("steps_applied", data["preprocessing"])
        self.assertIn("transient_processing_notice", data)

    def test_extract_blank_image_returns_no_passport_detected(self) -> None:
        img_bytes = make_image_bytes(width=800, height=550, fmt="PNG")
        mock_ocr_result = OcrEngineResult(
            requested_engine="rapidocr",
            active_engine="rapidocr_onnxruntime",
            fallback_used=False,
            fallback_reason=None,
            blocks=[],
            duration_ms=9.1,
        )
        with patch("app.api.passports.get_ocr_manager") as mock_get_mgr:
            mock_get_mgr.return_value.extract_text_blocks.return_value = mock_ocr_result
            response = self.client.post(
                "/api/passports/extract",
                files={"file": ("blank.png", img_bytes, "image/png")},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "no_passport_detected")
        self.assertEqual(data["document_classification"], "unknown")
        self.assertFalse(data["mrz"]["detected"])
        self.assertTrue(any(w["code"] == "EMPTY_OCR_RESULT" for w in data["warnings"]))

    def test_extract_rejects_invalid_file_signature_with_415(self) -> None:
        response = self.client.post(
            "/api/passports/extract",
            files={"file": ("malicious.png", b"not an image file payload", "image/png")},
        )
        self.assertEqual(response.status_code, 415)
        body = response.json()
        self.assertEqual(body["error"]["code"], "INVALID_FILE_SIGNATURE")

    def test_extract_rejects_oversized_upload_with_413(self) -> None:
        small_limit_settings = Settings(max_upload_bytes=512)
        with patch("app.api.passports.get_settings", return_value=small_limit_settings):
            img_bytes = make_image_bytes(width=800, height=550, fmt="JPEG")
            response = self.client.post(
                "/api/passports/extract",
                files={"file": ("large.jpg", img_bytes, "image/jpeg")},
            )
        self.assertEqual(response.status_code, 413)
        body = response.json()
        self.assertEqual(body["error"]["code"], "PAYLOAD_TOO_LARGE")

    @unittest.skipUnless(
        shutil.which("tesseract") is not None,
        "Requires local tesseract binary for live fallback OCR test",
    )
    def test_live_end_to_end_extraction_with_explicit_tesseract_fallback(self) -> None:
        """Run a genuine end-to-end image -> preprocessing -> Tesseract fallback OCR -> MRZ/VIZ test."""
        fallback_settings = Settings(
            ocr_primary_engine="rapidocr",
            ocr_allow_tesseract_fallback=True,
        )
        live_manager = RapidOcrEngineManager(settings=fallback_settings)
        synth_png = make_synthetic_passport_image_bytes()

        with (
            patch("app.api.passports.get_settings", return_value=fallback_settings),
            patch("app.api.passports.get_ocr_manager", return_value=live_manager),
        ):
            response = self.client.post(
                "/api/passports/extract",
                files={"file": ("synthetic_passport.png", synth_png, "image/png")},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ocr_metadata"]["requested_engine"], "rapidocr")
        self.assertEqual(data["ocr_metadata"]["active_engine"], "tesseract_fallback")
        self.assertTrue(data["ocr_metadata"]["fallback_used"])
        self.assertTrue(any(w["code"] == "OCR_FALLBACK_ENGINE_USED" for w in data["warnings"]))
        self.assertGreater(data["ocr_metadata"]["detected_blocks_count"], 5)
        self.assertEqual(data["fields"]["surname"]["value"], "ERIKSSON")


if __name__ == "__main__":
    unittest.main()
