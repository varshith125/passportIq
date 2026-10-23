# PassPortIQ — Intelligent Passport Data Extraction System (v2.0.0)

> **Accurate Passport Data Extraction with OCR & MRZ Validation**

PassPortIQ v2 is a full-stack web application that extracts, validates, and reconciles passport and travel document data from uploaded images using secure image decoding, conditional OpenCV preprocessing, OCR text extraction (**RapidOCR + ONNX Runtime** primary engine with explicit opt-in **Tesseract** fallback), **ICAO Doc 9303 MRZ parsing** (`TD1`, `TD2`, `TD3`), **Visible Inspection Zone (VIZ)** extraction, and cross-zone field reconciliation.

## Key Capabilities

* **Defense-in-Depth Upload Security**: Validates raw magic-byte signatures (`JPEG`, `PNG`, `WEBP`, `TIFF`), enforces byte-size (`10 MB`), dimension (`300×200` to `6000×6000`), and pixel-count (`20 MP`) limits prior to full image allocation, protects against decompression bombs, and applies lossless EXIF orientation correction.
* **Measurable Image Preprocessing**: Selectively applies area-interpolated downscaling, grayscale conversion, Hough-line skew detection and deskewing, bilateral denoising, and CLAHE contrast enhancement only when image statistics warrant it, while preserving the original decoded image.
* **Real OCR Integration with Honest Provider Reporting**: Uses `rapidocr_onnxruntime` as a singleton primary engine. Supports `tesseract` only when explicitly enabled via `PASSPORTIQ_OCR_ALLOW_TESSERACT_FALLBACK=true` or `PASSPORTIQ_OCR_PRIMARY_ENGINE=tesseract`, reporting `requested_engine`, `active_engine`, `fallback_used`, and `fallback_reason` in every response.
* **ICAO 9303 MRZ Detection, Parsing & Modulo-10 Validation**: Supports `TD1` (3×30), `TD2` (2×36), and `TD3` (2×44) formats, verifies individual and composite check digits with weights `[7, 3, 1]`, applies bounded and auditable OCR confusion recovery in strict single-type positions without blind padding/truncation, and preserves raw OCR lines.
* **Best-Effort VIZ Extraction & Cross-Zone Reconciliation**: Extracts visible fields using inline and spatial bounding-box alignment, guards against intervening-label misassignment, and compares MRZ and VIZ values using explicit statuses (`matched`, `mismatch`, `insufficient_data`, `not_checked`).
* **Transient In-Memory Privacy**: Processes images strictly in memory without database storage or persistent disk writes, and filters MRZ strings and PII labels from application logs.

## Project Structure

```text
passportiq-v2/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes (/health/live, /health/ready, /api/passports/extract)
│   │   ├── core/           # Settings, structured exceptions, PII-redacting logger
│   │   ├── mrz/            # ICAO 9303 check digits, detector, and TD1/TD2/TD3 parser
│   │   ├── ocr/            # OCR data structures and RapidOCR/Tesseract manager
│   │   ├── pipeline/       # Orchestrator and MRZ vs. VIZ reconciliation logic
│   │   ├── schemas/        # Typed Pydantic v2 request/response models
│   │   ├── services/       # Image signature/bomb security and OpenCV preprocessing
│   │   ├── viz/            # Visible Inspection Zone spatial/label extractor
│   │   └── main.py         # FastAPI application factory and exception handlers
│   ├── tests/              # Automated unittest/pytest suite + benchmark harness
│   └── pyproject.toml      # Backend dependencies and Ruff/Mypy/Pytest configuration
├── frontend/
│   ├── src/
│   │   ├── components/     # Header, UploadZone, ProcessingBanner, ExtractionSummary, FieldTable, MrzPanel, WarningsPanel, TechnicalDetails
│   │   ├── features/       # Scanner state hook and clipboard text formatter
│   │   ├── services/       # Typed fetch client for /api/passports/extract
│   │   ├── styles/         # CSS variables and responsive SaaS light theme
│   │   ├── test/           # Vitest + React Testing Library test suite
│   │   ├── types/          # TypeScript interfaces matching backend schemas
│   │   ├── App.tsx         # Main application workflow
│   │   └── main.tsx        # React DOM entry point
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── docs/
│   ├── architecture.md
│   ├── evaluation-plan.md
│   ├── security-and-privacy.md
│   └── testing.md
├── .env.example
├── .gitignore
├── README.md
└── RUNBOOK.md
```

## Installation & Startup Instructions

> **Quick Start**: See the dedicated [Operations Runbook](file:///c:/Users/varsh/Downloads/passportiq-v2/RUNBOOK.md) for copy-paste execution commands and troubleshooting.

### 1. Backend Setup

#### Linux / macOS

```bash
cd backend

# Create and activate a Python 3.11+ virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install backend dependencies (including RapidOCR + ONNX Runtime and dev tools)
pip install -e ".[dev,tesseract]"

# Start the FastAPI development server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Windows (PowerShell)

```powershell
cd backend

# Create and activate a Python 3.11+ virtual environment
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install -e ".[dev,tesseract]"

# Start the FastAPI development server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# Or run directly via the venv executable:
# .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

To enable the optional Tesseract fallback when testing in environments without RapidOCR ONNX model weights:

- **Linux / macOS**: `export PASSPORTIQ_OCR_ALLOW_TESSERACT_FALLBACK=true`
- **Windows (PowerShell)**: `$env:PASSPORTIQ_OCR_ALLOW_TESSERACT_FALLBACK="true"`

### 2. Frontend Setup

```bash
cd passportiq-v2/frontend

# Install Node.js dependencies
npm install

# Start the Vite development server (proxies /api and /health to http://127.0.0.1:8000)
npm run dev
```

Open `http://localhost:5173` in your browser.

## Testing & Quality Assurance

### Run Backend Tests & Linting
```bash
cd passportiq-v2/backend

# Run full backend test suite (92 tests)
pytest

# Strict type checking and linting
mypy app tests
ruff check app tests
```

### Run Frontend Tests & Build
```bash
cd passportiq-v2/frontend

# Run Vitest test suite (11 tests)
npm test

# TypeScript type checking
npm run typecheck

# Production build verification
npm run build
```

## Troubleshooting

1. **Port In Use (8000 or 5173)**:
   - On Windows PowerShell: `Get-NetTCPConnection -LocalPort 8000, 5173 -ErrorAction SilentlyContinue`
   - On Linux/macOS: `lsof -i :8000 -i :5173`
   - Terminate the conflicting process or run uvicorn on an alternate port: `uvicorn app.main:app --port 8001`.
2. **Virtual Environment on Windows**:
   - In PowerShell, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` if script activation is restricted, or run commands directly via `.\.venv\Scripts\python.exe` and `.\.venv\Scripts\pytest.exe`.
3. **OCR Engine Readiness**:
   - Query `GET /health/ready` to check RapidOCR ONNX model loading status.
   - If RapidOCR weights are not found, enable Tesseract fallback:
     - Linux/macOS: `export PASSPORTIQ_OCR_ALLOW_TESSERACT_FALLBACK=true`
     - Windows PowerShell: `$env:PASSPORTIQ_OCR_ALLOW_TESSERACT_FALLBACK="true"`
4. **Vite API Proxy**:
   - The Vite development server automatically proxies `/api` and `/health` requests to `http://127.0.0.1:8000`. Ensure the backend server is running before issuing scan requests from the browser.

## API Usage Examples

### Health Checks

```bash
# Liveness check
curl -i http://127.0.0.1:8000/health/live

# Readiness check (verifies OCR engine readiness)
curl -i http://127.0.0.1:8000/health/ready
```

### Extract Passport Data (`POST /api/passports/extract`)

```bash
curl -X POST http://127.0.0.1:8000/api/passports/extract \
  -F "file=@/path/to/passport_sample.png;type=image/png" \
  -H "Accept: application/json"
```

Example abbreviated response:

```json
{
  "status": "completed",
  "document_classification": "passport_td3",
  "fields": {
    "passport_number": {
      "field_name": "passport_number",
      "label": "Passport Number",
      "value": "L898902C3",
      "raw_evidence": "MRZ:L898902C3 | VIZ:Passport No -> L898902C3",
      "source": "reconciled",
      "validation_state": "valid_check_digit",
      "ocr_confidence": 0.99,
      "reconciliation_status": "matched",
      "mrz_value": "L898902C3",
      "viz_value": "L898902C3",
      "notes": []
    }
  },
  "mrz": {
    "detected": true,
    "mrz_format": "TD3",
    "all_check_digits_valid": true,
    "line_length_valid": true,
    "character_set_valid": true
  },
  "reconciliation": {
    "overall_status": "matched",
    "compared_fields_count": 9,
    "matched_count": 9,
    "mismatch_count": 0
  },
  "ocr_metadata": {
    "requested_engine": "rapidocr",
    "active_engine": "rapidocr_onnxruntime",
    "fallback_used": false
  }
}
```

## Known Limitations

1. **VIZ Layout Variability**: Visible Inspection Zone extraction uses bilingual keyword labels and spatial proximity heuristics. Passports with non-Latin-only VIZ labels, heavy holographic overlays obscuring labels, or non-standard multi-column layouts may yield `unavailable` or `unverified` VIZ fields while still extracting the standardized ICAO 9303 MRZ.
2. **Two-Digit MRZ Year Pivot**: ICAO 9303 encodes dates as `YYMMDD` without century digits. PassPortIQ resolves birth years as `<= current_year` (`19YY` vs `20YY`) and expiry years up to 25 years in the future (`20YY`), which can misclassify centenarian birth dates (>100 years old) unless corroborated by a 4-digit VIZ date.
3. **No Cryptographic or Physical Authenticity Verification**: Valid Modulo-10 check digits confirm internal OCR/MRZ consistency only and do not verify NFC ePassport chip signatures (ICAO PKD) or physical security features.

## Prioritized Future Improvements

1. **MRZ Crop & Second-Pass Specialized OCR**: Detect the bottom MRZ bounding box via morphological blackhat operations and run a dedicated OCR pass with an ICAO `0-9A-Z<` character whitelist to improve accuracy on low-resolution camera captures.
2. **Bilingual & Multi-Script VIZ Country Templates**: Add country-specific VIZ layout templates keyed by the 3-letter MRZ `issuing_country` code to boost `place_of_birth` and `date_of_issue` recall.
3. **Client-Side Perspective Crop & Glare Warning**: Add an interactive document bounding-box preview and specular glare detector in the frontend before uploading.
4. **Containerization & Rate Limiting**: Add a multi-stage `Dockerfile` pre-bundling RapidOCR ONNX weights and per-IP token-bucket rate limiting for production deployment.
