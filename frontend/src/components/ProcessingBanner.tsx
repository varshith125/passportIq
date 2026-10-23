import React from 'react';
import { Loader2, XCircle } from 'lucide-react';

interface ProcessingBannerProps {
  fileName: string;
  onCancel: () => void;
}

export const ProcessingBanner: React.FC<ProcessingBannerProps> = ({
  fileName,
  onCancel,
}) => {
  return (
    <div
      className="status-panel status-panel--processing"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="status-panel__content">
        <div className="status-panel__spinner-wrapper" aria-hidden="true">
          <Loader2 size={24} className="spin-icon" color="var(--color-accent)" />
        </div>

        <div className="status-panel__text">
          <div className="status-panel__title-row">
            <strong className="status-panel__title">
              Processing {fileName}
            </strong>
            <span className="badge badge--info">RapidOCR ONNX Runtime</span>
          </div>
          <p className="status-panel__subtext">
            Validating file signatures &amp; EXIF orientation, executing deep OCR text recognition, verifying ICAO 9303 Modulo-10 check digits, and reconciling VIZ/MRZ candidates.
          </p>
        </div>
      </div>

      <button
        type="button"
        className="btn btn--secondary status-panel__cancel-btn"
        onClick={onCancel}
        aria-label="Cancel document extraction"
      >
        <XCircle size={15} />
        <span>Cancel</span>
      </button>
    </div>
  );
};

export default ProcessingBanner;
