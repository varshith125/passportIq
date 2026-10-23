"""Reconciliation and field-status assembly comparing MRZ and VIZ extraction results."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from app.schemas.extraction import (
    ExtractedField,
    FieldReconciliationItem,
    FieldSource,
    FieldValidationState,
    MrzParseResult,
    PassportFieldsBundle,
    ReconciliationStatus,
    ReconciliationSummary,
)
from app.viz.extractor import VizFieldResult

# Common ISO-3166-1 alpha-3 country/nationality mappings for VIZ full-name comparison
_COUNTRY_SYNONYMS: Dict[str, str] = {
    "UNITED STATES OF AMERICA": "USA",
    "UNITED STATES": "USA",
    "AMERICAN": "USA",
    "UNITED KINGDOM": "GBR",
    "BRITISH CITIZEN": "GBR",
    "BRITISH": "GBR",
    "GREAT BRITAIN": "GBR",
    "CANADA": "CAN",
    "CANADIAN": "CAN",
    "INDIA": "IND",
    "INDIAN": "IND",
    "REPUBLIC OF INDIA": "IND",
    "GERMANY": "D",
    "DEUTSCH": "D",
    "DEU": "D",
    "FRANCE": "FRA",
    "FRENCH": "FRA",
    "FRANCAISE": "FRA",
    "FRANÇAISE": "FRA",
    "AUSTRALIA": "AUS",
    "AUSTRALIAN": "AUS",
    "JAPAN": "JPN",
    "JAPANESE": "JPN",
    "SINGAPORE": "SGP",
    "UTOPIA": "UTO",
}

_FIELD_LABELS: Dict[str, str] = {
    "document_type": "Document Type",
    "issuing_country": "Issuing Country / Authority",
    "surname": "Surname",
    "given_names": "Given Names",
    "full_name": "Full Name",
    "passport_number": "Passport Number",
    "nationality": "Nationality",
    "date_of_birth": "Date of Birth",
    "sex": "Sex",
    "date_of_expiry": "Date of Expiry",
    "date_of_issue": "Date of Issue",
    "place_of_birth": "Place of Birth",
    "personal_number": "Personal / Optional Number",
}

# Fields that exist only in the VIZ (not encoded in standard ICAO 9303 TD1/TD2/TD3 MRZ)
_VIZ_ONLY_FIELDS = {"date_of_issue", "place_of_birth"}

# Fields with dedicated ICAO 9303 check digits in MRZ
_CHECK_DIGIT_FIELDS = {
    "passport_number",
    "date_of_birth",
    "date_of_expiry",
    "personal_number",
}


def _normalize_for_comparison(field_name: str, value: Optional[str]) -> Optional[str]:
    """Normalize a field value into a canonical form for cross-zone comparison."""
    if value is None:
        return None
    cleaned = value.strip().upper()
    if not cleaned:
        return None

    if field_name in {"issuing_country", "nationality"}:
        if cleaned in _COUNTRY_SYNONYMS:
            return _COUNTRY_SYNONYMS[cleaned]
        compact_c = "".join(cleaned.split())
        for syn, code in _COUNTRY_SYNONYMS.items():
            if compact_c == "".join(syn.split()):
                return code
        if len(cleaned) == 3 and cleaned.isalpha():
            return "D" if cleaned == "DEU" else cleaned

    if field_name == "document_type":
        # MRZ 'P' or 'PO' vs VIZ 'P'
        return cleaned[0] if cleaned.startswith("P") else cleaned

    if field_name in {"surname", "given_names", "full_name"}:
        # Replace hyphens/punctuation with spaces so MRZ space-separated tokens match VIZ hyphenated names
        cleaned = re.sub(r"[^A-Z0-9]+", " ", cleaned).strip()
        return re.sub(r"\s+", " ", cleaned)

    if field_name == "sex":
        if cleaned in {"M", "MALE", "MASCULIN", "HOMBRE"}:
            return "M"
        if cleaned in {"F", "FEMALE", "FEMININ", "FÉMININ", "MUJER"}:
            return "F"
        if cleaned in {"X", "UNSPECIFIED"}:
            return "X"
        if cleaned == "<":
            return "<"
        return cleaned

    if field_name in {"passport_number", "personal_number"}:
        return re.sub(r"[^A-Z0-9]", "", cleaned)

    return cleaned


def reconcile_and_build_fields(
    mrz_result: MrzParseResult,
    viz_results: Dict[str, VizFieldResult],
) -> Tuple[PassportFieldsBundle, ReconciliationSummary]:
    """
    Compare MRZ and VIZ extractions field-by-field and produce honest validation and reconciliation states.

    - Never reports reconciliation as `matched` when `compared_fields_count == 0`.
    - Distinguishes MRZ check-digit validation from format validation and cross-source agreement.
    """
    check_digit_map = {cd.field_name: cd.is_valid for cd in mrz_result.check_digits}
    reconciliation_items: List[FieldReconciliationItem] = []
    extracted_fields: Dict[str, ExtractedField] = {}

    compared_count = 0
    matched_count = 0
    mismatch_count = 0
    insufficient_count = 0
    not_checked_count = 0

    for field_name, label in _FIELD_LABELS.items():
        mrz_val = mrz_result.parsed_fields.get(field_name) if mrz_result.detected else None
        viz_entry = viz_results.get(field_name)
        viz_val = viz_entry.value if viz_entry else None

        norm_mrz = _normalize_for_comparison(field_name, mrz_val)
        norm_viz = _normalize_for_comparison(field_name, viz_val)

        notes: List[str] = []
        if viz_entry and viz_entry.notes:
            notes.extend(viz_entry.notes)

        # Determine reconciliation status
        if field_name in _VIZ_ONLY_FIELDS:
            rec_status = ReconciliationStatus.NOT_CHECKED
            not_checked_count += 1
            explanation = (
                f"'{label}' is a VIZ-only field and is not encoded in standard ICAO 9303 MRZ lines."
            )
        elif norm_mrz is not None and norm_viz is not None:
            compared_count += 1
            if norm_mrz == norm_viz:
                rec_status = ReconciliationStatus.MATCHED
                matched_count += 1
                explanation = f"MRZ value ('{mrz_val}') and VIZ value ('{viz_val}') agree."
            else:
                rec_status = ReconciliationStatus.MISMATCH
                mismatch_count += 1
                explanation = (
                    f"Discrepancy detected: MRZ parsed '{mrz_val}' while VIZ extracted '{viz_val}'."
                )
                notes.append(explanation)
        elif norm_mrz is not None:
            rec_status = ReconciliationStatus.MRZ_ONLY
            insufficient_count += 1
            explanation = "Present in MRZ only; VIZ value was unavailable for cross-check."
        elif norm_viz is not None:
            rec_status = ReconciliationStatus.VIZ_ONLY
            insufficient_count += 1
            explanation = "Present in VIZ only; MRZ value was unavailable for cross-check."
        else:
            rec_status = ReconciliationStatus.INSUFFICIENT_DATA
            insufficient_count += 1
            explanation = "Neither MRZ nor VIZ yielded a readable value for this field."

        reconciliation_items.append(
            FieldReconciliationItem(
                field_name=field_name,
                mrz_value=mrz_val,
                viz_value=viz_val,
                normalized_mrz=norm_mrz,
                normalized_viz=norm_viz,
                status=rec_status,
                explanation=explanation,
            )
        )

        # Determine primary value, source, validation_state, and confidence
        if rec_status == ReconciliationStatus.MATCHED and mrz_val is not None:
            primary_value: Optional[str] = viz_val if field_name in {"surname", "given_names", "full_name"} and viz_val else mrz_val
            source = FieldSource.RECONCILED
            if field_name in _CHECK_DIGIT_FIELDS and field_name in check_digit_map:
                val_state = (
                    FieldValidationState.VALID_CHECK_DIGIT
                    if check_digit_map[field_name]
                    else FieldValidationState.INVALID_CHECK_DIGIT
                )
            else:
                val_state = FieldValidationState.VALID_FORMAT
        elif rec_status == ReconciliationStatus.MISMATCH:
            # In case of mismatch on check-digit fields, prefer check-digit backed MRZ.
            # On name fields without MRZ check digits where MRZ was truncated/clipped (MRZ is a suffix of VIZ),
            # prefer the fuller VIZ name while keeping the CONFLICT state explicit.
            if (
                field_name in {"surname", "given_names", "full_name"}
                and viz_val
                and mrz_val
                and viz_val.endswith(mrz_val)
                and len(viz_val) > len(mrz_val)
            ):
                primary_value = viz_val
                source = FieldSource.VIZ
            else:
                primary_value = mrz_val or viz_val
                source = FieldSource.MRZ if mrz_val is not None else FieldSource.VIZ
            val_state = FieldValidationState.CONFLICT
        elif mrz_val is not None:
            primary_value = mrz_val
            source = FieldSource.DERIVED if field_name == "full_name" else FieldSource.MRZ
            if field_name in _CHECK_DIGIT_FIELDS and field_name in check_digit_map:
                val_state = (
                    FieldValidationState.VALID_CHECK_DIGIT
                    if check_digit_map[field_name]
                    else FieldValidationState.INVALID_CHECK_DIGIT
                )
            else:
                val_state = FieldValidationState.VALID_FORMAT
        elif viz_val is not None:
            primary_value = viz_val
            source = FieldSource.DERIVED if field_name == "full_name" else FieldSource.VIZ
            val_state = FieldValidationState.VALID_FORMAT
        else:
            primary_value = None
            source = FieldSource.UNAVAILABLE
            if viz_entry and viz_entry.status == "ambiguous":
                val_state = FieldValidationState.UNVERIFIED
            elif field_name in _CHECK_DIGIT_FIELDS and field_name in check_digit_map and not check_digit_map[field_name]:
                val_state = FieldValidationState.INVALID_CHECK_DIGIT
            else:
                val_state = FieldValidationState.MISSING

            if not notes:
                if field_name == "sex":
                    notes.append("Sex marker label not detected and no reliable layout position found.")
                elif field_name == "document_type":
                    notes.append("Document type label or header not detected; unclassified document layout.")
                elif field_name == "personal_number":
                    notes.append("Optional personal number label not detected and not encoded in MRZ.")
                elif field_name in {"date_of_birth", "date_of_issue", "date_of_expiry"}:
                    notes.append(f"{label} label not detected and no candidate found in expected document position.")
                else:
                    notes.append(f"{label} label or candidate not detected.")

        # Confidence and raw evidence
        confs: List[float] = []
        if mrz_val is not None and mrz_result.ocr_confidence is not None:
            confs.append(mrz_result.ocr_confidence)
        if viz_entry and viz_entry.ocr_confidence is not None and viz_val is not None:
            confs.append(viz_entry.ocr_confidence)
        field_conf = round(sum(confs) / len(confs), 4) if confs else None

        raw_ev_parts: List[str] = []
        if mrz_val is not None:
            raw_ev_parts.append(f"MRZ:{mrz_val}")
        if viz_entry and viz_entry.raw_evidence:
            raw_ev_parts.append(f"VIZ:{viz_entry.raw_evidence}")
        raw_evidence = " | ".join(raw_ev_parts) if raw_ev_parts else None

        extracted_fields[field_name] = ExtractedField(
            field_name=field_name,
            label=label,
            value=primary_value,
            raw_evidence=raw_evidence,
            source=source,
            validation_state=val_state,
            ocr_confidence=field_conf,
            reconciliation_status=rec_status,
            mrz_value=mrz_val,
            viz_value=viz_val,
            notes=notes,
        )

    # Ensure bidirectional name derivation
    fn_field = extracted_fields.get("full_name")
    sn_field = extracted_fields.get("surname")
    gn_field = extracted_fields.get("given_names")

    if (not fn_field or not fn_field.value) and sn_field and sn_field.value and gn_field and gn_field.value:
        extracted_fields["full_name"] = ExtractedField(
            field_name="full_name",
            label="Full Name",
            value=f"{gn_field.value} {sn_field.value}",
            source=FieldSource.DERIVED,
            validation_state=FieldValidationState.VALID_FORMAT,
            ocr_confidence=gn_field.ocr_confidence,
            reconciliation_status=gn_field.reconciliation_status,
            notes=["Derived from extracted given names and surname."],
        )
    elif fn_field and fn_field.value:
        parts = fn_field.value.split()
        if len(parts) >= 2:
            if not gn_field or not gn_field.value:
                extracted_fields["given_names"] = ExtractedField(
                    field_name="given_names",
                    label="Given Names",
                    value=" ".join(parts[:-1]),
                    source=FieldSource.DERIVED,
                    validation_state=FieldValidationState.VALID_FORMAT,
                    ocr_confidence=fn_field.ocr_confidence,
                    reconciliation_status=fn_field.reconciliation_status,
                    notes=["Derived from full name."],
                )
            if not sn_field or not sn_field.value:
                extracted_fields["surname"] = ExtractedField(
                    field_name="surname",
                    label="Surname",
                    value=parts[-1],
                    source=FieldSource.DERIVED,
                    validation_state=FieldValidationState.VALID_FORMAT,
                    ocr_confidence=fn_field.ocr_confidence,
                    reconciliation_status=fn_field.reconciliation_status,
                    notes=["Derived from full name."],
                )

    # Overall reconciliation status: never claim MATCHED when compared_count == 0
    if compared_count == 0:
        overall_rec = ReconciliationStatus.INSUFFICIENT_DATA
    elif mismatch_count > 0:
        overall_rec = ReconciliationStatus.MISMATCH
    else:
        overall_rec = ReconciliationStatus.MATCHED

    summary = ReconciliationSummary(
        overall_status=overall_rec,
        compared_fields_count=compared_count,
        matched_count=matched_count,
        mismatch_count=mismatch_count,
        insufficient_data_count=insufficient_count,
        not_checked_count=not_checked_count,
        items=reconciliation_items,
    )

    bundle = PassportFieldsBundle(**extracted_fields)
    return bundle, summary
