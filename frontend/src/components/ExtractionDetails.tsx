import React, { useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import {
  Copy,
  Check,
  AlertTriangle,
  ShieldCheck,
  User,
  CreditCard,
  Binary,
  ChevronDown,
  ChevronUp,
  Cpu,
  RefreshCw,
  LayoutGrid,
  Table,
} from 'lucide-react';
import { formatExtractionForClipboard } from '../features/scanner/formatClipboardText';
import { formatDisplayFieldValue } from '../features/scanner/formatFieldValue';
import { FieldTable } from './FieldTable';
import type {
  DocumentClassification,
  ExtractedField,
  FieldSource,
  FieldValidationState,
  PassportExtractionResponse,
  ReconciliationStatus,
} from '../types/passport';

const isTestEnv =
  typeof import.meta !== 'undefined' &&
  (import.meta.env?.MODE === 'test' || Boolean(import.meta.env?.VITEST));

interface ExtractionDetailsProps {
  data: PassportExtractionResponse;
  onReset: () => void;
  defaultTechOpen?: boolean;
}

const PERSONAL_KEYS = [
  'surname',
  'given_names',
  'full_name',
  'date_of_birth',
  'place_of_birth',
  'nationality',
  'sex',
] as const;

const PASSPORT_KEYS = [
  'passport_number',
  'document_type',
  'issuing_country',
  'date_of_issue',
  'date_of_expiry',
  'personal_number',
] as const;

function formatSourceBadge(source: FieldSource): { label: string; className: string } {
  switch (source) {
    case 'reconciled':
      return { label: 'MRZ + VIZ', className: 'source-tag source-tag--reconciled' };
    case 'mrz':
      return { label: 'MRZ', className: 'source-tag source-tag--mrz' };
    case 'viz':
      return { label: 'VIZ', className: 'source-tag source-tag--viz' };
    case 'derived':
      return { label: 'Derived', className: 'source-tag source-tag--derived' };
    case 'unavailable':
    default:
      return { label: 'Unavailable', className: 'source-tag source-tag--unavailable' };
  }
}

function formatValidationBadge(state: FieldValidationState): { label: string; className: string } {
  switch (state) {
    case 'valid_check_digit':
      return { label: 'Valid Check Digit', className: 'badge badge--success' };
    case 'valid_format':
      return { label: 'Valid Format', className: 'badge badge--info' };
    case 'unverified':
      return { label: 'Unverified', className: 'badge badge--warning' };
    case 'invalid_check_digit':
      return { label: 'Failed Check Digit', className: 'badge badge--error' };
    case 'invalid_format':
      return { label: 'Invalid Format', className: 'badge badge--error' };
    case 'conflict':
      return { label: 'MRZ/VIZ Conflict', className: 'badge badge--error' };
    case 'missing':
    default:
      return { label: 'Missing', className: 'badge badge--neutral' };
  }
}

function formatReconciliationBadge(status: ReconciliationStatus): { label: string; className: string } {
  switch (status) {
    case 'matched':
      return { label: 'Matched', className: 'badge badge--success' };
    case 'mismatch':
      return { label: 'Mismatch', className: 'badge badge--error' };
    case 'viz_only':
      return { label: 'VIZ Only', className: 'badge badge--info' };
    case 'mrz_only':
      return { label: 'MRZ Only', className: 'badge badge--info' };
    case 'insufficient_data':
      return { label: 'Insufficient Data', className: 'badge badge--warning' };
    case 'not_checked':
    default:
      return { label: 'Not Checked (VIZ Only)', className: 'badge badge--neutral' };
  }
}

function formatDocumentClassification(classification: DocumentClassification): string {
  switch (classification) {
    case 'passport_td3':
      return 'Passport (ICAO TD3 · 2×44)';
    case 'travel_document_td2':
      return 'Travel Document (ICAO TD2 · 2×36)';
    case 'travel_document_td1':
      return 'ID / Travel Card (ICAO TD1 · 3×30)';
    case 'unclassified_document':
      return 'Unclassified Document (VIZ Only)';
    case 'unknown':
    default:
      return 'Unknown Document / Unrecognized Layout';
  }
}

export const ExtractionDetails: React.FC<ExtractionDetailsProps> = ({
  data,
  onReset,
  defaultTechOpen = false,
}) => {
  const [copiedAll, setCopiedAll] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [techOpen, setTechOpen] = useState(defaultTechOpen);
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards');

  const shouldReduceMotion = useReducedMotion();
  const disableAnimation = isTestEnv || shouldReduceMotion;

  const conflictingFields = Object.values(data.fields).filter(
    (f) => f.reconciliation_status === 'mismatch' || f.validation_state === 'conflict'
  );

  const handleCopyAll = async () => {
    const text = formatExtractionForClipboard(data);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
    }
    setCopiedAll(true);
    window.setTimeout(() => setCopiedAll(false), 2000);
  };

  const handleCopyFieldValue = async (fieldName: string, value: string | null) => {
    if (!value) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(value);
    }
    setCopiedField(fieldName);
    window.setTimeout(() => setCopiedField(null), 1800);
  };

  const renderFieldRow = (field: ExtractedField) => {
    const isCopied = copiedField === field.field_name;
    const sourceMeta = formatSourceBadge(field.source);
    const valMeta = formatValidationBadge(field.validation_state);
    const recMeta = formatReconciliationBadge(field.reconciliation_status);
    const rawDisplayValue = field.value ?? field.viz_value ?? field.mrz_value;
    const displayValue = formatDisplayFieldValue(field.field_name, rawDisplayValue) ?? rawDisplayValue;

    return (
      <div key={field.field_name} className="detail-row">
        <div className="detail-row__label-col">
          <span className="detail-row__label">{field.label}</span>
          <div className="detail-row__badges">
            <span className={sourceMeta.className}>{sourceMeta.label}</span>
            <span className={valMeta.className}>{valMeta.label}</span>
            {field.reconciliation_status !== 'not_checked' && (
              <span className={recMeta.className}>{recMeta.label}</span>
            )}
          </div>
        </div>

        <div className="detail-row__value-col">
          <div className="detail-row__value-wrapper">
            {displayValue ? (
              <span className={`detail-row__value ${field.field_name.includes('number') ? 'detail-row__value--mono' : ''}`}>
                {displayValue}
              </span>
            ) : (
              <span className="field-value--missing">Not Detected</span>
            )}

            {rawDisplayValue && (
              <button
                type="button"
                className={`field-copy-btn ${isCopied ? 'field-copy-btn--copied' : ''}`}
                onClick={() => handleCopyFieldValue(field.field_name, rawDisplayValue)}
                title={`Copy ${field.label}`}
                aria-label={`Copy ${field.label}`}
              >
                {isCopied ? <Check size={13} /> : <Copy size={13} />}
                <span>{isCopied ? 'Copied' : 'Copy'}</span>
              </button>
            )}
          </div>

          {field.reconciliation_status === 'mismatch' && (
            <div className="field-subnote field-subnote--error">
              <strong>Source Mismatch:</strong> MRZ: <code>{field.mrz_value ?? '—'}</code> vs VIZ: <code>{field.viz_value ?? '—'}</code>
            </div>
          )}

          {field.notes.length > 0 && (
            <div className="field-subnote">
              {field.notes.join(' ')}
            </div>
          )}
        </div>
      </div>
    );
  };

  const { fields, mrz, reconciliation, ocr_metadata, preprocessing, warnings } = data;
  const meanConf = ocr_metadata.mean_ocr_confidence !== null
    ? `${(ocr_metadata.mean_ocr_confidence * 100).toFixed(1)}%`
    : 'N/A';

  return (
    <div className="details-container" role="region" aria-label="Extracted Passport Data">
      {/* Overview Top Header Card */}
      <section className="section-card section-card--hero" aria-labelledby="summary-heading">
        <div className="section-card__header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <ShieldCheck size={18} color="var(--color-teal-accent)" />
              <h2 id="summary-heading" className="section-card__title">
                Extraction Overview
              </h2>
            </div>
            <p className="section-card__subtitle">
              Processed in {data.processing_duration_ms.toFixed(0)} ms using{' '}
              <code>{ocr_metadata.active_engine}</code>
            </p>
          </div>

          <div className="action-bar">
            <button
              type="button"
              className="btn btn--secondary"
              onClick={handleCopyAll}
              title="Copy all extracted passport fields to clipboard"
            >
              {copiedAll ? <Check size={15} /> : <Copy size={15} />}
              <span>{copiedAll ? 'Copied Extracted Details' : 'Copy Extracted Details'}</span>
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={onReset}
            >
              <RefreshCw size={14} />
              <span>Scan Another Document</span>
            </button>
          </div>
        </div>

        {/* Top Metric Tiles */}
        <div className="summary-grid">
          <div className="metric-tile">
            <span className="metric-tile__label">Processing Status</span>
            <div className="metric-tile__value">
              <span className={`badge ${data.status === 'completed' ? 'badge--success' : 'badge--warning'}`}>
                {data.status === 'completed'
                  ? 'Completed (MRZ & Core Fields Verified)'
                  : 'Partial / Needs Review'}
              </span>
            </div>
            <span className="metric-tile__hint">Individual field states are listed below</span>
          </div>

          <div className="metric-tile">
            <span className="metric-tile__label">Document Classification</span>
            <div className="metric-tile__value">
              {formatDocumentClassification(data.document_classification)}
            </div>
            <span className="metric-tile__hint">MRZ Detected: {mrz.detected ? 'Yes' : 'No'}</span>
          </div>

          <div className="metric-tile">
            <span className="metric-tile__label">MRZ vs. VIZ Reconciliation</span>
            <div className="metric-tile__value">
              <span className={`badge ${reconciliation.overall_status === 'matched' ? 'badge--success' : 'badge--warning'}`}>
                {reconciliation.overall_status === 'matched' ? 'Matched Across MRZ & VIZ' : 'Insufficient Overlapping Data'}
              </span>
            </div>
            <span className="metric-tile__hint">
              {reconciliation.matched_count} matched · {reconciliation.mismatch_count} mismatch · {reconciliation.insufficient_data_count} single-source/missing
            </span>
          </div>

          <div className="metric-tile">
            <span className="metric-tile__label">Mean OCR Recognition Confidence</span>
            <div className="metric-tile__value">{meanConf}</div>
            <span className="metric-tile__hint">Model character certainty (distinct from field validation)</span>
          </div>
        </div>

        {/* Quality Advisory & User Recommendation Banner */}
        {(preprocessing.is_blurry || data.status === 'partial' || mrz.is_partial) && (
          <div
            style={{
              marginTop: '1.25rem',
              padding: '0.85rem 1.1rem',
              borderRadius: '8px',
              background: 'rgba(234, 138, 0, 0.08)',
              border: '1px solid rgba(234, 138, 0, 0.35)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px',
            }}
          >
            <AlertTriangle size={18} color="var(--color-warning)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <strong style={{ display: 'block', marginBottom: '2px', color: 'var(--color-warning)' }}>
                {preprocessing.is_blurry
                  ? 'Mild Blur or Suboptimal Capture Quality Detected'
                  : 'Incomplete / Partial Document Extraction'}
              </strong>
              <span style={{ fontSize: '0.88rem', color: 'var(--color-text-secondary)' }}>
                Recommendation: Upload a sharper, uncropped image under even lighting for maximum character certainty and automated check-digit validation.
              </span>
            </div>
          </div>
        )}
      </section>

      {/* Cross-Zone Discrepancy Card if any */}
      {conflictingFields.length > 0 && (
        <section className="section-card section-card--discrepancy" aria-label="Cross-zone reconciliation conflicts">
          <div className="section-card__header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={18} color="var(--color-error)" />
              <h3 className="section-card__title" style={{ color: 'var(--color-error)' }}>
                Cross-Zone Reconciliation Discrepancy ({conflictingFields.length} Field{conflictingFields.length > 1 ? 's' : ''})
              </h3>
            </div>
            <span className="badge badge--error">Discrepancy Detected</span>
          </div>
          <p className="discrepancy-desc">
            Discrepancies were identified between the Machine Readable Zone (MRZ) and the Visible Inspection Zone (VIZ). The raw evidence from both zones is preserved below for human verification:
          </p>
          <div className="discrepancy-grid">
            {conflictingFields.map((f) => (
              <div key={f.field_name} className="discrepancy-card">
                <div className="discrepancy-card__title">{f.label}</div>
                <div className="discrepancy-compare">
                  <div className="discrepancy-col">
                    <span className="discrepancy-col__tag">MRZ Parsed Value</span>
                    <code className="discrepancy-code">{f.mrz_value ?? '—'}</code>
                  </div>
                  <div className="discrepancy-col">
                    <span className="discrepancy-col__tag">VIZ Extracted Value</span>
                    <code className="discrepancy-code">{f.viz_value ?? '—'}</code>
                  </div>
                </div>
                {f.notes.length > 0 && (
                  <div className="field-subnote field-subnote--error" style={{ marginTop: '0.5rem' }}>
                    {f.notes.join(' ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* View Mode Toggle Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '0.25rem 0' }}>
        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
          Extracted Fields Presentation
        </span>
        <div className="view-toggle" role="group" aria-label="Field presentation view mode">
          <button
            type="button"
            className={`view-toggle-btn ${viewMode === 'cards' ? 'view-toggle-btn--active' : ''}`}
            onClick={() => setViewMode('cards')}
            aria-pressed={viewMode === 'cards'}
          >
            <LayoutGrid size={14} />
            <span>Grouped Cards</span>
          </button>
          <button
            type="button"
            className={`view-toggle-btn ${viewMode === 'table' ? 'view-toggle-btn--active' : ''}`}
            onClick={() => setViewMode('table')}
            aria-pressed={viewMode === 'table'}
          >
            <Table size={14} />
            <span>Detailed Matrix</span>
          </button>
        </div>
      </div>

      {viewMode === 'table' ? (
        <FieldTable fields={fields} />
      ) : (
        <>
          {/* Card 1: Personal Information */}
          <section className="section-card" aria-labelledby="personal-heading">
            <div className="section-card__header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <User size={18} color="var(--color-blue-accent)" />
                <h3 id="personal-heading" className="section-card__title">
                  Personal Information
                </h3>
              </div>
              <span className="section-card__counter">
                {PERSONAL_KEYS.filter((k) => fields[k]?.value !== null).length} / {PERSONAL_KEYS.length} Extracted
              </span>
            </div>
            <div className="detail-rows-group">
              {PERSONAL_KEYS.map((key) => renderFieldRow(fields[key]))}
            </div>
          </section>

          {/* Card 2: Passport Information */}
          <section className="section-card" aria-labelledby="passport-heading">
            <div className="section-card__header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CreditCard size={18} color="var(--color-teal-accent)" />
                <h3 id="passport-heading" className="section-card__title">
                  Passport &amp; Document Information
                </h3>
              </div>
              <span className="section-card__counter">
                {PASSPORT_KEYS.filter((k) => fields[k]?.value !== null).length} / {PASSPORT_KEYS.length} Extracted
              </span>
            </div>
            <div className="detail-rows-group">
              {PASSPORT_KEYS.map((key) => renderFieldRow(fields[key]))}
            </div>
          </section>
        </>
      )}

      {/* Card 3: MRZ Inspection & Check Digits */}
      <section className="section-card" aria-labelledby="mrz-heading">
        <div className="section-card__header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Binary size={18} color="var(--color-navy-primary)" />
            <h3 id="mrz-heading" className="section-card__title">
              Machine Readable Zone (MRZ) Inspection
            </h3>
          </div>
          {mrz.detected && (
            <span
              className={`badge ${
                mrz.all_check_digits_valid && mrz.line_length_valid
                  ? 'badge--success'
                  : mrz.check_digits.length === 0
                  ? 'badge--warning'
                  : 'badge--error'
              }`}
            >
              {mrz.all_check_digits_valid && mrz.line_length_valid
                ? 'MRZ Check Digits Valid'
                : mrz.check_digits.length === 0
                ? 'Partial MRZ (Line 1 Detected)'
                : 'MRZ Validation Issues'}
            </span>
          )}
        </div>

        {mrz.detected ? (
          <>
            {mrz.is_partial && (
              <div
                style={{
                  marginBottom: '1rem',
                  padding: '0.75rem 1rem',
                  borderRadius: '6px',
                  background: 'rgba(234, 138, 0, 0.08)',
                  border: '1px solid rgba(234, 138, 0, 0.25)',
                  fontSize: '0.85rem',
                }}
              >
                <div style={{ fontWeight: 600, color: 'var(--color-warning)', marginBottom: '3px' }}>
                  Partial MRZ Zone Detected ({mrz.raw_lines.length} Line{mrz.raw_lines.length > 1 ? 's' : ''})
                </div>
                <div>
                  <strong>Reason:</strong> {mrz.partial_reason ? mrz.partial_reason.replace(/_/g, ' ') : 'Incomplete zone detected'}.
                </div>
                {mrz.failure_classification && (
                  <div style={{ marginTop: '3px', color: 'var(--color-text-secondary)' }}>
                    <strong>Classification:</strong> <code>{mrz.failure_classification}</code>
                  </div>
                )}
              </div>
            )}

            {mrz.check_digits.length === 0 && (
              <div
                style={{
                  marginBottom: '1rem',
                  padding: '0.75rem 1rem',
                  borderRadius: '6px',
                  background: 'var(--color-bg-page)',
                  border: '1px solid var(--color-border)',
                  fontSize: '0.82rem',
                  color: 'var(--color-text-secondary)',
                }}
              >
                <strong>Check Digits Notice:</strong> Mathematical check-digit verification is not applicable to incomplete or single-line MRZ candidates. Verification requires Line 2 (TD2/TD3) or Line 3 (TD1).
              </div>
            )}

            <div className="mrz-code-box" aria-label="Normalized MRZ lines">
              {mrz.normalized_lines.map((line, idx) => (
                <div key={idx}>{line}</div>
              ))}
            </div>

            {mrz.check_digits.length > 0 && (
              <div className="table-wrapper">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Check-Digit Target</th>
                      <th scope="col">Position</th>
                      <th scope="col">Data Segment</th>
                      <th scope="col">Expected</th>
                      <th scope="col">Actual</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mrz.check_digits.map((cd) => (
                      <tr key={cd.field_name}>
                        <td>
                          <strong>{cd.field_name}</strong>
                        </td>
                        <td>{cd.position_description}</td>
                        <td>
                          <code>{cd.data_segment}</code>
                        </td>
                        <td>
                          <code>{cd.expected_digit}</code>
                        </td>
                        <td>
                          <code>{cd.actual_digit}</code>
                        </td>
                        <td>
                          <span className={`badge ${cd.is_valid ? 'badge--success' : 'badge--error'}`}>
                            {cd.is_valid ? 'Valid' : 'Failed'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <div className="disclaimer-note">{mrz.authenticity_disclaimer}</div>
          </>
        ) : (
          <p style={{ margin: 0, color: 'var(--color-text-secondary)' }}>
            PassPortIQ could not locate a 2-line (TD2/TD3) or 3-line (TD1) Machine Readable Zone in this image. Ensure the bottom edge of the passport data page is unobstructed and clearly focused.
          </p>
        )}
      </section>

      {/* Warnings Panel if any (placed after MRZ so extracted details are at the top) */}
      {warnings.length > 0 && (
        <section className="section-card section-card--warning" aria-labelledby="warnings-heading">
          <div className="section-card__header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={18} color="var(--color-warning)" />
              <h3 id="warnings-heading" className="section-card__title">
                Validation Warnings &amp; Uncertainty Notices ({warnings.length})
              </h3>
            </div>
          </div>
          <ul className="warning-list">
            {warnings.map((w, index) => (
              <li key={`${w.code}-${index}`} className="warning-item warning-item--warning">
                <span className="badge badge--warning">{w.severity.toUpperCase()}</span>
                <div>
                  <strong>{w.code}</strong>
                  {w.field_name ? ` (${w.field_name})` : ''}: {w.message}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Card 4: Technical Diagnostics Accordion */}
      <section className="section-card">
        <button
          type="button"
          className="tech-details-toggle"
          onClick={() => setTechOpen((prev) => !prev)}
          aria-expanded={techOpen}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Cpu size={16} />
            <span style={{ fontWeight: 600 }}>Technical Diagnostics, Preprocessing &amp; Privacy Metadata</span>
          </div>
          {techOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>

        <AnimatePresence>
          {techOpen && (
            <motion.div
              initial={disableAnimation ? undefined : { opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={disableAnimation ? undefined : { opacity: 0, height: 0 }}
              transition={{ duration: disableAnimation ? 0 : 0.2, ease: 'easeInOut' }}
              className="tech-details-content"
              style={{ overflow: 'hidden' }}
            >
              <div className="tech-grid">
                <div>
                  <h4 style={{ fontSize: '0.88rem', margin: '0 0 0.5rem', color: 'var(--color-navy-primary)' }}>
                    OCR Engine Execution
                  </h4>
                  <dl className="kv-list">
                    <dt>Requested Engine</dt>
                    <dd>{ocr_metadata.requested_engine}</dd>
                    <dt>Active Engine</dt>
                    <dd>{ocr_metadata.active_engine}</dd>
                    <dt>Fallback Used</dt>
                    <dd>{ocr_metadata.fallback_used ? 'Yes' : 'No'}</dd>
                    <dt>Detected Blocks</dt>
                    <dd>{ocr_metadata.detected_blocks_count}</dd>
                    <dt>Confidence Range</dt>
                    <dd>
                      {ocr_metadata.min_ocr_confidence !== null && ocr_metadata.max_ocr_confidence !== null
                        ? `${(ocr_metadata.min_ocr_confidence * 100).toFixed(1)}% – ${(ocr_metadata.max_ocr_confidence * 100).toFixed(1)}%`
                        : 'N/A'}
                    </dd>
                  </dl>
                </div>

                <div>
                  <h4 style={{ fontSize: '0.88rem', margin: '0 0 0.5rem', color: 'var(--color-navy-primary)' }}>
                    Image Normalization &amp; Preprocessing
                  </h4>
                  <dl className="kv-list">
                    <dt>Original Dimensions</dt>
                    <dd>{preprocessing.original_width} × {preprocessing.original_height} px</dd>
                    <dt>Processed Dimensions</dt>
                    <dd>{preprocessing.processed_width} × {preprocessing.processed_height} px</dd>
                    <dt>EXIF Transpose</dt>
                    <dd>{preprocessing.exif_orientation_applied ? 'Applied' : 'Not needed'}</dd>
                    <dt>Deskew Angle</dt>
                    <dd>{preprocessing.deskew_angle_degrees.toFixed(2)}°</dd>
                    <dt>Pipeline Steps</dt>
                    <dd>{preprocessing.steps_applied.join(', ') || 'None'}</dd>
                  </dl>
                </div>

                <div>
                  <h4 style={{ fontSize: '0.88rem', margin: '0 0 0.5rem', color: 'var(--color-navy-primary)' }}>
                    Image Quality &amp; Recovery
                  </h4>
                  <dl className="kv-list">
                    <dt>Quality Assessment</dt>
                    <dd>{preprocessing.quality_assessment ?? (preprocessing.is_blurry ? 'Blurry' : 'Sharp')}</dd>
                    <dt>Blur Score (Laplacian)</dt>
                    <dd>{preprocessing.blur_score !== null && preprocessing.blur_score !== undefined ? preprocessing.blur_score.toFixed(1) : 'N/A'}</dd>
                    <dt>Blur Flag</dt>
                    <dd>{preprocessing.is_blurry ? 'Yes (Blurry)' : 'No (Clear)'}</dd>
                    <dt>Sharpening Applied</dt>
                    <dd>{preprocessing.sharpening_applied ? 'Yes (Unsharp Mask)' : 'No'}</dd>
                    <dt>Winning Variant</dt>
                    <dd>{preprocessing.winning_variant ?? 'baseline'}</dd>
                    <dt>Variants Evaluated</dt>
                    <dd>{preprocessing.variants_evaluated?.join(', ') || 'baseline'}</dd>
                  </dl>
                </div>
              </div>

              <p className="disclaimer-note" style={{ marginTop: '1rem' }}>
                <strong>Privacy &amp; Confidence Note:</strong> {data.transient_processing_notice} {ocr_metadata.ocr_confidence_note}
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </section>
    </div>
  );
};
