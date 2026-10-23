# PassPortIQ v2 — Testing Guide

## 1. Test Philosophy & Structure

PassPortIQ v2 includes unit, integration, and end-to-end API tests designed to run deterministically without requiring real personal passport images in source control.

All backend test modules in `backend/tests/` are written using Python's standard `unittest.TestCase` framework so they can be executed either with the standard library runner (`python3 -m unittest`) or with `pytest`.

### Backend Test Matrix (`backend/tests/`)

| Test File | Coverage Scope |
| :--- | :--- |
| `test_image_security.py` | Valid JPEG/PNG/WEBP/TIFF signatures, empty payload (`400`), spoofed PDF/text extension (`415`), oversized file bytes (`413`), undersized/oversized dimensions (`400`/`413`), decompression bomb pixel limits (`413`), corrupted streams (`400`), lossless EXIF orientation transpose, and PII/MRZ log redaction. |
| `test_preprocessing.py` | Oversized image downscaling for OCR while preserving original RGB array, conditional CLAHE contrast enhancement on low-dynamic-range images, skip of unnecessary transformations on clean images, and Hough-line deskew rotation. |
| `test_ocr_engine.py` | RapidOCR raw tuple normalization, malformed/empty output handling, confidence clamping, fail-closed `503` behavior when RapidOCR is missing and fallback is disabled, explicit opt-in `tesseract_fallback` reporting, and `504` timeout enforcement. |
| `test_mrz_parser.py` | ICAO 9303 Modulo-10 `[7, 3, 1]` check digits, valid TD3 (2×44), TD2 (2×36), and TD1 (3×30) parsing, failed check-digit detection, bounded OCR confusion recovery (`0`↔`O` in strict positions), rejection of invalid line lengths without blind padding/truncation, invalid calendar date rejection, and single-line incomplete MRZ handling. |
| `test_viz_extractor.py` | Spatial label-above-value and inline `Label: Value` extraction, intervening-label guard (preventing adjacent labels from stealing values), MRZ exclusion from VIZ, and unverified/ambiguous date rejection. |
| `test_regex_extractor.py` | Dedicated 20-scenario test suite verifying regex extraction layer, strict calendar date validation, impossible date rejection, ISO nationality validation, name & full name derivation, passport number alphanumeric format validation, and single-source reconciliation. |
| `test_reconciliation.py` | Full MRZ/VIZ agreement (`matched`), country-synonym matching (`UTO` vs `UTOPIA`), field conflict detection (`mismatch` + `CONFLICT`), zero-comparison guard (`insufficient_data` when VIZ is empty), and `not_checked` status for VIZ-only fields (`date_of_issue`, `place_of_birth`). |
| `test_health.py` | `GET /health/live` (`200`) and `GET /health/ready` (`200` when OCR engine ready, `503` when degraded). |
| `test_api_extract.py` | End-to-end `POST /api/passports/extract` with RapidOCR fixtures, blank image handling (`no_passport_detected`), `415`/`413` error envelopes, and live synthetic image OCR execution with explicit Tesseract fallback. |

### Frontend Test Matrix (`frontend/src/test/App.test.tsx`)

* Client-side file validation (empty file, unsupported MIME/extension, valid image).
* Clipboard text formatting with field sources and validation states.
* Full user workflow simulation (file selection, genuine loading state, extracted fields table, MRZ check-digit display, warning rendering, and reset/scan-another action).
* Structured API error banner rendering (`415 INVALID_FILE_SIGNATURE`).

## 2. Running Tests & Quality Checks

### Backend Commands

```bash
cd passportiq-v2/backend

# Run via Python standard library unittest (works offline without pytest installed)
python3 -m unittest discover -s tests -t . -v

# Run via pytest (when dev dependencies are installed)
pytest

# Run Ruff linter and formatter check
ruff check app tests

# Run Mypy strict type checking
mypy app tests
```

### Frontend Commands

```bash
cd passportiq-v2/frontend

# Install dependencies
npm install

# Run Vitest unit & component tests
npm test

# Run TypeScript compiler verification
npm run typecheck

# Run Oxlint static analysis
npm run lint

# Verify production bundle build
npm run build
```
