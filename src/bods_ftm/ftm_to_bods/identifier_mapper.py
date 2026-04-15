from __future__ import annotations

from followthemoney.proxy import EntityProxy

# FTM Company/Organization identifier properties that should become
# BODS identifiers, with the fallback BODS scheme code to use.
# The scheme code is indicative — callers should override using
# jurisdiction context when it is available.
FTM_IDENTIFIER_PROPERTIES: dict[str, str] = {
    "registrationNumber": "misc-regnum",
    "taxNumber": "misc-tax",
    "leiCode": "XI-LEI",
    "isin": "misc-isin",
    "dunsCode": "misc-duns",
    "innCode": "RU-INN",
    "ogrnCode": "RU-OGRN",
}

# FTM Person identifier properties
FTM_PERSON_IDENTIFIER_PROPERTIES: dict[str, str] = {
    "idNumber": "misc-id",
    "passportNumber": "misc-passport",
    "taxNumber": "misc-tax",
    "socialSecurityNumber": "misc-ssn",
}


def extract_entity_identifiers(
    proxy: EntityProxy,
    jurisdiction_code: str | None = None,
) -> list[dict[str, str]]:
    """Extract BODS-format identifier objects from an FTM entity proxy."""
    identifiers: list[dict[str, str]] = []

    for ftm_prop, default_scheme in FTM_IDENTIFIER_PROPERTIES.items():
        for value in proxy.get(ftm_prop, quiet=True):
            if not value:
                continue
            scheme = _resolve_scheme(ftm_prop, default_scheme, jurisdiction_code)
            identifiers.append({"id": value, "scheme": scheme})

    return identifiers


def extract_person_identifiers(proxy: EntityProxy) -> list[dict[str, str]]:
    """Extract BODS-format identifier objects from an FTM Person proxy."""
    identifiers: list[dict[str, str]] = []

    for ftm_prop, default_scheme in FTM_PERSON_IDENTIFIER_PROPERTIES.items():
        for value in proxy.get(ftm_prop, quiet=True):
            if not value:
                continue
            identifiers.append({"id": value, "scheme": default_scheme})

    return identifiers


def _resolve_scheme(
    ftm_prop: str,
    default_scheme: str,
    jurisdiction_code: str | None,
) -> str:
    """Attempt to resolve a jurisdiction-specific scheme code."""
    if not jurisdiction_code:
        return default_scheme

    juris = jurisdiction_code.upper()

    # Well-known jurisdiction → scheme mappings for registration numbers
    _juris_regnum_schemes = {
        "GB": "GB-COH",
        "US": "US-EIN",
        "DE": "DE-HRB",
        "FR": "FR-RCS",
        "NL": "NL-KVK",
        "BE": "BE-BCE_KBO",
        "SE": "SE-BV",
        "DK": "DK-CVR",
        "NO": "NO-BRREG",
        "AU": "AU-ABN",
        "CA": "CA-BN",
        "IN": "IN-MCA",
        "SG": "SG-ACRA",
        "UA": "UA-EDR",
        "BR": "BR-CNPJ",
        "ZA": "ZA-CIPC",
    }
    if ftm_prop == "registrationNumber" and juris in _juris_regnum_schemes:
        return _juris_regnum_schemes[juris]

    return default_scheme
