"""Unit tests for ICAO 9303 MRZ detection, TD1/TD2/TD3 parsing, check digits, and edge cases."""

from __future__ import annotations

import unittest

from app.mrz.check_digits import compute_icao_check_digit, verify_check_digit
from app.mrz.parser import parse_mrz_lines
from app.schemas.extraction import MrzFormat
from tests.fixtures.synthetic_passports import (
    build_valid_td1_lines,
    build_valid_td2_lines,
    build_valid_td3_lines,
)


class MrzParserTests(unittest.TestCase):
    """Verify check-digit rules, TD1/TD2/TD3 parsing, OCR confusion recovery, and malformed inputs."""

    def test_icao_9303_standard_check_digits(self) -> None:
        # Official ICAO Doc 9303 Part 3 Appendix B to Section IV example:
        # L898902C36UTO7408122F1204159ZE184226B<<<<<10
        self.assertEqual(compute_icao_check_digit("L898902C3"), "6")
        self.assertEqual(compute_icao_check_digit("740812"), "2")
        self.assertEqual(compute_icao_check_digit("120415"), "9")
        self.assertEqual(compute_icao_check_digit("ZE184226B<<<<<"), "1")
        self.assertEqual(
            compute_icao_check_digit("L898902C3674081221204159ZE184226B<<<<<1"),
            "0",
        )

        res = verify_check_digit("passport_number", "L898902C3", "6", "TD3 L2 [10]")
        self.assertTrue(res.is_valid)

    def test_valid_td3_passport_parsing(self) -> None:
        l1, l2 = build_valid_td3_lines()
        result = parse_mrz_lines([l1, l2])
        self.assertTrue(result.detected)
        self.assertEqual(result.mrz_format, MrzFormat.TD3)
        self.assertTrue(result.line_length_valid)
        self.assertTrue(result.character_set_valid)
        self.assertTrue(result.all_check_digits_valid)
        self.assertEqual(result.parsed_fields["document_type"], "P")
        self.assertEqual(result.parsed_fields["issuing_country"], "UTO")
        self.assertEqual(result.parsed_fields["surname"], "ERIKSSON")
        self.assertEqual(result.parsed_fields["given_names"], "ANNA MARIA")
        self.assertEqual(result.parsed_fields["full_name"], "ANNA MARIA ERIKSSON")
        self.assertEqual(result.parsed_fields["passport_number"], "L898902C3")
        self.assertEqual(result.parsed_fields["nationality"], "UTO")
        self.assertEqual(result.parsed_fields["date_of_birth"], "1974-08-12")
        self.assertEqual(result.parsed_fields["sex"], "F")
        self.assertEqual(result.parsed_fields["date_of_expiry"], "2030-04-15")
        self.assertEqual(result.parsed_fields["personal_number"], "ZE184226B")

    def test_valid_td2_document_parsing(self) -> None:
        l1, l2 = build_valid_td2_lines()
        result = parse_mrz_lines([l1, l2])
        self.assertTrue(result.detected)
        self.assertEqual(result.mrz_format, MrzFormat.TD2)
        self.assertTrue(result.all_check_digits_valid)
        self.assertEqual(result.parsed_fields["surname"], "STEVENSON")
        self.assertEqual(result.parsed_fields["given_names"], "PETER JOHN")
        self.assertEqual(result.parsed_fields["passport_number"], "D23145890")
        self.assertEqual(result.parsed_fields["date_of_birth"], "1985-03-21")
        self.assertEqual(result.parsed_fields["sex"], "M")
        self.assertEqual(result.parsed_fields["date_of_expiry"], "2031-09-30")

    def test_valid_td1_document_parsing(self) -> None:
        l1, l2, l3 = build_valid_td1_lines()
        result = parse_mrz_lines([l1, l2, l3])
        self.assertTrue(result.detected)
        self.assertEqual(result.mrz_format, MrzFormat.TD1)
        self.assertTrue(result.all_check_digits_valid)
        self.assertEqual(result.parsed_fields["passport_number"], "D23145890")
        self.assertEqual(result.parsed_fields["surname"], "ERIKSSON")
        self.assertEqual(result.parsed_fields["given_names"], "ANNA MARIA")
        self.assertEqual(result.parsed_fields["date_of_birth"], "1974-08-12")
        self.assertEqual(result.parsed_fields["date_of_expiry"], "2030-04-15")

    def test_failed_check_digit_reported_explicitly(self) -> None:
        l1, l2 = build_valid_td3_lines()
        corrupted_l2 = l2[:9] + "7" + l2[10:]
        result = parse_mrz_lines([l1, corrupted_l2])
        self.assertTrue(result.detected)
        self.assertFalse(result.all_check_digits_valid)
        self.assertTrue(any("passport_number" in err for err in result.errors))

    def test_bounded_ocr_confusion_recovery_preserves_raw_lines(self) -> None:
        l1, l2 = build_valid_td3_lines()
        noisy_l1 = l1[:4] + "0" + l1[5:]
        noisy_l2 = l2[:15] + "O" + l2[16:]
        result = parse_mrz_lines([noisy_l1, noisy_l2])
        self.assertTrue(result.detected)
        self.assertTrue(result.recovery_applied)
        self.assertEqual(result.raw_lines, [noisy_l1, noisy_l2])
        self.assertTrue(result.all_check_digits_valid)
        self.assertEqual(result.parsed_fields["issuing_country"], "UTO")
        self.assertEqual(result.parsed_fields["date_of_birth"], "1974-08-12")

    def test_invalid_line_length_is_not_blindly_padded_or_truncated(self) -> None:
        l1, l2 = build_valid_td3_lines()
        truncated_l2 = l2[:39]
        result = parse_mrz_lines([l1, truncated_l2])
        self.assertTrue(result.detected)
        self.assertFalse(result.line_length_valid)
        self.assertFalse(result.all_check_digits_valid)
        self.assertTrue(any("expected 44" in err for err in result.errors))

    def test_invalid_calendar_date_in_mrz_is_not_invented(self) -> None:
        l1, l2 = build_valid_td3_lines(dob_yymmdd="741512")
        result = parse_mrz_lines([l1, l2])
        self.assertIsNone(result.parsed_fields["date_of_birth"])
        self.assertTrue(any("Invalid calendar date" in err for err in result.errors))

    def test_single_incomplete_mrz_line_handled_safely(self) -> None:
        l1, _ = build_valid_td3_lines()
        result = parse_mrz_lines([l1])
        self.assertTrue(result.detected)
        self.assertIsNone(result.mrz_format)
        self.assertFalse(result.line_length_valid)
        self.assertTrue(any("Incomplete MRZ candidate" in err for err in result.errors))
        self.assertEqual(result.parsed_fields["surname"], "ERIKSSON")
        self.assertEqual(result.parsed_fields["given_names"], "ANNA MARIA")

    def test_single_line_td3_flores_extracts_all_identity_fields(self) -> None:
        raw_line = "P<USAFLORES<<KATHERINE<<<<<"
        result = parse_mrz_lines([raw_line])
        self.assertTrue(result.detected)
        self.assertEqual(result.parsed_fields["document_type"], "P")
        self.assertEqual(result.parsed_fields["issuing_country"], "USA")
        self.assertEqual(result.parsed_fields["surname"], "FLORES")
        self.assertEqual(result.parsed_fields["given_names"], "KATHERINE")
        self.assertEqual(result.parsed_fields["full_name"], "KATHERINE FLORES")
        self.assertEqual(result.parsed_fields["nationality"], "USA")

    def test_truncated_line2_retains_extracted_fields(self) -> None:
        l1, l2 = build_valid_td3_lines()
        truncated_l2 = l2[:39]
        result = parse_mrz_lines([l1, truncated_l2])
        self.assertTrue(result.detected)
        self.assertFalse(result.line_length_valid)
        self.assertEqual(result.parsed_fields["surname"], "ERIKSSON")
        self.assertEqual(result.parsed_fields["given_names"], "ANNA MARIA")
        self.assertEqual(result.parsed_fields["passport_number"], "L898902C3")


if __name__ == "__main__":
    unittest.main()
