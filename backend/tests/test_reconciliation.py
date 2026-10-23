"""Unit tests for MRZ and VIZ reconciliation status rules."""

from __future__ import annotations

import unittest

from app.mrz.parser import parse_mrz_from_blocks, parse_mrz_lines
from app.pipeline.reconciliation import reconcile_and_build_fields
from app.schemas.extraction import (
    FieldSource,
    FieldValidationState,
    MrzParseResult,
    ReconciliationStatus,
)
from app.viz.extractor import VizFieldResult, extract_viz_fields
from tests.fixtures.synthetic_passports import build_valid_td3_lines, make_synthetic_ocr_blocks


class ReconciliationTests(unittest.TestCase):
    """Test matched, mismatch, insufficient_data, and not_checked reconciliation states."""

    def test_reconciliation_all_matched(self) -> None:
        blocks = make_synthetic_ocr_blocks()
        mrz = parse_mrz_from_blocks(blocks)
        viz = extract_viz_fields(blocks, mrz_raw_lines=mrz.raw_lines)

        bundle, summary = reconcile_and_build_fields(mrz, viz)
        self.assertEqual(summary.overall_status, ReconciliationStatus.MATCHED)
        self.assertGreaterEqual(summary.compared_fields_count, 9)
        self.assertEqual(summary.mismatch_count, 0)
        self.assertEqual(bundle.passport_number.source, FieldSource.RECONCILED)
        self.assertEqual(
            bundle.passport_number.validation_state,
            FieldValidationState.VALID_CHECK_DIGIT,
        )
        # VIZ-only fields must be marked NOT_CHECKED
        self.assertEqual(
            bundle.place_of_birth.reconciliation_status,
            ReconciliationStatus.NOT_CHECKED,
        )
        self.assertEqual(
            bundle.date_of_issue.reconciliation_status,
            ReconciliationStatus.NOT_CHECKED,
        )

    def test_reconciliation_detects_mismatch_and_flags_conflict(self) -> None:
        l1, l2 = build_valid_td3_lines(surname="ERIKSSON")
        mrz = parse_mrz_lines([l1, l2])
        viz = {
            "surname": VizFieldResult(
                field_name="surname",
                value="ANDERSSON",
                raw_evidence="Surname: ANDERSSON",
                ocr_confidence=0.95,
                status="extracted",
            )
        }
        bundle, summary = reconcile_and_build_fields(mrz, viz)
        self.assertEqual(summary.overall_status, ReconciliationStatus.MISMATCH)
        self.assertEqual(summary.mismatch_count, 1)
        self.assertEqual(bundle.surname.reconciliation_status, ReconciliationStatus.MISMATCH)
        self.assertEqual(bundle.surname.validation_state, FieldValidationState.CONFLICT)
        self.assertEqual(bundle.surname.mrz_value, "ERIKSSON")
        self.assertEqual(bundle.surname.viz_value, "ANDERSSON")

    def test_reconciliation_never_claims_success_with_zero_comparisons(self) -> None:
        l1, l2 = build_valid_td3_lines()
        mrz = parse_mrz_lines([l1, l2])
        empty_viz: dict[str, VizFieldResult] = {}

        bundle, summary = reconcile_and_build_fields(mrz, empty_viz)
        self.assertEqual(summary.compared_fields_count, 0)
        self.assertEqual(summary.overall_status, ReconciliationStatus.INSUFFICIENT_DATA)
        self.assertEqual(bundle.passport_number.source, FieldSource.MRZ)

    def test_empty_mrz_and_empty_viz_reports_insufficient_data(self) -> None:
        mrz = MrzParseResult(detected=False)
        empty_viz: dict[str, VizFieldResult] = {}
        bundle, summary = reconcile_and_build_fields(mrz, empty_viz)
        self.assertEqual(summary.overall_status, ReconciliationStatus.INSUFFICIENT_DATA)
        self.assertEqual(bundle.passport_number.validation_state, FieldValidationState.MISSING)

    def test_spaceless_country_synonym_normalization(self) -> None:
        """Verify spaceless country text like UNITEDSTATESOFAMERICA reconciles cleanly with USA."""
        l1, l2 = build_valid_td3_lines(nationality="USA", issuing_country="USA")
        mrz = parse_mrz_lines([l1, l2])
        viz = {
            "nationality": VizFieldResult(
                field_name="nationality",
                value="UNITEDSTATESOFAMERICA",
                raw_evidence="Nationality: UNITEDSTATESOFAMERICA",
                ocr_confidence=0.98,
                status="extracted",
            )
        }
        bundle, summary = reconcile_and_build_fields(mrz, viz)
        self.assertEqual(bundle.nationality.reconciliation_status, ReconciliationStatus.MATCHED)
        self.assertEqual(bundle.nationality.value, "USA")
        self.assertEqual(bundle.nationality.viz_value, "UNITEDSTATESOFAMERICA")


if __name__ == "__main__":
    unittest.main()
