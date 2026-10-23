"""Targeted multi-variant OCR recovery and candidate reconciliation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.core.config import Settings, get_settings
from app.mrz.detector import detect_mrz_candidate
from app.mrz.parser import MrzParseResult, parse_mrz_candidate, parse_mrz_from_blocks
from app.ocr.base import OcrEngineResult, OcrTextBlock
from app.ocr.rapidocr_engine import RapidOcrEngineManager
from app.schemas.extraction import MrzFormat
from app.services.image_security import DecodedPassportImage
from app.services.preprocessing import (
    PreprocessedImageBundle,
    apply_conservative_sharpening,
)
from app.viz.extractor import VizFieldResult, extract_viz_fields


@dataclass
class OcrVariantCandidate:
    """Represents a candidate extraction outcome from an individual preprocessing variant."""

    variant_name: str
    blocks: List[OcrTextBlock]
    ocr_result: OcrEngineResult
    mrz_result: MrzParseResult
    viz_fields: Dict[str, VizFieldResult]
    mean_confidence: float
    mrz_score: float = 0.0
    viz_score: float = 0.0


def _score_mrz_candidate(mrz: MrzParseResult) -> float:
    """
    Score MRZ candidates using independent mathematical and structural evidence.

    Check-digit validity provides independent mathematical proof, far outranking raw OCR confidence.
    """
    if not mrz.detected:
        return 0.0

    score = 10.0
    if mrz.mrz_format in {MrzFormat.TD3, MrzFormat.TD2, MrzFormat.TD1}:
        score += 50.0

    if mrz.line_length_valid:
        score += 50.0

    if mrz.character_set_valid:
        score += 20.0

    # Check-digit mathematical proof
    valid_cd_count = sum(1 for cd in mrz.check_digits if cd.is_valid)
    total_cd_count = len(mrz.check_digits)
    score += valid_cd_count * 100.0

    if mrz.all_check_digits_valid and total_cd_count >= 3:
        score += 1000.0

    # Core fields extracted from MRZ
    for k in ("passport_number", "date_of_birth", "date_of_expiry", "surname", "given_names"):
        if mrz.parsed_fields.get(k):
            score += 30.0

    return score


def _score_viz_candidate(viz: Dict[str, VizFieldResult]) -> float:
    """Score VIZ candidate fields based on valid format and non-empty extraction."""
    score = 0.0
    for res in viz.values():
        if res.status == "extracted" and res.value:
            score += 20.0
    return score


def _crop_candidate_mrz_region(
    image: np.ndarray,
    blocks: List[OcrTextBlock],
) -> Optional[Tuple[np.ndarray, int, int]]:
    """
    Detect the physical band corresponding to the MRZ in a passport image.

    Returns (cropped_rgb, offset_x, offset_y) or None if reliable cropping is impossible.
    """
    h, w = image.shape[:2]
    if h < 100 or w < 100:
        return None

    # Case 1: An MRZ-like text block was detected (e.g. line starting with P< or containing chevrons)
    mrz_blocks = [
        b
        for b in blocks
        if "<" in b.text or b.text.strip().upper().startswith("P<") or (len(b.text) >= 20 and sum(1 for c in b.text if c.isdigit()) >= 5)
    ]
    if mrz_blocks:
        min_y = min(b.min_y for b in mrz_blocks)
        max_y = max(b.max_y for b in mrz_blocks)
        min_x = min(b.min_x for b in mrz_blocks)
        max_x = max(b.max_x for b in mrz_blocks)

        band_h = max(30.0, max_y - min_y)
        y_start = max(0, int(round(min_y - band_h * 0.4)))
        y_end = min(h, int(round(max_y + band_h * 0.8)))
        x_start = max(0, int(round(min_x - 40)))
        x_end = min(w, int(round(max_x + 40)))

        if (y_end - y_start) >= 40 and (x_end - x_start) >= 150:
            crop = image[y_start:y_end, x_start:x_end]
            return crop, x_start, y_start

    # Case 2: Document text envelope detected -> MRZ occupies the bottom 25-35% of the text bounds
    if len(blocks) >= 4:
        min_y = min(b.min_y for b in blocks)
        max_y = max(b.max_y for b in blocks)
        min_x = min(b.min_x for b in blocks)
        max_x = max(b.max_x for b in blocks)

        doc_h = max_y - min_y
        doc_w = max_x - min_x
        if doc_h >= 120 and doc_w >= 200:
            y_start = max(0, int(round(min_y + doc_h * 0.65)))
            y_end = min(h, int(round(max_y + doc_h * 0.12)))
            x_start = max(0, int(round(min_x - 30)))
            x_end = min(w, int(round(max_x + 30)))

            if (y_end - y_start) >= 40 and (x_end - x_start) >= 150:
                crop = image[y_start:y_end, x_start:x_end]
                return crop, x_start, y_start

    # Case 3: Geometric bottom 28% of the image
    y_start = int(round(h * 0.70))
    y_end = h
    x_start = 0
    x_end = w
    crop = image[y_start:y_end, x_start:x_end]
    return crop, x_start, y_start


def _remap_crop_blocks(
    crop_blocks: List[OcrTextBlock],
    offset_x: int,
    offset_y: int,
    scale_factor: float = 1.0,
) -> List[OcrTextBlock]:
    """Map bounding boxes from a cropped/upscaled subregion back to original image coordinates."""
    remapped: List[OcrTextBlock] = []
    inv_scale = 1.0 / scale_factor if scale_factor > 0 else 1.0
    for b in crop_blocks:
        new_bbox = tuple(
            (float(pt[0] * inv_scale + offset_x), float(pt[1] * inv_scale + offset_y))
            for pt in b.bbox
        )
        remapped.append(
            OcrTextBlock(
                text=b.text,
                confidence=b.confidence,
                bbox=new_bbox,  # type: ignore[arg-type]
            )
        )
    return remapped


def execute_targeted_ocr_recovery(
    decoded: DecodedPassportImage,
    baseline_prep: PreprocessedImageBundle,
    engine: RapidOcrEngineManager,
    settings: Optional[Settings] = None,
    start_time: Optional[float] = None,
) -> Tuple[List[OcrTextBlock], MrzParseResult, Dict[str, VizFieldResult], OcrEngineResult, List[str], str]:
    """
    Execute controlled multi-variant OCR candidate evaluation and recovery.

    - Fast-path for clear images: if baseline yields valid MRZ with valid check digits, returns immediately.
    - If baseline is imperfect, evaluates a bounded set of relevant variants (max 3 variants).
    - Prioritizes independent mathematical check digits over raw OCR confidence.
    """
    cfg = settings or get_settings()
    t0 = start_time or time.perf_counter()
    variants_evaluated: List[str] = ["baseline"]

    # 1. Evaluate Baseline
    baseline_ocr = engine.extract_text_blocks(
        rgb_image=baseline_prep.ocr_rgb,
        gray_image=baseline_prep.ocr_gray,
        settings=cfg,
    )
    baseline_mrz = parse_mrz_from_blocks(baseline_ocr.blocks)
    baseline_viz = extract_viz_fields(
        blocks=baseline_ocr.blocks,
        mrz_raw_lines=baseline_mrz.raw_lines if baseline_mrz.detected else None,
    )

    baseline_candidate = OcrVariantCandidate(
        variant_name="baseline",
        blocks=baseline_ocr.blocks,
        ocr_result=baseline_ocr,
        mrz_result=baseline_mrz,
        viz_fields=baseline_viz,
        mean_confidence=float(np.mean([b.confidence for b in baseline_ocr.blocks])) if baseline_ocr.blocks else 0.0,
        mrz_score=_score_mrz_candidate(baseline_mrz),
        viz_score=_score_viz_candidate(baseline_viz),
    )

    # FAST-PATH CHECK:
    # If baseline produced a valid MRZ with all check digits passing and core fields extracted,
    # skip remaining variants to keep latency low.
    core_keys = ("passport_number", "date_of_birth", "date_of_expiry", "surname")
    core_present = sum(1 for k in core_keys if baseline_candidate.mrz_result.parsed_fields.get(k)) >= 3
    if (
        baseline_mrz.detected
        and baseline_mrz.all_check_digits_valid
        and baseline_mrz.line_length_valid
        and core_present
    ):
        return (
            baseline_ocr.blocks,
            baseline_mrz,
            baseline_viz,
            baseline_ocr,
            variants_evaluated,
            "baseline",
        )

    # Check timeout budget (keep max variant evaluation within bounds)
    time_budget_remaining = cfg.ocr_timeout_seconds - (time.perf_counter() - t0)
    if time_budget_remaining < 1.0:
        return (
            baseline_ocr.blocks,
            baseline_mrz,
            baseline_viz,
            baseline_ocr,
            variants_evaluated,
            "baseline",
        )

    candidates: List[OcrVariantCandidate] = [baseline_candidate]

    # Variant A: Original RGB (unresized / unadjusted)
    # Particularly effective when downscaling or CLAHE in baseline degraded small text
    if baseline_prep.metadata.resized_for_ocr or baseline_prep.metadata.contrast_adjusted:
        orig_ocr = engine.extract_text_blocks(rgb_image=baseline_prep.original_rgb, settings=cfg)
        variants_evaluated.append("original_rgb")
        orig_mrz = parse_mrz_from_blocks(orig_ocr.blocks)
        orig_viz = extract_viz_fields(
            blocks=orig_ocr.blocks,
            mrz_raw_lines=orig_mrz.raw_lines if orig_mrz.detected else None,
        )
        candidates.append(
            OcrVariantCandidate(
                variant_name="original_rgb",
                blocks=orig_ocr.blocks,
                ocr_result=orig_ocr,
                mrz_result=orig_mrz,
                viz_fields=orig_viz,
                mean_confidence=float(np.mean([b.confidence for b in orig_ocr.blocks])) if orig_ocr.blocks else 0.0,
                mrz_score=_score_mrz_candidate(orig_mrz),
                viz_score=_score_viz_candidate(orig_viz),
            )
        )

        # Fast-exit if original image produced perfect check digits
        if orig_mrz.detected and orig_mrz.all_check_digits_valid and orig_mrz.line_length_valid:
            return (
                orig_ocr.blocks,
                orig_mrz,
                orig_viz,
                orig_ocr,
                variants_evaluated,
                "original_rgb",
            )

    # Variant B: Conservative Sharpening (if blurry and not already sharpened)
    if baseline_prep.metadata.is_blurry and not baseline_prep.metadata.sharpening_applied:
        sharpened_rgb = apply_conservative_sharpening(baseline_prep.original_rgb, amount=0.65)
        sharp_ocr = engine.extract_text_blocks(rgb_image=sharpened_rgb, settings=cfg)
        variants_evaluated.append("sharpened")
        sharp_mrz = parse_mrz_from_blocks(sharp_ocr.blocks)
        sharp_viz = extract_viz_fields(
            blocks=sharp_ocr.blocks,
            mrz_raw_lines=sharp_mrz.raw_lines if sharp_mrz.detected else None,
        )
        candidates.append(
            OcrVariantCandidate(
                variant_name="sharpened",
                blocks=sharp_ocr.blocks,
                ocr_result=sharp_ocr,
                mrz_result=sharp_mrz,
                viz_fields=sharp_viz,
                mean_confidence=float(np.mean([b.confidence for b in sharp_ocr.blocks])) if sharp_ocr.blocks else 0.0,
                mrz_score=_score_mrz_candidate(sharp_mrz),
                viz_score=_score_viz_candidate(sharp_viz),
            )
        )

    # Variant C: Targeted MRZ Region Crop & Enhanced Contrast
    # Evaluated when best MRZ so far has missing check digits or was not detected
    best_mrz_so_far = max(c.mrz_score for c in candidates)
    if best_mrz_so_far < 1000.0:
        # Determine source image for crop matching coordinate space of best_blocks
        best_cand = max(candidates, key=lambda c: (len(c.blocks), c.mrz_score))
        if best_cand.variant_name == "original_rgb":
            src_for_crop = baseline_prep.original_rgb
        else:
            src_for_crop = baseline_prep.ocr_rgb
        best_blocks = best_cand.blocks
        crop_info = _crop_candidate_mrz_region(src_for_crop, best_blocks)
        if crop_info is not None:
            crop_rgb, off_x, off_y = crop_info
            ch, cw = crop_rgb.shape[:2]
            scale = 1.0
            if ch < 180:
                scale = 2.0
                crop_rgb = cv2.resize(crop_rgb, (cw * 2, ch * 2), interpolation=cv2.INTER_CUBIC)

            # Apply CLAHE contrast on crop
            crop_gray = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
            crop_clahe = clahe.apply(crop_gray)
            crop_enhanced_rgb = cv2.cvtColor(crop_clahe, cv2.COLOR_GRAY2RGB)

            crop_ocr = engine.extract_text_blocks(rgb_image=crop_enhanced_rgb, settings=cfg)
            if crop_ocr.blocks:
                remapped_blocks = _remap_crop_blocks(crop_ocr.blocks, off_x, off_y, scale_factor=scale)
                crop_mrz = parse_mrz_from_blocks(remapped_blocks)
                variants_evaluated.append("mrz_region_crop")
                candidates.append(
                    OcrVariantCandidate(
                        variant_name="mrz_region_crop",
                        blocks=remapped_blocks,
                        ocr_result=crop_ocr,
                        mrz_result=crop_mrz,
                        viz_fields={},
                        mean_confidence=float(np.mean([b.confidence for b in remapped_blocks])),
                        mrz_score=_score_mrz_candidate(crop_mrz),
                        viz_score=0.0,
                    )
                )

    # 4. Candidate Selection & Merging
    # Find winning MRZ candidate
    best_mrz_candidate = max(candidates, key=lambda c: (c.mrz_score, c.mean_confidence))

    # Find winning VIZ candidate (excluding mrz_region_crop which only has MRZ blocks)
    viz_candidates = [c for c in candidates if c.variant_name != "mrz_region_crop"]
    best_viz_candidate = max(viz_candidates, key=lambda c: (c.viz_score, c.mean_confidence))

    final_mrz = best_mrz_candidate.mrz_result

    # If the winning MRZ came from a different variant than the winning VIZ:
    if best_mrz_candidate.variant_name != best_viz_candidate.variant_name and best_mrz_candidate.mrz_result.detected:
        winning_variant = f"{best_viz_candidate.variant_name}+{best_mrz_candidate.variant_name}"
        # Keep non-MRZ blocks from VIZ and MRZ blocks from best MRZ candidate
        mrz_raw_set = set(best_mrz_candidate.mrz_result.raw_lines)
        combined_blocks = list(best_viz_candidate.blocks) + [
            b for b in best_mrz_candidate.blocks if b.text.strip() in mrz_raw_set or "<" in b.text
        ]
        final_viz = best_viz_candidate.viz_fields
        final_ocr = best_viz_candidate.ocr_result
    else:
        winning = best_mrz_candidate if best_mrz_candidate.mrz_score >= 100.0 else best_viz_candidate
        combined_blocks = winning.blocks
        winning_variant = winning.variant_name
        final_viz = winning.viz_fields
        final_ocr = winning.ocr_result

    return (
        combined_blocks,
        final_mrz,
        final_viz,
        final_ocr,
        variants_evaluated,
        winning_variant,
    )
