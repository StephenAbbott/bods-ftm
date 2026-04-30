from __future__ import annotations

from typing import Any

import pycountry
from followthemoney.proxy import EntityProxy

from bods_ftm.config import PublisherConfig
from bods_ftm.ftm_to_bods.identifier_mapper import extract_person_identifiers
from bods_ftm.utils.dates import normalise_date
from bods_ftm.utils.ids import ftm_id_to_bods_record_id, ftm_id_to_bods_statement_id
from bods_ftm.utils.statements import person_statement, publication_details


def ftm_person_to_bods(
    proxy: EntityProxy,
    config: PublisherConfig,
) -> dict[str, Any] | None:
    """Convert an FTM Person proxy to a BODS v0.4 person statement.

    Returns None if the proxy has no usable name.
    """
    name = proxy.first("name", quiet=True)
    if not name:
        return None

    statement_id = ftm_id_to_bods_statement_id(proxy.id)
    record_id = ftm_id_to_bods_record_id(proxy.id)
    pub_details = publication_details(
        publisher_name=config.publisher_name,
        publisher_uri=config.publisher_uri,
        license_url=config.license_url,
        bods_version=config.bods_version,
    )

    names = [{"fullName": n} for n in proxy.get("name", quiet=True) if n]

    # Nationalities — FTM normalises to 2-letter ISO codes via EntityProxy,
    # so a pycountry lookup always succeeds for valid values. We emit both
    # name and code so the BODS output is self-describing.
    nationalities: list[dict[str, str]] = []
    for code in list(proxy.get("nationality", quiet=True)) + list(proxy.get("citizenship", quiet=True)):
        if not code:
            continue
        entry = _resolve_nationality(code)
        if entry not in nationalities:
            nationalities.append(entry)

    # Birth date
    birth_date = normalise_date(proxy.first("birthDate", quiet=True))

    # Identifiers
    identifiers = extract_person_identifiers(proxy)

    # Addresses
    addresses: list[dict[str, Any]] = []
    for addr_str in proxy.get("address", quiet=True):
        if addr_str:
            addresses.append({"type": "residence", "address": addr_str})
    for code in proxy.get("country", quiet=True):
        if code:
            # Attach country to first address if possible, else create standalone
            if addresses:
                addresses[0].setdefault("country", {"code": code.upper()})
            else:
                addresses.append({"type": "residence", "country": {"code": code.upper()}})

    record_details: dict[str, Any] = {
        "personType": "knownPerson",
        "names": names,
        "isComponent": False,
    }

    if nationalities:
        record_details["nationalities"] = nationalities
    if birth_date:
        record_details["birthDate"] = birth_date
    if identifiers:
        record_details["identifiers"] = identifiers
    if addresses:
        record_details["addresses"] = addresses

    # PEP: FTM position → BODS politicalExposure
    positions = list(proxy.get("position", quiet=True))
    if positions:
        record_details["politicalExposure"] = {
            "status": "isPep",
            "details": [{"reason": pos} for pos in positions],
        }

    statement_date = proxy.first("modifiedAt", quiet=True) or config.publication_date

    return person_statement(
        statement_id, record_id, record_details, pub_details, statement_date
    )


def _resolve_nationality(code: str) -> dict[str, str]:
    """Resolve an FTM nationality/citizenship code to a BODS nationality entry.

    FTM normalises nationality to 2-letter ISO codes, so pycountry lookups
    succeed for all well-formed values. Falls back to ``{"code": upper}``
    for any code that isn't in pycountry (e.g. custom or legacy values).
    """
    upper = code.strip().upper()
    try:
        country = pycountry.countries.lookup(upper)
        return {"name": country.name, "code": country.alpha_2}
    except LookupError:
        return {"code": upper}
