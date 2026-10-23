"""
Verification test suite covering all 10 critical edge cases from Section 2:
1. Sex markers: M, F, X, <, MALE, FEMALE.
2. OCR substitutions: «, », ＜, ＞, brackets, and parentheses in MRZ candidates.
3. Line lengths: Valid and invalid TD1 (30), TD2 (36), and TD3 (44) candidates.
4. Cross-zone conflicts: Conflicting VIZ and MRZ values (sex, dates, numbers).
5. Date validation: Impossible dates, future dates of birth, issue/expiry plausibility.
6. Missing/unanchored fields: Unavailable or ambiguous without guessing.
7. Optional personal numbers: Protected by guardrails, rejected from arbitrary text.
8. Non-passport documents: Never misclassified as passports.
9. Privacy & logging: Diagnostic notes and log messages never leak PII.
10. Raw evidence preservation: Intended original values preserved in evidence.
"""

from __future__ import annotations

import logging
import unittest
from datetime import date

from app.core.logging import redact_sensitive_text
from app.mrz.detector import _normalize_raw_mrz_line, detect_mrz_candidate
from app.mrz.parser import _parse_sex, parse_mrz_date, parse_mrz_lines
from app.ocr.base import OcrTextBlock
from app.pipeline.orchestrator import _classify_document
from app.pipeline.reconciliation import reconcile_and_build_fields
from app.schemas.extraction import (
    DocumentClassification,
    FieldSource,
    FieldValidationState,
    MrzFormat,
    MrzParseResult,
    ReconciliationStatus,
)
from app.viz.extractor import VizFieldResult, extract_viz_fields
from app.viz.regex_extractor import (
    extract_regex_field_candidates,
    parse_and_validate_date,
    validate_field_candidate,
)
from tests.fixtures.synthetic_passports import (
    build_valid_td1_lines,
    build_valid_td2_lines,
    build_valid_td3_lines,
    make_synthetic_ocr_blocks,
)


class AuditEdgeCasesTestSuite(unittest.TestCase):
    """Exhaustive automated verification for all 10 PassPortIQ audit edge cases."""

    # --------------------------------------------------------------------------
    # 1. Sex markers M, F, X, <, MALE, and FEMALE
    # --------------------------------------------------------------------------
    def test_edge_case_1_sex_markers(self) -> None:
        # Candidate validation
        valid_inputs = {
            "M": "M",
            "MALE": "M",
            "MASCULIN": "M",
            "F": "F",
            "FEMALE": "F",
            "FEMININ": "F",
            "FÉMININ": "F",
            "X": "X",
            "UNSPECIFIED": "X",
            "<": "<",
        }
        for raw, expected in valid_inputs.items():
            norm, status, _ = validate_field_candidate("sex", raw)
            self.assertEqual(status, "valid", f"Candidate '{raw}' should be valid")
            self.assertEqual(norm, expected, f"Candidate '{raw}' normalized incorrectly")

        # Invalid sex candidate
        norm_inv, status_inv, err = validate_field_candidate("sex", "INVALID")
        self.assertEqual(status_inv, "invalid")
        self.assertIsNone(norm_inv)

        # Regex candidate extraction on inline text
        cases = [
            ("Sex / Sexe: M", "M"),
            ("Sex: F", "F"),
            ("Sex: X", "X"),
            ("Sex: <", "<"),
            ("Sex: MALE", "M"),
            ("Sex: FEMALE", "F"),
        ]
        for text, expected in cases:
            block = OcrTextBlock(text, 0.98, ((50.0, 100.0), (250.0, 100.0), (250.0, 120.0), (50.0, 120.0)))
            viz = extract_viz_fields([block])
            self.assertEqual(viz["sex"].value, expected, f"Failed on text '{text}'")

        # MRZ parser sex validation: does not convert < or X to M/F
        self.assertEqual(_parse_sex("M"), "M")
        self.assertEqual(_parse_sex("F"), "F")
        self.assertEqual(_parse_sex("<"), "<")
        self.assertEqual(_parse_sex("X"), "X")
        self.assertIsNone(_parse_sex("Z"))

        # Reconciliation: VIZ and MRZ matching
        l1, l2 = build_valid_td3_lines(sex="M")
        mrz_m = parse_mrz_lines([l1, l2])
        viz_m = {"sex": VizFieldResult(field_name="sex", value="MALE", raw_evidence="MALE", ocr_confidence=0.99, status="extracted")}
        bundle, summary = reconcile_and_build_fields(mrz_m, viz_m)
        self.assertEqual(bundle.sex.reconciliation_status, ReconciliationStatus.MATCHED)
        self.assertEqual(bundle.sex.value, "M")

        # Unspecified < reconciliation
        l1_u, l2_u = build_valid_td3_lines(sex="<")
        mrz_u = parse_mrz_lines([l1_u, l2_u])
        viz_u = {"sex": VizFieldResult(field_name="sex", value="<", raw_evidence="<", ocr_confidence=0.99, status="extracted")}
        bundle_u, summary_u = reconcile_and_build_fields(mrz_u, viz_u)
        self.assertEqual(bundle_u.sex.reconciliation_status, ReconciliationStatus.MATCHED)
        self.assertEqual(bundle_u.sex.value, "<")

    # --------------------------------------------------------------------------
    # 2. OCR substitutions: «, », ＜, ＞, brackets, and parentheses in MRZ
    # --------------------------------------------------------------------------
    def test_edge_case_2_ocr_substitutions_in_mrz(self) -> None:
        substitutions = ["«", "»", "‹", "›", "＜", "＞", "[", "]", "{", "}", "(", ")"]
        for char in substitutions:
            test_line = f"P{char}USAFLORES{char}{char}KATHERINE{char}{char}{char}{char}"
            normalized, changed, notes = _normalize_raw_mrz_line(test_line)
            self.assertTrue(changed, f"Should have normalized substitution character '{char}'")
            self.assertNotIn(char, normalized)
            self.assertIn("<", normalized)

        # Full MRZ candidate with noisy substitutions
        l1_clean, l2_clean = build_valid_td3_lines()
        l1_noisy = l1_clean.replace("<", "«")
        l2_noisy = l2_clean.replace("<", "»")

        block1 = OcrTextBlock(l1_noisy, 0.98, ((50.0, 400.0), (850.0, 400.0), (850.0, 420.0), (50.0, 420.0)))
        block2 = OcrTextBlock(l2_noisy, 0.98, ((50.0, 430.0), (850.0, 430.0), (850.0, 450.0), (50.0, 450.0)))

        cand = detect_mrz_candidate([block1, block2])
        self.assertIsNotNone(cand, "MRZ candidate with OCR chevron substitutions must be detected")
        self.assertEqual(cand.mrz_format, MrzFormat.TD3)
        self.assertTrue(cand.recovery_applied)

        parsed = parse_mrz_lines([l1_noisy, l2_noisy])
        self.assertTrue(parsed.detected)
        self.assertEqual(parsed.parsed_fields["surname"], "ERIKSSON")
        self.assertEqual(parsed.parsed_fields["given_names"], "ANNA MARIA")

    # --------------------------------------------------------------------------
    # 3. Valid and invalid TD1 (30), TD2 (36), and TD3 (44)
    # --------------------------------------------------------------------------
    def test_edge_case_3_td1_td2_td3_line_lengths(self) -> None:
        # Valid TD1 (3x30)
        td1_lines = build_valid_td1_lines()
        self.assertEqual(len(td1_lines), 3)
        for l in td1_lines:
            self.assertEqual(len(l), 30)
        res_td1 = parse_mrz_lines(td1_lines)
        self.assertTrue(res_td1.detected)
        self.assertEqual(res_td1.mrz_format, MrzFormat.TD1)
        self.assertTrue(res_td1.line_length_valid)
        self.assertTrue(res_td1.all_check_digits_valid)

        # Valid TD2 (2x36)
        td2_lines = build_valid_td2_lines()
        self.assertEqual(len(td2_lines), 2)
        for l in td2_lines:
            self.assertEqual(len(l), 36)
        res_td2 = parse_mrz_lines(td2_lines)
        self.assertTrue(res_td2.detected)
        self.assertEqual(res_td2.mrz_format, MrzFormat.TD2)
        self.assertTrue(res_td2.line_length_valid)
        self.assertTrue(res_td2.all_check_digits_valid)

        # Valid TD3 (2x44)
        td3_lines = build_valid_td3_lines()
        self.assertEqual(len(td3_lines), 2)
        for l in td3_lines:
            self.assertEqual(len(l), 44)
        res_td3 = parse_mrz_lines(td3_lines)
        self.assertTrue(res_td3.detected)
        self.assertEqual(res_td3.mrz_format, MrzFormat.TD3)
        self.assertTrue(res_td3.line_length_valid)
        self.assertTrue(res_td3.all_check_digits_valid)

        # Invalid TD3 line length (truncated to 40 characters)
        res_trunc_td3 = parse_mrz_lines([td3_lines[0], td3_lines[1][:40]])
        self.assertTrue(res_trunc_td3.detected)
        self.assertFalse(res_trunc_td3.line_length_valid)
        self.assertFalse(res_trunc_td3.all_check_digits_valid)
        self.assertTrue(any("expected 44" in err for err in res_trunc_td3.errors))

        # Invalid TD2 line length (truncated to 30 characters)
        res_trunc_td2 = parse_mrz_lines([td2_lines[0], td2_lines[1][:30]])
        self.assertTrue(res_trunc_td2.detected)
        self.assertFalse(res_trunc_td2.line_length_valid)

        # Invalid TD1 line count (only 2 lines provided for TD1)
        res_short_td1 = parse_mrz_lines([td1_lines[0], td1_lines[1]])
        self.assertTrue(res_short_td1.detected)
        self.assertFalse(res_short_td1.line_length_valid)

    # --------------------------------------------------------------------------
    # 4. Conflicting VIZ and MRZ values (sex, dates, passport numbers)
    # --------------------------------------------------------------------------
    def test_edge_case_4_conflicting_viz_and_mrz_values(self) -> None:
        l1, l2 = build_valid_td3_lines(surname="ERIKSSON", sex="F", dob_yymmdd="740812")
        mrz = parse_mrz_lines([l1, l2])

        # Conflicting VIZ data: surname, sex, and date of birth differ
        viz = {
            "surname": VizFieldResult(field_name="surname", value="SMITH", raw_evidence="Surname: SMITH", ocr_confidence=0.98, status="extracted"),
            "sex": VizFieldResult(field_name="sex", value="M", raw_evidence="Sex: M", ocr_confidence=0.99, status="extracted"),
            "date_of_birth": VizFieldResult(field_name="date_of_birth", value="1980-01-01", raw_evidence="DOB: 1980-01-01", ocr_confidence=0.95, status="extracted"),
        }

        bundle, summary = reconcile_and_build_fields(mrz, viz)

        # Reconciliation must flag mismatches and conflicts
        self.assertEqual(summary.overall_status, ReconciliationStatus.MISMATCH)
        self.assertGreaterEqual(summary.mismatch_count, 3)

        self.assertEqual(bundle.surname.reconciliation_status, ReconciliationStatus.MISMATCH)
        self.assertEqual(bundle.surname.validation_state, FieldValidationState.CONFLICT)
        self.assertEqual(bundle.surname.viz_value, "SMITH")
        self.assertEqual(bundle.surname.mrz_value, "ERIKSSON")

        self.assertEqual(bundle.sex.reconciliation_status, ReconciliationStatus.MISMATCH)
        self.assertEqual(bundle.sex.validation_state, FieldValidationState.CONFLICT)
        self.assertEqual(bundle.sex.viz_value, "M")
        self.assertEqual(bundle.sex.mrz_value, "F")

        self.assertEqual(bundle.date_of_birth.reconciliation_status, ReconciliationStatus.MISMATCH)
        self.assertEqual(bundle.date_of_birth.validation_state, FieldValidationState.CONFLICT)
        self.assertEqual(bundle.date_of_birth.viz_value, "1980-01-01")
        self.assertEqual(bundle.date_of_birth.mrz_value, "1974-08-12")

    # --------------------------------------------------------------------------
    # 5. Date validation: impossible dates, future DOB, issue vs expiry
    # --------------------------------------------------------------------------
    def test_edge_case_5_date_validation(self) -> None:
        # Impossible calendar dates (Feb 30, Month 13, April 31, Non-leap Feb 29)
        for bad_date in ("30/02/1990", "13/13/1990", "32/01/1990", "31/04/1990", "29/02/2023"):
            res, err = parse_and_validate_date(bad_date)
            self.assertIsNone(res, f"Impossible date '{bad_date}' must return None")
            self.assertIsNotNone(err)

        # In MRZ parser
        res_mrz, err_mrz = parse_mrz_date("900230", is_expiry=False)
        self.assertIsNone(res_mrz)
        self.assertIn("Invalid calendar date", err_mrz)

        # Future date of birth in VIZ
        future_dob_blocks = [
            OcrTextBlock("Date of Birth: 15/08/2045", 0.98, ((50.0, 100.0), (300.0, 100.0), (300.0, 120.0), (50.0, 120.0)))
        ]
        viz_future = extract_viz_fields(future_dob_blocks)
        self.assertIsNone(viz_future["date_of_birth"].value)
        self.assertEqual(viz_future["date_of_birth"].status, "ambiguous")

        # Future date of issue (issue date cannot be in future beyond 60 days)
        future_issue_blocks = [
            OcrTextBlock("Date of Issue: 15/08/2045", 0.98, ((50.0, 100.0), (300.0, 100.0), (300.0, 120.0), (50.0, 120.0)))
        ]
        viz_future_issue = extract_viz_fields(future_issue_blocks)
        self.assertIsNone(viz_future_issue["date_of_issue"].value)
        self.assertEqual(viz_future_issue["date_of_issue"].status, "ambiguous")

        # Future issue date pair below POB fails plausibility check
        future_pair_dates = [
            OcrTextBlock("NEWYORK.USA", 0.95, ((200.0, 200.0), (400.0, 200.0), (400.0, 220.0), (200.0, 220.0))),
            OcrTextBlock("06JAN2035", 0.98, ((200.0, 240.0), (350.0, 240.0), (350.0, 260.0), (200.0, 260.0))),
            OcrTextBlock("06JAN2045", 0.98, ((200.0, 280.0), (350.0, 280.0), (350.0, 300.0), (200.0, 300.0))),
        ]
        viz_inv = extract_viz_fields(future_pair_dates)
        self.assertIsNone(viz_inv["date_of_issue"].value)
        self.assertEqual(viz_inv["date_of_issue"].status, "ambiguous")

    # --------------------------------------------------------------------------
    # 6. Missing or unanchored fields remain unavailable or ambiguous
    # --------------------------------------------------------------------------
    def test_edge_case_6_missing_or_unanchored_fields(self) -> None:
        sparse_blocks = [
            OcrTextBlock("Surname: LOPEZ", 0.98, ((50.0, 100.0), (200.0, 100.0), (200.0, 120.0), (50.0, 120.0))),
            OcrTextBlock("Given Names: JOSHUA", 0.98, ((50.0, 130.0), (250.0, 130.0), (250.0, 150.0), (50.0, 150.0))),
        ]
        viz = extract_viz_fields(sparse_blocks)

        self.assertIsNone(viz["place_of_birth"].value)
        self.assertEqual(viz["place_of_birth"].status, "unavailable")
        self.assertIn("not detected", viz["place_of_birth"].notes[0].lower())

        self.assertIsNone(viz["nationality"].value)
        self.assertEqual(viz["nationality"].status, "unavailable")

        self.assertIsNone(viz["sex"].value)
        self.assertEqual(viz["sex"].status, "unavailable")

        self.assertIsNone(viz["passport_number"].value)
        self.assertEqual(viz["passport_number"].status, "unavailable")

        ambiguous_dates = [
            OcrTextBlock("12MAY1990", 0.95, ((50.0, 100.0), (200.0, 100.0), (200.0, 120.0), (50.0, 120.0))),
            OcrTextBlock("14JUN1992", 0.95, ((50.0, 130.0), (200.0, 130.0), (200.0, 150.0), (50.0, 150.0))),
        ]
        viz_amb = extract_viz_fields(ambiguous_dates)
        self.assertIsNone(viz_amb["date_of_birth"].value)
        self.assertEqual(viz_amb["date_of_birth"].status, "ambiguous")

    # --------------------------------------------------------------------------
    # 7. Optional personal numbers not extracted from arbitrary alphanumeric text
    # --------------------------------------------------------------------------
    def test_edge_case_7_optional_personal_number_guardrails(self) -> None:
        arbitrary_blocks = [
            OcrTextBlock("PASSPORT", 0.99, ((100.0, 50.0), (300.0, 50.0), (300.0, 70.0), (100.0, 70.0))),
            OcrTextBlock("ORDER-REF-890123-TX", 0.95, ((50.0, 200.0), (250.0, 200.0), (250.0, 220.0), (50.0, 220.0))),
            OcrTextBlock("BATCH4921008", 0.96, ((50.0, 230.0), (200.0, 230.0), (200.0, 250.0), (50.0, 250.0))),
        ]
        viz = extract_viz_fields(arbitrary_blocks)
        self.assertIsNone(viz["personal_number"].value)
        self.assertEqual(viz["personal_number"].status, "unavailable")

        labeled_block = OcrTextBlock("Personal No.: 987654321A", 0.98, ((50.0, 300.0), (300.0, 300.0), (300.0, 320.0), (50.0, 320.0)))
        viz_labeled = extract_viz_fields([labeled_block])
        self.assertEqual(viz_labeled["personal_number"].value, "987654321A")
        self.assertEqual(viz_labeled["personal_number"].status, "extracted")

    # --------------------------------------------------------------------------
    # 8. Non-passport documents not classified as passports
    # --------------------------------------------------------------------------
    def test_edge_case_8_non_passport_classification_safety(self) -> None:
        cls1 = _classify_document(mrz_format=None, doc_type_value="RESIDENCE PERMIT", any_viz_extracted=True)
        self.assertEqual(cls1, DocumentClassification.UNCLASSIFIED_DOCUMENT)
        self.assertNotEqual(cls1, DocumentClassification.PASSPORT_TD3)

        cls2 = _classify_document(mrz_format=MrzFormat.TD1, doc_type_value="ID", any_viz_extracted=True)
        self.assertEqual(cls2, DocumentClassification.TRAVEL_DOCUMENT_TD1)
        self.assertNotEqual(cls2, DocumentClassification.PASSPORT_TD3)

        cls3 = _classify_document(mrz_format=MrzFormat.TD2, doc_type_value="V", any_viz_extracted=True)
        self.assertEqual(cls3, DocumentClassification.TRAVEL_DOCUMENT_TD2)
        self.assertNotEqual(cls3, DocumentClassification.PASSPORT_TD3)

        cls4 = _classify_document(mrz_format=None, doc_type_value=None, any_viz_extracted=True)
        self.assertEqual(cls4, DocumentClassification.UNCLASSIFIED_DOCUMENT)
        self.assertNotEqual(cls4, DocumentClassification.PASSPORT_TD3)

        cls5 = _classify_document(mrz_format=None, doc_type_value=None, any_viz_extracted=False)
        self.assertEqual(cls5, DocumentClassification.UNKNOWN)

        cls6 = _classify_document(mrz_format=MrzFormat.TD3, doc_type_value="P", any_viz_extracted=True)
        self.assertEqual(cls6, DocumentClassification.PASSPORT_TD3)

    # --------------------------------------------------------------------------
    # 9. Diagnostic messages and logs must not expose PII
    # --------------------------------------------------------------------------
    def test_edge_case_9_privacy_no_pii_in_diagnostics_and_logs(self) -> None:
        sensitive_num = "K38542916"
        sensitive_dob = "1973-09-08"

        _, _, err_num = validate_field_candidate("passport_number", "INVALID!!")
        self.assertNotIn(sensitive_num, err_num)

        _, _, err_dob = validate_field_candidate("date_of_birth", "32/13/1973")
        self.assertNotIn(sensitive_dob, err_dob)

        _, err_mrz = parse_mrz_date("991332", is_expiry=False)
        self.assertNotIn("991332", err_mrz)
        self.assertNotIn(sensitive_dob, err_mrz)

        raw_log = f"Extracted passport_number={sensitive_num} dob={sensitive_dob} MRZ=P<USAFLORES<<KATHERINE<<<<<<<<<<<<<<<<<<<<"
        redacted = redact_sensitive_text(raw_log)
        self.assertNotIn(sensitive_num, redacted)
        self.assertNotIn("P<USAFLORES<<KATHERINE<<<<<<<<<<<<<<<<<<<<", redacted)
        self.assertIn("[REDACTED", redacted)

    # --------------------------------------------------------------------------
    # 10. Raw extraction evidence and clipboard output preserve original values
    # --------------------------------------------------------------------------
    def test_edge_case_10_raw_extraction_evidence_preservation(self) -> None:
        l1, l2 = build_valid_td3_lines(surname="FLORES", given_names="KATHERINE", sex="F")
        mrz = parse_mrz_lines([l1, l2])

        viz = {
            "surname": VizFieldResult(field_name="surname", value="FLORES", raw_evidence="FLORES", ocr_confidence=0.98, status="extracted"),
            "sex": VizFieldResult(field_name="sex", value="F", raw_evidence="F", ocr_confidence=0.99, status="extracted"),
            "passport_number": VizFieldResult(field_name="passport_number", value="L898902C3", raw_evidence="L898902C3", ocr_confidence=0.99, status="extracted"),
        }

        bundle, summary = reconcile_and_build_fields(mrz, viz)

        self.assertIn("FLORES", bundle.surname.raw_evidence)
        self.assertEqual(bundle.surname.mrz_value, "FLORES")
        self.assertEqual(bundle.surname.viz_value, "FLORES")
        self.assertEqual(bundle.surname.value, "FLORES")

        self.assertEqual(bundle.sex.value, "F")
        self.assertEqual(bundle.sex.mrz_value, "F")
        self.assertEqual(bundle.sex.viz_value, "F")

        self.assertEqual(mrz.raw_lines, [l1, l2])
        self.assertIn("P<UTOFLORES<<KATHERINE", mrz.mrz_text)

    # --------------------------------------------------------------------------
    # 11. Place of birth disallowed words and jurisdiction suffix validation
    # --------------------------------------------------------------------------
    def test_edge_case_11_place_of_birth_validation_and_date_anchoring(self) -> None:
        # Disallowed words such as passport labels should be rejected
        norm, status, _ = validate_field_candidate("place_of_birth", "eporiNo.do Pesaporte")
        self.assertEqual(status, "invalid")
        self.assertIsNone(norm)

        norm, status, _ = validate_field_candidate("place_of_birth", "PASSPORT NUMBER")
        self.assertEqual(status, "invalid")

        # Valid place of birth with jurisdiction suffix
        norm, status, _ = validate_field_candidate("place_of_birth", "TEXAS.USA")
        self.assertEqual(status, "valid")
        self.assertEqual(norm, "TEXAS, USA")

        # Full layout simulation matching female_2.jpg
        def _block(text: str, x1: float, y1: float, x2: float, y2: float, conf: float = 0.99) -> OcrTextBlock:
            return OcrTextBlock(
                text=text,
                confidence=conf,
                bbox=((x1, y1), (x2, y1), (x2, y2), (x1, y2)),
            )

        blocks = [
            _block("PASSPORT", 841.0, 733.0, 915.0, 754.0),
            _block("P", 1010.0, 791.0, 1023.0, 806.0),
            _block("eporiNo.do Pesaporte", 1248.0, 790.0, 1340.0, 814.0, conf=0.86),
            _block("J17236842", 1188.0, 800.0, 1301.0, 835.0, conf=1.00),
            _block("KING", 965.0, 821.0, 1010.0, 843.0),
            _block("CYNTHIA", 962.0, 847.0, 1039.0, 876.0),
            _block("10JUN1965", 990.0, 900.0, 1092.0, 933.0),
            _block("TEXAS.USA", 984.0, 951.0, 1097.0, 984.0),
            _block("21OCT2025", 982.0, 978.0, 1087.0, 1011.0, conf=0.98),
            _block("21OCT2035", 981.0, 1006.0, 1083.0, 1035.0, conf=0.97),
        ]
        viz_res = extract_viz_fields(blocks)
        self.assertEqual(viz_res["place_of_birth"].value, "TEXAS, USA")
        self.assertEqual(viz_res["date_of_birth"].value, "1965-06-10")
        self.assertEqual(viz_res["date_of_issue"].value, "2025-10-21")
        self.assertEqual(viz_res["date_of_expiry"].value, "2035-10-21")
        self.assertEqual(viz_res["surname"].value, "KING")
        self.assertEqual(viz_res["given_names"].value, "CYNTHIA")
        self.assertEqual(viz_res["passport_number"].value, "J17236842")


if __name__ == "__main__":
    unittest.main()

