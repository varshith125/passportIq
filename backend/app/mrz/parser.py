"""Parser and validator for ICAO 9303 TD1, TD2, and TD3 Machine Readable Zones."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple

from app.mrz.check_digits import verify_check_digit
from app.mrz.detector import MrzCandidate, detect_mrz_candidate
from app.ocr.base import OcrTextBlock
from app.schemas.extraction import CheckDigitResult, MrzFormat, MrzParseResult

_VALID_MRZ_CHARS = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<")

# Strictly bounded character confusion maps used ONLY in single-type positions
_DIGIT_CONFUSION_MAP = {
    "O": "0",
    "Q": "0",
    "D": "0",
    "I": "1",
    "L": "1",
    "Z": "2",
    "S": "5",
    "B": "8",
}

_ALPHA_CONFUSION_MAP = {
    "0": "O",
    "1": "I",
    "2": "Z",
    "5": "S",
    "8": "B",
}


def _recover_numeric_segment(
    segment: str,
    field_label: str,
    recovery_notes: List[str],
) -> Tuple[str, bool]:
    """Recover unambiguous letter-to-digit OCR confusions inside strictly numeric MRZ positions."""
    out: List[str] = []
    changed = False
    for idx, ch in enumerate(segment):
        if ch in _DIGIT_CONFUSION_MAP:
            replacement = _DIGIT_CONFUSION_MAP[ch]
            out.append(replacement)
            changed = True
            recovery_notes.append(
                f"{field_label}[{idx}]: Replaced OCR character '{ch}' with digit '{replacement}'."
            )
        else:
            out.append(ch)
    return "".join(out), changed


def _recover_alpha_segment(
    segment: str,
    field_label: str,
    recovery_notes: List[str],
) -> Tuple[str, bool]:
    """Recover unambiguous digit-to-letter OCR confusions inside strictly alphabetic MRZ positions."""
    out: List[str] = []
    changed = False
    for idx, ch in enumerate(segment):
        if ch in _ALPHA_CONFUSION_MAP:
            replacement = _ALPHA_CONFUSION_MAP[ch]
            out.append(replacement)
            changed = True
            recovery_notes.append(
                f"{field_label}[{idx}]: Replaced OCR digit '{ch}' with letter '{replacement}'."
            )
        else:
            out.append(ch)
    return "".join(out), changed


def parse_mrz_date(yymmdd: str, is_expiry: bool = False) -> Tuple[Optional[str], Optional[str]]:
    """
    Convert an MRZ 6-digit YYMMDD string into ISO YYYY-MM-DD format.

    Never guesses unreadable dates: if any character is non-numeric or the calendar date is
    invalid (e.g., month 13 or Feb 30), returns (None, error_message).
    """
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        return None, "Invalid MRZ date token: must be exactly 6 numeric digits (YYMMDD)."

    yy = int(yymmdd[0:2])
    mm = int(yymmdd[2:4])
    dd = int(yymmdd[4:6])

    current_year = date.today().year
    current_yy = current_year % 100

    if is_expiry:
        # Expiry dates up to 25 years in the future map to 2000+YY; older map to 1900+YY
        year = 2000 + yy if yy <= (current_yy + 25) % 100 or yy <= 60 else 1900 + yy
    else:
        # Birth dates cannot be in the future
        year = 2000 + yy if yy <= current_yy else 1900 + yy

    try:
        parsed = date(year, mm, dd)
        return parsed.isoformat(), None
    except ValueError as exc:
        return None, f"Invalid calendar date in MRZ: {exc}."


def parse_names_field(raw_name_zone: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse ICAO 9303 primary (surname) and secondary (given names) identifiers separated by '<<'.

    Returns (surname, given_names, full_name).
    """
    stripped = raw_name_zone.strip("<")
    if not stripped:
        return None, None, None

    if "<<" in raw_name_zone:
        parts = raw_name_zone.split("<<", 1)
        raw_surname = parts[0]
        raw_given = parts[1]
    else:
        raw_surname = stripped
        raw_given = ""

    def clean_token(tok: str) -> str:
        out = []
        for ch in tok:
            if ch in _ALPHA_CONFUSION_MAP:
                out.append(_ALPHA_CONFUSION_MAP[ch])
            elif ch.isalpha() or ch in " -'":
                out.append(ch)
        return "".join(out).strip()

    surname_toks = [clean_token(tok) for tok in raw_surname.split("<") if clean_token(tok)]
    given_toks = [clean_token(tok) for tok in raw_given.split("<") if clean_token(tok)]

    surname = " ".join(surname_toks).strip() or None
    given_names = " ".join(given_toks).strip() or None

    if surname and given_names:
        full_name: Optional[str] = f"{given_names} {surname}"
    elif surname:
        full_name = surname
    elif given_names:
        full_name = given_names
    else:
        full_name = None

    return surname, given_names, full_name


def _clean_code(raw: str) -> Optional[str]:
    val = raw.replace("<", "").strip()
    return val if val else None


def _parse_sex(ch: str) -> Optional[str]:
    if ch in {"M", "F"}:
        return ch
    if ch in {"<", "X"}:
        return ch
    return None


def parse_mrz_from_blocks(blocks: List[OcrTextBlock]) -> MrzParseResult:
    """Detect and parse MRZ from OCR text blocks."""
    candidate = detect_mrz_candidate(blocks)
    if candidate is None:
        return MrzParseResult(detected=False)
    return parse_mrz_candidate(candidate)


def parse_mrz_lines(raw_lines: List[str], ocr_confidence: float = 1.0) -> MrzParseResult:
    """Directly parse a list of MRZ lines (convenience entry point for synthetic fixtures and tests)."""
    blocks = [
        OcrTextBlock(
            text=line,
            confidence=ocr_confidence,
            bbox=((0.0, float(i * 30)), (500.0, float(i * 30)), (500.0, float(i * 30 + 25)), (0.0, float(i * 30 + 25))),
        )
        for i, line in enumerate(raw_lines)
    ]
    return parse_mrz_from_blocks(blocks)


def _extract_fallback_fields_from_lines(
    lines: List[str],
    recovery_notes: List[str],
) -> Dict[str, Optional[str]]:
    """
    Extract best-effort fields from partial, single-line, or unclassified MRZ lines.
    Never throws away detected names, country codes, or dates just because full format validation failed.
    """
    fields: Dict[str, Optional[str]] = {
        "document_type": None,
        "issuing_country": None,
        "surname": None,
        "given_names": None,
        "full_name": None,
        "passport_number": None,
        "nationality": None,
        "date_of_birth": None,
        "sex": None,
        "date_of_expiry": None,
        "personal_number": None,
    }

    for line in lines:
        cleaned = line.strip().upper()
        if not cleaned:
            continue

        # Check for TD3/TD2 Line 1: Starts with P< or P[A-Z]
        if cleaned.startswith("P<") or (len(cleaned) >= 3 and cleaned[0] == "P" and cleaned[1].isalpha() and "<" in cleaned):
            padded = cleaned.ljust(44, "<")[:44]
            doc_code = padded[0:2].replace("<", "").strip() or "P"
            fields["document_type"] = doc_code

            issuing_raw, _ = _recover_alpha_segment(padded[2:5], "L1.issuing_country", recovery_notes)
            country = _clean_code(issuing_raw)
            if country and country.isalpha():
                fields["issuing_country"] = country
                if not fields["nationality"]:
                    fields["nationality"] = country

            name_zone_raw, _ = _recover_alpha_segment(padded[5:44], "L1.name_zone", recovery_notes)
            surname, given_names, full_name = parse_names_field(name_zone_raw)
            if surname:
                fields["surname"] = surname
            if given_names:
                fields["given_names"] = given_names
            if full_name:
                fields["full_name"] = full_name
            continue

        # Check for general name line with <<
        if "<<" in cleaned and sum(1 for c in cleaned if c.isalpha()) >= 4:
            name_zone_raw, _ = _recover_alpha_segment(cleaned, "fallback.name_zone", recovery_notes)
            surname, given_names, full_name = parse_names_field(name_zone_raw)
            if surname and not fields["surname"]:
                fields["surname"] = surname
            if given_names and not fields["given_names"]:
                fields["given_names"] = given_names
            if full_name and not fields["full_name"]:
                fields["full_name"] = full_name
            continue

        # Check for Line 2 pattern (passport number + DOB + Sex + Expiry)
        if len(cleaned) >= 20 and sum(1 for c in cleaned if c.isdigit()) >= 5:
            padded_l2 = cleaned.ljust(44, "<")[:44]
            doc_num_raw = padded_l2[0:9]
            nat_raw, _ = _recover_alpha_segment(padded_l2[10:13], "L2.nationality", recovery_notes)
            dob_raw, _ = _recover_numeric_segment(padded_l2[13:19], "L2.date_of_birth", recovery_notes)
            sex_raw = padded_l2[20:21]
            exp_raw, _ = _recover_numeric_segment(padded_l2[21:27], "L2.date_of_expiry", recovery_notes)
            pers_raw = padded_l2[28:42]

            doc_clean = _clean_code(doc_num_raw)
            if (
                doc_clean
                and 5 <= len(doc_clean) <= 9
                and not any(doc_clean.startswith(w) for w in ("DATE", "EXPI", "ISSU", "PASS", "NAME"))
            ):
                fields["passport_number"] = doc_clean

            nat_clean = _clean_code(nat_raw)
            if nat_clean and len(nat_clean) == 3 and nat_clean.isalpha():
                fields["nationality"] = nat_clean

            dob_iso, _ = parse_mrz_date(dob_raw, is_expiry=False)
            if dob_iso:
                fields["date_of_birth"] = dob_iso

            sex_val = _parse_sex(sex_raw)
            if sex_val:
                fields["sex"] = sex_val

            exp_iso, _ = parse_mrz_date(exp_raw, is_expiry=True)
            if exp_iso:
                fields["date_of_expiry"] = exp_iso

            pers_clean = _clean_code(pers_raw)
            if pers_clean:
                fields["personal_number"] = pers_clean

    return fields


def parse_mrz_candidate(candidate: MrzCandidate) -> MrzParseResult:
    """Validate structure, check digits, and fields for a detected MrzCandidate."""
    errors = list(candidate.errors)
    recovery_notes = list(candidate.recovery_notes)
    recovery_applied = candidate.recovery_applied
    lines = list(candidate.normalized_lines)
    mrz_format = candidate.mrz_format

    if mrz_format is None:
        parsed_fields = _extract_fallback_fields_from_lines(lines, recovery_notes)
        if any(v is not None for v in parsed_fields.values()):
            recovery_applied = True
        return MrzParseResult(
            detected=True,
            mrz_format=None,
            raw_lines=candidate.raw_lines,
            normalized_lines=lines,
            mrz_text="\n".join(lines),
            all_check_digits_valid=False,
            line_length_valid=False,
            character_set_valid=all(all(c in _ALLOWED_SET for c in ln) for ln in lines),
            recovery_applied=recovery_applied,
            recovery_notes=recovery_notes,
            errors=errors,
            parsed_fields=parsed_fields,
            ocr_confidence=candidate.ocr_confidence,
            is_partial=candidate.is_partial,
            partial_reason=candidate.partial_reason,
            failure_classification=candidate.failure_classification or "invalid_mrz",
        )

    expected_count = 3 if mrz_format == MrzFormat.TD1 else 2
    expected_len = 30 if mrz_format == MrzFormat.TD1 else (36 if mrz_format == MrzFormat.TD2 else 44)

    line_length_valid = len(lines) == expected_count and all(len(ln) == expected_len for ln in lines)
    if not line_length_valid:
        if len(lines) != expected_count:
            errors.append(
                f"Incomplete {mrz_format.value} candidate: detected {len(lines)} line(s) instead of required {expected_count}."
            )
        for idx, ln in enumerate(lines):
            if len(ln) != expected_len:
                errors.append(
                    f"Line {idx + 1} length is {len(ln)} characters; expected {expected_len} for {mrz_format.value}."
                )

    char_set_valid = True
    for idx, ln in enumerate(lines):
        invalid_chars = sorted({c for c in ln if c not in _VALID_MRZ_CHARS})
        if invalid_chars:
            char_set_valid = False
            errors.append(
                f"Line {idx + 1} contains invalid MRZ characters: {', '.join(repr(c) for c in invalid_chars)}."
            )

    if mrz_format == MrzFormat.TD3:
        return _parse_td3(candidate, lines, char_set_valid, recovery_applied, recovery_notes, errors, line_length_valid)
    if mrz_format == MrzFormat.TD2:
        return _parse_td2(candidate, lines, char_set_valid, recovery_applied, recovery_notes, errors, line_length_valid)
    return _parse_td1(candidate, lines, char_set_valid, recovery_applied, recovery_notes, errors, line_length_valid)


_ALLOWED_SET = _VALID_MRZ_CHARS


def _parse_td3(
    candidate: MrzCandidate,
    lines: List[str],
    char_set_valid: bool,
    recovery_applied: bool,
    recovery_notes: List[str],
    errors: List[str],
    line_length_valid: bool = True,
) -> MrzParseResult:
    if len(lines) == 1:
        line1 = lines[0].ljust(44, "<")[:44]
        doc_code = line1[0:2]
        issuing_raw, rec_iss = _recover_alpha_segment(line1[2:5], "L1.issuing_country", recovery_notes)
        name_zone_raw, rec_name = _recover_alpha_segment(line1[5:44], "L1.name_zone", recovery_notes)
        if rec_iss or rec_name:
            recovery_applied = True
            line1 = doc_code + issuing_raw + name_zone_raw

        surname, given_names, full_name = parse_names_field(name_zone_raw)
        issuing_country = _clean_code(issuing_raw)
        if issuing_country and (len(issuing_country) != 3 or not issuing_country.isalpha()):
            errors.append(f"Invalid issuing country code '{issuing_raw}' in TD3 Line 1.")
            issuing_country = None

        parsed_fields: Dict[str, Optional[str]] = {
            "document_type": _clean_code(doc_code) or "P",
            "issuing_country": issuing_country,
            "surname": surname,
            "given_names": given_names,
            "full_name": full_name,
            "passport_number": None,
            "nationality": issuing_country,
            "date_of_birth": None,
            "sex": None,
            "date_of_expiry": None,
            "personal_number": None,
        }

        return MrzParseResult(
            detected=True,
            mrz_format=MrzFormat.TD3,
            raw_lines=candidate.raw_lines,
            normalized_lines=[line1],
            mrz_text=line1,
            check_digits=[],
            all_check_digits_valid=False,
            line_length_valid=False,
            character_set_valid=char_set_valid,
            recovery_applied=recovery_applied,
            recovery_notes=recovery_notes,
            errors=errors,
            parsed_fields=parsed_fields,
            ocr_confidence=candidate.ocr_confidence,
        )

    line1 = lines[0].ljust(44, "<")[:44]
    line2 = lines[1].ljust(44, "<")[:44]

    # Recover unambiguous alpha positions in Line 1 (country + names) and Line 2 nationality
    doc_code = line1[0:2]
    issuing_raw, rec_iss = _recover_alpha_segment(line1[2:5], "L1.issuing_country", recovery_notes)
    name_zone_raw, rec_name = _recover_alpha_segment(line1[5:44], "L1.name_zone", recovery_notes)

    doc_num_raw = line2[0:9]
    doc_num_cd, rec_cd1 = _recover_numeric_segment(line2[9:10], "L2.passport_number_cd", recovery_notes)
    nat_raw, rec_nat = _recover_alpha_segment(line2[10:13], "L2.nationality", recovery_notes)
    dob_raw, rec_dob = _recover_numeric_segment(line2[13:19], "L2.date_of_birth", recovery_notes)
    dob_cd, rec_cd2 = _recover_numeric_segment(line2[19:20], "L2.date_of_birth_cd", recovery_notes)
    sex_raw = line2[20:21]
    exp_raw, rec_exp = _recover_numeric_segment(line2[21:27], "L2.date_of_expiry", recovery_notes)
    exp_cd, rec_cd3 = _recover_numeric_segment(line2[27:28], "L2.date_of_expiry_cd", recovery_notes)
    personal_raw = line2[28:42]
    personal_cd = line2[42:43]
    if personal_cd != "<":
        personal_cd, rec_cd4 = _recover_numeric_segment(personal_cd, "L2.personal_number_cd", recovery_notes)
    else:
        rec_cd4 = False
    comp_cd, rec_cd5 = _recover_numeric_segment(line2[43:44], "L2.composite_cd", recovery_notes)

    if any([rec_iss, rec_name, rec_cd1, rec_nat, rec_dob, rec_cd2, rec_exp, rec_cd3, rec_cd4, rec_cd5]):
        recovery_applied = True
        line1 = doc_code + issuing_raw + name_zone_raw
        line2 = (
            doc_num_raw
            + doc_num_cd
            + nat_raw
            + dob_raw
            + dob_cd
            + sex_raw
            + exp_raw
            + exp_cd
            + personal_raw
            + personal_cd
            + comp_cd
        )

    check_digits: List[CheckDigitResult] = [
        verify_check_digit(
            field_name="passport_number",
            data_segment=doc_num_raw,
            actual_digit=doc_num_cd,
            position_description="TD3 Line 2 [1-9] check digit at [10]",
        ),
        verify_check_digit(
            field_name="date_of_birth",
            data_segment=dob_raw,
            actual_digit=dob_cd,
            position_description="TD3 Line 2 [14-19] check digit at [20]",
        ),
        verify_check_digit(
            field_name="date_of_expiry",
            data_segment=exp_raw,
            actual_digit=exp_cd,
            position_description="TD3 Line 2 [22-27] check digit at [28]",
        ),
        verify_check_digit(
            field_name="personal_number",
            data_segment=personal_raw,
            actual_digit=personal_cd,
            position_description="TD3 Line 2 [29-42] check digit at [43]",
            allow_empty_filler_check=True,
        ),
        verify_check_digit(
            field_name="composite",
            data_segment=line2[0:10] + line2[13:20] + line2[21:43],
            actual_digit=comp_cd,
            position_description="TD3 Line 2 composite check digit at [44]",
        ),
    ]

    for cd in check_digits:
        if not cd.is_valid:
            errors.append(
                f"MRZ check-digit failure on '{cd.field_name}': expected '{cd.expected_digit}', got '{cd.actual_digit}'."
            )

    dob_iso, dob_err = parse_mrz_date(dob_raw, is_expiry=False)
    if dob_err:
        errors.append(dob_err)

    exp_iso, exp_err = parse_mrz_date(exp_raw, is_expiry=True)
    if exp_err:
        errors.append(exp_err)

    surname, given_names, full_name = parse_names_field(name_zone_raw)
    sex_val = _parse_sex(sex_raw)
    if sex_val is None:
        errors.append(f"Invalid sex marker '{sex_raw}' at TD3 Line 2 [21].")

    issuing_country = _clean_code(issuing_raw)
    if issuing_country and (len(issuing_country) != 3 or not issuing_country.isalpha()):
        errors.append(f"Invalid issuing country code '{issuing_raw}' in TD3 Line 1.")
        issuing_country = None

    nationality = _clean_code(nat_raw) or issuing_country
    if nationality and (len(nationality) != 3 or not nationality.isalpha()):
        errors.append(f"Invalid nationality code '{nat_raw}' in TD3 Line 2.")
        nationality = None

    parsed_fields: Dict[str, Optional[str]] = {
        "document_type": _clean_code(doc_code) or "P",
        "issuing_country": issuing_country,
        "surname": surname,
        "given_names": given_names,
        "full_name": full_name,
        "passport_number": _clean_code(doc_num_raw),
        "nationality": nationality,
        "date_of_birth": dob_iso,
        "sex": sex_val,
        "date_of_expiry": exp_iso,
        "personal_number": _clean_code(personal_raw),
    }

    norm_lines = [line1, line2]
    all_cd_valid = all(cd.is_valid for cd in check_digits) if line_length_valid else False

    return MrzParseResult(
        detected=True,
        mrz_format=MrzFormat.TD3,
        raw_lines=candidate.raw_lines,
        normalized_lines=norm_lines,
        mrz_text="\n".join(norm_lines),
        check_digits=check_digits,
        all_check_digits_valid=all_cd_valid,
        line_length_valid=line_length_valid,
        character_set_valid=char_set_valid,
        recovery_applied=recovery_applied,
        recovery_notes=recovery_notes,
        errors=errors,
        parsed_fields=parsed_fields,
        ocr_confidence=candidate.ocr_confidence,
        is_partial=candidate.is_partial,
        partial_reason=candidate.partial_reason,
        failure_classification=candidate.failure_classification if candidate.failure_classification else ("invalid_mrz" if not all_cd_valid else None),
    )


def _parse_td2(
    candidate: MrzCandidate,
    lines: List[str],
    char_set_valid: bool,
    recovery_applied: bool,
    recovery_notes: List[str],
    errors: List[str],
    line_length_valid: bool = True,
) -> MrzParseResult:
    if len(lines) == 1:
        line1 = lines[0].ljust(36, "<")[:36]
        doc_code = line1[0:2]
        issuing_raw, rec_iss = _recover_alpha_segment(line1[2:5], "L1.issuing_country", recovery_notes)
        name_zone_raw, rec_name = _recover_alpha_segment(line1[5:36], "L1.name_zone", recovery_notes)
        if rec_iss or rec_name:
            recovery_applied = True
            line1 = doc_code + issuing_raw + name_zone_raw

        surname, given_names, full_name = parse_names_field(name_zone_raw)
        issuing_country = _clean_code(issuing_raw)
        if issuing_country and (len(issuing_country) != 3 or not issuing_country.isalpha()):
            errors.append(f"Invalid issuing country code '{issuing_raw}' in TD2 Line 1.")
            issuing_country = None

        parsed_fields: Dict[str, Optional[str]] = {
            "document_type": _clean_code(doc_code),
            "issuing_country": issuing_country,
            "surname": surname,
            "given_names": given_names,
            "full_name": full_name,
            "passport_number": None,
            "nationality": issuing_country,
            "date_of_birth": None,
            "sex": None,
            "date_of_expiry": None,
            "personal_number": None,
        }

        return MrzParseResult(
            detected=True,
            mrz_format=MrzFormat.TD2,
            raw_lines=candidate.raw_lines,
            normalized_lines=[line1],
            mrz_text=line1,
            check_digits=[],
            all_check_digits_valid=False,
            line_length_valid=False,
            character_set_valid=char_set_valid,
            recovery_applied=recovery_applied,
            recovery_notes=recovery_notes,
            errors=errors,
            parsed_fields=parsed_fields,
            ocr_confidence=candidate.ocr_confidence,
        )

    line1 = lines[0].ljust(36, "<")[:36]
    line2 = lines[1].ljust(36, "<")[:36]

    doc_code = line1[0:2]
    issuing_raw, rec_iss = _recover_alpha_segment(line1[2:5], "L1.issuing_country", recovery_notes)
    name_zone_raw, rec_name = _recover_alpha_segment(line1[5:36], "L1.name_zone", recovery_notes)

    doc_num_raw = line2[0:9]
    doc_num_cd, rec_cd1 = _recover_numeric_segment(line2[9:10], "L2.passport_number_cd", recovery_notes)
    nat_raw, rec_nat = _recover_alpha_segment(line2[10:13], "L2.nationality", recovery_notes)
    dob_raw, rec_dob = _recover_numeric_segment(line2[13:19], "L2.date_of_birth", recovery_notes)
    dob_cd, rec_cd2 = _recover_numeric_segment(line2[19:20], "L2.date_of_birth_cd", recovery_notes)
    sex_raw = line2[20:21]
    exp_raw, rec_exp = _recover_numeric_segment(line2[21:27], "L2.date_of_expiry", recovery_notes)
    exp_cd, rec_cd3 = _recover_numeric_segment(line2[27:28], "L2.date_of_expiry_cd", recovery_notes)
    optional_raw = line2[28:35]
    comp_cd, rec_cd4 = _recover_numeric_segment(line2[35:36], "L2.composite_cd", recovery_notes)

    if any([rec_iss, rec_name, rec_cd1, rec_nat, rec_dob, rec_cd2, rec_exp, rec_cd3, rec_cd4]):
        recovery_applied = True
        line1 = doc_code + issuing_raw + name_zone_raw
        line2 = (
            doc_num_raw
            + doc_num_cd
            + nat_raw
            + dob_raw
            + dob_cd
            + sex_raw
            + exp_raw
            + exp_cd
            + optional_raw
            + comp_cd
        )

    check_digits = [
        verify_check_digit(
            field_name="passport_number",
            data_segment=doc_num_raw,
            actual_digit=doc_num_cd,
            position_description="TD2 Line 2 [1-9] check digit at [10]",
        ),
        verify_check_digit(
            field_name="date_of_birth",
            data_segment=dob_raw,
            actual_digit=dob_cd,
            position_description="TD2 Line 2 [14-19] check digit at [20]",
        ),
        verify_check_digit(
            field_name="date_of_expiry",
            data_segment=exp_raw,
            actual_digit=exp_cd,
            position_description="TD2 Line 2 [22-27] check digit at [28]",
        ),
        verify_check_digit(
            field_name="composite",
            data_segment=line2[0:10] + line2[13:20] + line2[21:35],
            actual_digit=comp_cd,
            position_description="TD2 Line 2 composite check digit at [36]",
        ),
    ]

    for cd in check_digits:
        if not cd.is_valid:
            errors.append(
                f"MRZ check-digit failure on '{cd.field_name}': expected '{cd.expected_digit}', got '{cd.actual_digit}'."
            )

    dob_iso, dob_err = parse_mrz_date(dob_raw, is_expiry=False)
    if dob_err:
        errors.append(dob_err)

    exp_iso, exp_err = parse_mrz_date(exp_raw, is_expiry=True)
    if exp_err:
        errors.append(exp_err)

    surname, given_names, full_name = parse_names_field(name_zone_raw)
    sex_val = _parse_sex(sex_raw)
    if sex_val is None:
        errors.append(f"Invalid sex marker '{sex_raw}' at TD2 Line 2 [21].")

    issuing_country = _clean_code(issuing_raw)
    if issuing_country and (len(issuing_country) != 3 or not issuing_country.isalpha()):
        errors.append(f"Invalid issuing country code '{issuing_raw}' in TD2 Line 1.")
        issuing_country = None

    nationality = _clean_code(nat_raw) or issuing_country
    if nationality and (len(nationality) != 3 or not nationality.isalpha()):
        errors.append(f"Invalid nationality code '{nat_raw}' in TD2 Line 2.")
        nationality = None

    parsed_fields = {
        "document_type": _clean_code(doc_code),
        "issuing_country": issuing_country,
        "surname": surname,
        "given_names": given_names,
        "full_name": full_name,
        "passport_number": _clean_code(doc_num_raw),
        "nationality": nationality,
        "date_of_birth": dob_iso,
        "sex": sex_val,
        "date_of_expiry": exp_iso,
        "personal_number": _clean_code(optional_raw),
    }

    norm_lines = [line1, line2]
    all_cd_valid = all(cd.is_valid for cd in check_digits) if line_length_valid else False

    return MrzParseResult(
        detected=True,
        mrz_format=MrzFormat.TD2,
        raw_lines=candidate.raw_lines,
        normalized_lines=norm_lines,
        mrz_text="\n".join(norm_lines),
        check_digits=check_digits,
        all_check_digits_valid=all_cd_valid,
        line_length_valid=line_length_valid,
        character_set_valid=char_set_valid,
        recovery_applied=recovery_applied,
        recovery_notes=recovery_notes,
        errors=errors,
        parsed_fields=parsed_fields,
        ocr_confidence=candidate.ocr_confidence,
        is_partial=candidate.is_partial,
        partial_reason=candidate.partial_reason,
        failure_classification=candidate.failure_classification if candidate.failure_classification else ("invalid_mrz" if not all_cd_valid else None),
    )


def _parse_td1(
    candidate: MrzCandidate,
    lines: List[str],
    char_set_valid: bool,
    recovery_applied: bool,
    recovery_notes: List[str],
    errors: List[str],
    line_length_valid: bool = True,
) -> MrzParseResult:
    if len(lines) < 3:
        parsed_fields = _extract_fallback_fields_from_lines(lines, recovery_notes)
        return MrzParseResult(
            detected=True,
            mrz_format=MrzFormat.TD1,
            raw_lines=candidate.raw_lines,
            normalized_lines=lines,
            mrz_text="\n".join(lines),
            check_digits=[],
            all_check_digits_valid=False,
            line_length_valid=False,
            character_set_valid=char_set_valid,
            recovery_applied=recovery_applied,
            recovery_notes=recovery_notes,
            errors=errors,
            parsed_fields=parsed_fields,
            ocr_confidence=candidate.ocr_confidence,
        )

    line1 = lines[0].ljust(30, "<")[:30]
    line2 = lines[1].ljust(30, "<")[:30]
    line3 = lines[2].ljust(30, "<")[:30]

    doc_code = line1[0:2]
    issuing_raw, rec_iss = _recover_alpha_segment(line1[2:5], "L1.issuing_country", recovery_notes)
    doc_num_raw = line1[5:14]
    doc_num_cd, rec_cd1 = _recover_numeric_segment(line1[14:15], "L1.passport_number_cd", recovery_notes)
    opt1_raw = line1[15:30]

    dob_raw, rec_dob = _recover_numeric_segment(line2[0:6], "L2.date_of_birth", recovery_notes)
    dob_cd, rec_cd2 = _recover_numeric_segment(line2[6:7], "L2.date_of_birth_cd", recovery_notes)
    sex_raw = line2[7:8]
    exp_raw, rec_exp = _recover_numeric_segment(line2[8:14], "L2.date_of_expiry", recovery_notes)
    exp_cd, rec_cd3 = _recover_numeric_segment(line2[14:15], "L2.date_of_expiry_cd", recovery_notes)
    nat_raw, rec_nat = _recover_alpha_segment(line2[15:18], "L2.nationality", recovery_notes)
    opt2_raw = line2[18:29]
    comp_cd, rec_cd4 = _recover_numeric_segment(line2[29:30], "L2.composite_cd", recovery_notes)

    name_zone_raw, rec_name = _recover_alpha_segment(line3[0:30], "L3.name_zone", recovery_notes)

    if any([rec_iss, rec_cd1, rec_dob, rec_cd2, rec_exp, rec_cd3, rec_nat, rec_cd4, rec_name]):
        recovery_applied = True
        line1 = doc_code + issuing_raw + doc_num_raw + doc_num_cd + opt1_raw
        line2 = dob_raw + dob_cd + sex_raw + exp_raw + exp_cd + nat_raw + opt2_raw + comp_cd
        line3 = name_zone_raw

    check_digits = [
        verify_check_digit(
            field_name="passport_number",
            data_segment=doc_num_raw,
            actual_digit=doc_num_cd,
            position_description="TD1 Line 1 [6-14] check digit at [15]",
        ),
        verify_check_digit(
            field_name="date_of_birth",
            data_segment=dob_raw,
            actual_digit=dob_cd,
            position_description="TD1 Line 2 [1-6] check digit at [7]",
        ),
        verify_check_digit(
            field_name="date_of_expiry",
            data_segment=exp_raw,
            actual_digit=exp_cd,
            position_description="TD1 Line 2 [9-14] check digit at [15]",
        ),
        verify_check_digit(
            field_name="composite",
            data_segment=line1[5:30] + line2[0:7] + line2[8:15] + line2[18:29],
            actual_digit=comp_cd,
            position_description="TD1 Line 2 composite check digit at [30]",
        ),
    ]

    for cd in check_digits:
        if not cd.is_valid:
            errors.append(
                f"MRZ check-digit failure on '{cd.field_name}': expected '{cd.expected_digit}', got '{cd.actual_digit}'."
            )

    dob_iso, dob_err = parse_mrz_date(dob_raw, is_expiry=False)
    if dob_err:
        errors.append(dob_err)

    exp_iso, exp_err = parse_mrz_date(exp_raw, is_expiry=True)
    if exp_err:
        errors.append(exp_err)

    surname, given_names, full_name = parse_names_field(name_zone_raw)
    sex_val = _parse_sex(sex_raw)
    if sex_val is None:
        errors.append(f"Invalid sex marker '{sex_raw}' at TD1 Line 2 [8].")

    issuing_country = _clean_code(issuing_raw)
    if issuing_country and (len(issuing_country) != 3 or not issuing_country.isalpha()):
        errors.append(f"Invalid issuing country code '{issuing_raw}' in TD1 Line 1.")
        issuing_country = None

    nationality = _clean_code(nat_raw) or issuing_country
    if nationality and (len(nationality) != 3 or not nationality.isalpha()):
        errors.append(f"Invalid nationality code '{nat_raw}' in TD1 Line 2.")
        nationality = None

    personal_combined = (_clean_code(opt1_raw) or "") + (_clean_code(opt2_raw) or "")

    parsed_fields = {
        "document_type": _clean_code(doc_code),
        "issuing_country": issuing_country,
        "surname": surname,
        "given_names": given_names,
        "full_name": full_name,
        "passport_number": _clean_code(doc_num_raw),
        "nationality": nationality,
        "date_of_birth": dob_iso,
        "sex": sex_val,
        "date_of_expiry": exp_iso,
        "personal_number": personal_combined or None,
    }

    norm_lines = [line1, line2, line3]
    all_cd_valid = all(cd.is_valid for cd in check_digits) if line_length_valid else False

    return MrzParseResult(
        detected=True,
        mrz_format=MrzFormat.TD1,
        raw_lines=candidate.raw_lines,
        normalized_lines=norm_lines,
        mrz_text="\n".join(norm_lines),
        check_digits=check_digits,
        all_check_digits_valid=all_cd_valid,
        line_length_valid=line_length_valid,
        character_set_valid=char_set_valid,
        recovery_applied=recovery_applied,
        recovery_notes=recovery_notes,
        errors=errors,
        parsed_fields=parsed_fields,
        ocr_confidence=candidate.ocr_confidence,
        is_partial=candidate.is_partial,
        partial_reason=candidate.partial_reason,
        failure_classification=candidate.failure_classification if candidate.failure_classification else ("invalid_mrz" if not all_cd_valid else None),
    )
