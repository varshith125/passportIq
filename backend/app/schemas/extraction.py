"""Typed extraction, MRZ, VIZ, and reconciliation schemas for PassPortIQ."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import Field

from app.schemas.common import SchemaModel


class ProcessingStatus(str, Enum):
    """Overall extraction outcome."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    NO_PASSPORT_DETECTED = "no_passport_detected"
    FAILED = "failed"


class DocumentClassification(str, Enum):
    """Detected document classification based on MRZ and VIZ evidence."""

    PASSPORT_TD3 = "passport_td3"
    TRAVEL_DOCUMENT_TD1 = "travel_document_td1"
    TRAVEL_DOCUMENT_TD2 = "travel_document_td2"
    UNCLASSIFIED_DOCUMENT = "unclassified_document"
    UNKNOWN = "unknown"


class FieldSource(str, Enum):
    """Origin of an extracted field value."""

    MRZ = "mrz"
    VIZ = "viz"
    RECONCILED = "reconciled"
    DERIVED = "derived"
    UNAVAILABLE = "unavailable"


class FieldValidationState(str, Enum):
    """Validation status of an individual field."""

    VALID_CHECK_DIGIT = "valid_check_digit"
    VALID_FORMAT = "valid_format"
    UNVERIFIED = "unverified"
    INVALID_CHECK_DIGIT = "invalid_check_digit"
    INVALID_FORMAT = "invalid_format"
    CONFLICT = "conflict"
    MISSING = "missing"


class ReconciliationStatus(str, Enum):
    """Comparison outcome between MRZ and VIZ values."""

    MATCHED = "matched"
    MISMATCH = "mismatch"
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_CHECKED = "not_checked"
    VIZ_ONLY = "viz_only"
    MRZ_ONLY = "mrz_only"


class MrzFormat(str, Enum):
    """Supported ICAO 9303 Machine Readable Zone formats."""

    TD1 = "TD1"
    TD2 = "TD2"
    TD3 = "TD3"


class WarningSeverity(str, Enum):
    """Severity level for diagnostic warnings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ExtractedField(SchemaModel):
    """Detailed representation of a single passport field."""

    field_name: str = Field(..., description="Canonical identifier for the field")
    label: str = Field(..., description="Human-readable field label")
    value: Optional[str] = Field(None, description="Normalized extracted value when available")
    raw_evidence: Optional[str] = Field(
        None, description="Raw OCR or MRZ substring supporting this field"
    )
    source: FieldSource = Field(..., description="Source that provided the primary value")
    validation_state: FieldValidationState = Field(
        ..., description="Format or check-digit validation state"
    )
    ocr_confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="OCR engine recognition confidence (distinct from extraction accuracy)",
    )
    reconciliation_status: ReconciliationStatus = Field(
        ..., description="Agreement status between MRZ and VIZ sources"
    )
    mrz_value: Optional[str] = Field(None, description="Value parsed from MRZ if present")
    viz_value: Optional[str] = Field(None, description="Value extracted from VIZ if present")
    notes: List[str] = Field(default_factory=list, description="Field-level diagnostic notes")


class CheckDigitResult(SchemaModel):
    """Result of an ICAO 9303 Modulo-10 check-digit verification."""

    field_name: str
    data_segment: str
    expected_digit: str
    actual_digit: str
    is_valid: bool
    position_description: str


class MrzParseResult(SchemaModel):
    """Structured output of MRZ detection, parsing, and check-digit validation."""

    detected: bool = False
    mrz_format: Optional[MrzFormat] = None
    raw_lines: List[str] = Field(default_factory=list)
    normalized_lines: List[str] = Field(default_factory=list)
    mrz_text: Optional[str] = None
    check_digits: List[CheckDigitResult] = Field(default_factory=list)
    all_check_digits_valid: bool = False
    line_length_valid: bool = False
    character_set_valid: bool = False
    recovery_applied: bool = False
    recovery_notes: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    parsed_fields: Dict[str, Optional[str]] = Field(default_factory=dict)
    ocr_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_partial: bool = False
    partial_reason: Optional[str] = None
    failure_classification: Optional[str] = None
    authenticity_disclaimer: str = (
        "Valid MRZ check digits confirm only internal character consistency under ICAO 9303 "
        "and do not verify document authenticity or cryptographic signatures."
    )


class FieldReconciliationItem(SchemaModel):
    """Comparison record for a single field across MRZ and VIZ."""

    field_name: str
    mrz_value: Optional[str] = None
    viz_value: Optional[str] = None
    normalized_mrz: Optional[str] = None
    normalized_viz: Optional[str] = None
    status: ReconciliationStatus
    explanation: str


class ReconciliationSummary(SchemaModel):
    """Aggregate summary of MRZ vs. VIZ cross-checking."""

    overall_status: ReconciliationStatus
    compared_fields_count: int = 0
    matched_count: int = 0
    mismatch_count: int = 0
    insufficient_data_count: int = 0
    not_checked_count: int = 0
    items: List[FieldReconciliationItem] = Field(default_factory=list)


class PreprocessingMetadata(SchemaModel):
    """Audit trail of image normalization and preprocessing operations."""

    original_width: int
    original_height: int
    original_format: str
    original_mode: str
    file_size_bytes: int
    exif_orientation_applied: bool = False
    exif_orientation_tag: Optional[int] = None
    resized_for_ocr: bool = False
    processed_width: int
    processed_height: int
    steps_applied: List[str] = Field(default_factory=list)
    grayscale_applied: bool = False
    contrast_adjusted: bool = False
    denoised: bool = False
    deskew_angle_degrees: float = 0.0
    threshold_applied: bool = False
    blur_score: Optional[float] = None
    is_blurry: bool = False
    sharpening_applied: bool = False
    quality_assessment: Optional[str] = None
    variants_evaluated: List[str] = Field(default_factory=list)
    winning_variant: Optional[str] = None


class OcrExecutionMetadata(SchemaModel):
    """Metadata describing the OCR engine execution and raw recognition confidence."""

    requested_engine: str
    active_engine: str
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    detected_blocks_count: int = 0
    mean_ocr_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_ocr_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_ocr_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    ocr_confidence_note: str = (
        "OCR engine confidence reflects character recognition certainty from the model and "
        "is separate from semantic field-extraction accuracy or document validity."
    )


class ExtractionWarning(SchemaModel):
    """Structured diagnostic warning or uncertainty notice."""

    code: str
    severity: WarningSeverity
    message: str
    field_name: Optional[str] = None


class PassportFieldsBundle(SchemaModel):
    """Structured collection of all supported passport fields."""

    document_type: ExtractedField
    issuing_country: ExtractedField
    surname: ExtractedField
    given_names: ExtractedField
    full_name: ExtractedField
    passport_number: ExtractedField
    nationality: ExtractedField
    date_of_birth: ExtractedField
    sex: ExtractedField
    date_of_expiry: ExtractedField
    date_of_issue: ExtractedField
    place_of_birth: ExtractedField
    personal_number: ExtractedField


class PassportExtractionResponse(SchemaModel):
    """Top-level response returned by POST /api/passports/extract."""

    status: ProcessingStatus
    document_classification: DocumentClassification
    fields: PassportFieldsBundle
    mrz: MrzParseResult
    reconciliation: ReconciliationSummary
    ocr_metadata: OcrExecutionMetadata
    preprocessing: PreprocessingMetadata
    warnings: List[ExtractionWarning] = Field(default_factory=list)
    processing_duration_ms: float = Field(..., ge=0.0)
    transient_processing_notice: str = (
        "Uploaded image bytes were processed transiently in memory and were not persisted to disk or database."
    )


class ApiErrorDetail(SchemaModel):
    """Structured error body returned on 4xx/5xx responses."""

    code: str
    message: str
    details: Dict[str, object] = Field(default_factory=dict)


class ApiErrorResponse(SchemaModel):
    """Top-level error envelope."""

    error: ApiErrorDetail
