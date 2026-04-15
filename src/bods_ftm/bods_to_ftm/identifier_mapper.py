from __future__ import annotations

# Mapping from BODS identifier scheme codes (org-id.guide format) to
# FollowTheMoney Company property names.
# Where no specific FTM property exists, falls back to registrationNumber.
SCHEME_TO_FTM_PROPERTY: dict[str, str] = {
    # International / cross-jurisdictional
    "XI-LEI": "leiCode",
    "ISIN": "isin",
    "DUNS": "dunsCode",
    # United Kingdom
    "GB-COH": "registrationNumber",
    # United States
    "US-EIN": "taxNumber",
    "US-SEC-CIK": "registrationNumber",
    # European Union / Member States
    "BE-BCE_KBO": "registrationNumber",
    "DE-HRB": "registrationNumber",
    "FR-RCS": "registrationNumber",
    "NL-KVK": "registrationNumber",
    "IT-REA": "registrationNumber",
    "ES-CIF": "taxNumber",
    "PL-KRS": "registrationNumber",
    "SE-BV": "registrationNumber",
    "DK-CVR": "registrationNumber",
    "NO-BRREG": "registrationNumber",
    "FI-PRH": "registrationNumber",
    "AT-FB": "registrationNumber",
    "PT-RNPC": "registrationNumber",
    "CZ-ARES": "registrationNumber",
    "HU-CG": "registrationNumber",
    "RO-TR": "registrationNumber",
    "BG-TR": "registrationNumber",
    # Russia
    "RU-INN": "innCode",
    "RU-OGRN": "ogrnCode",
    # Other jurisdictions
    "AU-ABN": "taxNumber",
    "CA-BN": "registrationNumber",
    "IN-MCA": "registrationNumber",
    "SG-ACRA": "registrationNumber",
    "HK-CR": "registrationNumber",
    "CN-SAIC": "registrationNumber",
    "JP-HAJ": "registrationNumber",
    "UA-EDR": "registrationNumber",
    "BR-CNPJ": "registrationNumber",
    "ZA-CIPC": "registrationNumber",
}

# Reverse mapping for FTM→BODS: FTM property name → BODS scheme code.
# Where multiple schemes map to the same FTM property, the most widely-used
# international code is preferred; callers can override with jurisdiction context.
FTM_PROPERTY_TO_SCHEME: dict[str, str] = {
    "leiCode": "XI-LEI",
    "isin": "ISIN",
    "dunsCode": "DUNS",
    "registrationNumber": "GB-COH",  # placeholder; override with jurisdiction
    "taxNumber": "US-EIN",           # placeholder; override with jurisdiction
    "innCode": "RU-INN",
    "ogrnCode": "RU-OGRN",
}


def bods_scheme_to_ftm_property(scheme: str) -> str:
    """Return the FTM property name for a BODS identifier scheme code.

    Falls back to registrationNumber for unknown schemes.
    """
    return SCHEME_TO_FTM_PROPERTY.get(scheme, "registrationNumber")


def ftm_property_to_bods_scheme(
    prop: str,
    jurisdiction_code: str | None = None,
) -> str:
    """Return the BODS identifier scheme for an FTM property name.

    When jurisdiction_code is provided, attempts a jurisdiction-specific
    scheme (e.g. "GB-COH" for registrationNumber + "GB").
    """
    if prop == "registrationNumber" and jurisdiction_code:
        candidate = f"{jurisdiction_code.upper()}-COH"
        if candidate in SCHEME_TO_FTM_PROPERTY:
            return candidate
    if prop == "taxNumber" and jurisdiction_code:
        candidate = f"{jurisdiction_code.upper()}-TAX"
        if candidate in SCHEME_TO_FTM_PROPERTY:
            return candidate
    return FTM_PROPERTY_TO_SCHEME.get(prop, "misc")
