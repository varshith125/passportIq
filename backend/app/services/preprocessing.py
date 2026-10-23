"""Measurable, conditional image preprocessing pipeline for passport OCR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np

from app.core.config import Settings, get_settings
from app.schemas.extraction import PreprocessingMetadata
from app.services.image_security import DecodedPassportImage


@dataclass(frozen=True)
class PreprocessedImageBundle:
    """Holds original and preprocessed image variants along with audit metadata."""

    original_rgb: np.ndarray
    ocr_rgb: np.ndarray
    ocr_gray: np.ndarray
    metadata: PreprocessingMetadata


def _estimate_skew_angle(gray: np.ndarray) -> float:
    """
    Estimate slight document skew angle in degrees using Canny edges and probabilistic Hough lines.

    Returns 0.0 when no reliable near-horizontal text line skew is detected.
    """
    h, w = gray.shape[:2]
    if h < 100 or w < 100:
        return 0.0

    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    min_line_length = max(40, w // 5)
    lines = cv2.HoughLinesP(
        edges,
        rho=1.0,
        theta=np.pi / 180.0,
        threshold=80,
        minLineLength=min_line_length,
        maxLineGap=15,
    )
    if lines is None or len(lines) < 3:
        return 0.0

    angles: List[float] = []
    for line in lines.reshape(-1, 4):
        x1, y1, x2, y2 = int(line[0]), int(line[1]), int(line[2]), int(line[3])
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0:
            continue
        angle = float(np.degrees(np.arctan2(dy, dx)))
        if -12.0 <= angle <= 12.0:
            angles.append(angle)

    if len(angles) < 3:
        return 0.0

    median_angle = float(np.median(angles))
    std_angle = float(np.std(angles))
    if abs(median_angle) >= 0.85 and std_angle <= 3.5:
        return round(median_angle, 2)
    return 0.0


def _rotate_bound(image: np.ndarray, angle_degrees: float) -> np.ndarray:
    """Rotate an image around its center by angle_degrees with border replication."""
    h, w = image.shape[:2]
    center = (w / 2.0, h / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle_degrees, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def compute_image_quality_metrics(gray: np.ndarray) -> dict[str, float]:
    """
    Measure quantitative image degradation signals:
    - blur_score: Variance of Laplacian. Sharp documents typically >= 130.0; mild blur < 110.0.
    - contrast_range: Foreground-to-background dynamic range (P99.5 - P0.5).
    - noise_estimate: High-frequency speckle difference from median filtering.
    """
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    blur_score = float(lap.var())

    p_low, p_high = np.percentile(gray, [0.5, 99.5])
    contrast_range = float(p_high - p_low)

    median_filtered = cv2.medianBlur(gray, 3)
    noise_estimate = float(np.mean(cv2.absdiff(gray, median_filtered)))

    return {
        "blur_score": round(blur_score, 2),
        "contrast_range": round(contrast_range, 2),
        "noise_estimate": round(noise_estimate, 2),
    }


def apply_conservative_sharpening(image: np.ndarray, amount: float = 0.6) -> np.ndarray:
    """
    Apply conservative Gaussian unsharp masking to recover soft character edges on mildly blurry images.

    Avoids harsh discrete Laplacian kernel ringing and halo artifacts.
    """
    gaussian = cv2.GaussianBlur(image, (0, 0), sigmaX=1.5)
    sharpened = cv2.addWeighted(image, 1.0 + amount, gaussian, -amount, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def preprocess_passport_image(
    decoded: DecodedPassportImage,
    settings: Optional[Settings] = None,
    enable_adaptive_threshold: bool = False,
    force_sharpening: bool = False,
) -> PreprocessedImageBundle:
    """
    Selectively normalize a decoded passport image for OCR without destroying visual evidence.

    Operations are applied conditionally based on measurable image statistics:
    - EXIF orientation (already recorded in DecodedPassportImage)
    - Downscaling oversized images (> ocr_max_dimension) with area interpolation
    - Grayscale conversion for luminance analysis
    - Deskewing when a consistent horizontal line skew (0.85°..12.0°) is detected
    - Bilateral denoising when high-frequency noise is elevated
    - Conservative unsharp masking when mild blur is detected without high noise
    - CLAHE contrast adjustment when foreground-background dynamic range (P99.5 - P0.5) is low (< 110.0)
    - Optional adaptive thresholding only when explicitly requested
    """
    cfg = settings or get_settings()
    steps: List[str] = []

    if decoded.exif_orientation_applied:
        steps.append(f"exif_orientation_transpose(tag={decoded.exif_orientation_tag})")

    working_rgb = decoded.rgb_array.copy()
    orig_h, orig_w = working_rgb.shape[:2]
    resized_for_ocr = False

    max_dim = max(orig_w, orig_h)
    if max_dim > cfg.ocr_max_dimension:
        scale = cfg.ocr_max_dimension / float(max_dim)
        new_w = max(1, int(round(orig_w * scale)))
        new_h = max(1, int(round(orig_h * scale)))
        working_rgb = cv2.resize(working_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
        resized_for_ocr = True
        steps.append(f"resize_for_ocr({orig_w}x{orig_h}->{new_w}x{new_h})")
    elif 0 < max_dim < 600:
        scale = 800.0 / float(max_dim)
        new_w = max(1, int(round(orig_w * scale)))
        new_h = max(1, int(round(orig_h * scale)))
        working_rgb = cv2.resize(working_rgb, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        resized_for_ocr = True
        steps.append(f"upscale_for_ocr({orig_w}x{orig_h}->{new_w}x{new_h})")

    gray = cv2.cvtColor(working_rgb, cv2.COLOR_RGB2GRAY)
    grayscale_applied = True
    steps.append("grayscale_conversion")

    skew_angle = _estimate_skew_angle(gray)
    if abs(skew_angle) >= 0.85:
        working_rgb = _rotate_bound(working_rgb, skew_angle)
        gray = _rotate_bound(gray, skew_angle)
        steps.append(f"deskew_rotation({skew_angle:.2f}deg)")
    else:
        skew_angle = 0.0

    metrics = compute_image_quality_metrics(gray)
    blur_score = metrics["blur_score"]
    dynamic_range = metrics["contrast_range"]
    noise_estimate = metrics["noise_estimate"]

    denoised = False
    if noise_estimate > 6.5:
        gray = cv2.bilateralFilter(gray, d=5, sigmaColor=35, sigmaSpace=35)
        denoised = True
        steps.append(f"bilateral_denoise(noise={noise_estimate:.2f})")

    is_blurry = blur_score < 110.0
    sharpening_applied = False
    if (is_blurry or force_sharpening) and noise_estimate < 10.0:
        gray = apply_conservative_sharpening(gray, amount=0.55)
        sharpening_applied = True
        steps.append(f"conservative_unsharp_mask(blur_score={blur_score:.1f})")

    contrast_adjusted = False
    if dynamic_range < 110.0:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        contrast_adjusted = True
        steps.append(f"clahe_contrast_enhancement(range={dynamic_range:.1f})")

    threshold_applied = False
    if enable_adaptive_threshold:
        gray = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            10,
        )
        threshold_applied = True
        steps.append("adaptive_gaussian_threshold")

    if contrast_adjusted or denoised or threshold_applied or sharpening_applied:
        ocr_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    else:
        ocr_rgb = working_rgb

    proc_h, proc_w = ocr_rgb.shape[:2]

    # Quality diagnosis
    quality_notes: List[str] = []
    if is_blurry:
        quality_notes.append("mild_blur")
    if dynamic_range < 110.0:
        quality_notes.append("low_contrast")
    if noise_estimate > 6.5:
        quality_notes.append("elevated_noise")
    quality_assessment = ", ".join(quality_notes) if quality_notes else "optimal"

    metadata = PreprocessingMetadata(
        original_width=decoded.original_width,
        original_height=decoded.original_height,
        original_format=decoded.original_format,
        original_mode=decoded.original_mode,
        file_size_bytes=decoded.file_size_bytes,
        exif_orientation_applied=decoded.exif_orientation_applied,
        exif_orientation_tag=decoded.exif_orientation_tag,
        resized_for_ocr=resized_for_ocr,
        processed_width=proc_w,
        processed_height=proc_h,
        steps_applied=steps,
        grayscale_applied=grayscale_applied,
        contrast_adjusted=contrast_adjusted,
        denoised=denoised,
        deskew_angle_degrees=skew_angle,
        threshold_applied=threshold_applied,
        blur_score=blur_score,
        is_blurry=is_blurry,
        sharpening_applied=sharpening_applied,
        quality_assessment=quality_assessment,
        variants_evaluated=["baseline"],
        winning_variant="baseline",
    )

    return PreprocessedImageBundle(
        original_rgb=decoded.rgb_array,
        ocr_rgb=ocr_rgb,
        ocr_gray=gray,
        metadata=metadata,
    )
