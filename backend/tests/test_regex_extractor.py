"""
Comprehensive automated tests for the Regex extraction layer.
Covers all 20 scenarios required by the PassPortIQ specification:
1. Labeled surname extraction.
2. Labeled given-name extraction with multiple names.
3. Full-name derivation without changing the source fields.
4. Date of birth in supported formats.
5. Impossible calendar dates.
6. Date-of-birth versus issue/expiry-date confusion.
7. Passport numbers with letters and digits.
8. False passport-number candidates in unrelated text.
9. Nationality validation.
10. Sex-marker extraction.
11. Place-of-birth extraction.
12. OCR punctuation and whitespace variations.
13. Missing and incomplete OCR text.
14. Multiple conflicting candidates.
15. MRZ success and MRZ failure.
16. VIZ extraction when MRZ parsing fails.
17. VIZ/MRZ mismatch and insufficient-data statuses.
18. Residence permits or unsupported layouts.
19. OCR text containing misleading labels or malformed values.
20. API response compatibility and serialization.
"""

from __future__ import annotations

import unittest

from app.mrz.parser import parse_mrz_lines
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
    clean_label_remainder,
    extract_regex_field_candidates,
    normalize_field_ocr_confusions,
    parse_and_validate_date,
    validate_field_candidate,
)
from tests.fixtures.synthetic_passports import build_valid_td3_lines


class RegexExtractorTestSuite(unittest.TestCase):
    """Test suite verifying robust Regex extraction, validation, and reconciliation."""

    # 1. Labeled surname extraction
    def test_labeled_surname_extraction(self) -> None:
        examples = [
            ("Surname: GUMMADI", "GUMMADI"),
            ("Family Name: SMITH", "SMITH"),
            ("Last Name: JOHNSON-WILLIAMS", "JOHNSON-WILLIAMS"),
            ("Nom / Surname: DUPONT", "DUPONT"),
            ("Apellidos: GARCIA LOPEZ", "GARCIA LOPEZ"),
        ]
        for line, expected in examples:
            block = OcrTextBlock(line, 0.98, ((50.0, 100.0), (300.0, 100.0), (300.0, 120.0), (50.0, 120.0)))
            res = extract_viz_fields([block])
            self.assertEqual(res["surname"].value, expected, f"Failed on: {line}")
            self.assertEqual(res["surname"].status, "extracted")

    # 2. Labeled given-name extraction with multiple names
    def test_labeled_given_names_with_multiple_names(self) -> None:
        examples = [
            ("Given Names: VENKATA VARSHITH", "VENKATA VARSHITH"),
            ("Given Name: ANNA MARIA", "ANNA MARIA"),
            ("First Name: JEAN-LUC", "JEAN-LUC"),
            ("Prénoms: MARIE CLAIRE O'NEILL", "MARIE CLAIRE O'NEILL"),
            ("Forenames: CHARLES PHILIP ARTHUR", "CHARLES PHILIP ARTHUR"),
        ]
        for line, expected in examples:
            block = OcrTextBlock(line, 0.98, ((50.0, 100.0), (400.0, 100.0), (400.0, 120.0), (50.0, 120.0)))
            res = extract_viz_fields([block])
            self.assertEqual(res["given_names"].value, expected, f"Failed on: {line}")
            self.assertEqual(res["given_names"].status, "extracted")

    # 3. Full-name derivation without changing source fields
    def test_full_name_derivation_without_mutating_components(self) -> None:
        b1 = OcrTextBlock("Surname: GUMMADI", 0.98, ((50.0, 100.0), (250.0, 100.0), (250.0, 120.0), (50.0, 120.0)))
        b2 = OcrTextBlock("Given Names: VENKATA VARSHITH", 0.98, ((50.0, 130.0), (380.0, 130.0), (380.0, 150.0), (50.0, 150.0)))

        res = extract_viz_fields([b1, b2])
        self.assertEqual(res["surname"].value, "GUMMADI")
        self.assertEqual(res["given_names"].value, "VENKATA VARSHITH")
        self.assertEqual(res["full_name"].value, "VENKATA VARSHITH GUMMADI")
        self.assertIn("Derived", res["full_name"].notes[0])

    # 4. Date of birth in supported formats
    def test_date_of_birth_supported_formats(self) -> None:
        cases = [
            ("DOB: 27/11/2004", "2004-11-27"),
            ("Date of Birth: 27-11-2004", "2004-11-27"),
            ("Date of Birth: 2004-11-27", "2004-11-27"),
            ("Date of Birth: 27.11.2004", "2004-11-27"),
            ("Date of Birth: 14 OCT 1988", "1988-10-14"),
            ("DOB: 12 AUG 1974", "1974-08-12"),
            ("DOB: 08SEP1973", "1973-09-08"),
            ("Date of Birth: 06JAN2024", "2024-01-06"),
        ]
        for line, expected_iso in cases:
            block = OcrTextBlock(line, 0.98, ((50.0, 100.0), (350.0, 100.0), (350.0, 120.0), (50.0, 120.0)))
            res = extract_viz_fields([block])
            self.assertEqual(res["date_of_birth"].value, expected_iso, f"Failed on: {line}")
            self.assertEqual(res["date_of_birth"].status, "extracted")

    # 5. Impossible calendar dates rejected
    def test_impossible_calendar_dates_rejected(self) -> None:
        invalid_dates = [
            "31/02/2004",  # Feb 31 does not exist
            "30/02/2020",  # Feb 30 does not exist
            "31/04/2021",  # April has only 30 days
            "31/06/2022",  # June has only 30 days
            "31/09/2023",  # September has only 30 days
            "31/11/2024",  # November has only 30 days
            "29/02/2001",  # 2001 was not a leap year
            "99/99/1999",  # Month 99 / Day 99
        ]
        for bad_date in invalid_dates:
            val, err = parse_and_validate_date(bad_date)
            self.assertIsNone(val, f"Should reject impossible date: {bad_date}")
            self.assertIsNotNone(err)

            # In full extractor pipeline
            block = OcrTextBlock(f"Date of Birth: {bad_date}", 0.98, ((50.0, 100.0), (350.0, 100.0), (350.0, 120.0), (50.0, 120.0)))
            res = extract_viz_fields([block])
            self.assertIsNone(res["date_of_birth"].value)
            self.assertEqual(res["date_of_birth"].status, "ambiguous")

    # 6. Date of birth vs issue vs expiry date separation
    def test_date_separation_does_not_confuse_dates(self) -> None:
        blocks = [
            OcrTextBlock("Date of Birth: 12 AUG 1974", 0.98, ((50.0, 100.0), (300.0, 100.0), (300.0, 120.0), (50.0, 120.0))),
            OcrTextBlock("Date of Issue: 15 APR 2020", 0.98, ((50.0, 140.0), (300.0, 140.0), (300.0, 160.0), (50.0, 160.0))),
            OcrTextBlock("Date of Expiry: 15 APR 2030", 0.98, ((50.0, 180.0), (300.0, 180.0), (300.0, 200.0), (50.0, 200.0))),
        ]
        res = extract_viz_fields(blocks)
        self.assertEqual(res["date_of_birth"].value, "1974-08-12")
        self.assertEqual(res["date_of_issue"].value, "2020-04-15")
        self.assertEqual(res["date_of_expiry"].value, "2030-04-15")

    # 7. Passport numbers with letters and digits
    def test_passport_numbers_with_letters_and_digits(self) -> None:
        examples = [
            ("Passport No: L898902C3", "L898902C3"),
            ("Passport Number: 990280124", "990280124"),
            ("Document No: Z1234567A", "Z1234567A"),
            ("Passnummer: C01X00T47", "C01X00T47"),
        ]
        for line, expected in examples:
            block = OcrTextBlock(line, 0.98, ((50.0, 100.0), (300.0, 100.0), (300.0, 120.0), (50.0, 120.0)))
            res = extract_viz_fields([block])
            self.assertEqual(res["passport_number"].value, expected)
            self.assertEqual(res["passport_number"].status, "extracted")

    # 8. False passport-number candidates in unrelated text
    def test_false_passport_number_candidates_rejected(self) -> None:
        # A long dictionary word or sentence should not be accepted as passport number
        val, status, err = validate_field_candidate("passport_number", "AUTHENTICATION")
        self.assertEqual(status, "invalid")
        self.assertIsNone(val)

        # Dates must never be accepted as passport numbers
        for date_str in ["08SEP1973", "06JAN2024", "15AUG1990"]:
            val_date, status_date, _ = validate_field_candidate("passport_number", date_str)
            self.assertEqual(status_date, "invalid", f"Date should not pass as passport number: {date_str}")
            self.assertIsNone(val_date)

    # 9. Nationality validation against ISO registry
    def test_nationality_validation_against_registry(self) -> None:
        valid_nationalities = [
            ("Nationality: INDIAN", "INDIAN"),
            ("Nationality: AMERICAN", "AMERICAN"),
            ("Nationality: BRITISH", "BRITISH"),
            ("Nationality: CANADIAN", "CANADIAN"),
            ("Nationality: FRA", "FRA"),
            ("Nationality: UTOPIA", "UTOPIA"),
        ]
        for line, expected in valid_nationalities:
            block = OcrTextBlock(line, 0.98, ((50.0, 100.0), (300.0, 100.0), (300.0, 120.0), (50.0, 120.0)))
            res = extract_viz_fields([block])
            self.assertEqual(res["nationality"].value, expected)
            self.assertEqual(res["nationality"].status, "extracted")

    # 10. Sex-marker extraction
    def test_sex_marker_extraction(self) -> None:
        markers = [
            ("Sex: M", "M"),
            ("Sex: F", "F"),
            ("Gender: X", "X"),
            ("Sexe: MALE", "M"),
            ("Sex: FEMALE", "F"),
        ]
        for line, expected in markers:
            block = OcrTextBlock(line, 0.98, ((50.0, 100.0), (250.0, 100.0), (250.0, 120.0), (50.0, 120.0)))
            res = extract_viz_fields([block])
            self.assertEqual(res["sex"].value, expected)
            self.assertEqual(res["sex"].status, "extracted")

    # 11. Place of birth extraction
    def test_place_of_birth_extraction(self) -> None:
        examples = [
            ("Place of Birth: HYDERABAD, INDIA", "HYDERABAD, INDIA"),
            ("Place of birth / Lieu de naissance: FLORIDA, U.S.A.", "FLORIDA, U.S.A."),
            ("Birthplace: STOCKHOLM", "STOCKHOLM"),
        ]
        for line, expected in examples:
            block = OcrTextBlock(line, 0.98, ((50.0, 100.0), (450.0, 100.0), (450.0, 120.0), (50.0, 120.0)))
            res = extract_viz_fields([block])
            self.assertEqual(res["place_of_birth"].value, expected)
            self.assertEqual(res["place_of_birth"].status, "extracted")

    # 12. OCR punctuation and whitespace variations
    def test_ocr_punctuation_and_whitespace_variations(self) -> None:
        noisy_lines = [
            ("Surname  :   VARSHITH  ", "surname", "VARSHITH"),
            ("Given  Names- - -VENKATA", "given_names", "VENKATA"),
            ("Passport  No  .  :  L898902C3", "passport_number", "L898902C3"),
            ("DOB :  27 / 11 / 2004", "date_of_birth", "2004-11-27"),
        ]
        for line, field_name, expected in noisy_lines:
            block = OcrTextBlock(line, 0.95, ((50.0, 100.0), (400.0, 100.0), (400.0, 120.0), (50.0, 120.0)))
            res = extract_viz_fields([block])
            self.assertEqual(res[field_name].value, expected)

    # 13. Missing and incomplete OCR text
    def test_missing_ocr_text_returns_unavailable_not_fabricated(self) -> None:
        res = extract_viz_fields([])
        for field_name, fld in res.items():
            self.assertIsNone(fld.value, f"{field_name} should be None")
            self.assertEqual(fld.status, "unavailable")

    # 14. Multiple conflicting candidates prioritized by label context
    def test_conflicting_candidates_prioritized_by_label(self) -> None:
        blocks = [
            OcrTextBlock("Random Number: 12345678", 0.85, ((50.0, 50.0), (250.0, 50.0), (250.0, 70.0), (50.0, 70.0))),
            OcrTextBlock("Passport No: P98765432", 0.98, ((50.0, 100.0), (250.0, 100.0), (250.0, 120.0), (50.0, 120.0))),
        ]
        res = extract_viz_fields(blocks)
        self.assertEqual(res["passport_number"].value, "P98765432")

    # 15. MRZ success and MRZ failure
    def test_mrz_success_and_mrz_failure(self) -> None:
        l1, l2 = build_valid_td3_lines()
        success_mrz = parse_mrz_lines([l1, l2])
        self.assertTrue(success_mrz.detected)
        self.assertTrue(success_mrz.all_check_digits_valid)

        corrupt_l2 = l2[:9] + "0" + l2[10:]
        failed_mrz = parse_mrz_lines([l1, corrupt_l2])
        self.assertTrue(failed_mrz.detected)
        self.assertFalse(failed_mrz.all_check_digits_valid)

    # 16. VIZ extraction when MRZ parsing fails
    def test_viz_extraction_continues_when_mrz_fails(self) -> None:
        # Document with corrupted MRZ lines but clear VIZ
        corrupt_mrz = ["P<USAINVALID<<<MRZ<<<<<<<<<<<<<<<<<<<<<<", "MALFORMED_LINE_TOO_SHORT"]
        blocks = [
            OcrTextBlock("Surname: GUMMADI", 0.98, ((50.0, 100.0), (250.0, 100.0), (250.0, 120.0), (50.0, 120.0))),
            OcrTextBlock("Given Names: VARSHITH", 0.98, ((50.0, 130.0), (280.0, 130.0), (280.0, 150.0), (50.0, 150.0))),
            OcrTextBlock("Passport No: N1234567", 0.98, ((50.0, 160.0), (280.0, 160.0), (280.0, 180.0), (50.0, 180.0))),
            OcrTextBlock(corrupt_mrz[0], 0.90, ((50.0, 400.0), (600.0, 400.0), (600.0, 420.0), (50.0, 420.0))),
            OcrTextBlock(corrupt_mrz[1], 0.85, ((50.0, 430.0), (400.0, 430.0), (400.0, 450.0), (50.0, 450.0))),
        ]
        viz = extract_viz_fields(blocks, mrz_raw_lines=corrupt_mrz)
        self.assertEqual(viz["surname"].value, "GUMMADI")
        self.assertEqual(viz["given_names"].value, "VARSHITH")
        self.assertEqual(viz["passport_number"].value, "N1234567")

    # 17. VIZ/MRZ mismatch and reconciliation statuses
    def test_reconciliation_single_source_and_mismatch_statuses(self) -> None:
        l1, l2 = build_valid_td3_lines(surname="ERIKSSON")
        mrz = parse_mrz_lines([l1, l2])
        viz = {
            "surname": VizFieldResult(
                field_name="surname",
                value="ANDERSSON",
                raw_evidence="Surname: ANDERSSON",
                ocr_confidence=0.95,
                status="extracted",
            ),
            "place_of_birth": VizFieldResult(
                field_name="place_of_birth",
                value="HYDERABAD",
                raw_evidence="Place of Birth: HYDERABAD",
                ocr_confidence=0.96,
                status="extracted",
            ),
        }
        bundle, summary = reconcile_and_build_fields(mrz, viz)

        # Mismatch
        self.assertEqual(bundle.surname.reconciliation_status, ReconciliationStatus.MISMATCH)
        self.assertEqual(bundle.surname.validation_state, FieldValidationState.CONFLICT)

        # MRZ only
        self.assertEqual(bundle.passport_number.reconciliation_status, ReconciliationStatus.MRZ_ONLY)

        # VIZ only / not checked
        self.assertEqual(bundle.place_of_birth.reconciliation_status, ReconciliationStatus.NOT_CHECKED)

    # 18. Residence permits and unclassified documents
    def test_unclassified_document_not_forced_to_passport_td3(self) -> None:
        doc_class = _classify_document(
            mrz_format=None,
            doc_type_value="ID",
            any_viz_extracted=True,
        )
        self.assertEqual(doc_class, DocumentClassification.UNCLASSIFIED_DOCUMENT)

        doc_unknown = _classify_document(
            mrz_format=None,
            doc_type_value=None,
            any_viz_extracted=False,
        )
        self.assertEqual(doc_unknown, DocumentClassification.UNKNOWN)

    # 19. Misleading labels and malformed values
    def test_misleading_labels_and_malformed_values(self) -> None:
        # A line where label has no value and is followed by another label
        blocks = [
            OcrTextBlock("Surname:", 0.98, ((50.0, 100.0), (150.0, 100.0), (150.0, 120.0), (50.0, 120.0))),
            OcrTextBlock("Given Names:", 0.98, ((50.0, 130.0), (180.0, 130.0), (180.0, 150.0), (50.0, 150.0))),
        ]
        res = extract_viz_fields(blocks)
        self.assertIsNone(res["surname"].value)
        self.assertEqual(res["surname"].status, "unavailable")

    # 20. Candidate model serialization compatibility
    def test_candidate_model_and_response_serialization(self) -> None:
        l1, l2 = build_valid_td3_lines()
        mrz = parse_mrz_lines([l1, l2])
        viz = extract_viz_fields([
            OcrTextBlock("Surname: ERIKSSON", 0.98, ((50.0, 100.0), (250.0, 100.0), (250.0, 120.0), (50.0, 120.0))),
        ])
        bundle, summary = reconcile_and_build_fields(mrz, viz)
        dumped = bundle.model_dump()
        self.assertIn("surname", dumped)
        self.assertIn("passport_number", dumped)
        self.assertEqual(dumped["surname"]["value"], "ERIKSSON")


if __name__ == "__main__":
    unittest.main()
