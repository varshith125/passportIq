"""RapidOCR + ONNX Runtime primary OCR engine with explicit opt-in Tesseract fallback."""

from __future__ import annotations

import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, List, Optional, Tuple

import numpy as np

from app.core.config import Settings, get_settings
from app.core.errors import OcrEngineUnavailableError, OcrProcessingTimeoutError
from app.ocr.base import OcrEngineResult, OcrTextBlock
from app.schemas.health import OcrDependencyStatus

# Prevent OpenMP thread thrashing in containerized deployments when Tesseract fallback is invoked
os.environ.setdefault("OMP_THREAD_LIMIT", "1")


def _clamp_confidence(value: Any) -> float:
    """Normalize OCR confidence score into [0.0, 1.0]."""
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.0
    if np.isnan(conf):
        return 0.0
    if conf > 1.0 and conf <= 100.0:
        conf = conf / 100.0
    return max(0.0, min(1.0, round(conf, 4)))


def _normalize_bbox(
    raw_box: Any,
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float], Tuple[float, float]]]:
    """Convert raw 4-point polygon or [x, y, w, h] coordinates into a 4-point tuple."""
    try:
        if isinstance(raw_box, (list, tuple, np.ndarray)) and len(raw_box) == 4:
            first = raw_box[0]
            if isinstance(first, (list, tuple, np.ndarray)) and len(first) >= 2:
                pts = tuple((float(pt[0]), float(pt[1])) for pt in raw_box[:4])
                return (pts[0], pts[1], pts[2], pts[3])
    except (TypeError, ValueError, IndexError):
        return None
    return None


def parse_rapidocr_raw_output(raw_result: Any) -> List[OcrTextBlock]:
    """
    Convert RapidOCR raw output `([[bbox, text, score], ...], elapse)` into OcrTextBlock items.

    Safely handles None, empty lists, malformed tuples, and whitespace-only strings.
    """
    if raw_result is None:
        return []

    items = raw_result[0] if isinstance(raw_result, tuple) and len(raw_result) >= 1 else raw_result
    if not items or not isinstance(items, (list, tuple)):
        return []

    blocks: List[OcrTextBlock] = []
    for entry in items:
        if not isinstance(entry, (list, tuple)) or len(entry) < 2:
            continue
        raw_box = entry[0]
        raw_text = entry[1]
        raw_score = entry[2] if len(entry) >= 3 else 0.0

        if not isinstance(raw_text, str):
            continue
        cleaned_text = raw_text.strip()
        if not cleaned_text:
            continue

        bbox = _normalize_bbox(raw_box)
        if bbox is None:
            continue

        confidence = _clamp_confidence(raw_score)
        blocks.append(
            OcrTextBlock(
                text=cleaned_text,
                confidence=confidence,
                bbox=bbox,
            )
        )

    blocks.sort(key=lambda b: (round(b.min_y / 12.0), b.min_x))
    return blocks


class RapidOcrEngineManager:
    """
    Singleton-friendly OCR manager.

    - Uses `rapidocr_onnxruntime.RapidOCR` as the primary engine.
    - Reuses initialized model instances across requests.
    - Supports `tesseract` ONLY when explicitly configured as primary or when
      `ocr_allow_tesseract_fallback=True` is explicitly enabled.
    - Never silently switches engines or hides fallback usage.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._lock = threading.Lock()
        self._rapidocr_instance: Any = None
        self._rapidocr_init_attempted = False
        self._rapidocr_error: Optional[str] = None

    def _ensure_rapidocr_loaded(self) -> Tuple[bool, str]:
        """Attempt lazy singleton initialization of RapidOCR + ONNX Runtime."""
        with self._lock:
            if self._rapidocr_instance is not None:
                return True, "RapidOCR ONNX model initialized and ready."
            if self._rapidocr_init_attempted and self._rapidocr_error is not None:
                return False, self._rapidocr_error

            self._rapidocr_init_attempted = True
            try:
                from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-not-found]

                self._rapidocr_instance = RapidOCR()
                self._rapidocr_error = None
                return True, "RapidOCR ONNX model initialized and ready."
            except ImportError as exc:
                self._rapidocr_error = (
                    f"rapidocr_onnxruntime package is not installed in this environment ({exc})."
                )
                return False, self._rapidocr_error
            except Exception as exc:
                self._rapidocr_error = f"RapidOCR initialization failed: {exc}"
                return False, self._rapidocr_error

    @staticmethod
    def _check_tesseract_available() -> bool:
        """Check whether both the tesseract binary and pytesseract module are available."""
        if shutil.which("tesseract") is None:
            return False
        try:
            import pytesseract  # noqa: F401

            return True
        except ImportError:
            return False

    def get_readiness_status(self, settings: Optional[Settings] = None) -> OcrDependencyStatus:
        """Inspect availability of the primary and optional fallback OCR engines."""
        cfg = settings or self._settings
        rapid_ok, rapid_detail = self._ensure_rapidocr_loaded()
        tess_ok = self._check_tesseract_available()

        primary = cfg.ocr_primary_engine
        fallback_enabled = cfg.ocr_allow_tesseract_fallback

        if primary == "rapidocr":
            primary_available = rapid_ok
            primary_detail = rapid_detail
            if rapid_ok:
                active_engine: Optional[str] = "rapidocr_onnxruntime"
                ready = True
            elif fallback_enabled and tess_ok:
                active_engine = "tesseract_fallback"
                ready = True
            else:
                active_engine = None
                ready = False
        elif primary == "tesseract":
            primary_available = tess_ok
            primary_detail = (
                "Tesseract OCR binary and pytesseract are available."
                if tess_ok
                else "Tesseract OCR binary or pytesseract is unavailable."
            )
            active_engine = "tesseract" if tess_ok else None
            ready = tess_ok
        else:
            primary_available = False
            primary_detail = f"Unsupported primary engine configuration: '{primary}'."
            active_engine = None
            ready = False

        return OcrDependencyStatus(
            primary_engine=primary,
            primary_available=primary_available,
            primary_status_detail=primary_detail,
            tesseract_fallback_enabled=fallback_enabled,
            tesseract_available=tess_ok,
            active_engine=active_engine,
            ready=ready,
        )

    def _run_rapidocr(self, rgb_image: np.ndarray) -> List[OcrTextBlock]:
        raw_output = self._rapidocr_instance(rgb_image)
        return parse_rapidocr_raw_output(raw_output)

    @staticmethod
    def _run_tesseract(rgb_image: np.ndarray) -> List[OcrTextBlock]:
        """Run pytesseract line-level extraction and convert to OcrTextBlock objects."""
        import pytesseract
        from PIL import Image

        os.environ.setdefault("OMP_THREAD_LIMIT", "1")
        pil_img = Image.fromarray(rgb_image)
        data = pytesseract.image_to_data(
            pil_img,
            output_type=pytesseract.Output.DICT,
            config="--oem 3 --psm 6",
        )
        pil_img.close()

        n_boxes = len(data.get("text", []))
        line_groups: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
        for i in range(n_boxes):
            word = str(data["text"][i]).strip()
            if not word:
                continue
            conf_raw = data["conf"][i]
            try:
                conf_val = float(conf_raw)
            except (TypeError, ValueError):
                conf_val = -1.0
            if conf_val < 0:
                continue

            key = (
                int(data["block_num"][i]),
                int(data["par_num"][i]),
                int(data["line_num"][i]),
            )
            left = float(data["left"][i])
            top = float(data["top"][i])
            width = float(data["width"][i])
            height = float(data["height"][i])
            line_groups.setdefault(key, []).append(
                {
                    "text": word,
                    "conf": _clamp_confidence(conf_val),
                    "x1": left,
                    "y1": top,
                    "x2": left + width,
                    "y2": top + height,
                }
            )

        blocks: List[OcrTextBlock] = []
        for tokens in line_groups.values():
            line_text = " ".join(t["text"] for t in tokens).strip()
            if not line_text:
                continue
            min_x = min(t["x1"] for t in tokens)
            min_y = min(t["y1"] for t in tokens)
            max_x = max(t["x2"] for t in tokens)
            max_y = max(t["y2"] for t in tokens)
            mean_conf = float(np.mean([t["conf"] for t in tokens]))
            bbox = (
                (min_x, min_y),
                (max_x, min_y),
                (max_x, max_y),
                (min_x, max_y),
            )
            blocks.append(
                OcrTextBlock(
                    text=line_text,
                    confidence=round(mean_conf, 4),
                    bbox=bbox,
                )
            )

        blocks.sort(key=lambda b: (round(b.min_y / 12.0), b.min_x))
        return blocks

    def extract_text_blocks(
        self,
        rgb_image: np.ndarray,
        gray_image: Optional[np.ndarray] = None,
        settings: Optional[Settings] = None,
    ) -> OcrEngineResult:
        """
        Execute OCR within configured timeout limits and return structured OcrEngineResult.
        """
        cfg = settings or self._settings
        status = self.get_readiness_status(cfg)

        if not status.ready or status.active_engine is None:
            raise OcrEngineUnavailableError(
                message=(
                    f"Configured primary OCR engine '{cfg.ocr_primary_engine}' is unavailable "
                    f"({status.primary_status_detail}) and fallback is disabled."
                ),
                details={
                    "requested_engine": cfg.ocr_primary_engine,
                    "tesseract_fallback_enabled": cfg.ocr_allow_tesseract_fallback,
                    "tesseract_available": status.tesseract_available,
                },
            )

        fallback_used = status.active_engine == "tesseract_fallback"
        fallback_reason = status.primary_status_detail if fallback_used else None

        start_time = time.perf_counter()
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            if status.active_engine == "rapidocr_onnxruntime":
                future = executor.submit(self._run_rapidocr, rgb_image)
            else:
                future = executor.submit(self._run_tesseract, rgb_image)

            blocks = future.result(timeout=cfg.ocr_timeout_seconds)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise OcrProcessingTimeoutError(
                message=(
                    f"OCR engine '{status.active_engine}' exceeded timeout of "
                    f"{cfg.ocr_timeout_seconds:.1f}s."
                )
            ) from exc
        except OcrEngineUnavailableError:
            raise
        except Exception as exc:
            raise OcrEngineUnavailableError(
                message=f"OCR execution failed in engine '{status.active_engine}': {exc}",
                details={"active_engine": status.active_engine},
            ) from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return OcrEngineResult(
            requested_engine=cfg.ocr_primary_engine,
            active_engine=status.active_engine,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            blocks=blocks,
            duration_ms=duration_ms,
        )


_default_ocr_manager: Optional[RapidOcrEngineManager] = None
_manager_lock = threading.Lock()


def get_ocr_manager() -> RapidOcrEngineManager:
    """Return process-wide singleton RapidOcrEngineManager."""
    global _default_ocr_manager
    with _manager_lock:
        if _default_ocr_manager is None:
            _default_ocr_manager = RapidOcrEngineManager()
        return _default_ocr_manager
