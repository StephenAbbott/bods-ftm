from __future__ import annotations

from followthemoney import model
from followthemoney.proxy import EntityProxy

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
    # FtM 4.11.3: ``irsCode`` (US EIN, on Organization and its subclasses)
    # and ``cikCode`` (SEC Central Index Key, on LegalEntity). Where the FtM
    # schema has no irsCode (a bare LegalEntity) or FtM refuses the value as
    # an EIN, the entity mapper writes it to taxNumber instead.
    "US-EIN": "irsCode",
    "US-SEC-CIK": "cikCode",
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
    "irsCode": "US-EIN",
    "cikCode": "US-SEC-CIK",
}

# Where an identifier's dedicated FtM property is absent from the schema, or
# FtM's cleaning refuses the value, it is written here instead so it is not
# lost.
FTM_PROPERTY_FALLBACK: dict[str, str] = {
    "irsCode": "taxNumber",
    "cikCode": "registrationNumber",
}


# BODS schemes that are handled specially in entity_mapper (not via a simple
# FTM property assignment) or have no FTM equivalent.  Callers should check
# for these before calling bods_scheme_to_ftm_property.
#
# OPENCORPORATES: the ``id`` is a company path (e.g. "se/556056-6258");
#   entity_mapper constructs the full URL and sets ``opencorporatesUrl``.
# QCC Code, ISO-10383, ISO-9362: GLEIF LEI Mapping identifiers for which
#   the FtM LegalEntity schema has no corresponding property; they are
#   preserved in BODS output but not round-trippable through FtM.
BODS_SCHEMES_NO_FTM_PROPERTY: frozenset[str] = frozenset({
    "OPENCORPORATES",
    "QCC Code",
    "ISO-10383",
    "ISO-9362",
})


def bods_scheme_to_ftm_property(scheme: str) -> str | None:
    """Return the FTM property name for a BODS identifier scheme code.

    Returns ``None`` for schemes in ``BODS_SCHEMES_NO_FTM_PROPERTY`` (either
    handled specially by the caller or having no FtM equivalent).
    Falls back to ``registrationNumber`` for all other unknown schemes.
    """
    if scheme in BODS_SCHEMES_NO_FTM_PROPERTY:
        return None
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


def add_identifier(proxy: EntityProxy, ftm_prop: str, value: str) -> None:
    """Add an identifier to ``proxy``, falling back (``FTM_PROPERTY_FALLBACK``)
    when the schema lacks the property or FtM's cleaning refuses the value."""
    if proxy.schema.get(ftm_prop) is not None:
        # Clean on a scratch entity first: an add FtM refuses is silent.
        probe = model.make_entity(proxy.schema)
        probe.add(ftm_prop, value, quiet=True)
        if probe.get(ftm_prop, quiet=True):
            proxy.add(ftm_prop, value, quiet=True)
            return
    fallback = FTM_PROPERTY_FALLBACK.get(ftm_prop)
    if fallback:
        proxy.add(fallback, value, quiet=True)
