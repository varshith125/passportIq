"""ICAO Doc 9303 Modulo-10 check-digit calculation and verification."""

from __future__ import annotations

from app.schemas.extraction import CheckDigitResult

_WEIGHTS = (7, 3, 1)
_VALID_MRZ_CHARS = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<")


def char_to_mrz_value(ch: str) -> int:
    """
    Convert a single MRZ character to its ICAO 9303 numeric value.

    - '0'-'9' -> 0-9
    - 'A'-'Z' -> 10-35
    - '<'     -> 0
    Raises ValueError for invalid characters.
    """
    if len(ch) != 1 or ch not in _VALID_MRZ_CHARS:
        raise ValueError(f"Invalid MRZ character for check-digit calculation: {ch!r}")
    if ch == "<":
        return 0
    if "0" <= ch <= "9":
        return ord(ch) - ord("0")
    return ord(ch) - ord("A") + 10


def compute_icao_check_digit(data_segment: str) -> str:
    """Compute the ICAO 9303 Modulo-10 check digit (weights 7, 3, 1) for a data segment."""
    total = 0
    for idx, ch in enumerate(data_segment):
        value = char_to_mrz_value(ch)
        weight = _WEIGHTS[idx % 3]
        total += value * weight
    return str(total % 10)


def verify_check_digit(
    field_name: str,
    data_segment: str,
    actual_digit: str,
    position_description: str,
    allow_empty_filler_check: bool = False,
) -> CheckDigitResult:
    """
    Validate an MRZ check digit against its corresponding data segment.

    For optional/personal number fields that are completely filled with '<', ICAO 9303 permits
    either '0' or '<' in the check digit position when `allow_empty_filler_check=True`.
    """
    try:
        expected = compute_icao_check_digit(data_segment)
    except ValueError:
        return CheckDigitResult(
            field_name=field_name,
            data_segment=data_segment,
            expected_digit="?",
            actual_digit=actual_digit,
            is_valid=False,
            position_description=position_description,
        )

    if allow_empty_filler_check and all(c == "<" for c in data_segment) and actual_digit in {"<", "0"}:
        return CheckDigitResult(
            field_name=field_name,
            data_segment=data_segment,
            expected_digit=expected,
            actual_digit=actual_digit,
            is_valid=True,
            position_description=position_description,
        )

    return CheckDigitResult(
        field_name=field_name,
        data_segment=data_segment,
        expected_digit=expected,
        actual_digit=actual_digit,
        is_valid=(actual_digit == expected),
        position_description=position_description,
    )
