"""Best-effort Visible Inspection Zone (VIZ) field extraction using labels and spatial heuristics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple

from app.ocr.base import OcrTextBlock

_MONTH_MAP = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "SEPT": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

# Bilingual / standard ICAO VIZ label patterns mapped to canonical field names
_LABEL_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    (
        "passport_number",
        re.compile(
            r"\b(?:passport\s*(?:no|number|#)|document\s*(?:no|number)|no\.?\s*du\s*passeport|passeport\s*no\.?|passnummer)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "given_names",
        re.compile(
            r"\b(?:given\s*names?|given\s*name\s*\([a-z]\)|first\s*names?|forenames?|pr[eé]noms?|nombres?|vorname[n]?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "surname",
        re.compile(
            r"\b(?:surname|family\s*name|last\s*name|nom(?:\s*de\s*famille)?|apellidos?|nachname|hame)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "full_name",
        re.compile(
            r"\b(?:full\s*name|holder'?s?\s*name|bearer'?s?\s*name|name\s*of\s*(?:bearer|holder)|name(?:\s*/\s*nom)?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "nationality",
        re.compile(r"\b(?:nationality|nationalit[eé]|nacionalidad|staatsangehörigkeit)\b", re.IGNORECASE),
    ),
    (
        "date_of_birth",
        re.compile(
            r"\b(?:date\s*of\s*birth|birth\s*date|dob|date\s*de\s*naissance|fecha\s*de\s*nacimiento|geburtsdatum)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "sex",
        re.compile(r"\b(?:sex|gender|sexe|sexo|geschlecht)\b", re.IGNORECASE),
    ),
    (
        "place_of_birth",
        re.compile(
            r"\b(?:place\s*of\s*birth|birth\s*place|birthplace|lieu\s*de\s*naissance|lugar\s*de\s*nacimiento|pob|geburtsort)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "date_of_issue",
        re.compile(
            r"\b(?:date\s*(?:of|df)\s*issue|issue\s*date|date\s*de\s*d[eé]livrance|fecha\s*de\s*expedici[oó]n|ausstellungsdatum)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "date_of_expiry",
        re.compile(
            r"\b(?:date\s*(?:of|df)\s*expir(?:y|ation)|expir(?:y|ation)\s*date|valid\s*until|validuntil|date\s*d'expiration|fecha\s*de\s*caducidad|ablaufdatum)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "issuing_country",
        re.compile(
            r"\b(?:country\s*code|issuing\s*(?:country|state|authority)|code\s*du\s*pays|code\s*pays|c[oó]digo\s*del\s*pa[ií]s|authority|autorit[eé]|autoridad|beh[oö]rde)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "document_type",
        re.compile(r"\b(?:type|document\s*type|cat[eé]gorie|tipo|residence\s*permit|identity\s*card|passport|passeport)\b", re.IGNORECASE),
    ),
    (
        "personal_number",
        re.compile(r"\b(?:personal\s*(?:no|number)|id\s*(?:no|number))\b", re.IGNORECASE),
    ),
]

_HEADER_NOISE_PATTERNS = re.compile(
    r"^(?:republic\s+of|united\s+states(?:\s+of\s+america)?|european\s+union|type\s+of\s+permit|leave\s+to\s+enter)$",
    re.IGNORECASE,
)

_LABEL_WORD_SET = {
    "nom", "famille", "prenoms", "prénoms", "apellidos", "nombres",
    "lieu", "naissance", "lugar", "nacimiento", "nationalite", "nationalité",
    "nacionalidad", "nationality", "nacio", "nacion", "nac", "staatsangehoerigkeit", "staatsangehörigkeit",
    "date", "sexe", "sexo", "code", "pays", "pais", "país", "country",
    "delivrance", "délivrance", "expedicion", "expedición", "expiration", "caducidad",
    "autorite", "autorité", "autoridad", "categorie", "catégorie", "tipo", "typer", "typef", "type",
    "passpo", "nonodu", "papor", "depasor", "codel", "codei", "codigo",
    "du", "de", "del", "d", "permit", "permis", "residence", "talent", "restricted",
    "leave", "remarks", "work", "sports", "train", "enter", "migrant", "signature",
    "titular", "titulaire", "firma", "bearer", "holder", "typeofpeemi"
}


@dataclass(frozen=True)
class VizFieldResult:
    """Extraction outcome for a single field in the Visible Inspection Zone."""

    field_name: str
    value: Optional[str] = None
    raw_evidence: Optional[str] = None
    ocr_confidence: Optional[float] = None
    status: str = "unavailable"  # "extracted" | "ambiguous" | "unavailable"
    notes: List[str] = field(default_factory=list)


def _is_label_text(text: str) -> bool:
    """Return True if text matches a pure VIZ field label or document header noise."""
    cleaned = text.strip(" :./-")
    if not cleaned:
        return True
    if _HEADER_NOISE_PATTERNS.match(cleaned):
        return True
    for _, pattern in _LABEL_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            rem = cleaned[match.end() :].strip(" :./-")
            if not rem:
                return True
            # If remainder has another label, it's label text
            if any(p.search(rem) for _, p in _LABEL_PATTERNS):
                return True
            return False
    return False


from app.viz.regex_extractor import (
    clean_label_remainder,
    normalize_field_ocr_confusions,
    parse_and_validate_date,
    validate_field_candidate,
    SEX_PATTERNS,
    ISO_NATIONALITY_REGISTRY,
    NATIONALITY_NAME_TO_CODE,
)

def _clean_label_remainder(remainder: str) -> str:
    return clean_label_remainder(remainder)


def normalize_viz_date(raw: str) -> Optional[str]:
    """
    Parse common VIZ date formats into ISO YYYY-MM-DD using strict calendar validation.
    """
    val, _ = parse_and_validate_date(raw)
    return val


def _validate_and_clean_field_value(field_name: str, raw_val: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate and normalize a candidate VIZ value for `field_name` using strict regex validation.
    """
    strip_chars = " :-/|_" if field_name in {"place_of_birth", "surname", "given_names", "full_name", "nationality", "issuing_country"} else " :.-/|_"
    val = raw_val.strip(strip_chars)
    if not val:
        return None, "Candidate value is empty."
    if field_name not in {"issuing_country", "place_of_birth"} and _is_label_text(val):
        return None, "Candidate value resembles a field label or is empty."

    norm_val, status, err = validate_field_candidate(field_name, val)
    if status == "valid":
        return norm_val, None
    elif status == "unverified":
        return norm_val, err
    return None, err


def _decompose_blocks_to_lines(blocks: List[OcrTextBlock]) -> List[OcrTextBlock]:
    """
    Decompose multiline OCR blocks into individual line-level OcrTextBlock items.
    Computes accurate vertical bounding sub-boxes for each line so spatial matching works reliably.
    """
    decomposed: List[OcrTextBlock] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.text.splitlines() if ln.strip()]
        if len(lines) <= 1:
            decomposed.append(block)
            continue
        line_count = len(lines)
        line_height = block.height / float(line_count)
        for idx, ln in enumerate(lines):
            y_min = block.min_y + idx * line_height
            y_max = block.min_y + (idx + 1) * line_height
            sub_bbox = (
                (block.min_x, y_min),
                (block.max_x, y_min),
                (block.max_x, y_max),
                (block.min_x, y_max),
            )
            decomposed.append(OcrTextBlock(text=ln, confidence=block.confidence, bbox=sub_bbox))
    return decomposed


def extract_viz_fields(
    blocks: List[OcrTextBlock],
    mrz_raw_lines: Optional[List[str]] = None,
) -> Dict[str, VizFieldResult]:
    """
    Extract supported passport fields from the Visible Inspection Zone (VIZ).
    """
    target_fields = [
        "document_type",
        "issuing_country",
        "surname",
        "given_names",
        "full_name",
        "passport_number",
        "nationality",
        "date_of_birth",
        "sex",
        "date_of_expiry",
        "date_of_issue",
        "place_of_birth",
        "personal_number",
    ]
    results: Dict[str, VizFieldResult] = {
        fname: VizFieldResult(field_name=fname, status="unavailable") for fname in target_fields
    }

    if not blocks:
        return results

    decomposed_blocks = _decompose_blocks_to_lines(blocks)

    mrz_set: Set[str] = {ln.strip() for ln in (mrz_raw_lines or []) if ln.strip()}
    viz_blocks: List[OcrTextBlock] = []
    for b in decomposed_blocks:
        txt = b.text.strip()
        compact = "".join(txt.split())
        if txt in mrz_set or "<<" in compact or (len(compact) >= 28 and compact.count("<") >= 3):
            continue
        viz_blocks.append(b)

    # Sort blocks in reading order: top-to-bottom, left-to-right
    viz_blocks.sort(key=lambda b: (round(b.min_y / 14.0), b.min_x))

    claimed_block_indices: Set[int] = set()

    for idx, block in enumerate(viz_blocks):
        text = block.text.strip()
        for field_name, pattern in _LABEL_PATTERNS:
            if results[field_name].status == "extracted":
                continue
            match = pattern.search(text)
            if not match:
                continue

            # Special case for document_type headers (e.g. "RESIDENCE PERMIT", "PASSPORT", "PASSEPORT", "IDENTITY CARD", "VISA")
            if field_name == "document_type" and re.search(r"\b(?:residence\s*permit|identity\s*card|passport|passeport|pasaporte|visa|travel\s*document)\b", text, re.IGNORECASE):
                up_text = text.upper()
                if "RESIDENCE" in up_text or "PERMIT" in up_text:
                    doc_val = "RESIDENCE PERMIT"
                elif "IDENTITY" in up_text or "ID CARD" in up_text:
                    doc_val = "ID"
                elif "VISA" in up_text or "TRAVEL DOCUMENT" in up_text:
                    doc_val = "V"
                else:
                    doc_val = "P"
                claimed_block_indices.add(idx)
                results[field_name] = VizFieldResult(
                    field_name=field_name,
                    value=doc_val,
                    raw_evidence=text,
                    ocr_confidence=block.confidence,
                    status="extracted",
                    notes=["Extracted from document header line."],
                )
                break

            # Strip leading label and any secondary/tertiary multilingual labels
            remainder = text[match.end() :].strip()
            inline_candidate = _clean_label_remainder(remainder)

            if inline_candidate:
                cleaned_val, err_note = _validate_and_clean_field_value(field_name, inline_candidate)
                if cleaned_val is not None:
                    claimed_block_indices.add(idx)
                    results[field_name] = VizFieldResult(
                        field_name=field_name,
                        value=cleaned_val,
                        raw_evidence=text,
                        ocr_confidence=block.confidence,
                        status="extracted",
                        notes=["Extracted from inline VIZ label-value line."],
                    )
                    break
                elif err_note and results[field_name].status == "unavailable":
                    results[field_name] = VizFieldResult(
                        field_name=field_name,
                        value=None,
                        raw_evidence=text,
                        ocr_confidence=block.confidence,
                        status="ambiguous",
                        notes=[err_note],
                    )

            # Check spatial candidate below or to the right
            claimed_block_indices.add(idx)
            neighbor = _find_spatial_value_block(idx, block, viz_blocks, claimed_block_indices)
            if neighbor is not None:
                n_idx, n_block = neighbor
                cleaned_val, err_note = _validate_and_clean_field_value(field_name, n_block.text)
                if cleaned_val is not None:
                    claimed_block_indices.add(n_idx)
                    combined_conf = round((block.confidence + n_block.confidence) / 2.0, 4)
                    results[field_name] = VizFieldResult(
                        field_name=field_name,
                        value=cleaned_val,
                        raw_evidence=f"{block.text} -> {n_block.text}",
                        ocr_confidence=combined_conf,
                        status="extracted",
                        notes=["Extracted via spatial label-to-value alignment in VIZ."],
                    )
                elif results[field_name].status == "unavailable":
                    results[field_name] = VizFieldResult(
                        field_name=field_name,
                        value=None,
                        raw_evidence=f"{block.text} -> {n_block.text}",
                        ocr_confidence=n_block.confidence,
                        status="ambiguous",
                        notes=[err_note or "Could not validate value."],
                    )
            break

    # --------------------------------------------------------------------------
    # Pass 2: Value-First Pattern & Spatial Fallback (when labels are absent/unsegmented)
    # --------------------------------------------------------------------------
    unclaimed_blocks = [b for i, b in enumerate(viz_blocks) if i not in claimed_block_indices]

    # 1. Document Type (from prominent header text if still unavailable)
    if results["document_type"].status != "extracted":
        for b in unclaimed_blocks:
            up = b.text.strip().upper()
            if "RESIDENCE PERMIT" in up or ("RESIDENCE" in up and "PERMIT" in up):
                results["document_type"] = VizFieldResult(
                    field_name="document_type",
                    value="RESIDENCE PERMIT",
                    raw_evidence=b.text,
                    ocr_confidence=b.confidence,
                    status="extracted",
                    notes=["Extracted from document header."],
                )
                break
            elif "IDENTITY CARD" in up or "ID CARD" in up:
                results["document_type"] = VizFieldResult(
                    field_name="document_type",
                    value="ID",
                    raw_evidence=b.text,
                    ocr_confidence=b.confidence,
                    status="extracted",
                    notes=["Extracted from document header."],
                )
                break
            elif "VISA" in up:
                results["document_type"] = VizFieldResult(
                    field_name="document_type",
                    value="V",
                    raw_evidence=b.text,
                    ocr_confidence=b.confidence,
                    status="extracted",
                    notes=["Extracted from document header."],
                )
                break
            elif "PASSPORT" in up or "PASSEPORT" in up or "PASAPORTE" in up:
                results["document_type"] = VizFieldResult(
                    field_name="document_type",
                    value="P",
                    raw_evidence=b.text,
                    ocr_confidence=b.confidence,
                    status="extracted",
                    notes=["Extracted from document header."],
                )
                break

    # 2. Place of Birth (Anchor for spatial date and identity alignment)
    pob_block: Optional[OcrTextBlock] = None
    if results["place_of_birth"].value:
        for b in viz_blocks:
            if results["place_of_birth"].value in b.text.upper():
                pob_block = b
                break
    else:
        for b in unclaimed_blocks:
            raw = b.text.strip()
            if ("." in raw or "," in raw) and any(c.isalpha() for c in raw):
                parts = re.split(r"[,.]", raw)
                suffix = parts[-1].strip().upper()
                is_recognized_jurisdiction = (
                    suffix in NATIONALITY_NAME_TO_CODE
                    or suffix in ISO_NATIONALITY_REGISTRY
                    or suffix in {"USA", "US", "CAN", "UK", "GBR", "U.S.A.", "U.S."}
                )
                if not is_recognized_jurisdiction:
                    continue

                norm_val, st, _ = validate_field_candidate("place_of_birth", raw)
                if st == "valid" and norm_val:
                    results["place_of_birth"] = VizFieldResult(
                        field_name="place_of_birth",
                        value=norm_val,
                        raw_evidence=raw,
                        ocr_confidence=b.confidence,
                        status="extracted",
                        notes=["Extracted from place of birth format in VIZ."],
                    )
                    pob_block = b
                    try:
                        claimed_block_indices.add(viz_blocks.index(b))
                    except ValueError:
                        pass
                    break

    # 3. Position-Anchored Date Extraction with Plausibility Checks
    # (DOB, Issue Date, Expiry Date prioritized by explicit layout anchors and plausibility)
    unclaimed_date_blocks: List[Tuple[date, str, OcrTextBlock, int]] = []
    for idx, b in enumerate(viz_blocks):
        if idx in claimed_block_indices:
            continue
        iso_val, _ = parse_and_validate_date(b.text)
        if iso_val:
            try:
                y, m, d = [int(p) for p in iso_val.split("-")]
                unclaimed_date_blocks.append((date(y, m, d), iso_val, b, idx))
            except ValueError:
                pass

    today = date.today()

    if unclaimed_date_blocks:
        # Sort candidates top-to-bottom by vertical coordinate (min_y)
        unclaimed_date_blocks.sort(key=lambda item: item[2].min_y)

        if pob_block is not None:
            # Spatial partition around Place of Birth
            dates_above_pob = [item for item in unclaimed_date_blocks if item[2].min_y < pob_block.min_y - 2.0]
            dates_below_pob = [item for item in unclaimed_date_blocks if item[2].min_y > pob_block.min_y + 2.0]

            # Assign Date of Birth from candidates above POB
            if results["date_of_birth"].status != "extracted":
                plausible_dob = [item for item in dates_above_pob if item[0] <= today - timedelta(days=365)]
                if len(plausible_dob) == 1:
                    d_obj, iso_str, b, idx = plausible_dob[0]
                    claimed_block_indices.add(idx)
                    results["date_of_birth"] = VizFieldResult(
                        field_name="date_of_birth",
                        value=iso_str,
                        raw_evidence=b.text,
                        ocr_confidence=b.confidence,
                        status="extracted",
                        notes=["Extracted via standard passport layout (positioned above place of birth)."],
                    )
                elif len(plausible_dob) > 1:
                    results["date_of_birth"] = VizFieldResult(
                        field_name="date_of_birth",
                        status="ambiguous",
                        notes=["Multiple ambiguous date candidates positioned above place of birth."],
                    )
                elif dates_above_pob:
                    results["date_of_birth"] = VizFieldResult(
                        field_name="date_of_birth",
                        status="ambiguous",
                        notes=["Candidate date above place of birth failed birth date plausibility check."],
                    )

            # Assign Issue and Expiry Dates from candidates below POB
            avail_below = [item for item in dates_below_pob if item[3] not in claimed_block_indices]
            if len(avail_below) >= 2:
                sorted_by_date = sorted(avail_below, key=lambda x: x[0])
                cand_issue = sorted_by_date[0]
                cand_expiry = sorted_by_date[-1]

                issue_plausible = cand_issue[0] <= today + timedelta(days=60)
                order_plausible = cand_expiry[0] > cand_issue[0]

                if issue_plausible and order_plausible:
                    if results["date_of_issue"].status != "extracted":
                        claimed_block_indices.add(cand_issue[3])
                        results["date_of_issue"] = VizFieldResult(
                            field_name="date_of_issue",
                            value=cand_issue[1],
                            raw_evidence=cand_issue[2].text,
                            ocr_confidence=cand_issue[2].confidence,
                            status="extracted",
                            notes=["Extracted via standard passport layout (earlier date below place of birth)."],
                        )
                    if results["date_of_expiry"].status != "extracted":
                        claimed_block_indices.add(cand_expiry[3])
                        results["date_of_expiry"] = VizFieldResult(
                            field_name="date_of_expiry",
                            value=cand_expiry[1],
                            raw_evidence=cand_expiry[2].text,
                            ocr_confidence=cand_expiry[2].confidence,
                            status="extracted",
                            notes=["Extracted via standard passport layout (later date below place of birth)."],
                        )
                else:
                    if results["date_of_issue"].status != "extracted":
                        results["date_of_issue"] = VizFieldResult(
                            field_name="date_of_issue",
                            status="ambiguous",
                            notes=["Candidate dates below place of birth failed issue/expiry plausibility validation."],
                        )
                    if results["date_of_expiry"].status != "extracted":
                        results["date_of_expiry"] = VizFieldResult(
                            field_name="date_of_expiry",
                            status="ambiguous",
                            notes=["Candidate dates below place of birth failed issue/expiry plausibility validation."],
                        )
            elif len(avail_below) == 1:
                d_obj, iso_str, b, idx = avail_below[0]
                if d_obj > today and results["date_of_expiry"].status != "extracted":
                    claimed_block_indices.add(idx)
                    results["date_of_expiry"] = VizFieldResult(
                        field_name="date_of_expiry",
                        value=iso_str,
                        raw_evidence=b.text,
                        ocr_confidence=b.confidence,
                        status="extracted",
                        notes=["Extracted as future date below place of birth (expiry)."],
                    )
                elif results["date_of_expiry"].status == "extracted" and results["date_of_issue"].status != "extracted":
                    claimed_block_indices.add(idx)
                    results["date_of_issue"] = VizFieldResult(
                        field_name="date_of_issue",
                        value=iso_str,
                        raw_evidence=b.text,
                        ocr_confidence=b.confidence,
                        status="extracted",
                        notes=["Extracted as remaining date below place of birth (issue)."],
                    )
                else:
                    if results["date_of_issue"].status != "extracted":
                        results["date_of_issue"] = VizFieldResult(
                            field_name="date_of_issue",
                            status="ambiguous",
                            notes=["Single candidate date below place of birth is ambiguous."],
                        )

        else:
            avail = [item for item in unclaimed_date_blocks if item[3] not in claimed_block_indices]
            if len(avail) >= 3:
                top_cand, mid_cand, bot_cand = avail[0], avail[1], avail[2]
                is_valid_order = top_cand[0] < mid_cand[0] < bot_cand[0]
                is_valid_dob = top_cand[0] <= today - timedelta(days=365)
                is_valid_issue = mid_cand[0] <= today + timedelta(days=60)
                if is_valid_order and is_valid_dob and is_valid_issue:
                    if results["date_of_birth"].status != "extracted":
                        claimed_block_indices.add(top_cand[3])
                        results["date_of_birth"] = VizFieldResult(
                            field_name="date_of_birth",
                            value=top_cand[1],
                            raw_evidence=top_cand[2].text,
                            ocr_confidence=top_cand[2].confidence,
                            status="extracted",
                            notes=["Extracted via spatial top position and verified birth plausibility."],
                        )
                    if results["date_of_issue"].status != "extracted":
                        claimed_block_indices.add(mid_cand[3])
                        results["date_of_issue"] = VizFieldResult(
                            field_name="date_of_issue",
                            value=mid_cand[1],
                            raw_evidence=mid_cand[2].text,
                            ocr_confidence=mid_cand[2].confidence,
                            status="extracted",
                            notes=["Extracted via intermediate spatial position and verified issue plausibility."],
                        )
                    if results["date_of_expiry"].status != "extracted":
                        claimed_block_indices.add(bot_cand[3])
                        results["date_of_expiry"] = VizFieldResult(
                            field_name="date_of_expiry",
                            value=bot_cand[1],
                            raw_evidence=bot_cand[2].text,
                            ocr_confidence=bot_cand[2].confidence,
                            status="extracted",
                            notes=["Extracted via bottom spatial position and verified expiry plausibility."],
                        )
                else:
                    for df in ("date_of_birth", "date_of_issue", "date_of_expiry"):
                        if results[df].status != "extracted":
                            results[df] = VizFieldResult(
                                field_name=df,
                                status="ambiguous",
                                notes=["Candidate dates failed chronological or spatial plausibility validation."],
                            )
            elif len(avail) == 2:
                c1, c2 = avail[0], avail[1]
                if c1[0].year <= today.year - 15 and c2[0] > today:
                    if results["date_of_birth"].status != "extracted":
                        claimed_block_indices.add(c1[3])
                        results["date_of_birth"] = VizFieldResult(
                            field_name="date_of_birth",
                            value=c1[1],
                            raw_evidence=c1[2].text,
                            ocr_confidence=c1[2].confidence,
                            status="extracted",
                            notes=["Extracted as past date (birth)."],
                        )
                    if results["date_of_expiry"].status != "extracted":
                        claimed_block_indices.add(c2[3])
                        results["date_of_expiry"] = VizFieldResult(
                            field_name="date_of_expiry",
                            value=c2[1],
                            raw_evidence=c2[2].text,
                            ocr_confidence=c2[2].confidence,
                            status="extracted",
                            notes=["Extracted as later date (expiry)."],
                        )
                elif c1[0] <= today + timedelta(days=60) and c2[0] > today:
                    if results["date_of_issue"].status != "extracted":
                        claimed_block_indices.add(c1[3])
                        results["date_of_issue"] = VizFieldResult(
                            field_name="date_of_issue",
                            value=c1[1],
                            raw_evidence=c1[2].text,
                            ocr_confidence=c1[2].confidence,
                            status="extracted",
                            notes=["Extracted as earlier date (issue)."],
                        )
                    if results["date_of_expiry"].status != "extracted":
                        claimed_block_indices.add(c2[3])
                        results["date_of_expiry"] = VizFieldResult(
                            field_name="date_of_expiry",
                            value=c2[1],
                            raw_evidence=c2[2].text,
                            ocr_confidence=c2[2].confidence,
                            status="extracted",
                            notes=["Extracted as later date (expiry)."],
                        )
                else:
                    for df in ("date_of_birth", "date_of_issue", "date_of_expiry"):
                        if results[df].status != "extracted":
                            results[df] = VizFieldResult(
                                field_name=df,
                                status="ambiguous",
                                notes=["Unanchored date candidates cannot be assigned with confidence."],
                            )
            elif len(avail) == 1:
                d_obj, iso_str, b, idx = avail[0]
                if d_obj > today and results["date_of_expiry"].status != "extracted":
                    claimed_block_indices.add(idx)
                    results["date_of_expiry"] = VizFieldResult(
                        field_name="date_of_expiry",
                        value=iso_str,
                        raw_evidence=b.text,
                        ocr_confidence=b.confidence,
                        status="extracted",
                        notes=["Extracted as future date (expiry)."],
                    )
                elif d_obj.year <= today.year - 15 and results["date_of_birth"].status != "extracted":
                    claimed_block_indices.add(idx)
                    results["date_of_birth"] = VizFieldResult(
                        field_name="date_of_birth",
                        value=iso_str,
                        raw_evidence=b.text,
                        ocr_confidence=b.confidence,
                        status="extracted",
                        notes=["Extracted as past date (birth)."],
                    )

    # 4. Sex Marker Extraction (Explicit pattern match or layout position adjacent to Date of Birth)
    if results["sex"].status != "extracted":
        for idx, b in enumerate(viz_blocks):
            if idx in claimed_block_indices:
                continue
            for p in SEX_PATTERNS:
                m = p.search(b.text)
                if m:
                    cand_val = m.group("val") if "val" in m.groupdict() else None
                    if cand_val:
                        norm_sex, st, _ = validate_field_candidate("sex", cand_val)
                        if st == "valid" and norm_sex:
                            claimed_block_indices.add(idx)
                            results["sex"] = VizFieldResult(
                                field_name="sex",
                                value=norm_sex,
                                raw_evidence=b.text,
                                ocr_confidence=b.confidence,
                                status="extracted",
                                notes=["Extracted via explicit sex regex pattern."],
                            )
                            break
            if results["sex"].status == "extracted":
                break

    if results["sex"].status != "extracted":
        dob_res = results["date_of_birth"]
        dob_block: Optional[OcrTextBlock] = None
        if dob_res.value:
            for b in viz_blocks:
                d_iso, _ = parse_and_validate_date(b.text)
                if d_iso == dob_res.value:
                    dob_block = b
                    break

        sex_candidates: List[Tuple[float, int, OcrTextBlock, str]] = []
        if dob_block is not None:
            for idx, b in enumerate(viz_blocks):
                if idx in claimed_block_indices:
                    continue
                raw_t = b.text.strip().upper()
                if raw_t in {"M", "F", "X", "<", "MALE", "FEMALE", "MASCULIN", "FEMININ", "FÉMININ", "UNSPECIFIED", "M / M", "F / F"}:
                    norm_sex, st, _ = validate_field_candidate("sex", raw_t.split("/")[0].strip())
                    if st == "valid" and norm_sex:
                        v_diff = abs(b.vertical_center - dob_block.vertical_center)
                        h_diff = abs(b.min_x - dob_block.max_x)
                        if v_diff <= max(30.0, dob_block.height * 1.5) and h_diff <= 450.0:
                            dist = v_diff * 2.0 + h_diff
                            sex_candidates.append((dist, idx, b, norm_sex))

        if len(sex_candidates) == 1:
            _, s_idx, s_block, s_val = sex_candidates[0]
            claimed_block_indices.add(s_idx)
            results["sex"] = VizFieldResult(
                field_name="sex",
                value=s_val,
                raw_evidence=s_block.text,
                ocr_confidence=s_block.confidence,
                status="extracted",
                notes=["Extracted via standard passport layout (anchored adjacent to date of birth)."],
            )
        elif len(sex_candidates) > 1:
            unique_vals = {c[3] for c in sex_candidates}
            if len(unique_vals) == 1:
                _, s_idx, s_block, s_val = min(sex_candidates, key=lambda c: c[0])
                claimed_block_indices.add(s_idx)
                results["sex"] = VizFieldResult(
                    field_name="sex",
                    value=s_val,
                    raw_evidence=s_block.text,
                    ocr_confidence=s_block.confidence,
                    status="extracted",
                    notes=["Extracted via standard passport layout (anchored adjacent to date of birth)."],
                )
            else:
                results["sex"] = VizFieldResult(
                    field_name="sex",
                    status="ambiguous",
                    notes=["Multiple ambiguous sex marker candidates found near date of birth."],
                )
        else:
            if results["sex"].status == "unavailable":
                results["sex"] = VizFieldResult(
                    field_name="sex",
                    status="unavailable",
                    notes=["Sex marker label not detected and no reliable layout position found."],
                )

    # 5. Passport Number (Standalone alphanumeric token if not extracted)
    if results["passport_number"].status != "extracted":
        for b in [b for i, b in enumerate(viz_blocks) if i not in claimed_block_indices]:
            raw = b.text.strip()
            if parse_and_validate_date(raw)[0] is not None:
                continue
            norm_val, st, _ = validate_field_candidate("passport_number", raw)
            if st == "valid" and norm_val and any(c.isdigit() for c in norm_val):
                if 6 <= len(norm_val) <= 12 and not _is_label_text(norm_val):
                    results["passport_number"] = VizFieldResult(
                        field_name="passport_number",
                        value=norm_val,
                        raw_evidence=raw,
                        ocr_confidence=b.confidence,
                        status="extracted",
                        notes=["Extracted from standalone passport number format in VIZ."],
                    )
                    break

    # 6. Nationality / Issuing Authority
    if results["nationality"].status != "extracted" or results["issuing_country"].status != "extracted":
        for b in [b for i, b in enumerate(viz_blocks) if i not in claimed_block_indices]:
            up = b.text.strip().upper()
            if up in ISO_NATIONALITY_REGISTRY:
                if results["nationality"].status != "extracted":
                    results["nationality"] = VizFieldResult(
                        field_name="nationality",
                        value=up,
                        raw_evidence=b.text,
                        ocr_confidence=b.confidence,
                        status="extracted",
                        notes=["Extracted from standard ISO country code in VIZ."],
                    )
                if results["issuing_country"].status != "extracted":
                    results["issuing_country"] = VizFieldResult(
                        field_name="issuing_country",
                        value=up,
                        raw_evidence=b.text,
                        ocr_confidence=b.confidence,
                        status="extracted",
                        notes=["Extracted from standard ISO country code in VIZ."],
                    )
            elif "UNITED STATES" in up or "UNTTED STNTES" in up:
                if results["issuing_country"].status != "extracted":
                    results["issuing_country"] = VizFieldResult(
                        field_name="issuing_country",
                        value="USA",
                        raw_evidence=b.text,
                        ocr_confidence=b.confidence,
                        status="extracted",
                        notes=["Extracted from issuing authority title."],
                    )

    # 6. Names (Surname & Given Names from stacked name blocks)
    if results["surname"].status != "extracted" or results["given_names"].status != "extracted":
        _NON_NAME_TERMS = (
            "TITULAR", "TITULA", "FIRMA", "SIGNATURE", "BEARER", "HOLDER",
            "PERMIT", "PEEMI", "MIGRANT", "TALENT", "ENTER", "REMARK", "REMARR",
            "RESTRICT", "SPORT", "TRAIN", "LEAVE", "UNITED", "STATES",
            "AMERICA", "REPUBLIC", "PASSPORT", "PASSEPORT", "DEPART", "STATE",
            "STAT", "ATA", "HAME", "NAME", "CODE", "TYPE", "OFAMERICA", "OFAMIERICA",
            "OFAMECRICA", "UNTIED", "STNEES", "STNTES", "NLLTED", "AMIERICA",
            "DEPARTMENT", "GOVERNMENT", "AUTHORITY", "AUTORITE", "MINISTRY"
        )
        name_candidates: List[OcrTextBlock] = []
        for b in unclaimed_blocks:
            txt = b.text.strip()
            clean_txt = re.sub(r"[^A-Za-zÀ-ÿ\-'\s]", "", txt).strip()
            words = clean_txt.split()
            if (
                clean_txt == txt
                and 2 <= len(txt) <= 22
                and len(words) <= 3
                and not any(c.isdigit() for c in txt)
                and txt.upper() not in ISO_NATIONALITY_REGISTRY
                and not any(term in txt.upper() for term in _NON_NAME_TERMS)
                and not _is_label_text(txt)
                and parse_and_validate_date(txt)[0] is None
            ):
                name_candidates.append(b)

        # Check if we have a Date of Birth block to anchor the identity column
        dob_block: Optional[OcrTextBlock] = None
        if results["date_of_birth"].value:
            for b in viz_blocks:
                d_iso, _ = parse_and_validate_date(b.text)
                if d_iso == results["date_of_birth"].value:
                    dob_block = b
                    break

        if dob_block is not None:
            col_candidates = [
                b for b in name_candidates
                if abs(b.min_x - dob_block.min_x) <= 120.0 and 0.0 < (dob_block.min_y - b.min_y) <= 180.0
            ]
            if len(col_candidates) >= 1:
                name_candidates = col_candidates

        name_candidates.sort(key=lambda b: (round(b.min_y / 14.0), b.min_x))

        if results["surname"].status != "extracted" and results["given_names"].status != "extracted":
            if len(name_candidates) >= 2:
                results["surname"] = VizFieldResult(
                    field_name="surname",
                    value=name_candidates[0].text.strip().upper(),
                    raw_evidence=name_candidates[0].text,
                    ocr_confidence=name_candidates[0].confidence,
                    status="extracted",
                    notes=["Extracted via standard passport layout (top name line)."],
                )
                results["given_names"] = VizFieldResult(
                    field_name="given_names",
                    value=name_candidates[1].text.strip().upper(),
                    raw_evidence=name_candidates[1].text,
                    ocr_confidence=name_candidates[1].confidence,
                    status="extracted",
                    notes=["Extracted via standard passport layout (second name line)."],
                )
            elif len(name_candidates) == 1 and results["full_name"].status != "extracted":
                parts = name_candidates[0].text.strip().split()
                if len(parts) >= 2:
                    results["full_name"] = VizFieldResult(
                        field_name="full_name",
                        value=name_candidates[0].text.strip().upper(),
                        raw_evidence=name_candidates[0].text,
                        ocr_confidence=name_candidates[0].confidence,
                        status="extracted",
                        notes=["Extracted from composite name block."],
                    )
        elif results["given_names"].status != "extracted" and len(name_candidates) >= 1:
            results["given_names"] = VizFieldResult(
                field_name="given_names",
                value=name_candidates[0].text.strip().upper(),
                raw_evidence=name_candidates[0].text,
                ocr_confidence=name_candidates[0].confidence,
                status="extracted",
                notes=["Extracted from name candidate in VIZ."],
            )
        elif results["surname"].status != "extracted" and len(name_candidates) >= 1:
            results["surname"] = VizFieldResult(
                field_name="surname",
                value=name_candidates[0].text.strip().upper(),
                raw_evidence=name_candidates[0].text,
                ocr_confidence=name_candidates[0].confidence,
                status="extracted",
                notes=["Extracted from name candidate in VIZ."],
            )

    # Reconcile full name with given names & surname
    surname_res = results["surname"]
    given_res = results["given_names"]
    full_res = results["full_name"]

    if surname_res.value and given_res.value and not full_res.value:
        confs = [c for c in (surname_res.ocr_confidence, given_res.ocr_confidence) if c is not None]
        results["full_name"] = VizFieldResult(
            field_name="full_name",
            value=f"{given_res.value} {surname_res.value}",
            raw_evidence=f"{given_res.value} {surname_res.value}",
            ocr_confidence=round(sum(confs) / len(confs), 4) if confs else None,
            status="extracted",
            notes=["Derived from VIZ given_names and surname."],
        )
    elif full_res.value and (not surname_res.value or not given_res.value):
        parts = full_res.value.split()
        if len(parts) >= 2:
            if not given_res.value:
                results["given_names"] = VizFieldResult(
                    field_name="given_names",
                    value=" ".join(parts[:-1]),
                    raw_evidence=full_res.raw_evidence,
                    ocr_confidence=full_res.ocr_confidence,
                    status="extracted",
                    notes=["Derived from full name."],
                )
            if not surname_res.value:
                results["surname"] = VizFieldResult(
                    field_name="surname",
                    value=parts[-1],
                    raw_evidence=full_res.raw_evidence,
                    ocr_confidence=full_res.ocr_confidence,
                    status="extracted",
                    notes=["Derived from full name."],
                )

    # Ensure all unavailable/missing fields have safe diagnostic notes
    _DEFAULT_DIAGNOSTIC_NOTES = {
        "document_type": "Document header or type label not detected.",
        "issuing_country": "Issuing authority label or candidate not detected.",
        "surname": "Surname label or candidate not detected.",
        "given_names": "Given names label or candidate not detected.",
        "full_name": "Full name candidate not detected.",
        "passport_number": "Passport number label or candidate not detected.",
        "nationality": "Nationality label or candidate not detected.",
        "date_of_birth": "Date of birth label or candidate not detected.",
        "sex": "Sex marker label not detected and no reliable layout position found.",
        "date_of_expiry": "Date of expiration label or candidate not detected.",
        "date_of_issue": "Date of issue label or candidate not detected.",
        "place_of_birth": "Place of birth label or candidate not detected.",
        "personal_number": "Optional personal number label not detected.",
    }
    for fname, res in results.items():
        if res.status == "unavailable" and not res.notes:
            note = _DEFAULT_DIAGNOSTIC_NOTES.get(fname, f"{fname.replace('_', ' ').capitalize()} label or candidate not detected.")
            results[fname] = VizFieldResult(
                field_name=fname,
                value=None,
                raw_evidence=res.raw_evidence,
                ocr_confidence=res.ocr_confidence,
                status="unavailable",
                notes=[note],
            )

    return results


def _has_intervening_label_below(
    label_idx: int,
    label_block: OcrTextBlock,
    cand_idx: int,
    cand_block: OcrTextBlock,
    all_blocks: List[OcrTextBlock],
) -> bool:
    """Return True if another label block sits vertically between label_block and cand_block."""
    for idx, other in enumerate(all_blocks):
        if idx in {label_idx, cand_idx}:
            continue
        if not _is_label_text(other.text):
            continue
        if other.min_y >= label_block.max_y - 4.0 and other.max_y <= cand_block.min_y + 4.0:
            if abs(other.min_x - label_block.min_x) <= max(200.0, label_block.width * 2.0):
                return True
    return False


def _find_spatial_value_block(
    label_idx: int,
    label_block: OcrTextBlock,
    all_blocks: List[OcrTextBlock],
    claimed_indices: Set[int],
) -> Optional[Tuple[int, OcrTextBlock]]:
    """
    Locate the closest unclaimed non-label block positioned below or to the right of label_block.
    """
    best_candidate: Optional[Tuple[float, int, OcrTextBlock]] = None
    max_vertical_gap = max(180.0, label_block.height * 4.0)
    max_horizontal_offset = max(250.0, label_block.width * 2.5)

    for idx, cand in enumerate(all_blocks):
        if idx == label_idx or idx in claimed_indices:
            continue
        if _is_label_text(cand.text):
            continue

        vertical_gap = cand.min_y - label_block.max_y
        horizontal_delta = abs(cand.min_x - label_block.min_x)
        if -15.0 <= vertical_gap <= max_vertical_gap and horizontal_delta <= max_horizontal_offset:
            if _has_intervening_label_below(label_idx, label_block, idx, cand, all_blocks):
                continue
            score = max(0.0, vertical_gap) + horizontal_delta * 0.5
            if best_candidate is None or score < best_candidate[0]:
                best_candidate = (score, idx, cand)
                continue

        same_line_delta = abs(cand.vertical_center - label_block.vertical_center)
        right_gap = cand.min_x - label_block.max_x
        if same_line_delta <= max(25.0, label_block.height * 1.5) and -15.0 <= right_gap <= 450.0:
            score = max(0.0, right_gap) + same_line_delta * 2.0 + 20.0
            if best_candidate is None or score < best_candidate[0]:
                best_candidate = (score, idx, cand)

    if best_candidate is None:
        return None
    return best_candidate[1], best_candidate[2]
