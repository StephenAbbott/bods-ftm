from __future__ import annotations

import pycountry
from followthemoney.proxy import EntityProxy

# FTM Company/Organization identifier properties that should become
# BODS identifiers, with the fallback BODS scheme code to use.
# The scheme code is indicative — callers should override using
# jurisdiction context when it is available.
FTM_IDENTIFIER_PROPERTIES: dict[str, str] = {
    "registrationNumber": "misc-regnum",  # overridden by _resolve_scheme
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

# Well-known jurisdictions that have a dedicated org-id.guide scheme code for
# their company register. For all other jurisdictions we fall back to
# "REG-{alpha2}" (e.g. "REG-SE") rather than the generic "misc-regnum" so
# that reconcilers can bridge on the same identifier across sources.
_KNOWN_REGNUM_SCHEMES: dict[str, str] = {
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


_OC_URL_MARKER = "opencorporates.com/companies/"


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

    # ``opencorporatesUrl`` is a url-type FTM property (not in the identifier
    # property table above).  Extract the company path from the URL and surface
    # it as an OPENCORPORATES scheme identifier so roundtrips are lossless.
    for oc_url in proxy.get("opencorporatesUrl", quiet=True):
        if not oc_url or _OC_URL_MARKER not in oc_url:
            continue
        path = oc_url.split(_OC_URL_MARKER, 1)[1].rstrip("/")
        if path:
            identifiers.append({
                "id": path,
                "scheme": "OPENCORPORATES",
                "schemeName": "OpenCorporates company identifier",
                "uri": oc_url,
            })

    return identifiers


def extract_person_identifiers(proxy: EntityProxy) -> list[dict[str, str]]:
    """Extract BODS-format identifier objects from an FTM Person proxy."""
    identifiers: list[dict[str, str]] = []

    for ftm_prop, default_scheme in FTM_PERSON_IDENTIFIER_PROPERTIES.items():
        for value in proxy.get(ftm_prop, quiet=True):
            if not value:
                continue
            identifiers.append({"id": value, "scheme": default_scheme})

    # ``opencorporatesUrl`` is a url-type FTM property (not in the identifier
    # property table above).  Extract the company path from the URL and surface
    # it as an OPENCORPORATES scheme identifier so roundtrips are lossless.
    for oc_url in proxy.get("opencorporatesUrl", quiet=True):
        if not oc_url or _OC_URL_MARKER not in oc_url:
            continue
        path = oc_url.split(_OC_URL_MARKER, 1)[1].rstrip("/")
        if path:
            identifiers.append({
                "id": path,
                "scheme": "OPENCORPORATES",
                "schemeName": "OpenCorporates company identifier",
                "uri": oc_url,
            })

    return identifiers


def _resolve_scheme(
    ftm_prop: str,
    default_scheme: str,
    jurisdiction_code: str | None,
) -> str:
    """Resolve a jurisdiction-specific scheme code for a registration number.

    For ``registrationNumber``:
    - If the jurisdiction matches a well-known registry with a dedicated
      org-id.guide scheme code (e.g. GB → GB-COH), use that.
    - Otherwise, if the jurisdiction is a valid ISO 3166-1 alpha-2 code,
      use ``REG-{alpha2}`` so reconcilers can bridge across sources on the
      same identifier without resorting to the opaque ``misc-regnum`` fallback.
    - Only fall back to the default scheme (``misc-regnum``) when no
      jurisdiction is known at all.

    All other FTM properties use their fixed scheme codes unchanged.
    """
    if ftm_prop != "registrationNumber" or not jurisdiction_code:
        return default_scheme

    juris = jurisdiction_code.upper()

    # 1. Well-known registry with dedicated org-id.guide scheme.
    if juris in _KNOWN_REGNUM_SCHEMES:
        return _KNOWN_REGNUM_SCHEMES[juris]

    # 2. Any other ISO 3166-1 jurisdiction → REG-{alpha2}.
    try:
        alpha2 = pycountry.countries.lookup(juris).alpha_2
        return f"REG-{alpha2}"
    except LookupError:
        pass

    return default_scheme
