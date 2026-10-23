import React from 'react';
import { formatDisplayFieldValue } from '../features/scanner/formatFieldValue';
import type {
  ExtractedField,
  FieldSource,
  FieldValidationState,
  PassportFieldsBundle,
  ReconciliationStatus,
} from '../types/passport';

interface FieldTableProps {
  fields: PassportFieldsBundle;
}

const ORDERED_KEYS: Array<keyof PassportFieldsBundle> = [
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
];

function renderValidationBadge(state: FieldValidationState): React.ReactNode {
  switch (state) {
    case 'valid_check_digit':
      return <span className="badge badge--success">Valid Check Digit</span>;
    case 'valid_format':
      return <span className="badge badge--info">Valid Format</span>;
    case 'conflict':
      return <span className="badge badge--error">MRZ / VIZ Conflict</span>;
    case 'invalid_check_digit':
      return <span className="badge badge--error">Failed Check Digit</span>;
    case 'invalid_format':
      return <span className="badge badge--error">Invalid Format</span>;
    case 'unverified':
      return <span className="badge badge--warning">Unverified / Ambiguous</span>;
    case 'missing':
    default:
      return <span className="badge badge--neutral">Missing</span>;
  }
}

function renderReconciliationBadge(status: ReconciliationStatus): React.ReactNode {
  switch (status) {
    case 'matched':
      return <span className="badge badge--success">Matched</span>;
    case 'mismatch':
      return <span className="badge badge--error">Mismatch</span>;
    case 'viz_only':
      return <span className="badge badge--info">VIZ Only</span>;
    case 'mrz_only':
      return <span className="badge badge--info">MRZ Only</span>;
    case 'insufficient_data':
      return <span className="badge badge--warning">Insufficient Data</span>;
    case 'not_checked':
    default:
      return <span className="badge badge--neutral">Not Checked (VIZ Only)</span>;
  }
}

function formatSourceLabel(source: FieldSource): string {
  switch (source) {
    case 'reconciled':
      return 'MRZ + VIZ (Reconciled)';
    case 'mrz':
      return 'MRZ';
    case 'viz':
      return 'Visible Zone (VIZ)';
    case 'derived':
      return 'Derived';
    case 'unavailable':
    default:
      return 'Unavailable';
  }
}

export const FieldTable: React.FC<FieldTableProps> = ({ fields }) => {
  const rows: ExtractedField[] = ORDERED_KEYS.map((key) => fields[key]);

  return (
    <section className="section-card" aria-labelledby="fields-heading">
      <div className="section-card__header">
        <div>
          <h2 id="fields-heading" className="section-card__title">
            Extracted Passport Fields
          </h2>
          <p className="section-card__subtitle">
            Each field reports its extraction source, validation state, cross-zone agreement, and OCR recognition confidence separately.
          </p>
        </div>
      </div>

      <div className="table-wrapper">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">Extracted Value</th>
              <th scope="col">Source</th>
              <th scope="col">Validation State</th>
              <th scope="col">MRZ vs. VIZ Reconciliation</th>
              <th scope="col">OCR Recognition Confidence</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((field) => (
              <tr key={field.field_name}>
                <td>
                  <strong>{field.label}</strong>
                </td>
                <td>
                  {field.value !== null ? (
                    <span className="field-value">
                      {formatDisplayFieldValue(field.field_name, field.value) ?? field.value}
                    </span>
                  ) : field.viz_value || field.mrz_value ? (
                    <span className="field-value">
                      {formatDisplayFieldValue(field.field_name, field.viz_value ?? field.mrz_value) ?? (field.viz_value ?? field.mrz_value)}
                    </span>
                  ) : (
                    <span className="field-value--missing">
                      Not Detected
                    </span>
                  )}
                  {field.reconciliation_status === 'mismatch' && (
                    <div className="field-subnote">
                      MRZ: <code>{field.mrz_value ?? '—'}</code> · VIZ:{' '}
                      <code>{field.viz_value ?? '—'}</code>
                    </div>
                  )}
                  {field.notes.length > 0 && (
                    <div className="field-subnote">
                      {field.notes.join(' ')}
                    </div>
                  )}
                </td>
                <td>{formatSourceLabel(field.source)}</td>
                <td>{renderValidationBadge(field.validation_state)}</td>
                <td>{renderReconciliationBadge(field.reconciliation_status)}</td>
                <td>
                  {field.ocr_confidence !== null
                    ? `${(field.ocr_confidence * 100).toFixed(1)}%`
                    : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
