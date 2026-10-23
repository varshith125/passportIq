"""Unit tests for Visible Inspection Zone (VIZ) field extraction."""

from __future__ import annotations

import unittest

from app.ocr.base import OcrTextBlock
from app.viz.extractor import extract_viz_fields
from tests.fixtures.synthetic_passports import build_valid_td3_lines, make_synthetic_ocr_blocks


class VizExtractorTests(unittest.TestCase):
    """Verify spatial and inline VIZ extraction, label isolation, and ambiguous date handling."""

    def test_spatial_viz_extraction_on_standard_blocks(self) -> None:
        blocks = make_synthetic_ocr_blocks()
        l1, l2 = build_valid_td3_lines()
        viz = extract_viz_fields(blocks, mrz_raw_lines=[l1, l2])

        self.assertEqual(viz["document_type"].value, "P")
        self.assertEqual(viz["issuing_country"].value, "UTO")
        self.assertEqual(viz["passport_number"].value, "L898902C3")
        self.assertEqual(viz["surname"].value, "ERIKSSON")
        self.assertEqual(viz["given_names"].value, "ANNA MARIA")
        self.assertEqual(viz["full_name"].value, "ANNA MARIA ERIKSSON")
        self.assertEqual(viz["nationality"].value, "UTOPIA")
        self.assertEqual(viz["date_of_birth"].value, "1974-08-12")
        self.assertEqual(viz["sex"].value, "F")
        self.assertEqual(viz["place_of_birth"].value, "STOCKHOLM")
        self.assertEqual(viz["date_of_issue"].value, "2020-04-15")
        self.assertEqual(viz["date_of_expiry"].value, "2030-04-15")

    def test_adjacent_label_is_never_assigned_as_field_value(self) -> None:
        # Surname label has no value below it, only the "Given Names" label directly below
        blocks = [
            OcrTextBlock("Surname", 0.98, ((50.0, 100.0), (160.0, 100.0), (160.0, 120.0), (50.0, 120.0))),
            OcrTextBlock("Given Names", 0.98, ((50.0, 130.0), (190.0, 130.0), (190.0, 150.0), (50.0, 150.0))),
            OcrTextBlock("CARLOS", 0.99, ((50.0, 158.0), (160.0, 158.0), (160.0, 180.0), (50.0, 180.0))),
        ]
        viz = extract_viz_fields(blocks)
        self.assertIsNone(viz["surname"].value)
        self.assertEqual(viz["surname"].status, "unavailable")
        self.assertEqual(viz["given_names"].value, "CARLOS")

    def test_unreadable_viz_date_returns_ambiguous_not_guessed(self) -> None:
        blocks = [
            OcrTextBlock(
                "Date of Birth: 99/99/1999",
                0.88,
                ((50.0, 100.0), (300.0, 100.0), (300.0, 125.0), (50.0, 125.0)),
            )
        ]
        viz = extract_viz_fields(blocks)
        self.assertIsNone(viz["date_of_birth"].value)
        self.assertEqual(viz["date_of_birth"].status, "ambiguous")


    def test_multiline_block_extracts_all_names_and_place_of_birth(self) -> None:
        text = """Surname / Nom / Apellidos
FLORES
Given names / Prénoms / Nombres
KATHERINE
Place of birth / Lieu de naissance / Lugar de nacimiento
FLORIDA, U.S.A."""
        block = OcrTextBlock(text, 0.95, ((100.0, 100.0), (500.0, 100.0), (500.0, 300.0), (100.0, 300.0)))
        viz = extract_viz_fields([block])

        self.assertEqual(viz["surname"].value, "FLORES")
        self.assertEqual(viz["given_names"].value, "KATHERINE")
        self.assertEqual(viz["full_name"].value, "KATHERINE FLORES")
        self.assertEqual(viz["place_of_birth"].value, "FLORIDA, U.S.A.")

    def test_trilingual_place_of_birth_inline_and_spatial(self) -> None:
        # Inline with slash-separated multilingual labels
        b1 = OcrTextBlock(
            "Place of birth / Lieu de naissance / Lugar de nacimiento: NEW YORK, U.S.A.",
            0.96,
            ((50.0, 200.0), (450.0, 200.0), (450.0, 225.0), (50.0, 225.0)),
        )
        viz1 = extract_viz_fields([b1])
        self.assertEqual(viz1["place_of_birth"].value, "NEW YORK, U.S.A.")

        # Spatial below trilingual label
        b2_label = OcrTextBlock(
            "Place of birth / Lieu de naissance / Lugar de nacimiento",
            0.96,
            ((50.0, 200.0), (400.0, 200.0), (400.0, 220.0), (50.0, 220.0)),
        )
        b2_val = OcrTextBlock(
            "CALIFORNIA, USA",
            0.97,
            ((50.0, 225.0), (250.0, 225.0), (250.0, 245.0), (50.0, 245.0)),
        )
        viz2 = extract_viz_fields([b2_label, b2_val])
        self.assertEqual(viz2["place_of_birth"].value, "CALIFORNIA, USA")

    def test_value_first_pattern_and_spatial_fallback_without_labels(self) -> None:
        """Verify extraction from document where OCR detected only bold values without field labels."""
        blocks = [
            OcrTextBlock("PASSPORT", 0.99, ((300.0, 50.0), (500.0, 50.0), (500.0, 80.0), (300.0, 80.0))),
            OcrTextBlock("UNITED STATES OF AMERICA", 0.98, ((200.0, 90.0), (600.0, 90.0), (600.0, 120.0), (200.0, 120.0))),
            OcrTextBlock("LOPEZ", 0.99, ((250.0, 150.0), (350.0, 150.0), (350.0, 180.0), (250.0, 180.0))),
            OcrTextBlock("JOSHUA", 0.98, ((250.0, 190.0), (380.0, 190.0), (380.0, 220.0), (250.0, 220.0))),
            OcrTextBlock("USA", 0.99, ((250.0, 230.0), (310.0, 230.0), (310.0, 250.0), (250.0, 250.0))),
            OcrTextBlock("08SEP1973", 0.97, ((250.0, 260.0), (400.0, 260.0), (400.0, 280.0), (250.0, 280.0))),
            OcrTextBlock("NEWYORK.USA", 0.92, ((250.0, 290.0), (450.0, 290.0), (450.0, 310.0), (250.0, 310.0))),
            OcrTextBlock("06JAN2024", 0.98, ((250.0, 320.0), (400.0, 320.0), (400.0, 340.0), (250.0, 340.0))),
            OcrTextBlock("06JAN2034", 0.98, ((250.0, 350.0), (400.0, 350.0), (400.0, 370.0), (250.0, 370.0))),
            OcrTextBlock("K38542916", 0.98, ((600.0, 80.0), (780.0, 80.0), (780.0, 110.0), (600.0, 110.0))),
        ]
        viz = extract_viz_fields(blocks)

        self.assertEqual(viz["document_type"].value, "P")
        self.assertEqual(viz["issuing_country"].value, "USA")
        self.assertEqual(viz["surname"].value, "LOPEZ")
        self.assertEqual(viz["given_names"].value, "JOSHUA")
        self.assertEqual(viz["full_name"].value, "JOSHUA LOPEZ")
        self.assertEqual(viz["nationality"].value, "USA")
        self.assertEqual(viz["date_of_birth"].value, "1973-09-08")
        self.assertEqual(viz["place_of_birth"].value, "NEWYORK, USA")
        self.assertEqual(viz["date_of_issue"].value, "2024-01-06")
        self.assertEqual(viz["date_of_expiry"].value, "2034-01-06")
        self.assertEqual(viz["passport_number"].value, "K38542916")

    def test_chronological_date_disambiguation_without_labels(self) -> None:
        """Verify that 3 unlabelled dates sort chronologically into DOB, Issue, and Expiry."""
        blocks = [
            OcrTextBlock("15MAY1982", 0.98, ((100.0, 100.0), (250.0, 100.0), (250.0, 120.0), (100.0, 120.0))),
            OcrTextBlock("10JUN2021", 0.98, ((100.0, 140.0), (250.0, 140.0), (250.0, 160.0), (100.0, 160.0))),
            OcrTextBlock("10JUN2031", 0.98, ((100.0, 180.0), (250.0, 180.0), (250.0, 200.0), (100.0, 200.0))),
        ]
        viz = extract_viz_fields(blocks)
        self.assertEqual(viz["date_of_birth"].value, "1982-05-15")
        self.assertEqual(viz["date_of_issue"].value, "2021-06-10")
        self.assertEqual(viz["date_of_expiry"].value, "2031-06-10")

    def test_residence_permit_header_extraction(self) -> None:
        """Verify document type detection from RESIDENCE PERMIT header."""
        blocks = [
            OcrTextBlock("RESIDENCE PERMIT", 0.99, ((100.0, 50.0), (350.0, 50.0), (350.0, 80.0), (100.0, 80.0))),
        ]
        viz = extract_viz_fields(blocks)
        self.assertEqual(viz["document_type"].value, "RESIDENCE PERMIT")

    def test_missing_mrz_does_not_suppress_viz_results(self) -> None:
        """Verify that MRZ detection failure does not prevent independent VIZ extraction or reconciliation."""
        from app.pipeline.reconciliation import reconcile_and_build_fields
        from app.schemas.extraction import FieldSource, MrzParseResult, ReconciliationStatus

        mrz = MrzParseResult(detected=False)
        blocks = [
            OcrTextBlock("Surname: GUMMADI", 0.98, ((50.0, 100.0), (250.0, 100.0), (250.0, 120.0), (50.0, 120.0))),
            OcrTextBlock("Given Names: VENKATA VARSHITH", 0.98, ((50.0, 130.0), (380.0, 130.0), (380.0, 150.0), (50.0, 150.0))),
            OcrTextBlock("Passport No: K38542916", 0.98, ((50.0, 160.0), (300.0, 160.0), (300.0, 180.0), (50.0, 180.0))),
        ]
        viz = extract_viz_fields(blocks)
        bundle, summary = reconcile_and_build_fields(mrz_result=mrz, viz_results=viz)

        self.assertEqual(bundle.surname.value, "GUMMADI")
        self.assertEqual(bundle.surname.source, FieldSource.VIZ)
        self.assertEqual(bundle.surname.reconciliation_status, ReconciliationStatus.VIZ_ONLY)

        self.assertEqual(bundle.given_names.value, "VENKATA VARSHITH")
        self.assertEqual(bundle.given_names.source, FieldSource.VIZ)
        self.assertEqual(bundle.given_names.reconciliation_status, ReconciliationStatus.VIZ_ONLY)

        self.assertEqual(bundle.full_name.value, "VENKATA VARSHITH GUMMADI")
        self.assertEqual(bundle.full_name.source, FieldSource.DERIVED)

        self.assertEqual(bundle.passport_number.value, "K38542916")
        self.assertEqual(bundle.passport_number.source, FieldSource.VIZ)
        self.assertEqual(bundle.passport_number.reconciliation_status, ReconciliationStatus.VIZ_ONLY)

        # Missing MRZ means reconciliation has insufficient overlapping data, not false success
        self.assertEqual(summary.overall_status, ReconciliationStatus.INSUFFICIENT_DATA)

    def test_layout_adjacent_sex_extraction_when_labels_absent(self) -> None:
        """Verify Sex is extracted from layout-specific position adjacent to DOB when labels are missing."""
        blocks = [
            OcrTextBlock("PASSPORT", 0.99, ((300.0, 50.0), (500.0, 50.0), (500.0, 80.0), (300.0, 80.0))),
            OcrTextBlock("LOPEZ", 0.99, ((250.0, 150.0), (350.0, 150.0), (350.0, 180.0), (250.0, 180.0))),
            OcrTextBlock("JOSHUA", 0.98, ((250.0, 190.0), (380.0, 190.0), (380.0, 220.0), (250.0, 220.0))),
            OcrTextBlock("08SEP1973", 0.97, ((250.0, 260.0), (400.0, 260.0), (400.0, 280.0), (250.0, 280.0))),
            OcrTextBlock("M", 0.99, ((420.0, 260.0), (450.0, 260.0), (450.0, 280.0), (420.0, 280.0))),
            OcrTextBlock("NEWYORK.USA", 0.92, ((250.0, 290.0), (450.0, 290.0), (450.0, 310.0), (250.0, 310.0))),
        ]
        viz = extract_viz_fields(blocks)
        self.assertEqual(viz["sex"].value, "M")
        self.assertEqual(viz["sex"].status, "extracted")
        self.assertIn("anchored adjacent to date of birth", viz["sex"].notes[0])

    def test_sex_marker_supports_unspecified_x_and_chevron(self) -> None:
        """Verify sex markers support < and X without mapping to Male/Female, and words Male/Female map correctly."""
        # Unspecified X
        b_x = OcrTextBlock("Sex: X", 0.98, ((50.0, 100.0), (200.0, 100.0), (200.0, 120.0), (50.0, 120.0)))
        viz_x = extract_viz_fields([b_x])
        self.assertEqual(viz_x["sex"].value, "X")

        # Unspecified <
        b_chev = OcrTextBlock("Sex: <", 0.98, ((50.0, 100.0), (200.0, 100.0), (200.0, 120.0), (50.0, 120.0)))
        viz_chev = extract_viz_fields([b_chev])
        self.assertEqual(viz_chev["sex"].value, "<")

        # Word Female
        b_f = OcrTextBlock("Sex: FEMALE", 0.98, ((50.0, 100.0), (200.0, 100.0), (200.0, 120.0), (50.0, 120.0)))
        viz_f = extract_viz_fields([b_f])
        self.assertEqual(viz_f["sex"].value, "F")

        # Word Male
        b_m = OcrTextBlock("Sex / Sexe: MALE", 0.98, ((50.0, 100.0), (250.0, 100.0), (250.0, 120.0), (50.0, 120.0)))
        viz_m = extract_viz_fields([b_m])
        self.assertEqual(viz_m["sex"].value, "M")

    def test_multiple_ambiguous_sex_candidates_near_dob_return_ambiguous(self) -> None:
        """Verify conflicting sex candidates adjacent to DOB are flagged ambiguous, not arbitrarily guessed."""
        blocks = [
            OcrTextBlock("08SEP1973", 0.97, ((250.0, 260.0), (400.0, 260.0), (400.0, 280.0), (250.0, 280.0))),
            OcrTextBlock("M", 0.99, ((420.0, 260.0), (440.0, 260.0), (440.0, 280.0), (420.0, 280.0))),
            OcrTextBlock("F", 0.99, ((460.0, 260.0), (480.0, 260.0), (480.0, 280.0), (460.0, 280.0))),
        ]
        viz = extract_viz_fields(blocks)
        self.assertIsNone(viz["sex"].value)
        self.assertEqual(viz["sex"].status, "ambiguous")
        self.assertIn("Multiple ambiguous sex marker candidates", viz["sex"].notes[0])

    def test_missing_sex_marker_returns_not_detected_without_inferring_from_name(self) -> None:
        """Verify sex is never inferred from masculine/feminine names or photo."""
        blocks = [
            OcrTextBlock("LOPEZ", 0.99, ((250.0, 150.0), (350.0, 150.0), (350.0, 180.0), (250.0, 180.0))),
            OcrTextBlock("JOSHUA", 0.98, ((250.0, 190.0), (380.0, 190.0), (380.0, 220.0), (250.0, 220.0))),
            OcrTextBlock("08SEP1973", 0.97, ((250.0, 260.0), (400.0, 260.0), (400.0, 280.0), (250.0, 280.0))),
        ]
        viz = extract_viz_fields(blocks)
        self.assertIsNone(viz["sex"].value)
        self.assertEqual(viz["sex"].status, "unavailable")
        self.assertIn("Sex marker label not detected", viz["sex"].notes[0])

    def test_conflicting_or_implausible_dates_flagged_as_ambiguous(self) -> None:
        """Verify candidate dates that fail plausibility (e.g. future birth date) return ambiguous."""
        blocks = [
            OcrTextBlock("NEWYORK.USA", 0.92, ((250.0, 290.0), (450.0, 290.0), (450.0, 310.0), (250.0, 310.0))),
            # Future date positioned above POB (impossible birth date)
            OcrTextBlock("15AUG2035", 0.97, ((250.0, 260.0), (400.0, 260.0), (400.0, 280.0), (250.0, 280.0))),
        ]
        viz = extract_viz_fields(blocks)
        self.assertIsNone(viz["date_of_birth"].value)
        self.assertEqual(viz["date_of_birth"].status, "ambiguous")

    def test_optional_number_rejected_without_explicit_label(self) -> None:
        """Verify arbitrary alphanumeric strings on page are not assigned to optional number."""
        blocks = [
            OcrTextBlock("PASSPORT", 0.99, ((300.0, 50.0), (500.0, 50.0), (500.0, 80.0), (300.0, 80.0))),
            OcrTextBlock("XYZ9876543210", 0.95, ((100.0, 400.0), (300.0, 400.0), (300.0, 420.0), (100.0, 420.0))),
        ]
        viz = extract_viz_fields(blocks)
        self.assertIsNone(viz["personal_number"].value)
        self.assertEqual(viz["personal_number"].status, "unavailable")
        self.assertIn("personal number label not detected", viz["personal_number"].notes[0].lower())

    def test_document_type_headers_id_and_visa(self) -> None:
        """Verify IDENTITY CARD and VISA headers are correctly extracted into canonical codes."""
        b_id = OcrTextBlock("IDENTITY CARD", 0.99, ((100.0, 50.0), (350.0, 50.0), (350.0, 80.0), (100.0, 80.0)))
        viz_id = extract_viz_fields([b_id])
        self.assertEqual(viz_id["document_type"].value, "ID")
        b_v = OcrTextBlock("VISA", 0.99, ((100.0, 50.0), (250.0, 50.0), (250.0, 80.0), (100.0, 80.0)))
        viz_v = extract_viz_fields([b_v])
        self.assertEqual(viz_v["document_type"].value, "V")

    def test_multilingual_slash_delimited_labels_clean_correctly(self) -> None:
        """Verify unspaced slash-separated multilingual labels clean properly and don't leak label tokens."""
        block = OcrTextBlock(
            "Nationality/Nationalite/Nacio USA",
            0.98,
            ((50.0, 100.0), (350.0, 100.0), (350.0, 120.0), (50.0, 120.0)),
        )
        viz = extract_viz_fields([block])
        self.assertEqual(viz["nationality"].value, "USA")
        self.assertEqual(viz["nationality"].status, "extracted")


if __name__ == "__main__":
    unittest.main()
