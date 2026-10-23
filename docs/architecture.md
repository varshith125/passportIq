# PassPortIQ v2 — System Architecture

## 1. Architectural Overview

PassPortIQ v2 is a modular, stateless document-processing web application separated into two independent subsystems:

1. **Frontend (`frontend/`)**: A responsive React 18 + TypeScript single-page application built with Vite. It manages client-side file constraint checks, multipart upload dispatch with cancellation (`AbortController`), field-level validation and reconciliation rendering, MRZ check-digit inspection, and clipboard export.
2. **Backend (`backend/`)**: A Python 3.11 + FastAPI service structured into isolated domain layers (`services`, `ocr`, `mrz`, `viz`, `pipeline`, `schemas`, `api`). Uploaded passport images are processed strictly transiently in memory without database storage or disk persistence.

```text
[Browser Client (React + TS)]
        │
        │ POST /api/passports/extract (multipart/form-data)
        ▼
[FastAPI Route Layer (app/api/passports.py)]
        │  Bounded chunk reader (64 KB chunks, max 10 MB)
        ▼
[Pipeline Orchestrator (app/pipeline/orchestrator.py)]
   ├── 1. Image Security & Decoding (app/services/image_security.py)
   │      • Magic-byte signature verification (JPEG, PNG, WEBP, TIFF)
   │      • Decompression bomb & header dimension checks (300×200 .. 6000×6000, ≤20 MP)
   │      • Lossless EXIF orientation transpose
   │
   ├── 2. Conditional Preprocessing (app/services/preprocessing.py)
   │      • Area-interpolated downscaling (>2200 px max dimension)
   │      • Grayscale conversion & Hough-line skew estimation/deskewing
   │      • Conditional bilateral denoising & CLAHE contrast enhancement
   │
   ├── 3. OCR Engine Execution (app/ocr/rapidocr_engine.py)
   │      • Primary singleton: RapidOCR + ONNX Runtime
   │      • Optional explicit fallback: Tesseract OCR (never silent)
   │      • Bounded thread execution with configurable timeout
   │
   ├── 4. MRZ Detection & Validation (app/mrz/detector.py, parser.py, check_digits.py)
   │      • Spatial & lexical detection for ICAO 9303 TD1 (3×30), TD2 (2×36), TD3 (2×44)
   │      • Bounded, auditable OCR confusion recovery
   │      • Modulo-10 [7, 3, 1] check-digit verification (individual + composite)
   │
   ├── 5. Visible Inspection Zone Extraction & Regex Validation (app/viz/extractor.py, regex_extractor.py)
   │      • Inline and spatial label-to-value bounding box alignment
   │      • Intervening-label guard to prevent cross-field misassignment
   │      • Regex validation layer with strict calendar date parsing, ISO nationality registry, and OCR confusion normalization
   │
   └── 6. Cross-Zone Reconciliation (app/pipeline/reconciliation.py)
          • Field-by-field comparison between MRZ and VIZ
          • Explicit statuses: matched, mismatch, insufficient_data, not_checked
```

## 2. Separation of Concerns

* **Route Handlers (`app/api/`)**: Contain zero business logic. They handle HTTP status codes, chunked upload streaming, and schema serialization.
* **OCR Engine Confidence vs. Field Validation**: The API and UI explicitly separate `ocr_confidence` (the character recognition probability reported by the OCR model) from `validation_state` (deterministic ICAO 9303 check-digit or format verification) and `reconciliation_status` (agreement between MRZ and VIZ).
* **Explicit OCR Fallback Policy**: `RapidOcrEngineManager` loads `rapidocr_onnxruntime` as a process-wide singleton. If `rapidocr_onnxruntime` is unavailable, the service fails closed (`503 Service Unavailable`) unless `PASSPORTIQ_OCR_ALLOW_TESSERACT_FALLBACK=true` is explicitly enabled, in which case the response sets `ocr_metadata.fallback_used = true`, `ocr_metadata.active_engine = "tesseract_fallback"`, and emits an `OCR_FALLBACK_ENGINE_USED` warning.
