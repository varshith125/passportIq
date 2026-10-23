"""Spatial and lexical candidate detection for TD1, TD2, and TD3 MRZ lines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.ocr.base import OcrTextBlock
from app.schemas.extraction import MrzFormat

_CHEVRON_TRANSLATION = str.maketrans(
    {
        "«": "<",
        "»": "<",
        "‹": "<",
        "›": "<",
        "＜": "<",
        "＞": "<",
        "[": "<",
        "]": "<",
        "{": "<",
        "}": "<",
        "(": "<",
        ")": "<",
    }
)

_ALLOWED_MRZ_CHARS = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<")


@dataclass(frozen=True)
class MrzCandidate:
    """Detected MRZ candidate lines with provenance and bounded recovery metadata."""

    mrz_format: Optional[MrzFormat]
    raw_lines: List[str]
    normalized_lines: List[str]
    ocr_confidence: float
    recovery_applied: bool = False
    recovery_notes: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    is_partial: bool = False
    partial_reason: Optional[str] = None
    failure_classification: Optional[str] = None


def _normalize_raw_mrz_line(raw: str) -> Tuple[str, bool, List[str]]:
    """
    Perform bounded, transparent lexical normalization on a potential MRZ line.
    """
    notes: List[str] = []
    recovery = False

    trimmed = raw.strip()
    if " " in trimmed or "\t" in trimmed:
        no_space = "".join(trimmed.split())
        recovery = True
        notes.append("Removed internal whitespace from OCR MRZ line.")
    else:
        no_space = trimmed

    upper = no_space.upper()
    if upper != no_space:
        recovery = True
        notes.append("Normalized lowercase characters in MRZ candidate to uppercase.")

    translated = upper.translate(_CHEVRON_TRANSLATION)
    if translated != upper:
        recovery = True
        notes.append("Normalized OCR chevron symbols to standard '<' filler.")

    return translated, recovery, notes


def _is_likely_mrz_line(text: str) -> bool:
    """Determine if a text line exhibits strong MRZ structural signals."""
    raw_upper = text.strip().upper()
    compact = "".join(raw_upper.split()).translate(_CHEVRON_TRANSLATION)

    # Every valid or partial ICAO MRZ line contains at least one '<' chevron
    if "<" not in compact:
        return False

    # Real MRZ lines never contain slashes or backslashes
    if "/" in compact or "\\" in compact:
        return False

    # Reject text containing punctuation typical of VIZ labels/dates
    if any(ch in compact for ch in (":", ";", "?", "!")):
        return False

    _VIZ_DISALLOWED_PREFIXES = (
        "DATE", "SURNAME", "GIVEN", "PASSPORT", "PLACE", "NATIONALITY",
        "AUTHORITY", "ISSUED", "EXPIRY", "DELIVRANCE", "NAISSANCE",
        "GENDER", "SEXE", "PAGE", "PROROGATION", "NOTES", "EXPLANATORY",
        "AUTORITE", "PRENOMS",
    )
    if any(compact.startswith(prefix) for prefix in _VIZ_DISALLOWED_PREFIXES):
        return False
    if any(word in compact for word in ("ISSUEDAT", "FAITA", "FAITD", "DELIVRANCE", "NAISSANCE")):
        return False

    if len(compact) < 12 or len(compact) > 52:
        return False

    # Standard passport line 1 starts with P< or P[A-Z]
    if compact.startswith("P<") or (len(compact) >= 3 and compact[0] == "P" and compact[1].isalpha() and "<" in compact):
        return True

    # Travel document / ID line 1 starts with I<, ID, A<, C<, V<
    if any(compact.startswith(pre) for pre in ("I<", "ID", "A<", "C<", "V<")):
        return True

    # High chevron density indicates MRZ filler
    if compact.count("<") >= 2 and len(compact) >= 15:
        valid_count = sum(1 for c in compact if c in _ALLOWED_MRZ_CHARS)
        if valid_count / float(len(compact)) >= 0.85:
            return True

    # Line 2 typically has high alphanumeric density, multiple digits, and chevrons
    if len(compact) >= 20 and sum(1 for c in compact if c.isdigit()) >= 5 and "<" in compact:
        valid_count = sum(1 for c in compact if c in _ALLOWED_MRZ_CHARS)
        if valid_count / float(len(compact)) >= 0.85:
            return True

    return False


def _adjust_single_filler_boundary(
    line: str,
    target_len: int,
    line_index: int,
) -> Tuple[str, bool, Optional[str]]:
    """
    Pad missing trailing '<' filler up to target_len on name lines or bounded Line 2 filler.
    """
    if len(line) == target_len:
        return line, False, None

    # Line 1 (Name line in TD3/TD2): trailing characters are exclusively '<' filler
    if line_index == 0 and len(line) < target_len and ("<" in line or line.startswith("P")):
        diff = target_len - len(line)
        if diff <= 35:
            padded = line.ljust(target_len, "<")
            return (
                padded,
                True,
                f"Line 1: Appended {diff} missing trailing '<' filler characters ({len(line)}->{target_len}).",
            )

    # For other lines (with check digits): strictly bounded 1-character boundary recovery only
    if len(line) == target_len + 1 and line.endswith("<<"):
        return (
            line[:target_len],
            True,
            f"Line {line_index + 1}: Trimmed 1 redundant trailing '<' filler ({len(line)}->{target_len}).",
        )

    if len(line) == target_len - 1 and line.endswith("<"):
        return (
            line + "<",
            True,
            f"Line {line_index + 1}: Appended 1 missing trailing '<' filler ({len(line)}->{target_len}).",
        )

    return line, False, None


def _cluster_horizontal_sublines(
    raw_sublines: List[Tuple[str, float, float, float, float]],
) -> List[Tuple[str, float, float]]:
    """
    Cluster sublines by vertical proximity (Y) and concatenate left-to-right (X)
    to reassemble horizontally segmented MRZ lines.
    """
    if not raw_sublines:
        return []

    sorted_by_y = sorted(raw_sublines, key=lambda item: item[2])
    clusters: List[List[Tuple[str, float, float, float, float]]] = []
    for item in sorted_by_y:
        _, _, y_mid, _, _ = item
        placed = False
        for c in clusters:
            c_y = sum(x[2] for x in c) / len(c)
            if abs(y_mid - c_y) <= 22.0:
                c.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])

    merged_lines: List[Tuple[str, float, float]] = []
    for c in clusters:
        c.sort(key=lambda x: x[3])
        is_mrz = any(
            "<" in x[0].translate(_CHEVRON_TRANSLATION)
            for x in c
        )
        sep = "" if is_mrz else " "
        combined_text = sep.join(x[0] for x in c).strip()
        mean_conf = sum(x[1] for x in c) / float(len(c))
        mean_y = sum(x[2] for x in c) / float(len(c))
        merged_lines.append((combined_text, mean_conf, mean_y))

    for item in raw_sublines:
        text, conf, y_mid, _, _ = item
        if _is_likely_mrz_line(text):
            merged_lines.append((text, conf, y_mid))

    unique: List[Tuple[str, float, float]] = []
    seen = set()
    for txt, conf, y in sorted(merged_lines, key=lambda x: x[2]):
        compact = "".join(txt.split())
        if compact not in seen:
            seen.add(compact)
            unique.append((txt, conf, y))

    return unique


def detect_mrz_candidate(blocks: List[OcrTextBlock]) -> Optional[MrzCandidate]:
    """
    Inspect OCR blocks (sorted top-to-bottom) and detect TD3 (2x44), TD2 (2x36), or TD1 (3x30) candidates.
    """
    if not blocks:
        return None

    # Collect all sublines with spatial bounds
    raw_sublines: List[Tuple[str, float, float, float, float]] = []
    for block in blocks:
        sublines = [s.strip() for s in block.text.splitlines() if s.strip()]
        line_count = max(1, len(sublines))
        line_h = block.height / float(line_count)
        for idx, sub in enumerate(sublines):
            y_mid = block.min_y + (idx + 0.5) * line_h
            raw_sublines.append((sub, block.confidence, y_mid, block.min_x, block.max_x))

    expanded_lines = _cluster_horizontal_sublines(raw_sublines)

    candidate_entries: List[Tuple[str, str, float, bool, List[str]]] = []
    for raw_text, conf, _ in expanded_lines:
        if _is_likely_mrz_line(raw_text):
            norm_text, rec, notes = _normalize_raw_mrz_line(raw_text)
            candidate_entries.append((raw_text, norm_text, conf, rec, notes))

    if not candidate_entries:
        return None

    # 1. Search for dedicated TD3 Passport anchor:
    # A line starting with 'P<' or 'P[A-Z]' followed by candidate Line 2 with digits
    for i in range(len(candidate_entries) - 1):
        for j in range(i + 1, min(i + 3, len(candidate_entries))):
            l1_norm = candidate_entries[i][1]
            l2_norm = candidate_entries[j][1]
            if (l1_norm.startswith("P<") or (len(l1_norm) >= 2 and l1_norm[0] == "P" and l1_norm[1].isalpha() and "<" in l1_norm)):
                if (any(c.isdigit() for c in l2_norm) or l2_norm.count("<") >= 2) and len(l2_norm) >= 15:
                    pair = [candidate_entries[i], candidate_entries[j]]
                    return _build_candidate_for_format(pair, MrzFormat.TD3, target_len=44)

    # 2. Check 3-line TD1 window if 3 lines near 30 chars exist
    if len(candidate_entries) >= 3:
        for i in range(len(candidate_entries) - 2):
            triplet = candidate_entries[i : i + 3]
            lengths = [len(item[1]) for item in triplet]
            if all(24 <= length <= 36 for length in lengths):
                return _build_candidate_for_format(triplet, MrzFormat.TD1, target_len=30)

    # 3. Check 2-line TD3 (44 chars) or TD2 (36 chars)
    if len(candidate_entries) >= 2:
        for i in range(len(candidate_entries) - 1):
            pair = [candidate_entries[i], candidate_entries[i + 1]]
            l1_len = len(pair[0][1])
            l2_len = len(pair[1][1])
            avg_len = (l1_len + l2_len) / 2.0
            is_passport_prefix = pair[0][1].startswith("P")
            if (is_passport_prefix or l2_len >= 40 or avg_len >= 40.0) and (l1_len >= 24 and l2_len >= 24):
                return _build_candidate_for_format(pair, MrzFormat.TD3, target_len=44)
            if 32.0 <= avg_len < 40.0 and (28 <= l1_len <= 40 and 28 <= l2_len <= 40):
                return _build_candidate_for_format(pair, MrzFormat.TD2, target_len=36)

        last_two = candidate_entries[-2:]
        line1_len = len(last_two[0][1])
        line2_len = len(last_two[1][1])
        avg_len = (line1_len + line2_len) / 2.0

        is_passport_prefix = last_two[0][1].startswith("P")
        if (is_passport_prefix or line2_len >= 40 or avg_len >= 40.0) and (line1_len >= 24 and line2_len >= 24):
            return _build_candidate_for_format(last_two, MrzFormat.TD3, target_len=44)
        if 32.0 <= avg_len < 40.0:
            return _build_candidate_for_format(last_two, MrzFormat.TD2, target_len=36)
        if 24.0 <= avg_len < 32.0:
            return _build_candidate_for_format(
                last_two,
                MrzFormat.TD1,
                target_len=30,
                extra_errors=["Incomplete TD1 MRZ candidate: detected 2 lines instead of required 3 lines."],
                is_partial=True,
                partial_reason="td1_detected_2_of_3_lines",
                failure_classification="incomplete_image_crop",
            )
        return _build_candidate_for_format(
            last_two,
            None,
            target_len=0,
            extra_errors=[
                f"Ambiguous MRZ line lengths ({[len(x[1]) for x in last_two]}); does not match TD3 (44), TD2 (36), or TD1 (30)."
            ],
            is_partial=True,
            partial_reason="ambiguous_line_lengths",
            failure_classification="invalid_mrz",
        )

    # Single MRZ-like line detected -> incomplete MRZ
    single = candidate_entries[-1:]
    first_norm = single[0][1]
    is_line1 = first_norm.startswith("P<") or (len(first_norm) >= 3 and first_norm[0] == "P" and "<" in first_norm)
    is_line2 = any(c.isdigit() for c in first_norm) and sum(1 for c in first_norm if c.isdigit()) >= 5

    extra_errors = [
        f"Incomplete MRZ candidate: only 1 MRZ-like line detected (length {len(first_norm)})."
    ]
    if is_line1:
        partial_reason = "line_1_only_detected"
        extra_errors.append(
            "Incomplete TD3 MRZ candidate: Line 1 was detected, but Line 2 is blurred, damaged, or obscured."
        )
    elif is_line2:
        partial_reason = "line_2_only_detected"
        extra_errors.append(
            "Incomplete MRZ candidate: Line 2 was detected with document and date tokens, but Line 1 is obscured."
        )
    else:
        partial_reason = "single_line_detected"

    return _build_candidate_for_format(
        single,
        None,
        target_len=0,
        extra_errors=extra_errors,
        is_partial=True,
        partial_reason=partial_reason,
        failure_classification="incomplete_image_crop" if len(first_norm) < 36 else "ocr_failure",
    )


def _build_candidate_for_format(
    entries: List[Tuple[str, str, float, bool, List[str]]],
    mrz_format: Optional[MrzFormat],
    target_len: int,
    extra_errors: Optional[List[str]] = None,
    is_partial: bool = False,
    partial_reason: Optional[str] = None,
    failure_classification: Optional[str] = None,
) -> MrzCandidate:
    raw_lines = [e[0] for e in entries]
    norm_lines: List[str] = []
    recovery_applied = any(e[3] for e in entries)
    recovery_notes: List[str] = []
    for idx, e in enumerate(entries):
        for note in e[4]:
            recovery_notes.append(f"Line {idx + 1}: {note}")
        if target_len > 0:
            adj_line, adj_rec, adj_note = _adjust_single_filler_boundary(e[1], target_len, idx)
            norm_lines.append(adj_line)
            if adj_rec and adj_note:
                recovery_applied = True
                recovery_notes.append(adj_note)
        else:
            norm_lines.append(e[1])

    mean_conf = round(sum(e[2] for e in entries) / float(len(entries)), 4)
    return MrzCandidate(
        mrz_format=mrz_format,
        raw_lines=raw_lines,
        normalized_lines=norm_lines,
        ocr_confidence=mean_conf,
        recovery_applied=recovery_applied,
        recovery_notes=recovery_notes,
        errors=list(extra_errors or []),
        is_partial=is_partial,
        partial_reason=partial_reason,
        failure_classification=failure_classification,
    )
