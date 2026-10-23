/**
 * Presentation helper for passport field values.
 * Maps standard sex codes to human-readable representations while preserving underlying source indicators.
 * Retains < and X without mapping to Male or Female.
 */
export function formatDisplayFieldValue(fieldName: string, value: string | null | undefined): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (fieldName === 'sex') {
    const trimmed = value.trim().toUpperCase();
    if (trimmed === 'M' || trimmed === 'MALE' || trimmed === 'MASCULIN') {
      return 'Male (M)';
    }
    if (trimmed === 'F' || trimmed === 'FEMALE' || trimmed === 'FEMININ' || trimmed === 'FÉMININ') {
      return 'Female (F)';
    }
    if (trimmed === 'X' || trimmed === 'UNSPECIFIED') {
      return 'X (Unspecified)';
    }
    if (trimmed === '<') {
      return '< (Unspecified)';
    }
  }
  return value;
}
