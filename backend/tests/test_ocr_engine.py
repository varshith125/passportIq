"""Unit tests for RapidOCR output normalization, fallback policy, and timeout handling."""

from __future__ import annotations

import time
import unittest
from unittest.mock import patch

import numpy as np

from app.core.config import Settings
from app.core.errors import OcrEngineUnavailableError, OcrProcessingTimeoutError
from app.ocr.rapidocr_engine import RapidOcrEngineManager, parse_rapidocr_raw_output


class OcrEngineTests(unittest.TestCase):
    """Test OCR result parsing, explicit fallback policy, and timeout enforcement."""

    def test_parse_rapidocr_raw_output_handles_valid_and_malformed_entries(self) -> None:
        raw = (
            [
                [[[10, 20], [200, 20], [200, 45], [10, 45]], "PASSPORT", 0.982],
                [[[10, 60], [300, 60], [300, 85], [10, 85]], "   ", 0.91],  # whitespace only -> skipped
                ["malformed_entry"],  # skipped safely
                [[[10, 100], [400, 100], [400, 130], [10, 130]], "Surname: ERIKSSON", "95.5"],  # % clamped
            ],
            0.042,
        )
        blocks = parse_rapidocr_raw_output(raw)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].text, "PASSPORT")
        self.assertAlmostEqual(blocks[0].confidence, 0.982, places=3)
        self.assertEqual(blocks[1].text, "Surname: ERIKSSON")
        self.assertAlmostEqual(blocks[1].confidence, 0.955, places=3)

    def test_parse_rapidocr_empty_or_none_returns_empty_list(self) -> None:
        self.assertEqual(parse_rapidocr_raw_output(None), [])
        self.assertEqual(parse_rapidocr_raw_output((None, 0.01)), [])
        self.assertEqual(parse_rapidocr_raw_output(([], 0.01)), [])

    def test_unavailable_rapidocr_fails_closed_when_fallback_disabled(self) -> None:
        cfg = Settings(ocr_primary_engine="rapidocr", ocr_allow_tesseract_fallback=False)
        manager = RapidOcrEngineManager(settings=cfg)
        with patch.object(
            manager,
            "_ensure_rapidocr_loaded",
            return_value=(False, "rapidocr_onnxruntime not installed"),
        ):
            status = manager.get_readiness_status(cfg)
            self.assertFalse(status.ready)
            self.assertIsNone(status.active_engine)

            dummy_img = np.zeros((300, 400, 3), dtype=np.uint8)
            with self.assertRaises(OcrEngineUnavailableError) as ctx:
                manager.extract_text_blocks(dummy_img, settings=cfg)
            self.assertEqual(ctx.exception.status_code, 503)

    def test_explicit_tesseract_fallback_reports_fallback_transparently(self) -> None:
        cfg = Settings(ocr_primary_engine="rapidocr", ocr_allow_tesseract_fallback=True)
        manager = RapidOcrEngineManager(settings=cfg)
        with (
            patch.object(
                manager,
                "_ensure_rapidocr_loaded",
                return_value=(False, "rapidocr_onnxruntime unavailable in offline test"),
            ),
            patch.object(manager, "_check_tesseract_available", return_value=True),
            patch.object(manager, "_run_tesseract", return_value=[]),
        ):
            status = manager.get_readiness_status(cfg)
            self.assertTrue(status.ready)
            self.assertEqual(status.active_engine, "tesseract_fallback")

            dummy_img = np.zeros((300, 400, 3), dtype=np.uint8)
            result = manager.extract_text_blocks(dummy_img, settings=cfg)
            self.assertEqual(result.requested_engine, "rapidocr")
            self.assertEqual(result.active_engine, "tesseract_fallback")
            self.assertTrue(result.fallback_used)
            self.assertIn("unavailable", result.fallback_reason or "")

    def test_ocr_timeout_raises_timeout_error(self) -> None:
        cfg = Settings(
            ocr_primary_engine="rapidocr",
            ocr_allow_tesseract_fallback=False,
            ocr_timeout_seconds=0.05,
        )
        manager = RapidOcrEngineManager(settings=cfg)

        def _slow_ocr(_img: np.ndarray) -> list:
            time.sleep(0.3)
            return []

        with (
            patch.object(manager, "_ensure_rapidocr_loaded", return_value=(True, "ready")),
            patch.object(manager, "_run_rapidocr", side_effect=_slow_ocr),
        ):
            dummy_img = np.zeros((300, 400, 3), dtype=np.uint8)
            with self.assertRaises(OcrProcessingTimeoutError) as ctx:
                manager.extract_text_blocks(dummy_img, settings=cfg)
            self.assertEqual(ctx.exception.status_code, 504)


if __name__ == "__main__":
    unittest.main()
