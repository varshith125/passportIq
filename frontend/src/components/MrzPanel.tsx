import React from 'react';
import type { MrzParseResult } from '../types/passport';

interface MrzPanelProps {
  mrz: MrzParseResult;
}

export const MrzPanel: React.FC<MrzPanelProps> = ({ mrz }) => {
  return (
    <section className="section-card" aria-labelledby="mrz-heading">
      <div className="section-card__header">
        <div>
          <h2 id="mrz-heading" className="section-card__title">
            Machine Readable Zone (MRZ) Inspection
          </h2>
          <p className="section-card__subtitle">
            {mrz.detected
              ? `Format: ${
                  mrz.mrz_format ?? (mrz.parsed_fields?.document_type === 'P' ? 'TD3 (Partial / Line 1)' : 'Unclassified')
                } · Check Digits: ${
                  mrz.all_check_digits_valid
                    ? 'All Passed'
                    : mrz.check_digits.length > 0
                    ? 'Failures Detected'
                    : 'Line 2 Missing / Not Checked'
                }`
              : 'No Machine Readable Zone candidate was detected in the uploaded image.'}
          </p>
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
                        <span
                          className={`badge ${
                            cd.is_valid ? 'badge--success' : 'badge--error'
                          }`}
                        >
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
  );
};
