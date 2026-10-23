"""
Dedicated Regex-based passport field extraction and validation layer.

Provides compiled, documented regex patterns, field-specific OCR confusions normalization,
strict calendar date validation using datetime, nationality validation, and structured candidate output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Set, Tuple

from app.ocr.base import OcrTextBlock

# ==============================================================================
# 1. Standard ISO-3166-1 Alpha-3 Code & Nationality Registry
# ==============================================================================

# Mapping of ISO-3166-1 alpha-3 code -> Canonical English nationality / country name
ISO_NATIONALITY_REGISTRY: Dict[str, str] = {
    "AFG": "AFGHAN",
    "ALB": "ALBANIAN",
    "DZA": "ALGERIAN",
    "AND": "ANDORRAN",
    "AGO": "ANGOLAN",
    "ARG": "ARGENTINE",
    "ARM": "ARMENIAN",
    "AUS": "AUSTRALIAN",
    "AUT": "AUSTRIAN",
    "AZE": "AZERBAIJANI",
    "BHS": "BAHAMIAN",
    "BHR": "BAHRAINI",
    "BGD": "BANGLADESHI",
    "BRB": "BARBADIAN",
    "BLR": "BELARUSIAN",
    "BEL": "BELGIAN",
    "BLZ": "BELIZEAN",
    "BEN": "BENINESE",
    "BTN": "BHUTANESE",
    "BOL": "BOLIVIAN",
    "BIH": "BOSNIAN",
    "BWA": "BOTSWANAN",
    "BRA": "BRAZILIAN",
    "BRN": "BRUNEIAN",
    "BGR": "BULGARIAN",
    "BFA": "BURKINABE",
    "BDI": "BURUNDIAN",
    "KHM": "CAMBODIAN",
    "CMR": "CAMEROONIAN",
    "CAN": "CANADIAN",
    "CPV": "CAPE VERDEAN",
    "CHL": "CHILEAN",
    "CHN": "CHINESE",
    "COL": "COLOMBIAN",
    "CRI": "COSTA RICAN",
    "HRV": "CROATIAN",
    "CUB": "CUBAN",
    "CYP": "CYPRIOT",
    "CZE": "CZECH",
    "DNK": "DANISH",
    "DJI": "DJIBOUTIAN",
    "DOM": "DOMINICAN",
    "ECU": "ECUADORIAN",
    "EGY": "EGYPTIAN",
    "SLV": "SALVADORAN",
    "EST": "ESTONIAN",
    "ETH": "ETHIOPIAN",
    "FJI": "FIJIAN",
    "FIN": "FINNISH",
    "FRA": "FRENCH",
    "GAB": "GABONESE",
    "GMB": "GAMBIAN",
    "GEO": "GEORGIAN",
    "DEU": "GERMAN",
    "GHA": "GHANAIAN",
    "GRC": "GREEK",
    "GTM": "GUATEMALAN",
    "GIN": "GUINEAN",
    "GUY": "GUYANESE",
    "HTI": "HAITIAN",
    "HND": "HONDURAN",
    "HUN": "HUNGARIAN",
    "ISL": "ICELANDIC",
    "IND": "INDIAN",
    "IDN": "INDONESIAN",
    "IRN": "IRANIAN",
    "IRQ": "IRAQI",
    "IRL": "IRISH",
    "ISR": "ISRAELI",
    "ITA": "ITALIAN",
    "JAM": "JAMAICAN",
    "JPN": "JAPANESE",
    "JOR": "JORDANIAN",
    "KAZ": "KAZAKHSTANI",
    "KEN": "KENYAN",
    "KWT": "KUWAITI",
    "KGZ": "KYRGYZ",
    "LAO": "LAOTIAN",
    "LVA": "LATVIAN",
    "LBN": "LEBANESE",
    "LBY": "LIBYAN",
    "LIE": "LIECHTENSTEIN",
    "LTU": "LITHUANIAN",
    "LUX": "LUXEMBOURGISH",
    "MYS": "MALAYSIAN",
    "MDV": "MALDIVIAN",
    "MLI": "MALIAN",
    "MLT": "MALTESE",
    "MEX": "MEXICAN",
    "MDA": "MOLDAVIAN",
    "MCO": "MONACAN",
    "MNG": "MONGOLIAN",
    "MNE": "MONTENEGRIN",
    "MAR": "MOROCCAN",
    "MOZ": "MOZAMBICAN",
    "MMR": "MYANMAR",
    "NAM": "NAMIBIAN",
    "NPL": "NEPALESE",
    "NLD": "DUTCH",
    "NZL": "NEW ZEALANDER",
    "NIC": "NICARAGUAN",
    "NER": "NIGERIEN",
    "NGA": "NIGERIAN",
    "NOR": "NORWEGIAN",
    "OMN": "OMANI",
    "PAK": "PAKISTANI",
    "PAN": "PANAMANIAN",
    "PNG": "PAPUA NEW GUINEAN",
    "PRY": "PARAGUAYAN",
    "PER": "PERUVIAN",
    "PHL": "FILIPINO",
    "POL": "POLISH",
    "PRT": "PORTUGUESE",
    "QAT": "QATARI",
    "ROU": "ROMANIAN",
    "RUS": "RUSSIAN",
    "RWA": "RWANDAN",
    "SAU": "SAUDI",
    "SEN": "SENEGALESE",
    "SRB": "SERBIAN",
    "SGP": "SINGAPOREAN",
    "SVK": "SLOVAK",
    "SVN": "SLOVENIAN",
    "SOM": "SOMALI",
    "ZAF": "SOUTH AFRICAN",
    "KOR": "KOREAN",
    "ESP": "SPANISH",
    "LKA": "SRI LANKAN",
    "SDN": "SUDANESE",
    "SWE": "SWEDISH",
    "CHE": "SWISS",
    "SYR": "SYRIAN",
    "TWN": "TAIWANESE",
    "TZA": "TANZANIAN",
    "THA": "THAI",
    "TUN": "TUNISIAN",
    "TUR": "TURKISH",
    "UGA": "UGANDAN",
    "UKR": "UKRAINIAN",
    "ARE": "EMIRATI",
    "GBR": "BRITISH",
    "USA": "AMERICAN",
    "URY": "URUGUAYAN",
    "UZB": "UZBEK",
    "VEN": "VENEZUELAN",
    "VNM": "VIETNAMESE",
    "YEM": "YEMENI",
    "ZMB": "ZAMBIAN",
    "ZWE": "ZIMBABWEAN",
    # ICAO Spec fictitious country used in standard testing
    "UTO": "UTOPIAN",
    "D": "GERMAN",
}

# Reverse mapping: Nationality Demonyn / Country Name -> ISO-3166-1 Code
NATIONALITY_NAME_TO_CODE: Dict[str, str] = {
    # Direct demonsyms & countries
    "AMERICAN": "USA",
    "UNITED STATES": "USA",
    "UNITED STATES OF AMERICA": "USA",
    "U.S.A.": "USA",
    "USA": "USA",
    "INDIAN": "IND",
    "INDIA": "IND",
    "REPUBLIC OF INDIA": "IND",
    "IND": "IND",
    "BRITISH": "GBR",
    "BRITISH CITIZEN": "GBR",
    "UNITED KINGDOM": "GBR",
    "GREAT BRITAIN": "GBR",
    "UK": "GBR",
    "GBR": "GBR",
    "CANADIAN": "CAN",
    "CANADA": "CAN",
    "CAN": "CAN",
    "AUSTRALIAN": "AUS",
    "AUSTRALIA": "AUS",
    "AUS": "AUS",
    "GERMAN": "DEU",
    "GERMANY": "DEU",
    "DEUTSCH": "DEU",
    "DEUTSCHLAND": "DEU",
    "DEU": "DEU",
    "D": "DEU",
    "FRENCH": "FRA",
    "FRANCE": "FRA",
    "FRANCAIS": "FRA",
    "FRANCAISE": "FRA",
    "FRANÇAISE": "FRA",
    "FRA": "FRA",
    "ITALIAN": "ITA",
    "ITALY": "ITA",
    "ITALIANA": "ITA",
    "ITA": "ITA",
    "SPANISH": "ESP",
    "SPAIN": "ESP",
    "ESPAÑOL": "ESP",
    "ESPAÑOLA": "ESP",
    "ESP": "ESP",
    "JAPANESE": "JPN",
    "JAPAN": "JPN",
    "JPN": "JPN",
    "CHINESE": "CHN",
    "CHINA": "CHN",
    "CHN": "CHN",
    "DUTCH": "NLD",
    "NETHERLANDS": "NLD",
    "NLD": "NLD",
    "SWEDISH": "SWE",
    "SWEDEN": "SWE",
    "SVERIGE": "SWE",
    "SWE": "SWE",
    "SWISS": "CHE",
    "SWITZERLAND": "CHE",
    "CHE": "CHE",
    "MEXICAN": "MEX",
    "MEXICO": "MEX",
    "MEX": "MEX",
    "BRAZILIAN": "BRA",
    "BRAZIL": "BRA",
    "BRASIL": "BRA",
    "BRA": "BRA",
    "SINGAPOREAN": "SGP",
    "SINGAPORE": "SGP",
    "SGP": "SGP",
    "UTOPIAN": "UTO",
    "UTOPIA": "UTO",
    "UTO": "UTO",
}

# Add standard entries from ISO_NATIONALITY_REGISTRY
for _code, _nat in ISO_NATIONALITY_REGISTRY.items():
    if _nat not in NATIONALITY_NAME_TO_CODE:
        NATIONALITY_NAME_TO_CODE[_nat] = _code
    if _code not in NATIONALITY_NAME_TO_CODE:
        NATIONALITY_NAME_TO_CODE[_code] = _code

# Month abbreviations to calendar month numbers (supports multilingual months)
_MONTH_MAP: Dict[str, int] = {
    "JAN": 1, "JANV": 1, "ENERO": 1, "ENE": 1, "JANUAR": 1,
    "FEB": 2, "FEVR": 2, "FÉVR": 2, "FEBRERO": 2, "FEBRUAR": 2,
    "MAR": 3, "MARS": 3, "MARZO": 3, "MÄRZ": 3, "MAERZ": 3,
    "APR": 4, "AVR": 4, "AVRIL": 4, "ABR": 4, "ABRIL": 4,
    "MAY": 5, "MAI": 5, "MAYO": 5,
    "JUN": 6, "JUIN": 6, "JUNIO": 6,
    "JUL": 7, "JUIL": 7, "JULIO": 7,
    "AUG": 8, "AOÛT": 8, "AOUT": 8, "AGO": 8, "AGOSTO": 8,
    "SEP": 9, "SEPT": 9, "SEPTIEMBRE": 9,
    "OCT": 10, "OKT": 10, "OCTOBRE": 10, "OCTUBRE": 10,
    "NOV": 11, "NOVIEMBRE": 11,
    "DEC": 12, "DÉC": 12, "DEZ": 12, "DICIEMBRE": 12,
}

# ==============================================================================
# 2. Field-Specific Compiled Regex Patterns
# ==============================================================================

# A. Surname / Last Name patterns
SURNAME_PATTERNS = [
    re.compile(
        r"^(?:surname|family\s*name|last\s*name|nom(?:\s*de\s*famille)?|apellidos?|nachname)\b\s*[:./\-_|\\]*\s*(?P<val>[A-Za-zÀ-ÿ\s\-'.]+)?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:surname|family\s*name|last\s*name|nom(?:\s*de\s*famille)?|apellidos?|nachname)\b\s*[:./\-_|\\]+\s*(?P<val>[A-Za-zÀ-ÿ\s\-'.]+)",
        re.IGNORECASE,
    ),
]

# B. Given Names / First Name patterns
GIVEN_NAMES_PATTERNS = [
    re.compile(
        r"^(?:given\s*names?|given\s*name\s*\([a-z]\)|first\s*names?|forenames?|pr[eé]noms?|nombres?|vorname[n]?)\b\s*[:./\-_|\\]*\s*(?P<val>[A-Za-zÀ-ÿ\s\-'.]+)?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:given\s*names?|given\s*name\s*\([a-z]\)|first\s*names?|forenames?|pr[eé]noms?|nombres?|vorname[n]?)\b\s*[:./\-_|\\]+\s*(?P<val>[A-Za-zÀ-ÿ\s\-'.]+)",
        re.IGNORECASE,
    ),
]

# C. Full Name patterns
FULL_NAME_PATTERNS = [
    re.compile(
        r"^(?:full\s*name|holder'?s?\s*name|bearer'?s?\s*name|name\s*of\s*(?:bearer|holder)|name(?:\s*/\s*nom)?)\b\s*[:./\-_|\\]*\s*(?P<val>[A-Za-zÀ-ÿ\s\-'.]+)?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:full\s*name|holder'?s?\s*name|bearer'?s?\s*name|name\s*of\s*(?:bearer|holder)|name(?:\s*/\s*nom)?)\b\s*[:./\-_|\\]+\s*(?P<val>[A-Za-zÀ-ÿ\s\-'.]+)",
        re.IGNORECASE,
    ),
]

# D. Date of Birth patterns
DOB_PATTERNS = [
    re.compile(
        r"\b(?:date\s*of\s*birth|birth\s*date|dob|date\s*de\s*naissance|fecha\s*de\s*nacimiento|geburtsdatum)\b\s*[:./\-_|\\]*\s*(?P<val>\d{1,4}[-/. \w/]+\d{2,4})",
        re.IGNORECASE,
    ),
]

# E. Date of Issue patterns
ISSUE_DATE_PATTERNS = [
    re.compile(
        r"\b(?:date\s*of\s*issue|issue\s*date|date\s*de\s*d[eé]livrance|fecha\s*de\s*expedici[oó]n|ausstellungsdatum|issued\s*on)\b\s*[:./\-_|\\]*\s*(?P<val>\d{1,4}[-/. \w/]+\d{2,4})",
        re.IGNORECASE,
    ),
]

# F. Date of Expiry patterns
EXPIRY_DATE_PATTERNS = [
    re.compile(
        r"\b(?:date\s*of\s*expir(?:y|ation)|expir(?:y|ation)\s*date|valid\s*until|date\s*d'expiration|fecha\s*de\s*caducidad|ablaufdatum|expires\s*on)\b\s*[:./\-_|\\]*\s*(?P<val>\d{1,4}[-/. \w/]+\d{2,4})",
        re.IGNORECASE,
    ),
]

# G. Passport / Document Number patterns
PASSPORT_NUMBER_PATTERNS = [
    re.compile(
        r"\b(?:passport\s*(?:no|number|#)|document\s*(?:no|number)|no\.?\s*du\s*passeport|passeport\s*no\.?|passnummer)\b\s*[:./\-_|\\]*\s*(?P<val>[A-Za-z0-9\s\-]+)",
        re.IGNORECASE,
    ),
]

# H. Nationality patterns
NATIONALITY_PATTERNS = [
    re.compile(
        r"\b(?:nationality|nationalit[eé]|nacionalidad|staatsangeh[oö]rigkeit)\b\s*[:./\-_|\\]*\s*(?P<val>[A-Za-zÀ-ÿ\s\-]+)",
        re.IGNORECASE,
    ),
]

# I. Sex Marker patterns
SEX_PATTERNS = [
    re.compile(
        r"^(?:sex|gender|sexe|sexo|geschlecht)\b\s*[:./\-_|\\]*\s*(?P<val>[MFX<]|MALE|FEMALE|MASCULIN|F[EÉ]MININ|UNSPECIFIED)?(?:\b|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:sex|gender|sexe|sexo|geschlecht)\b\s*[:./\-_|\\]+\s*(?P<val>[MFX<]|MALE|FEMALE|MASCULIN|F[EÉ]MININ|UNSPECIFIED)(?:\b|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:sex|gender|sexe|sexo|geschlecht)\s*(?:/|\\)\s*(?:sexe|sexo|sex|gender)\s*[:./\-_|\\]*\s*(?P<val>[MFX<]|MALE|FEMALE|MASCULIN|F[EÉ]MININ|UNSPECIFIED)(?:\b|$)",
        re.IGNORECASE,
    ),
]

# J. Place of Birth patterns
PLACE_OF_BIRTH_PATTERNS = [
    re.compile(
        r"\b(?:place\s*of\s*birth|birth\s*place|birthplace|lieu\s*de\s*naissance|lugar\s*de\s*nacimiento|pob|geburtsort)\b\s*[:./\-_|\\]*\s*(?P<val>[A-Za-zÀ-ÿ0-9\s,.\-/'_]+)?",
        re.IGNORECASE,
    ),
]

# K. Document Type patterns
DOC_TYPE_PATTERNS = [
    re.compile(
        r"\b(?:type|document\s*type|cat[eé]gorie|tipo)\b\s*[:./\-_|\\]*\s*(?P<val>[A-Za-z0-9]+)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<val>residence\s*permit|identity\s*card|passport|passeport|pasaporte|visa|travel\s*document)\b",
        re.IGNORECASE,
    ),
]

# L. Issuing Country / Authority patterns
ISSUING_AUTHORITY_PATTERNS = [
    re.compile(
        r"\b(?:country\s*code|issuing\s*(?:country|state|authority)|code\s*du\s*pays|code\s*pays|c[oó]digo\s*del\s*pa[ií]s|authority|autorit[eé]|autoridad|beh[oö]rde)\b\s*[:./\-_|\\]*\s*(?P<val>[A-Za-zÀ-ÿ0-9\s,.\-]+)",
        re.IGNORECASE,
    ),
]

# M. Personal / ID Number patterns
PERSONAL_NUMBER_PATTERNS = [
    re.compile(
        r"\b(?:personal\s*(?:no|number|id)|id\s*(?:no|number)|national\s*id(?:\s*no)?|num[eé]ro\s*personnel|n[uú]mero\s*personal|personal\s*code)\b\s*[:./\-_|\\]*\s*(?P<val>[A-Za-z0-9\-]+)",
        re.IGNORECASE,
    ),
]

# Label word set for stripping multilingual chaining
_LABEL_WORD_SET: Set[str] = {
    "nom", "famille", "prenoms", "prénoms", "apellidos", "nombres", "surname",
    "given", "names", "first", "lieu", "naissance", "lugar", "nacimiento",
    "nationalite", "nationalité", "nacionalidad", "nationality", "nacio", "nacion", "nac",
    "staatsangehoerigkeit", "staatsangehörigkeit",
    "date", "birth", "issue", "expiry", "delivrance", "délivrance", "expedicion", "expedición",
    "expiration", "caducidad", "sexe", "sexo", "sex", "gender", "geschlecht",
    "code", "codel", "codei", "codigo", "código", "pays", "pais", "país", "country",
    "autorite", "autorité", "autoridad", "authority", "behörde", "categorie", "catégorie",
    "tipo", "typer", "typef", "type", "du", "de", "del", "d", "of", "and", "or", "pob", "dob",
    "passpo", "nonodu", "papor", "depasor", "passport", "passeport", "pasaporte", "document",
    "signature", "titular", "titulaire", "firma", "bearer", "holder",
}

# ==============================================================================
# 3. Candidate Model & Field Result
# ==============================================================================

@dataclass
class RegexFieldCandidate:
    """Structured extraction candidate produced by the Regex extraction layer."""

    field_name: str
    value: Optional[str] = None
    raw_evidence: Optional[str] = None
    source: str = "viz"
    ocr_confidence: Optional[float] = None
    validation_status: str = "missing"  # "valid" | "unverified" | "invalid" | "missing"
    rejection_reason: Optional[str] = None
    notes: List[str] = field(default_factory=list)


# ==============================================================================
# 4. Strict Calendar Date Parsing & Validation
# ==============================================================================

def parse_and_validate_date(raw_date_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse candidate date string into ISO-8601 YYYY-MM-DD using strict calendar validation.
    Rejects impossible calendar dates (e.g., 31/02/2004, 2023-04-31).
    """
    cleaned = raw_date_str.strip().upper()
    cleaned = re.sub(r"[\s]+", " ", cleaned)
    # Collapse OCR splitting artifacts inside date tokens (e.g. "15/0 1/2020" -> "15/01/2020")
    cleaned = re.sub(r"(?<=[\d\-/./])\s+(?=[\d\-/./])", "", cleaned)

    # 1. ISO format: YYYY-MM-DD or YYYY/MM/DD or YYYY.MM.DD (allowing optional spaces)
    iso_match = re.search(
        r"\b(?P<y>19\d{2}|20\d{2})\s*[-/.]\s*(?P<m>\d{1,2})\s*[-/.]\s*(?P<d>\d{1,2})\b",
        cleaned,
    )
    if iso_match:
        y, m, d = int(iso_match.group("y")), int(iso_match.group("m")), int(iso_match.group("d"))
        try:
            val_date = date(y, m, d)
            return val_date.isoformat(), None
        except ValueError as exc:
            return None, f"Impossible calendar date ({exc})."

    # 2. Alphanumeric month: 27 NOV 2004 or 27/NOV/2004 or 27-NOV-2004 or 08SEP1973
    alpha_match = re.search(
        r"\b(?P<d>\d{1,2})[-/. ]*(?P<mon>[A-Za-zÀ-ÿ]{3,10})(?:/[-/. \w]+)?[-/. ]*(?P<y>19\d{2}|20\d{2})\b",
        cleaned,
    )
    if alpha_match:
        d = int(alpha_match.group("d"))
        y = int(alpha_match.group("y"))
        mon_raw = alpha_match.group("mon").upper()
        # Find matching month prefix
        mon_num = None
        for k, v in _MONTH_MAP.items():
            if mon_raw.startswith(k):
                mon_num = v
                break
        if mon_num is not None:
            try:
                val_date = date(y, mon_num, d)
                return val_date.isoformat(), None
            except ValueError as exc:
                return None, f"Impossible calendar date ({exc})."

    # 3. Numeric DMY or MDY: DD/MM/YYYY or DD-MM-YYYY (allowing optional spaces around separators)
    dmy_match = re.search(
        r"\b(?P<first>\d{1,2})\s*[-/.]\s*(?P<second>\d{1,2})\s*[-/.]\s*(?P<y>19\d{2}|20\d{2})\b",
        cleaned,
    )
    if dmy_match:
        first = int(dmy_match.group("first"))
        second = int(dmy_match.group("second"))
        y = int(dmy_match.group("y"))

        # If first > 12, it must be DD/MM/YYYY
        if first > 12 and second <= 12:
            try:
                val_date = date(y, second, first)
                return val_date.isoformat(), None
            except ValueError as exc:
                return None, f"Impossible calendar date ({exc})."
        # If second > 12, it must be MM/DD/YYYY
        elif second > 12 and first <= 12:
            try:
                val_date = date(y, first, second)
                return val_date.isoformat(), None
            except ValueError as exc:
                return None, f"Impossible calendar date ({exc})."
        # Both <= 12: standard international convention is DD/MM/YYYY
        else:
            try:
                val_date = date(y, second, first)
                return val_date.isoformat(), None
            except ValueError:
                try:
                    val_date = date(y, first, second)
                    return val_date.isoformat(), None
                except ValueError as exc:
                    return None, f"Impossible calendar date ({exc})."

    return None, "Unrecognized date format."


# ==============================================================================
# 5. Field-Specific Conservative OCR Normalization
# ==============================================================================

def normalize_field_ocr_confusions(field_name: str, raw_text: str) -> str:
    """
    Apply conservative, field-specific OCR character replacements without global corruption.
    - Dates: 'O'/'o' -> '0', 'l'/'I' -> '1', 'S'/'s' -> '5', 'B' -> '8'.
    - Passport Numbers: standard alphanumeric normalization and uppercase conversion.
    - Names: preserve letters, hyphens, apostrophes, Unicode chars.
    """
    text = raw_text.strip()
    if not text:
        return ""

    if field_name in {"date_of_birth", "date_of_issue", "date_of_expiry"}:
        # In purely numeric date components, normalize OCR confusions
        def _replace_date_confusions(match: re.Match[str]) -> str:
            segment = match.group(0)
            tr = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "S": "5", "s": "5", "B": "8"})
            return segment.translate(tr)

        # Apply substitution only to digit-like token groups
        normalized = re.sub(
            r"\b[0-9OolISsB]{1,4}\s*[-/. ]\s*[0-9OolISsB]{1,4}\s*[-/. ]\s*[0-9OolISsB]{2,4}\b",
            _replace_date_confusions,
            text,
        )
        normalized = re.sub(r"(?<=[\d\-/./])\s+(?=[\d\-/./])", "", normalized)
        return normalized

    if field_name == "passport_number":
        # Remove whitespace and punctuation
        compact = re.sub(r"[\s\-_.]+", "", text).upper()
        # Only normalize 'O' to '0' if the string already has digits (i.e. is an alphanumeric passport code)
        if any(c.isdigit() for c in compact):
            chars = list(compact)
            for idx in range(1, len(chars)):
                if chars[idx] == "O":
                    chars[idx] = "0"
            compact = "".join(chars)
        return compact

    if field_name in {"surname", "given_names", "full_name"}:
        # Strip digits or invalid OCR noise symbols from names
        cleaned = re.sub(r"[0-9_#$*@+=\[\]{}<>]+", "", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" :-/|_")
        return cleaned.upper()

    if field_name == "sex":
        tok = text.upper().split()[0].strip(" :/.-_")
        if tok in {"M", "MALE", "MASCULIN", "HOMBRE"}:
            return "M"
        if tok in {"F", "FEMALE", "FEMININ", "FÉMININ", "MUJER"}:
            return "F"
        if tok in {"X", "UNSPECIFIED"}:
            return "X"
        if tok == "<":
            return "<"
        return tok

    if field_name == "nationality":
        cleaned = re.sub(r"[^A-Za-zÀ-ÿ\s]", "", text).strip().upper()
        return cleaned

    if field_name == "place_of_birth":
        # Preserve commas, dots, hyphens
        cleaned = re.sub(r"\s+", " ", text).strip(" :-/|_")
        return cleaned.upper()

    return text.strip()


# ==============================================================================
# 6. Label Remainder Cleaner (Multilingual Support)
# ==============================================================================

def clean_label_remainder(remainder: str) -> str:
    """
    Strip chained bilingual/trilingual secondary/tertiary label prefixes to isolate the actual field value.
    Example:
      '/ Lieu de naissance / Lugar de nacimiento: FLORIDA, U.S.A.' -> 'FLORIDA, U.S.A.'
      'Nationality/Nationalite/Nacio' -> ''
    """
    cleaned = remainder.strip(" :-/|_\\")
    if not cleaned:
        return ""
    if ":" in remainder:
        val = remainder.split(":", 1)[1].strip(" :-/|_\\")
        if val:
            return val
    # Split across whitespace and delimiter symbols (/, |, \, -)
    tokens = [t for t in re.split(r"[\s/\-|\\:]+", cleaned) if t]
    idx = 0
    while idx < len(tokens):
        w = re.sub(r"[^a-zA-ZáéíóúÁÉÍÓÚàèìòùÀÈÌÒÙâêîôûÂÊÎÔÛäëïöüÄËÏÖÜñÑçÇ]", "", tokens[idx].lower())
        if w in _LABEL_WORD_SET or not w:
            idx += 1
        else:
            break
    remaining_tokens = tokens[idx:]
    if not remaining_tokens:
        return ""
    first_val = remaining_tokens[0]
    pos = cleaned.find(first_val)
    if pos != -1:
        return cleaned[pos:].strip(" :-/|_\\")
    return " ".join(remaining_tokens).strip(" :-/|_\\")


# ==============================================================================
# 7. Candidate Validation Logic
# ==============================================================================

def validate_field_candidate(field_name: str, raw_candidate: str) -> Tuple[Optional[str], str, Optional[str]]:
    """
    Validate a candidate value for field_name.
    Returns: (normalized_value, validation_status, rejection_reason)
    """
    val = normalize_field_ocr_confusions(field_name, raw_candidate)
    if not val:
        return None, "missing", "Candidate value is empty after normalization."

    # Validate Dates
    if field_name in {"date_of_birth", "date_of_issue", "date_of_expiry"}:
        iso_val, err = parse_and_validate_date(val)
        if iso_val is not None:
            try:
                parsed_d = date.fromisoformat(iso_val)
                today = date.today()
                if field_name == "date_of_birth" and parsed_d > today:
                    return None, "invalid", "Date of birth cannot be in the future."
                if field_name == "date_of_issue" and parsed_d > today + timedelta(days=60):
                    return None, "invalid", "Date of issue cannot be in the future."
            except Exception:
                pass
            return iso_val, "valid", None
        return None, "invalid", err or "Invalid date format or calendar date."

    # Validate Passport Number
    if field_name == "passport_number":
        compact = re.sub(r"[\s-]+", "", val)
        # Check if candidate is actually a calendar date
        d_val, _ = parse_and_validate_date(compact)
        if d_val is not None:
            return None, "invalid", "Candidate is a valid calendar date, not a passport number."
        if 5 <= len(compact) <= 15 and compact.isalnum():
            # Check for false candidates in unrelated text
            if compact.isalpha() and len(compact) > 9:
                return None, "invalid", "Candidate consists solely of letters and resembles word text."
            return compact, "valid", None
        return None, "invalid", "Candidate failed 5-15 alphanumeric passport number format check."

    # Validate Sex
    if field_name == "sex":
        norm_s = val.upper().strip()
        if norm_s in {"M", "MALE", "MASCULIN"}:
            return "M", "valid", None
        if norm_s in {"F", "FEMALE", "FEMININ", "FÉMININ"}:
            return "F", "valid", None
        if norm_s in {"X", "UNSPECIFIED"}:
            return "X", "valid", None
        if norm_s in {"<"}:
            return "<", "valid", None
        return None, "invalid", "Unrecognized sex marker candidate."

    # Validate Nationality
    if field_name == "nationality":
        norm_code = NATIONALITY_NAME_TO_CODE.get(val.upper())
        if norm_code:
            return val.upper(), "valid", None
        if len(val) == 3 and val.isalpha():
            return val.upper(), "unverified", "Country code is not in standard ISO-3166-1 table."
        words_in_val = [re.sub(r"[^a-zA-Z]", "", w.lower()) for w in val.split()]
        if any(w in _LABEL_WORD_SET for w in words_in_val if w):
            return None, "invalid", "Candidate resembles label text rather than a nationality."
        if 2 <= len(val) <= 40:
            return val.upper(), "unverified", "Nationality is unverified against standard registry."
        return None, "invalid", "Invalid nationality format."

    # Validate Names
    if field_name in {"surname", "given_names", "full_name"}:
        cleaned = re.sub(r"[^A-Za-zÀ-ÿ\s\-'.]", "", val).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        words = cleaned.upper().split()
        _DISALLOWED_NAME_WORDS = {
            "RECEIPT", "DOCUMENT", "BEARER", "SIGN", "CONTAINS", "PAGES",
            "NOTICE", "WARNING", "IMPORTANT", "OFFICIAL", "IMMEDIATELY",
            "AUTHORITY", "DEPARTMENT", "HOLDER", "SIGNATURE", "PASSPORT", "PASSEPORT",
        }
        if any(w in _DISALLOWED_NAME_WORDS for w in words):
            return None, "invalid", "Candidate resembles instructional notice or document text."
        if field_name == "full_name" and len(words) > 4:
            return None, "invalid", "Candidate contains too many words to be a personal name."
        if 1 <= len(cleaned) <= 80:
            return cleaned.upper(), "valid", None
        return None, "invalid", "Invalid name format."

    # Validate Place of Birth
    if field_name == "place_of_birth":
        cleaned = re.sub(r"\s+", " ", val).strip(" :-/|_")
        words = [re.sub(r"[^a-zA-Z]", "", w.lower()) for w in cleaned.split()]
        _POB_DISALLOWED_WORDS = {
            "passport", "passeport", "pasaporte", "pesaporte", "epori", "eporino",
            "document", "republic", "republique", "republica", "signature",
            "titular", "titulaire", "bearer", "autorite", "authority", "department",
            "united", "states"
        }
        if any(w in _POB_DISALLOWED_WORDS for w in words):
            return None, "invalid", "Candidate resembles document header or authority text."
        if all(w in _LABEL_WORD_SET or not w for w in words):
            return None, "invalid", "Candidate resembles label text rather than a place of birth."
        if "." in val and "," not in cleaned:
            parts = val.split(".", 1)
            p1, p2 = parts[0].strip(), parts[1].strip().upper()
            if p2 in NATIONALITY_NAME_TO_CODE or p2 in ISO_NATIONALITY_REGISTRY or p2 in {"USA", "US", "CAN", "UK", "GBR", "U.S.A.", "U.S."}:
                cleaned = f"{p1}, {p2}"
        if 2 <= len(cleaned) <= 80:
            return cleaned.upper(), "valid", None
        return None, "invalid", "Place of birth candidate out of length bounds."

    # Validate Document Type
    if field_name == "document_type":
        tok = val.upper().strip()
        if "RESIDENCE" in tok or "PERMIT" in tok:
            return "RESIDENCE PERMIT", "valid", None
        if "IDENTITY" in tok or tok in {"ID", "IDENTITY CARD"}:
            return "ID", "valid", None
        if "VISA" in tok or tok == "V":
            return "V", "valid", None
        if tok in {"P", "PA", "PM", "PO", "PS", "PT"}:
            return tok[0] if tok.startswith("P") and len(tok) == 1 else tok, "valid", None
        if "PASSPORT" in tok or "PASSEPORT" in tok or "PASAPORTE" in tok:
            return "P", "valid", None
        return None, "unverified", "Unrecognized document type code."

    # Validate Issuing Country / Authority
    if field_name == "issuing_country":
        tok = val.upper().strip()
        if "UNTTED" in tok or "UNITED STATES" in tok:
            return "USA", "valid", None
        _LABEL_NOISE = {"CODE", "CODE D'AUTORITE", "AUTORITE", "AUTHORITY CODE", "COUNTRY CODE", "CODE DU PAYS"}
        if tok in _LABEL_NOISE or tok.startswith("CODE/") or "CODE D'AUTORITE" in tok:
            return None, "invalid", "Candidate resembles label text rather than issuing authority."
        cleaned = re.sub(r"[^A-Z]", "", tok)
        if len(cleaned) == 3 and cleaned in NATIONALITY_NAME_TO_CODE:
            return cleaned, "valid", None
        if 2 <= len(tok) <= 60:
            return tok, "valid", None
        return None, "invalid", "Invalid issuing authority format."

    # Personal Number
    if field_name == "personal_number":
        compact = re.sub(r"[\s-]+", "", val.upper())
        if 3 <= len(compact) <= 25 and compact.isalnum():
            return compact, "valid", None
        return None, "invalid", "Invalid personal number format."

    return val, "valid", None


# ==============================================================================
# 8. Main Regex Field Extraction Function
# ==============================================================================

FIELD_PATTERN_MAP = {
    "passport_number": PASSPORT_NUMBER_PATTERNS,
    "surname": SURNAME_PATTERNS,
    "given_names": GIVEN_NAMES_PATTERNS,
    "full_name": FULL_NAME_PATTERNS,
    "date_of_birth": DOB_PATTERNS,
    "date_of_issue": ISSUE_DATE_PATTERNS,
    "date_of_expiry": EXPIRY_DATE_PATTERNS,
    "nationality": NATIONALITY_PATTERNS,
    "sex": SEX_PATTERNS,
    "place_of_birth": PLACE_OF_BIRTH_PATTERNS,
    "document_type": DOC_TYPE_PATTERNS,
    "issuing_country": ISSUING_AUTHORITY_PATTERNS,
    "personal_number": PERSONAL_NUMBER_PATTERNS,
}


def extract_regex_field_candidates(
    blocks: List[OcrTextBlock],
    mrz_raw_lines: Optional[List[str]] = None,
) -> Dict[str, RegexFieldCandidate]:
    """
    Perform pure and spatial Regex extraction on OCR text blocks.
    Returns a structured dictionary of RegexFieldCandidate objects for each supported field.
    """
    target_fields = list(FIELD_PATTERN_MAP.keys())
    candidates: Dict[str, RegexFieldCandidate] = {
        fname: RegexFieldCandidate(field_name=fname, validation_status="missing") for fname in target_fields
    }

    if not blocks:
        return candidates

    mrz_set: Set[str] = {ln.strip() for ln in (mrz_raw_lines or []) if ln.strip()}
    viz_blocks: List[OcrTextBlock] = []
    for b in blocks:
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
        for field_name, patterns in FIELD_PATTERN_MAP.items():
            if candidates[field_name].validation_status == "valid":
                continue

            for pattern in patterns:
                match = pattern.search(text)
                if not match:
                    continue

                # 1. Inline extraction candidate
                raw_val = match.groupdict().get("val")
                if not raw_val:
                    # Value might be remainder after label
                    remainder = text[match.end() :].strip()
                    raw_val = clean_label_remainder(remainder)
                else:
                    raw_val = clean_label_remainder(raw_val)

                if raw_val:
                    norm_val, status, err_reason = validate_field_candidate(field_name, raw_val)
                    if status == "valid" and norm_val is not None:
                        claimed_block_indices.add(idx)
                        candidates[field_name] = RegexFieldCandidate(
                            field_name=field_name,
                            value=norm_val,
                            raw_evidence=text,
                            source="viz",
                            ocr_confidence=block.confidence,
                            validation_status="valid",
                            notes=["Matched labeled inline pattern."],
                        )
                        break
                    elif status in {"invalid", "unverified"} and candidates[field_name].validation_status == "missing":
                        candidates[field_name] = RegexFieldCandidate(
                            field_name=field_name,
                            value=norm_val,
                            raw_evidence=text,
                            source="viz",
                            ocr_confidence=block.confidence,
                            validation_status=status,
                            rejection_reason=err_reason,
                            notes=[err_reason or "Invalid inline value."],
                        )

                # 2. Spatial extraction candidate (next line / neighbor below or to right)
                claimed_block_indices.add(idx)
                for next_idx in range(idx + 1, min(idx + 6, len(viz_blocks))):
                    if next_idx in claimed_block_indices:
                        continue
                    next_block = viz_blocks[next_idx]
                    next_text = next_block.text.strip()
                    cleaned_next = clean_label_remainder(next_text)
                    if not cleaned_next:
                        continue

                    # Don't grab another label line as value
                    is_another_label = any(p.search(next_text) for p_list in FIELD_PATTERN_MAP.values() for p in p_list)
                    if is_another_label:
                        break

                    norm_val, status, err_reason = validate_field_candidate(field_name, cleaned_next)
                    if status == "valid" and norm_val is not None:
                        claimed_block_indices.add(next_idx)
                        combined_conf = round((block.confidence + next_block.confidence) / 2.0, 4)
                        candidates[field_name] = RegexFieldCandidate(
                            field_name=field_name,
                            value=norm_val,
                            raw_evidence=f"{block.text} -> {next_block.text}",
                            source="viz",
                            ocr_confidence=combined_conf,
                            validation_status="valid",
                            notes=["Extracted via spatial label-value alignment."],
                        )
                        break
                    elif status == "unverified" and candidates[field_name].validation_status == "missing":
                        candidates[field_name] = RegexFieldCandidate(
                            field_name=field_name,
                            value=norm_val,
                            raw_evidence=f"{block.text} -> {next_block.text}",
                            source="viz",
                            ocr_confidence=next_block.confidence,
                            validation_status=status,
                            rejection_reason=err_reason,
                            notes=[err_reason or "Unverified spatial candidate."],
                        )
                break

    # 3. Full Name Derivation (Section 3.C)
    surname_cand = candidates["surname"]
    given_cand = candidates["given_names"]
    full_cand = candidates["full_name"]

    if surname_cand.value and given_cand.value and not full_cand.value:
        confs = [c for c in (surname_cand.ocr_confidence, given_cand.ocr_confidence) if c is not None]
        candidates["full_name"] = RegexFieldCandidate(
            field_name="full_name",
            value=f"{given_cand.value} {surname_cand.value}",
            raw_evidence=f"{given_cand.value} {surname_cand.value}",
            source="derived",
            ocr_confidence=round(sum(confs) / len(confs), 4) if confs else None,
            validation_status="valid",
            notes=["Derived from extracted given names and surname."],
        )
    elif full_cand.value and (not surname_cand.value or not given_cand.value):
        parts = full_cand.value.split()
        if len(parts) >= 2:
            if not given_cand.value:
                candidates["given_names"] = RegexFieldCandidate(
                    field_name="given_names",
                    value=" ".join(parts[:-1]),
                    raw_evidence=full_cand.raw_evidence,
                    source="derived",
                    ocr_confidence=full_cand.ocr_confidence,
                    validation_status="valid",
                    notes=["Derived from full name."],
                )
            if not surname_cand.value:
                candidates["surname"] = RegexFieldCandidate(
                    field_name="surname",
                    value=parts[-1],
                    raw_evidence=full_cand.raw_evidence,
                    source="derived",
                    ocr_confidence=full_cand.ocr_confidence,
                    validation_status="valid",
                    notes=["Derived from full name."],
                )

    return candidates
