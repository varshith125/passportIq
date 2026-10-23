import React, { useEffect, useRef, useState } from 'react';
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Eye,
  Upload,
  FileText,
  Sliders,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import type { ScannerPhase } from '../features/scanner/usePassportScanner';
import type { PreprocessingMetadata } from '../types/passport';

interface PassportPreviewProps {
  file: File | null;
  phase: ScannerPhase;
  preprocessing?: PreprocessingMetadata;
  onReplaceFile: (file: File) => void;
}

type InspectFilter = 'normal' | 'contrast' | 'grayscale' | 'invert';

export const PassportPreview: React.FC<PassportPreviewProps> = ({
  file,
  phase,
  preprocessing,
  onReplaceFile,
}) => {
  const [zoom, setZoom] = useState<number>(1);
  const [filter, setFilter] = useState<InspectFilter>('normal');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isPanning, setIsPanning] = useState(false);
  const [panPos, setPanPos] = useState({ x: 0, y: 0 });
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Generate object URL for file
  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const isImage = file.type.startsWith('image/') || /\.(png|jpe?g|webp|tiff?|bmp)$/i.test(file.name);
    if (isImage && typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function') {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
      return () => {
        if (typeof URL.revokeObjectURL === 'function') {
          URL.revokeObjectURL(url);
        }
      };
    } else {
      setPreviewUrl(null);
    }
  }, [file]);

  const handleZoomIn = () => {
    setZoom((prev) => Math.min(prev + 0.25, 3.0));
  };

  const handleZoomOut = () => {
    setZoom((prev) => Math.max(prev - 0.25, 0.75));
  };

  const handleResetZoom = () => {
    setZoom(1);
    setPanPos({ x: 0, y: 0 });
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newFile = e.target.files?.[0];
    if (newFile) {
      onReplaceFile(newFile);
      setZoom(1);
      setPanPos({ x: 0, y: 0 });
    }
    e.target.value = '';
  };

  // Mouse pan handling when zoomed in
  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoom <= 1) return;
    setIsPanning(true);
    setDragStart({ x: e.clientX - panPos.x, y: e.clientY - panPos.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning || zoom <= 1) return;
    setPanPos({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  // Format filter style
  const getFilterStyle = (): string => {
    switch (filter) {
      case 'contrast':
        return 'contrast(160%) brightness(95%)';
      case 'grayscale':
        return 'grayscale(100%) contrast(130%)';
      case 'invert':
        return 'invert(90%) hue-rotate(180deg)';
      case 'normal':
      default:
        return 'none';
    }
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes && bytes !== 0) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="preview-card" role="region" aria-label="Passport Document Preview">
      {/* Card Header */}
      <div className="preview-card__header">
        <div className="preview-card__title-group">
          <div className="preview-card__icon" aria-hidden="true">
            <Eye size={18} />
          </div>
          <div>
            <h3 className="preview-card__title">
              {file ? file.name : 'Passport Document Preview'}
            </h3>
            <span className="preview-card__meta">
              {file && (
                <>
                  {formatFileSize(file.size)}
                  {preprocessing && (
                    <> · {preprocessing.original_width} × {preprocessing.original_height} px</>
                  )}
                </>
              )}
            </span>
          </div>
        </div>

        <div className="preview-card__actions">
          <button
            type="button"
            className="btn btn--secondary btn--sm"
            onClick={() => fileInputRef.current?.click()}
            title="Upload another passport or replace document"
            aria-label="Replace document"
          >
            <Upload size={14} />
            <span>Replace Image</span>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/tiff,image/bmp,application/pdf"
            style={{ display: 'none' }}
            onChange={handleFileInputChange}
            aria-label="Replace passport document input"
          />
        </div>
      </div>

      {/* Control Toolbar */}
      <div className="preview-toolbar" aria-label="Preview controls">
        <div className="preview-toolbar__group">
          <button
            type="button"
            className="toolbar-btn"
            onClick={handleZoomOut}
            disabled={zoom <= 0.75}
            title="Zoom Out"
            aria-label="Zoom out preview"
          >
            <ZoomOut size={15} />
          </button>
          <span className="toolbar-zoom-indicator" aria-live="polite">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            className="toolbar-btn"
            onClick={handleZoomIn}
            disabled={zoom >= 3.0}
            title="Zoom In"
            aria-label="Zoom in preview"
          >
            <ZoomIn size={15} />
          </button>
          <button
            type="button"
            className="toolbar-btn"
            onClick={handleResetZoom}
            disabled={zoom === 1 && panPos.x === 0 && panPos.y === 0}
            title="Reset Zoom & Pan"
            aria-label="Reset zoom and position"
          >
            <RotateCcw size={15} />
          </button>
        </div>

        <div className="preview-toolbar__group">
          <span className="toolbar-label" id="inspect-label">
            <Sliders size={13} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
            Inspect:
          </span>
          <div className="pill-group" role="radiogroup" aria-labelledby="inspect-label">
            <button
              type="button"
              className={`pill-btn ${filter === 'normal' ? 'pill-btn--active' : ''}`}
              onClick={() => setFilter('normal')}
              aria-checked={filter === 'normal'}
              role="radio"
            >
              Normal
            </button>
            <button
              type="button"
              className={`pill-btn ${filter === 'contrast' ? 'pill-btn--active' : ''}`}
              onClick={() => setFilter('contrast')}
              aria-checked={filter === 'contrast'}
              role="radio"
              title="Enhance contrast to read faint text or stamps"
            >
              Contrast
            </button>
            <button
              type="button"
              className={`pill-btn ${filter === 'grayscale' ? 'pill-btn--active' : ''}`}
              onClick={() => setFilter('grayscale')}
              aria-checked={filter === 'grayscale'}
              role="radio"
              title="Black & white inspection mode"
            >
              B&amp;W
            </button>
          </div>
        </div>
      </div>

      {/* Main Preview Viewport */}
      <div
        ref={containerRef}
        className={`preview-viewport ${zoom > 1 ? 'preview-viewport--zoomed' : ''} ${
          isPanning ? 'preview-viewport--panning' : ''
        }`}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {phase === 'uploading' && (
          <div className="preview-viewport__overlay">
            <Loader2 size={32} className="spin-icon" />
            <p>Scanning Document &amp; Performing OCR...</p>
          </div>
        )}

        {previewUrl ? (
          <div
            className="preview-viewport__stage"
            style={{
              transform: `translate(${panPos.x}px, ${panPos.y}px) scale(${zoom})`,
              transformOrigin: 'center center',
              transition: isPanning ? 'none' : 'transform 150ms ease-out',
            }}
          >
            <img
              src={previewUrl}
              alt="Uploaded Passport Document"
              className="preview-viewport__img"
              style={{
                filter: getFilterStyle(),
              }}
              draggable={false}
            />
          </div>
        ) : file ? (
          <div className="preview-viewport__fallback">
            <FileText size={48} className="preview-viewport__fallback-icon" />
            <h4>{file.name}</h4>
            <p>Document uploaded ({formatFileSize(file.size)})</p>
            <span className="badge badge--info">Processed Transiently</span>
          </div>
        ) : (
          <div className="preview-viewport__empty">
            <Eye size={36} color="var(--color-text-secondary)" />
            <p>No document selected</p>
          </div>
        )}
      </div>

      {/* Preview Footer / Status */}
      <div className="preview-card__footer">
        <div className="preview-card__badge-row">
          <span className="preview-badge">
            <CheckCircle2 size={13} color="var(--color-teal-accent)" />
            <span>Exact Upload Preserved</span>
          </span>
          {zoom > 1 && (
            <span className="preview-card__hint">
              Click &amp; drag image to pan
            </span>
          )}
        </div>
        <div className="preview-card__legal">
          Document data is processed strictly in-memory.
        </div>
      </div>
    </div>
  );
};
