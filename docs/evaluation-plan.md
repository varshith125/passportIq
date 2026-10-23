# PassPortIQ v2 — Accuracy and Performance Evaluation Plan

## 1. Evaluation Principles

PassPortIQ separates **synthetic benchmark evaluation** (deterministic parser, check-digit, VIZ, and image perturbation tests) from **real-world evaluation** (authorized, access-controlled physical document captures). Synthetic metrics validate algorithmic correctness and regression safety; they do not substitute for multi-country physical optical benchmarks.

## 2. Tracked Evaluation Metrics

1. **MRZ Detection Rate (%)**: Proportion of documents containing a valid MRZ where the detector locates the correct format (`TD1`, `TD2`, or `TD3`) and line boundaries.
2. **MRZ Character Error Rate (CER, %)**: Edit distance (`Levenshtein distance / total MRZ characters`) between normalized MRZ output and ground-truth MRZ strings.
3. **Check-Digit Validation Accuracy (%)**:
   * **True Positive Rate**: Valid MRZ fixtures where all check digits pass (`all_check_digits_valid == True`).
   * **True Negative (Tamper/Noise Detection) Rate**: Corrupted MRZ fixtures where failed check digits are accurately flagged (`all_check_digits_valid == False`).
4. **Field-Level Extraction Accuracy (%)**: Exact match rate per canonical field (`passport_number`, `surname`, `given_names`, `date_of_birth`, `date_of_expiry`, `nationality`, `issuing_country`, `sex`) against ground truth.
5. **VIZ Extraction Accuracy (%)**: Exact match rate on visible-zone fields (`date_of_issue`, `place_of_birth`, and overlapping VIZ labels).
6. **Incorrect Extraction (Hallucination / False Accept) Rate (%)**: Proportion of missing, unreadable, or corrupted fields where the extractor outputs an incorrect non-null value instead of `null` / `unverified` / `invalid_check_digit`. Target is `< 0.5%` on check-digit-protected fields.
7. **Processing Latency (`p50`, `p95`, `max` in ms)**: End-to-end pipeline execution time across image decoding, preprocessing, OCR, MRZ/VIZ parsing, and reconciliation.
8. **Failure Rate Across Image Conditions (%)**: Rejection or partial-extraction rates under controlled image conditions (clean scan, 90° EXIF rotation, 3.5° skew, low contrast, Gaussian noise, oversized 4K resolution).

## 3. Repeatable Benchmark Harness (`backend/tests/evaluate_benchmark.py`)

A self-contained evaluation script is included at `backend/tests/evaluate_benchmark.py`. Run it at any time with:

```bash
cd passportiq-v2/backend
python3 -m tests.evaluate_benchmark
```

### Latest Measured Synthetic Benchmark Results (In-Environment Execution)

The benchmark evaluates:
* **30 synthetic MRZ fixtures** across `TD3` (10), `TD2` (5), `TD1` (5), OCR character-confusion fixtures (5), and corrupted check-digit fixtures (5).
* **6 image condition pipelines** (clean high-res, EXIF-rotated, low-contrast, skewed, oversized 3200×2200, and corrupted/unreadable).
* **Live OCR fallback benchmark** using rendered synthetic passport imagery.

See the verification section in `README.md` or run `python3 -m tests.evaluate_benchmark` for exact console output.

## 4. Protocol for Real-World Authorized Document Evaluation

When evaluating on physical or sample specimen passports (such as public PRADO / ICAO specimen images):
1. Store specimen images outside the git repository in an encrypted, access-controlled directory with a JSON ground-truth manifest (`manifest.json`).
2. Never commit specimen or personal images to version control (`.gitignore` blocks `*.passport.*`, `uploads/`, and `tmp/`).
3. Record results separately by document format (`TD3`, `TD2`, `TD1`), lighting condition (flatbed scan vs. mobile camera glare), and active OCR engine (`rapidocr_onnxruntime` vs. `tesseract_fallback`).
