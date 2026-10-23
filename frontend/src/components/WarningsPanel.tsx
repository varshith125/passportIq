import React from 'react';
import type { ExtractionWarning, WarningSeverity } from '../types/passport';

interface WarningsPanelProps {
  warnings: ExtractionWarning[];
}

function getSeverityBadge(severity: WarningSeverity): {
  label: string;
  badgeClass: string;
  itemClass: string;
} {
  switch (severity) {
    case 'error':
      return {
        label: 'Error',
        badgeClass: 'badge--error',
        itemClass: 'warning-item--error',
      };
    case 'warning':
      return {
        label: 'Warning',
        badgeClass: 'badge--warning',
        itemClass: 'warning-item--warning',
      };
    case 'info':
    default:
      return {
        label: 'Notice',
        badgeClass: 'badge--info',
        itemClass: '',
      };
  }
}

export const WarningsPanel: React.FC<WarningsPanelProps> = ({ warnings }) => {
  if (warnings.length === 0) {
    return null;
  }

  return (
    <section className="section-card" aria-labelledby="warnings-heading">
      <div className="section-card__header">
        <div>
          <h2 id="warnings-heading" className="section-card__title">
            Validation Warnings &amp; Uncertainty Notices ({warnings.length})
          </h2>
          <p className="section-card__subtitle">
            Review these diagnostic findings before relying on extracted values.
          </p>
        </div>
      </div>

      <ul className="warning-list">
        {warnings.map((w, index) => {
          const meta = getSeverityBadge(w.severity);
          return (
            <li
              key={`${w.code}-${index}`}
              className={`warning-item ${meta.itemClass}`}
            >
              <span className={`badge ${meta.badgeClass}`}>{meta.label}</span>
              <div>
                <strong>{w.code}</strong>
                {w.field_name ? ` (${w.field_name})` : ''}: {w.message}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
};
