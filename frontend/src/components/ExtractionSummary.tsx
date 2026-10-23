import React, { useState } from 'react';
import { formatExtractionForClipboard } from '../features/scanner/formatClipboardText';
import type {
  DocumentClassification,
  PassportExtractionResponse,
  ProcessingStatus,
  ReconciliationStatus,
} from '../types/passport';

interface ExtractionSummaryProps {
  data: PassportExtractionResponse;
  onReset: () => void;
}

function getStatusBadge(status: ProcessingStatus): {
  label: string;
  variant: string;
} {
  switch (status) {
    case 'completed':
      return { label: 'Completed (MRZ & Core Fields Verified)', variant: 'badge--success' };
    case 'partial':
      return { label: 'Partial / Needs Review', variant: 'badge--warning' };
    case 'no_passport_detected':
      return { label: 'No Passport Data Detected', variant: 'badge--error' };
    case 'failed':
    default:
      return { label: 'Failed', variant: 'badge--error' };
  }
}

function formatClassification(cls: DocumentClassification): string {
  switch (cls) {
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
      return 'Unknown / Unrecognized Layout';
  }
}

function getReconciliationBadge(status: ReconciliationStatus): {
  label: string;
  variant: string;
} {
  switch (status) {
    case 'matched':
      return { label: 'Matched Across MRZ & VIZ', variant: 'badge--success' };
    case 'mismatch':
      return { label: 'Field Discrepancy Detected', variant: 'badge--error' };
    case 'insufficient_data':
      return { label: 'Insufficient Overlapping Data', variant: 'badge--warning' };
    case 'not_checked':
    default:
      return { label: 'Not Checked', variant: 'badge--neutral' };
  }
}

export const ExtractionSummary: React.FC<ExtractionSummaryProps> = ({
  data,
  onReset,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const text = formatExtractionForClipboard(data);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  const statusBadge = getStatusBadge(data.status);
  const recBadge = getReconciliationBadge(data.reconciliation.overall_status);
  const meanConf =
    data.ocr_metadata.mean_ocr_confidence !== null
      ? `${(data.ocr_metadata.mean_ocr_confidence * 100).toFixed(1)}%`
      : 'N/A';

  return (
    <section className="section-card" aria-labelledby="summary-heading">
      <div className="section-card__header">
        <div>
          <h2 id="summary-heading" className="section-card__title">
            Extraction Overview
          </h2>
          <p className="section-card__subtitle">
            Processed in {data.processing_duration_ms.toFixed(0)} ms using{' '}
            <code>{data.ocr_metadata.active_engine}</code>
          </p>
        </div>
        <div className="action-bar">
          <button
            type="button"
            className="btn btn--secondary"
            onClick={handleCopy}
          >
            {copied ? 'Copied Extracted Details' : 'Copy Extracted Details'}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={onReset}
          >
            Scan Another Document
          </button>
        </div>
      </div>

      {(data.preprocessing.is_blurry || data.status === 'partial' || data.mrz.is_partial) && (
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
          <div>
            <strong style={{ display: 'block', marginBottom: '2px', color: 'var(--color-warning)' }}>
              {data.preprocessing.is_blurry
                ? 'Mild Blur or Suboptimal Image Quality Detected'
                : 'Incomplete / Partial Document Extraction'}
            </strong>
            <span style={{ fontSize: '0.88rem', color: 'var(--color-text-secondary)' }}>
              Recommendation: Upload a sharper, uncropped image under even lighting for higher extraction accuracy and automated check-digit validation.
            </span>
          </div>
        </div>
      )}

      <div className="summary-grid" style={{ marginTop: '1.25rem' }}>
        <div className="metric-tile">
          <span className="metric-tile__label">Processing Status</span>
          <div className="metric-tile__value">
            <span className={`badge ${statusBadge.variant}`}>
              {statusBadge.label}
            </span>
          </div>
          <span className="metric-tile__hint">
            Individual field states are listed below
          </span>
        </div>

        <div className="metric-tile">
          <span className="metric-tile__label">Document Classification</span>
          <div className="metric-tile__value">
            {formatClassification(data.document_classification)}
          </div>
          <span className="metric-tile__hint">
            MRZ Detected: {data.mrz.detected ? 'Yes' : 'No'} {data.mrz.is_partial ? '(Partial)' : ''}
          </span>
        </div>

        <div className="metric-tile">
          <span className="metric-tile__label">MRZ vs. VIZ Reconciliation</span>
          <div className="metric-tile__value">
            <span className={`badge ${recBadge.variant}`}>{recBadge.label}</span>
          </div>
          <span className="metric-tile__hint">
            {data.reconciliation.matched_count} matched ·{' '}
            {data.reconciliation.mismatch_count} mismatch ·{' '}
            {data.reconciliation.insufficient_data_count} single-source/missing
          </span>
        </div>

        <div className="metric-tile">
          <span className="metric-tile__label">
            Mean OCR Recognition Confidence
          </span>
          <div className="metric-tile__value">{meanConf}</div>
          <span className="metric-tile__hint">
            Model certainty (distinct from field validation)
          </span>
        </div>
      </div>
    </section>
  );
};
