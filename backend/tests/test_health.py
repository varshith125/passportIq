"""API tests for /health/live and /health/ready endpoints."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.health import OcrDependencyStatus


class HealthEndpointTests(unittest.TestCase):
    """Verify liveness and readiness API behavior."""

    def setUp(self) -> None:
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_health_live_returns_200(self) -> None:
        response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "alive")
        self.assertEqual(body["service"], "PassPortIQ")

    def test_health_ready_returns_200_when_ocr_ready(self) -> None:
        mock_status = OcrDependencyStatus(
            primary_engine="rapidocr",
            primary_available=True,
            primary_status_detail="RapidOCR ONNX model initialized and ready.",
            tesseract_fallback_enabled=False,
            tesseract_available=True,
            active_engine="rapidocr_onnxruntime",
            ready=True,
        )
        with patch("app.api.health.get_ocr_manager") as mock_get_mgr:
            mock_get_mgr.return_value.get_readiness_status.return_value = mock_status
            response = self.client.get("/health/ready")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["ready"])
            self.assertEqual(body["ocr"]["active_engine"], "rapidocr_onnxruntime")

    def test_health_ready_returns_503_when_ocr_unavailable(self) -> None:
        mock_status = OcrDependencyStatus(
            primary_engine="rapidocr",
            primary_available=False,
            primary_status_detail="rapidocr_onnxruntime package is not installed.",
            tesseract_fallback_enabled=False,
            tesseract_available=True,
            active_engine=None,
            ready=False,
        )
        with patch("app.api.health.get_ocr_manager") as mock_get_mgr:
            mock_get_mgr.return_value.get_readiness_status.return_value = mock_status
            response = self.client.get("/health/ready")
            self.assertEqual(response.status_code, 503)
            body = response.json()
            self.assertFalse(body["ready"])
            self.assertEqual(body["status"], "degraded")


if __name__ == "__main__":
    unittest.main()
