/**
 * Strict TypeScript contract matching PassPortIQ v2 backend Pydantic schemas.
 */

export type ProcessingStatus =
  | 'completed'
  | 'partial'
  | 'no_passport_detected'
  | 'failed';

export type DocumentClassification =
  | 'passport_td3'
  | 'travel_document_td1'
  | 'travel_document_td2'
  | 'unclassified_document'
  | 'unknown';

export type FieldSource =
  | 'mrz'
  | 'viz'
  | 'reconciled'
  | 'derived'
  | 'unavailable';

export type FieldValidationState =
  | 'valid_check_digit'
  | 'valid_format'
  | 'unverified'
  | 'invalid_check_digit'
  | 'invalid_format'
  | 'conflict'
  | 'missing';

export type ReconciliationStatus =
  | 'matched'
  | 'mismatch'
  | 'insufficient_data'
  | 'not_checked'
  | 'viz_only'
  | 'mrz_only';

export type MrzFormat = 'TD1' | 'TD2' | 'TD3';

export type WarningSeverity = 'info' | 'warning' | 'error';

export interface ExtractedField {
  field_name: string;
  label: string;
  value: string | null;
  raw_evidence: string | null;
  source: FieldSource;
  validation_state: FieldValidationState;
  ocr_confidence: number | null;
  reconciliation_status: ReconciliationStatus;
  mrz_value: string | null;
  viz_value: string | null;
  notes: string[];
}

export interface CheckDigitResult {
  field_name: string;
  data_segment: string;
  expected_digit: string;
  actual_digit: string;
  is_valid: boolean;
  position_description: string;
}

export interface MrzParseResult {
  detected: boolean;
  mrz_format: MrzFormat | null;
  raw_lines: string[];
  normalized_lines: string[];
  mrz_text: string | null;
  check_digits: CheckDigitResult[];
  all_check_digits_valid: boolean;
  line_length_valid: boolean;
  character_set_valid: boolean;
  recovery_applied: boolean;
  recovery_notes: string[];
  errors: string[];
  parsed_fields: Record<string, string | null>;
  ocr_confidence: number | null;
  is_partial?: boolean;
  partial_reason?: string | null;
  failure_classification?: string | null;
  authenticity_disclaimer: string;
}

export interface FieldReconciliationItem {
  field_name: string;
  mrz_value: string | null;
  viz_value: string | null;
  normalized_mrz: string | null;
  normalized_viz: string | null;
  status: ReconciliationStatus;
  explanation: string;
}

export interface ReconciliationSummary {
  overall_status: ReconciliationStatus;
  compared_fields_count: number;
  matched_count: number;
  mismatch_count: number;
  insufficient_data_count: number;
  not_checked_count: number;
  items: FieldReconciliationItem[];
}

export interface PreprocessingMetadata {
  original_width: number;
  original_height: number;
  original_format: string;
  original_mode: string;
  file_size_bytes: number;
  exif_orientation_applied: boolean;
  exif_orientation_tag: number | null;
  resized_for_ocr: boolean;
  processed_width: number;
  processed_height: number;
  steps_applied: string[];
  grayscale_applied: boolean;
  contrast_adjusted: boolean;
  denoised: boolean;
  deskew_angle_degrees: number;
  threshold_applied: boolean;
  blur_score?: number | null;
  is_blurry?: boolean;
  sharpening_applied?: boolean;
  quality_assessment?: string | null;
  variants_evaluated?: string[];
  winning_variant?: string | null;
}

export interface OcrExecutionMetadata {
  requested_engine: string;
  active_engine: string;
  fallback_used: boolean;
  fallback_reason: string | null;
  detected_blocks_count: number;
  mean_ocr_confidence: number | null;
  min_ocr_confidence: number | null;
  max_ocr_confidence: number | null;
  ocr_confidence_note: string;
}

export interface ExtractionWarning {
  code: string;
  severity: WarningSeverity;
  message: string;
  field_name: string | null;
}

export interface PassportFieldsBundle {
  document_type: ExtractedField;
  issuing_country: ExtractedField;
  surname: ExtractedField;
  given_names: ExtractedField;
  full_name: ExtractedField;
  passport_number: ExtractedField;
  nationality: ExtractedField;
  date_of_birth: ExtractedField;
  sex: ExtractedField;
  date_of_expiry: ExtractedField;
  date_of_issue: ExtractedField;
  place_of_birth: ExtractedField;
  personal_number: ExtractedField;
}

export interface PassportExtractionResponse {
  status: ProcessingStatus;
  document_classification: DocumentClassification;
  fields: PassportFieldsBundle;
  mrz: MrzParseResult;
  reconciliation: ReconciliationSummary;
  ocr_metadata: OcrExecutionMetadata;
  preprocessing: PreprocessingMetadata;
  warnings: ExtractionWarning[];
  processing_duration_ms: number;
  transient_processing_notice: string;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}
