"""Unit tests for measurable and conditional image preprocessing operations."""

from __future__ import annotations

import unittest

import cv2
import numpy as np

from app.core.config import Settings
from app.services.image_security import DecodedPassportImage, validate_and_decode_image
from app.services.preprocessing import preprocess_passport_image
from tests.fixtures.synthetic_passports import make_image_bytes


class PreprocessingTests(unittest.TestCase):
    """Verify resizing, contrast adjustment, denoising, deskewing, and preservation of original image."""

    def test_oversized_image_resized_for_ocr_while_preserving_original(self) -> None:
        raw = make_image_bytes(width=1600, height=1000, fmt="PNG")
        decoded = validate_and_decode_image(raw)
        cfg = Settings(ocr_max_dimension=800)

        bundle = preprocess_passport_image(decoded, settings=cfg)
        self.assertTrue(bundle.metadata.resized_for_ocr)
        self.assertEqual(bundle.metadata.processed_width, 800)
        self.assertEqual(bundle.metadata.processed_height, 500)
        # Original decoded RGB array must remain untouched at full resolution
        self.assertEqual(bundle.original_rgb.shape, (1000, 1600, 3))

    def test_low_contrast_image_triggers_clahe(self) -> None:
        # Uniform gray image has std=0 (< 58.0) -> triggers CLAHE contrast enhancement
        raw = make_image_bytes(width=600, height=400, fmt="PNG", color=(128, 128, 128))
        decoded = validate_and_decode_image(raw)
        bundle = preprocess_passport_image(decoded)
        self.assertTrue(bundle.metadata.contrast_adjusted)
        self.assertTrue(any("clahe_contrast_enhancement" in s for s in bundle.metadata.steps_applied))

    def test_high_contrast_clean_image_skips_clahe_and_denoise(self) -> None:
        # Half black (0), half white (255) has std ~127.5 and zero speckle noise
        arr = np.zeros((400, 600, 3), dtype=np.uint8)
        arr[:, 300:] = 255
        decoded = DecodedPassportImage(
            rgb_array=arr,
            original_width=600,
            original_height=400,
            original_format="PNG",
            original_mode="RGB",
            file_size_bytes=24000,
            exif_orientation_applied=False,
            exif_orientation_tag=None,
        )
        bundle = preprocess_passport_image(decoded)
        self.assertFalse(bundle.metadata.contrast_adjusted)
        self.assertFalse(bundle.metadata.denoised)

    def test_skewed_lines_trigger_deskew_rotation(self) -> None:
        canvas = np.full((500, 800, 3), 255, dtype=np.uint8)
        for y in range(100, 420, 45):
            # Draw parallel lines tilted by ~4 degrees
            cv2.line(canvas, (80, y), (720, y + 45), (0, 0, 0), 3)

        decoded = DecodedPassportImage(
            rgb_array=canvas,
            original_width=800,
            original_height=500,
            original_format="PNG",
            original_mode="RGB",
            file_size_bytes=30000,
            exif_orientation_applied=False,
            exif_orientation_tag=None,
        )
        bundle = preprocess_passport_image(decoded)
        self.assertGreater(abs(bundle.metadata.deskew_angle_degrees), 2.0)
        self.assertTrue(any("deskew_rotation" in s for s in bundle.metadata.steps_applied))


if __name__ == "__main__":
    unittest.main()
