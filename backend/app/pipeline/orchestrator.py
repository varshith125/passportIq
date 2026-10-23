"""End-to-end passport extraction pipeline orchestrator."""

from __future__ import annotations

import time
from typing import List, Optional

from app.core.config import Settings, get_settings
from app.core.logging import get_privacy_logger
from app.mrz.parser import parse_mrz_from_blocks
from app.ocr.base import OcrEngineResult
from app.ocr.rapidocr_engine import RapidOcrEngineManager, get_ocr_manager
from app.ocr.recovery import execute_targeted_ocr_recovery
from app.pipeline.reconciliation import reconcile_and_build_fields
from app.schemas.extraction import (
    DocumentClassification,
    ExtractionWarning,
    MrzFormat,
    OcrExecutionMetadata,
    PassportExtractionResponse,
    ProcessingStatus,
    ReconciliationStatus,
    WarningSeverity,
)
from app.services.image_security import validate_and_decode_image
from app.services.preprocessing import preprocess_passport_image
from app.viz.extractor import extract_viz_fields

logger = get_privacy_logger("passportiq.pipeline")


def _classify_document(
    mrz_format: Optional[MrzFormat],
    doc_type_value: Optional[str],
    any_viz_extracted: bool,
) -> DocumentClassification:
    if mrz_format == MrzFormat.TD3:
        return DocumentClassification.PASSPORT_TD3
    if mrz_format == MrzFormat.TD2:
        return DocumentClassification.TRAVEL_DOCUMENT_TD2
    if mrz_format == MrzFormat.TD1:
        return DocumentClassification.TRAVEL_DOCUMENT_TD1
    if doc_type_value and (doc_type_value.upper() in {"P", "PA", "PM", "PO", "PS", "PT"} or "PASSPORT" in doc_type_value.upper() or "PASSEPORT" in doc_type_value.upper()):
        return DocumentClassification.PASSPORT_TD3
    if any_viz_extracted or doc_type_value:
        return DocumentClassification.UNCLASSIFIED_DOCUMENT
    return DocumentClassification.UNKNOWN


def _build_ocr_metadata(ocr_result: OcrEngineResult) -> OcrExecutionMetadata:
    blocks = ocr_result.blocks
    if blocks:
        confs = [b.confidence for b in blocks]
        mean_c: Optional[float] = round(sum(confs) / len(confs), 4)
        min_c: Optional[float] = round(min(confs), 4)
        max_c: Optional[float] = round(max(confs), 4)
    else:
        mean_c = None
        min_c = None
        max_c = None

    return OcrExecutionMetadata(
        requested_engine=ocr_result.requested_engine,
        active_engine=ocr_result.active_engine,
        fallback_used=ocr_result.fallback_used,
        fallback_reason=ocr_result.fallback_reason,
        detected_blocks_count=len(blocks),
        mean_ocr_confidence=mean_c,
        min_ocr_confidence=min_c,
        max_ocr_confidence=max_c,
    )


def run_extraction_pipeline(
    raw_bytes: bytes,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    settings: Optional[Settings] = None,
    ocr_manager: Optional[RapidOcrEngineManager] = None,
) -> PassportExtractionResponse:
    """
    Execute the complete, transient passport extraction pipeline:
    1. Validate file signature, dimensions, pixel limits, and decode safely.
    2. Normalize and selectively preprocess image.
    3. Execute targeted OCR recovery across controlled variants.
    4. Detect, parse, and check-digit-validate MRZ (TD1, TD2, TD3, partial).
    5. Extract best-effort VIZ fields.
    6. Reconcile MRZ and VIZ fields and generate actionable warnings and status.
    """
    start_ts = time.perf_counter()
    cfg = settings or get_settings()
    engine = ocr_manager or get_ocr_manager()

    decoded = validate_and_decode_image(
        raw_bytes=raw_bytes,
        filename=filename,
        content_type=content_type,
        settings=cfg,
    )

    preprocessed = preprocess_passport_image(decoded=decoded, settings=cfg)

    (
        ocr_blocks,
        mrz_result,
        viz_results,
        ocr_result,
        variants_evaluated,
        winning_variant,
    ) = execute_targeted_ocr_recovery(
        decoded=decoded,
        baseline_prep=preprocessed,
        engine=engine,
        settings=cfg,
        start_time=start_ts,
    )

    preprocessing_meta = preprocessed.metadata.model_copy(
        update={
            "variants_evaluated": variants_evaluated,
            "winning_variant": winning_variant,
        }
    )

    fields_bundle, reconciliation = reconcile_and_build_fields(
        mrz_result=mrz_result,
        viz_results=viz_results,
    )

    warnings: List[ExtractionWarning] = []

    if ocr_result.fallback_used:
        warnings.append(
            ExtractionWarning(
                code="OCR_FALLBACK_ENGINE_USED",
                severity=WarningSeverity.WARNING,
                message=(
                    f"Primary OCR engine '{ocr_result.requested_engine}' was unavailable; "
                    f"explicitly configured fallback engine '{ocr_result.active_engine}' was used. "
                    f"Reason: {ocr_result.fallback_reason}"
                ),
            )
        )

    if not ocr_blocks:
        warnings.append(
            ExtractionWarning(
                code="EMPTY_OCR_RESULT",
                severity=WarningSeverity.WARNING,
                message="OCR engine completed but detected no readable text blocks in the uploaded image.",
            )
        )

    if preprocessed.metadata.is_blurry:
        warnings.append(
            ExtractionWarning(
                code="SUBOPTIMAL_IMAGE_QUALITY",
                severity=WarningSeverity.WARNING,
                message=(
                    f"Image exhibits noticeable blur (blur score {preprocessed.metadata.blur_score:.1f}). "
                    "Recommendation: For maximum extraction accuracy, upload a sharper, uncropped image under even lighting."
                ),
            )
        )

    if mrz_result.is_partial:
        warnings.append(
            ExtractionWarning(
                code="PARTIAL_MRZ_DETECTED",
                severity=WarningSeverity.WARNING,
                message=(
                    f"Partial Machine Readable Zone (MRZ) detected ({mrz_result.partial_reason or 'incomplete line'}). "
                    "Available fields were extracted with explicit uncertainty. Recommendation: Ensure the entire bottom MRZ band is visible and not cropped."
                ),
            )
        )

    if not mrz_result.detected and ocr_blocks:
        warnings.append(
            ExtractionWarning(
                code="MRZ_NOT_DETECTED",
                severity=WarningSeverity.WARNING,
                message="No Machine Readable Zone (MRZ) was detected in the image; extraction relied solely on VIZ.",
            )
        )

    if mrz_result.detected:
        if mrz_result.recovery_applied:
            warnings.append(
                ExtractionWarning(
                    code="MRZ_OCR_RECOVERY_APPLIED",
                    severity=WarningSeverity.INFO,
                    message=(
                        "Bounded OCR normalization was applied to MRZ candidate lines: "
                        + "; ".join(mrz_result.recovery_notes)
                    ),
                )
            )
        for err in mrz_result.errors:
            warnings.append(
                ExtractionWarning(
                    code="MRZ_VALIDATION_ISSUE",
                    severity=WarningSeverity.ERROR if "check-digit" in err.lower() else WarningSeverity.WARNING,
                    message=err,
                )
            )

    if reconciliation.overall_status == ReconciliationStatus.MISMATCH:
        for item in reconciliation.items:
            if item.status == ReconciliationStatus.MISMATCH:
                warnings.append(
                    ExtractionWarning(
                        code="MRZ_VIZ_FIELD_MISMATCH",
                        severity=WarningSeverity.WARNING,
                        message=item.explanation,
                        field_name=item.field_name,
                    )
                )
    elif reconciliation.overall_status == ReconciliationStatus.INSUFFICIENT_DATA and (
        mrz_result.detected or any(v.value is not None for v in viz_results.values())
    ):
        warnings.append(
            ExtractionWarning(
                code="RECONCILIATION_INSUFFICIENT_DATA",
                severity=WarningSeverity.INFO,
                message=(
                    "Cross-zone reconciliation could not verify all fields because either MRZ or VIZ "
                    "values were missing for overlapping fields."
                ),
            )
        )

    # Count extracted core fields to determine overall status
    field_dict = fields_bundle.model_dump()
    extracted_count = sum(1 for f in field_dict.values() if f.get("value") is not None)
    core_keys = ("surname", "given_names", "passport_number", "date_of_birth", "date_of_expiry")
    core_extracted = sum(1 for k in core_keys if field_dict[k].get("value") is not None)

    if extracted_count == 0:
        status = ProcessingStatus.NO_PASSPORT_DETECTED
    elif (
        mrz_result.detected
        and mrz_result.all_check_digits_valid
        and mrz_result.line_length_valid
        and core_extracted == len(core_keys)
        and reconciliation.mismatch_count == 0
    ):
        status = ProcessingStatus.COMPLETED
    else:
        status = ProcessingStatus.PARTIAL

    classification = _classify_document(
        mrz_format=mrz_result.mrz_format,
        doc_type_value=fields_bundle.document_type.value,
        any_viz_extracted=(extracted_count > 0),
    )

    duration_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)

    logger.info(
        "Extraction completed: status=%s classification=%s engine=%s blocks=%d duration_ms=%.2f variant=%s",
        status.value,
        classification.value,
        ocr_result.active_engine,
        len(ocr_blocks),
        duration_ms,
        winning_variant,
    )

    return PassportExtractionResponse(
        status=status,
        document_classification=classification,
        fields=fields_bundle,
        mrz=mrz_result,
        reconciliation=reconciliation,
        ocr_metadata=_build_ocr_metadata(ocr_result),
        preprocessing=preprocessing_meta,
        warnings=warnings,
        processing_duration_ms=duration_ms,
    )
