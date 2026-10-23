import React from 'react';
import type { PassportExtractionResponse } from '../types/passport';

interface TechnicalDetailsProps {
  data: PassportExtractionResponse;
}

export const TechnicalDetails: React.FC<TechnicalDetailsProps> = ({ data }) => {
  const { ocr_metadata, preprocessing } = data;

  return (
    <section className="section-card">
      <details className="tech-details">
        <summary>
          Technical Diagnostics, Preprocessing &amp; Privacy Metadata
        </summary>
        <div className="tech-grid">
          <div>
            <h3 style={{ fontSize: '0.9rem', marginBottom: '0.6rem' }}>
              OCR Engine Execution
            </h3>
            <dl className="kv-list">
              <dt>Requested Engine</dt>
              <dd>{ocr_metadata.requested_engine}</dd>
              <dt>Active Engine</dt>
              <dd>{ocr_metadata.active_engine}</dd>
              <dt>Fallback Used</dt>
              <dd>{ocr_metadata.fallback_used ? 'Yes' : 'No'}</dd>
              {ocr_metadata.fallback_reason && (
                <>
                  <dt>Fallback Reason</dt>
                  <dd>{ocr_metadata.fallback_reason}</dd>
                </>
              )}
              <dt>Detected Text Blocks</dt>
              <dd>{ocr_metadata.detected_blocks_count}</dd>
              <dt>Confidence Range</dt>
              <dd>
                {ocr_metadata.min_ocr_confidence !== null &&
                ocr_metadata.max_ocr_confidence !== null
                  ? `${(ocr_metadata.min_ocr_confidence * 100).toFixed(1)}% – ${(
                      ocr_metadata.max_ocr_confidence * 100
                    ).toFixed(1)}%`
                  : 'N/A'}
              </dd>
            </dl>
          </div>

          <div>
            <h3 style={{ fontSize: '0.9rem', marginBottom: '0.6rem' }}>
              Image Normalization &amp; Preprocessing
            </h3>
            <dl className="kv-list">
              <dt>Original Format</dt>
              <dd>
                {preprocessing.original_format} ({preprocessing.original_mode})
              </dd>
              <dt>Original Dimensions</dt>
              <dd>
                {preprocessing.original_width} × {preprocessing.original_height} px
              </dd>
              <dt>Processed Dimensions</dt>
              <dd>
                {preprocessing.processed_width} × {preprocessing.processed_height} px
              </dd>
              <dt>EXIF Transpose</dt>
              <dd>
                {preprocessing.exif_orientation_applied
                  ? `Applied (Tag ${preprocessing.exif_orientation_tag})`
                  : 'Not needed'}
              </dd>
              <dt>Deskew Angle</dt>
              <dd>{preprocessing.deskew_angle_degrees.toFixed(2)}°</dd>
              <dt>Pipeline Steps</dt>
              <dd>{preprocessing.steps_applied.join(', ') || 'None'}</dd>
            </dl>
          </div>

          <div>
            <h3 style={{ fontSize: '0.9rem', marginBottom: '0.6rem' }}>
              Image Quality &amp; Multi-Variant Recovery
            </h3>
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
          <strong>Privacy &amp; Confidence Note:</strong>{' '}
          {data.transient_processing_notice} {ocr_metadata.ocr_confidence_note}
        </p>
      </details>
    </section>
  );
};
