import React, { useRef, useState } from 'react';
import { UploadCloud, FileCheck2, ShieldCheck, FileText } from 'lucide-react';

interface UploadZoneProps {
  disabled?: boolean;
  onFileSelected: (file: File) => void;
}

export const UploadZone: React.FC<UploadZoneProps> = ({
  disabled = false,
  onFileSelected,
}) => {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      onFileSelected(file);
    }
    event.target.value = '';
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (!disabled) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    if (disabled) {
      return;
    }
    const file = event.dataTransfer.files?.[0];
    if (file) {
      onFileSelected(file);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (disabled) {
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      inputRef.current?.click();
    }
  };

  const classNames = [
    'upload-card',
    isDragging ? 'upload-card--active' : '',
    disabled ? 'upload-card--disabled' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={classNames}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      aria-label="Upload passport image by clicking or dragging and dropping a file"
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={handleKeyDown}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="upload-card__icon" aria-hidden="true">
        <UploadCloud size={28} />
      </div>

      <h2 className="upload-card__heading">
        Upload a Passport Image or Document
      </h2>

      <p className="upload-card__subtext">
        Drag and drop your passport document, photo, or scan here, or browse from your device
      </p>

      <button
        type="button"
        className="btn btn--primary btn--upload-action"
        disabled={disabled}
        onClick={(e) => {
          e.stopPropagation();
          inputRef.current?.click();
        }}
      >
        <FileText size={16} />
        <span>Select Passport File</span>
      </button>

      <div className="upload-card__constraints-box">
        <div className="upload-constraint-item">
          <FileCheck2 size={13} className="upload-constraint-icon" aria-hidden="true" />
          <span>Supported formats: <strong>JPEG, PNG, WebP, TIFF, BMP, PDF</strong></span>
        </div>
        <div className="upload-constraint-item">
          <ShieldCheck size={13} className="upload-constraint-icon" aria-hidden="true" />
          <span>Max upload: <strong>200 MB</strong> · Safe in-memory decoding with decompression bomb protection</span>
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/tiff,image/bmp,application/pdf"
        onChange={handleFileChange}
        disabled={disabled}
        aria-label="Passport image file input"
        style={{ display: 'none' }}
      />
    </div>
  );
};

export default UploadZone;
