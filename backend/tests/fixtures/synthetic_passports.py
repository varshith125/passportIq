"""Synthetic ICAO 9303 MRZ fixtures and in-memory test image generators."""

from __future__ import annotations

import io
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

from app.mrz.check_digits import compute_icao_check_digit
from app.ocr.base import OcrTextBlock


def build_valid_td3_lines(
    doc_code: str = "P<",
    issuing_country: str = "UTO",
    surname: str = "ERIKSSON",
    given_names: str = "ANNA<MARIA",
    passport_number: str = "L898902C3",
    nationality: str = "UTO",
    dob_yymmdd: str = "740812",
    sex: str = "F",
    exp_yymmdd: str = "300415",
    personal_number: str = "ZE184226B<<<<<",
) -> Tuple[str, str]:
    """Construct a deterministic, check-digit-valid 2x44 TD3 MRZ pair."""
    name_body = f"{surname}<<{given_names}"
    line1 = f"{doc_code:<2}{issuing_country:<3}{name_body}".ljust(44, "<")[:44]

    doc_field = passport_number.ljust(9, "<")[:9]
    doc_cd = compute_icao_check_digit(doc_field)
    dob_cd = compute_icao_check_digit(dob_yymmdd)
    exp_cd = compute_icao_check_digit(exp_yymmdd)
    pers_field = personal_number.ljust(14, "<")[:14]
    pers_cd = compute_icao_check_digit(pers_field)

    composite_source = doc_field + doc_cd + dob_yymmdd + dob_cd + exp_yymmdd + exp_cd + pers_field + pers_cd
    comp_cd = compute_icao_check_digit(composite_source)

    line2 = f"{doc_field}{doc_cd}{nationality:<3}{dob_yymmdd}{dob_cd}{sex}{exp_yymmdd}{exp_cd}{pers_field}{pers_cd}{comp_cd}"
    assert len(line1) == 44
    assert len(line2) == 44
    return line1, line2


def build_valid_td2_lines(
    doc_code: str = "I<",
    issuing_country: str = "UTO",
    surname: str = "STEVENSON",
    given_names: str = "PETER<JOHN",
    doc_number: str = "D23145890",
    nationality: str = "UTO",
    dob_yymmdd: str = "850321",
    sex: str = "M",
    exp_yymmdd: str = "310930",
    optional_data: str = "<<<<<<<",
) -> Tuple[str, str]:
    """Construct a deterministic, check-digit-valid 2x36 TD2 MRZ pair."""
    name_body = f"{surname}<<{given_names}"
    line1 = f"{doc_code:<2}{issuing_country:<3}{name_body}".ljust(36, "<")[:36]

    doc_field = doc_number.ljust(9, "<")[:9]
    doc_cd = compute_icao_check_digit(doc_field)
    dob_cd = compute_icao_check_digit(dob_yymmdd)
    exp_cd = compute_icao_check_digit(exp_yymmdd)
    opt_field = optional_data.ljust(7, "<")[:7]

    composite_source = doc_field + doc_cd + dob_yymmdd + dob_cd + exp_yymmdd + exp_cd + opt_field
    comp_cd = compute_icao_check_digit(composite_source)

    line2 = f"{doc_field}{doc_cd}{nationality:<3}{dob_yymmdd}{dob_cd}{sex}{exp_yymmdd}{exp_cd}{opt_field}{comp_cd}"
    assert len(line1) == 36
    assert len(line2) == 36
    return line1, line2


def build_valid_td1_lines(
    doc_code: str = "I<",
    issuing_country: str = "UTO",
    doc_number: str = "D23145890",
    opt1: str = "7<<<<<<<<<<<<<<",
    dob_yymmdd: str = "740812",
    sex: str = "F",
    exp_yymmdd: str = "300415",
    nationality: str = "UTO",
    opt2: str = "<<<<<<<<<<<",
    surname: str = "ERIKSSON",
    given_names: str = "ANNA<MARIA",
) -> Tuple[str, str, str]:
    """Construct a deterministic, check-digit-valid 3x30 TD1 MRZ triplet."""
    doc_field = doc_number.ljust(9, "<")[:9]
    doc_cd = compute_icao_check_digit(doc_field)
    opt1_field = opt1.ljust(15, "<")[:15]
    line1 = f"{doc_code:<2}{issuing_country:<3}{doc_field}{doc_cd}{opt1_field}"

    dob_cd = compute_icao_check_digit(dob_yymmdd)
    exp_cd = compute_icao_check_digit(exp_yymmdd)
    opt2_field = opt2.ljust(11, "<")[:11]

    composite_source = line1[5:30] + dob_yymmdd + dob_cd + exp_yymmdd + exp_cd + opt2_field
    comp_cd = compute_icao_check_digit(composite_source)

    line2 = f"{dob_yymmdd}{dob_cd}{sex}{exp_yymmdd}{exp_cd}{nationality:<3}{opt2_field}{comp_cd}"
    line3 = f"{surname}<<{given_names}".ljust(30, "<")[:30]
    assert len(line1) == 30
    assert len(line2) == 30
    assert len(line3) == 30
    return line1, line2, line3


def make_image_bytes(
    width: int = 800,
    height: int = 550,
    fmt: str = "PNG",
    color: Tuple[int, int, int] = (248, 250, 252),
    exif_orientation: int | None = None,
) -> bytes:
    """Create an in-memory image in the requested format with optional EXIF orientation tag."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    if exif_orientation is not None:
        exif = img.getexif()
        exif[0x0112] = exif_orientation
        img.save(buf, format=fmt, exif=exif.tobytes())
    else:
        img.save(buf, format=fmt)
    img.close()
    return buf.getvalue()


def make_synthetic_passport_image_bytes() -> bytes:
    """
    Render a clean, high-contrast synthetic passport image containing VIZ fields and TD3 MRZ lines
    suitable for live OCR testing.
    """
    canvas = np.full((760, 1100, 3), 255, dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX

    lines_to_draw = [
        ("PASSPORT", (60, 70), 1.0, 2),
        ("Type: P", (60, 130), 0.85, 2),
        ("Issuing Country: UTO", (350, 130), 0.85, 2),
        ("Passport No: L898902C3", (680, 130), 0.85, 2),
        ("Surname: ERIKSSON", (60, 200), 0.85, 2),
        ("Given Names: ANNA MARIA", (60, 265), 0.85, 2),
        ("Nationality: UTO", (60, 330), 0.85, 2),
        ("Date of Birth: 1974-08-12", (60, 395), 0.85, 2),
        ("Sex: F", (60, 460), 0.85, 2),
        ("Place of Birth: STOCKHOLM", (350, 460), 0.85, 2),
        ("Date of Issue: 2020-04-15", (60, 525), 0.85, 2),
        ("Date of Expiry: 2030-04-15", (520, 525), 0.85, 2),
    ]
    for text, (x, y), scale, thickness in lines_to_draw:
        cv2.putText(canvas, text, (x, y), font, scale, (15, 23, 42), thickness, cv2.LINE_AA)

    l1, l2 = build_valid_td3_lines()
    cv2.putText(canvas, l1, (45, 640), font, 0.78, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(canvas, l2, (45, 705), font, 0.78, (0, 0, 0), 2, cv2.LINE_AA)

    pil_img = Image.fromarray(canvas)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    pil_img.close()
    return buf.getvalue()


def make_synthetic_ocr_blocks() -> List[OcrTextBlock]:
    """Create structured OcrTextBlock fixtures representing a full TD3 passport with VIZ + MRZ."""
    l1, l2 = build_valid_td3_lines()
    entries = [
        ("Type", 60, 100, 120, 120, 0.98),
        ("P", 60, 126, 95, 150, 0.99),
        ("Issuing Country", 220, 100, 380, 120, 0.97),
        ("UTO", 220, 126, 290, 150, 0.99),
        ("Passport No", 480, 100, 620, 120, 0.98),
        ("L898902C3", 480, 126, 640, 150, 0.99),
        ("Surname", 60, 170, 180, 190, 0.98),
        ("ERIKSSON", 60, 196, 230, 222, 0.99),
        ("Given Names", 60, 240, 220, 260, 0.98),
        ("ANNA MARIA", 60, 266, 260, 292, 0.99),
        ("Nationality", 60, 310, 200, 330, 0.97),
        ("UTOPIA", 60, 336, 180, 360, 0.98),
        ("Date of Birth", 60, 380, 220, 400, 0.98),
        ("12 AUG 1974", 60, 406, 230, 430, 0.97),
        ("Sex", 320, 380, 370, 400, 0.98),
        ("F", 320, 406, 355, 430, 0.99),
        ("Place of Birth", 450, 380, 610, 400, 0.97),
        ("STOCKHOLM", 450, 406, 620, 430, 0.96),
        ("Date of Issue", 60, 450, 220, 470, 0.97),
        ("15 APR 2020", 60, 476, 225, 500, 0.98),
        ("Date of Expiry", 320, 450, 490, 470, 0.98),
        ("15 APR 2030", 320, 476, 495, 500, 0.98),
        (l1, 50, 560, 750, 590, 0.99),
        (l2, 50, 605, 750, 635, 0.99),
    ]
    blocks: List[OcrTextBlock] = []
    for text, x1, y1, x2, y2, conf in entries:
        blocks.append(
            OcrTextBlock(
                text=text,
                confidence=conf,
                bbox=((float(x1), float(y1)), (float(x2), float(y1)), (float(x2), float(y2)), (float(x1), float(y2))),
            )
        )
    return blocks
