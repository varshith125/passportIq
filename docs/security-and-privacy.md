# PassPortIQ v2 — Security and Privacy Architecture

## 1. Threat Model & Upload Security Controls

PassPortIQ handles high-sensitivity identity documents. Every image upload is treated as untrusted binary input and passes through defense-in-depth checks in `backend/app/services/image_security.py` before any OCR or computer-vision processing occurs:

| Control | Implementation | Default Limit / Policy | Error Code & HTTP Status |
| :--- | :--- | :--- | :--- |
| **Stream Size Enforcement** | Chunked 64 KB reader in `app/api/passports.py` aborts before full buffer allocation if limit is exceeded | `10,485,760` bytes (10 MB) | `PAYLOAD_TOO_LARGE` (`413`) |
| **Empty File Rejection** | Immediate check on byte length | `> 0` bytes | `EMPTY_PAYLOAD` (`400`) |
| **Magic-Byte Signature Inspection** | Raw header inspection (`\xff\xd8\xff`, `\x89PNG\r\n\x1a\n`, `RIFF....WEBP`, `II*\x00` / `MM\x00*`); client filenames and MIME headers are never trusted | JPEG, PNG, WEBP, TIFF only | `INVALID_FILE_SIGNATURE` (`415`) |
| **Header vs. Magic Cross-Check** | Pillow `Image.open` format must match magic-byte format prior to pixel decoding | Strict equality | `UNSUPPORTED_MEDIA_TYPE` (`415`) |
| **Decompression Bomb Protection** | Sets `Image.MAX_IMAGE_PIXELS` and inspects `width * height` from image headers before `.load()` | `20,000,000` pixels (20 MP) | `IMAGE_PIXEL_LIMIT_EXCEEDED` / `DECOMPRESSION_BOMB_DETECTED` (`413`) |
| **Dimension Bounds** | Rejects tiny unreadable thumbnails and extreme aspect ratios | `300×200` min to `6000×6000` max | `IMAGE_DIMENSIONS_OUT_OF_RANGE` (`400` / `413`) |
| **Integrity Verification** | Runs `header_img.verify()` followed by guarded pixel decoding | Rejects truncated/corrupt streams | `CORRUPT_IMAGE_DATA` (`400`) |
| **OCR Execution Timeout** | Bounded `ThreadPoolExecutor` timeout per request | `30.0` seconds | `OCR_PROCESSING_TIMEOUT` (`504`) |
| **Narrow CORS Policy** | `CORSMiddleware` restricted to configured origins and `GET, POST, OPTIONS` | `http://localhost:5173,http://127.0.0.1:5173` | Browser CORS enforcement |

## 2. Transient Data Handling & Zero Persistence

* **No Disk or Database Storage**: Uploaded passport bytes are read into an in-memory `bytearray`, immediately cleared after decoding into a NumPy RGB array, and garbage-collected once the HTTP response is returned.
* **No Temporary Files**: Image decoding, EXIF orientation correction, OpenCV preprocessing, and RapidOCR inference operate entirely on in-memory buffers.

## 3. Privacy-Preserving Logging

* `backend/app/core/logging.py` attaches `SensitiveDataRedactionFilter` to all application loggers.
* Operational logs record only non-sensitive metadata: request status, document classification enum, active OCR engine name, number of detected text blocks, and processing duration in milliseconds.
* Any accidental inclusion of labeled PII fields (`passport_number`, `surname`, `given_names`, `full_name`, `date_of_birth`, `mrz_text`) or MRZ-like angle-bracket sequences (`<<`) is automatically scrubbed to `[REDACTED]` or `[REDACTED_MRZ]`.
* Unhandled exceptions return a generic `INTERNAL_SERVER_ERROR` (`500`) envelope without stack traces or internal file paths.

## 4. Document Authenticity Disclaimer

PassPortIQ validates ICAO 9303 Modulo-10 check digits and reconciles visible text against the MRZ. Valid check digits confirm only mathematical character consistency and **do not** verify physical security features, UV/IR patterns, or ICAO PKD cryptographic chip signatures (BAC/PACE/Passive Authentication).
