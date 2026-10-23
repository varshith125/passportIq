import type { ExtractedField, PassportExtractionResponse } from '../../types/passport';
import { formatDisplayFieldValue } from './formatFieldValue';

const ORDERED_FIELD_KEYS = [
  'document_type',
  'issuing_country',
  'passport_number',
  'surname',
  'given_names',
  'full_name',
  'nationality',
  'date_of_birth',
  'sex',
  'date_of_issue',
  'date_of_expiry',
  'place_of_birth',
  'personal_number',
] as const;

/**
 * Format available extracted passport information into a structured plain-text summary
 * suitable for copying to the user's clipboard, preserving validation and source qualifiers.
 */
export function formatExtractionForClipboard(
  response: PassportExtractionResponse,
): string {
  const lines: string[] = [
    'PassPortIQ — Extracted Passport Summary',
    `Overall Status: ${response.status}`,
    `Document Classification: ${response.document_classification}`,
    `Reconciliation Status: ${response.reconciliation.overall_status} (${response.reconciliation.matched_count}/${response.reconciliation.compared_fields_count} matched)`,
    `Active OCR Engine: ${response.ocr_metadata.active_engine}`,
    '',
    'Extracted Fields:',
  ];

  const fieldsRecord = response.fields as unknown as Record<string, ExtractedField>;

  for (const key of ORDERED_FIELD_KEYS) {
    const field = fieldsRecord[key];
    if (!field || field.value === null) {
      if (field && field.notes.length > 0) {
        lines.push(`- ${field.label}: Not Detected (${field.notes.join(' ')})`);
      }
      continue;
    }
    const displayVal = formatDisplayFieldValue(field.field_name, field.value) ?? field.value;
    lines.push(
      `- ${field.label}: ${displayVal} [source=${field.source}, validation=${field.validation_state}, reconciliation=${field.reconciliation_status}]`,
    );
  }

  if (response.mrz.detected && response.mrz.mrz_text) {
    lines.push('');
    lines.push(`MRZ (${response.mrz.mrz_format ?? 'Unknown Format'}):`);
    lines.push(response.mrz.mrz_text);
  }

  return lines.join('\n');
}
