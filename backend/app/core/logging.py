"""Privacy-preserving logging utilities that prevent leaking PII or MRZ data."""

from __future__ import annotations

import logging
import re

# Patterns that look like MRZ lines (long sequences with angle brackets) or passport data
_MRZ_PATTERN = re.compile(r"[A-Z0-9<]{15,44}")
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(passport_number|surname|given_names|full_name|date_of_birth|mrz_text|raw_ocr)\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)


def redact_sensitive_text(text: str) -> str:
    """Redact potential MRZ strings or explicitly labeled PII fields from log messages."""
    redacted = _SENSITIVE_KEY_PATTERN.sub(r"\1=[REDACTED]", text)
    # Redact sequences containing at least two filler brackets '<' inside an MRZ-like token
    def _replace_mrz(match: re.Match[str]) -> str:
        token = match.group(0)
        if "<<" in token or token.count("<") >= 3:
            return "[REDACTED_MRZ]"
        return token

    return _MRZ_PATTERN.sub(_replace_mrz, redacted)


class SensitiveDataRedactionFilter(logging.Filter):
    """Logging filter that strips MRZ strings and labeled PII from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    redact_sensitive_text(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (redact_sensitive_text(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
        return True


def get_privacy_logger(name: str = "passportiq") -> logging.Logger:
    """Return a logger configured with the privacy redaction filter."""
    logger = logging.getLogger(name)
    if not any(isinstance(f, SensitiveDataRedactionFilter) for f in logger.filters):
        logger.addFilter(SensitiveDataRedactionFilter())
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.addFilter(SensitiveDataRedactionFilter())
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
