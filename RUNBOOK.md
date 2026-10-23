# PassPortIQ v2 — Operations & Execution Runbook

This runbook provides step-by-step instructions to run, verify, test, and troubleshoot both the **FastAPI Backend** and the **React + Vite Frontend** on Windows (PowerShell) and Linux / macOS (Bash).

---

## 1. Quick Start (TL;DR)

Open **two separate terminal windows**:

### Terminal 1 — Backend (FastAPI + RapidOCR ONNX)
```powershell
cd c:\Users\varsh\Downloads\passportiq-v2\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*Backend API will be active at: `http://127.0.0.1:8000` (Swagger docs at `/docs`)*

### Terminal 2 — Frontend (React + Vite)
```powershell
cd c:\Users\varsh\Downloads\passportiq-v2\frontend
npm run dev
```
*Frontend will be active at: `http://localhost:5173/`*

---

## 2. Prerequisites & Environment

| Component | Requirement | Check Command |
| :--- | :--- | :--- |
| **Python** | 3.11 or higher | `python --version` |
| **Node.js** | 18.0 or higher (LTS recommended) | `node -v` |
| **npm** | 9.0 or higher | `npm -v` |
| **OS** | Windows 10/11, macOS, or Linux | System terminal |

---

## 3. Detailed Backend Setup & Run Guide

### Option A — Windows (PowerShell)

1. Open PowerShell and navigate to the backend directory:
   ```powershell
   cd c:\Users\varsh\Downloads\passportiq-v2\backend
   ```

2. If PowerShell script execution is restricted on your machine, bypass it for the current process:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   ```

3. Activate the pre-configured virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
   *(Your prompt will change to show `(.venv)`)*

4. *(First-time only)* Verify dependencies:
   ```powershell
   pip install -e ".[dev,tesseract]"
   ```

5. Launch the FastAPI server:
   ```powershell
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

   **Direct Executable Method (No activation required):**
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

### Option B — Linux / macOS (Bash)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,tesseract]"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Health Verification
Open your browser or run:
```powershell
curl http://127.0.0.1:8000/health/live
```
**Expected Response:**
```json
{"status":"alive"}
```

And readiness check:
```powershell
curl http://127.0.0.1:8000/health/ready
```
**Expected Response:**
```json
{"status":"ready","ocr_engine":"rapidocr_onnxruntime"}
```

---

## 4. Detailed Frontend Setup & Run Guide

1. Open a new terminal and navigate to the frontend directory:
   ```powershell
   cd c:\Users\varsh\Downloads\passportiq-v2\frontend
   ```

2. *(First-time only)* Install dependencies:
   ```powershell
   npm install
   ```

3. Start the Vite development server:
   ```powershell
   npm run dev
   ```

4. Open your browser and navigate to:
   ```text
   http://localhost:5173/
   ```

> **Note on API Proxying**: Vite is pre-configured in `vite.config.ts` to automatically proxy all requests from `/api` and `/health` to `http://127.0.0.1:8000`. You do not need to configure CORS or custom URLs.

---

## 5. End-to-End Extraction Verification

To test live document scanning:

1. Open `http://localhost:5173/` in your browser.
2. Drag and drop any test image from the repository fixtures:
   - `backend\tests\fixtures\sample_passport.jpg`
   - `backend\eval_data\female_2.jpg`
3. Extraction executes in ~1 second.
4. Verify the **2-column workspace layout**:
   - **Left Panel**: High-resolution document photo, zoom controls (+, -, reset), and live contrast / B&W filter pills.
   - **Right Panel**: Extracted passport details (Surname, Given Names, Passport Number, Nationality, DOB, Expiry, Sex, Place of Birth), MRZ code box, and Modulo-10 checksum validation table.
5. Click **"Copy"** next to any field or **"Copy Extracted Details"** at the top to test clipboard functionality.
6. Click **"Scan Another Document"** to return to the upload screen.

---

## 6. Running Tests & Quality Gates

### Backend Automated Test Suite (102 Tests)
Run from `backend` directory:
```powershell
cd c:\Users\varsh\Downloads\passportiq-v2\backend
.\.venv\Scripts\python.exe -m pytest tests -v
```

To run only the accuracy and performance benchmark:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_accuracy_benchmark.py -v -s
```

### Frontend Automated Test Suite (14 Tests)
Run from `frontend` directory:
```powershell
cd c:\Users\varsh\Downloads\passportiq-v2\frontend
npx vitest run
```

### Frontend Typechecking & Linting
```powershell
cd c:\Users\varsh\Downloads\passportiq-v2\frontend

# Strict TypeScript type check (0 errors expected)
npm run typecheck

# Fast linter (0 warnings expected)
npm run lint

# Production bundle build
npm run build
```

---

## 7. Troubleshooting Guide

### Issue 1: Port 8000 or 5173 Already in Use
If uvicorn or vite fails because the port is occupied:

**Windows PowerShell:**
```powershell
# Check which process is using port 8000 or 5173:
Get-NetTCPConnection -LocalPort 8000, 5173 -ErrorAction SilentlyContinue | Select-Object OwningProcess, LocalPort

# Kill process by PID (e.g., PID 1234):
Stop-Process -Id 1234 -Force
```

### Issue 2: PowerShell Script Execution Policy Restriction
If you see `Activate.ps1 cannot be loaded because running scripts is disabled on this system`:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```
*Or execute python directly without activating:*
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Issue 3: Frontend Cannot Reach Backend (`Failed to fetch` or 502 Bad Gateway)
1. Ensure the backend terminal is running and displays:
   `Application startup complete. Uvicorn running on http://127.0.0.1:8000`
2. Test `curl http://127.0.0.1:8000/health/live` in terminal.
3. Check `frontend/vite.config.ts` has the proxy target pointing to `http://127.0.0.1:8000`.

---

## 8. Summary of Ports & Endpoints

| Service | Address | Description |
| :--- | :--- | :--- |
| **Frontend Web App** | `http://localhost:5173/` | PassPortIQ React UI |
| **Backend REST API** | `http://127.0.0.1:8000/` | FastAPI Root |
| **API Documentation** | `http://127.0.0.1:8000/docs` | Interactive Swagger UI |
| **Live Health Probe** | `http://127.0.0.1:8000/health/live` | Process liveness check |
| **Readiness Health Probe** | `http://127.0.0.1:8000/health/ready` | OCR engine readiness check |
| **Extraction Endpoint** | `POST /api/passports/extract` | Multipart image extraction |
