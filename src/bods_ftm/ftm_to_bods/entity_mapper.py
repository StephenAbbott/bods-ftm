from __future__ import annotations

from typing import Any

from followthemoney.proxy import EntityProxy

from bods_ftm.config import PublisherConfig
from bods_ftm.ftm_to_bods.identifier_mapper import extract_entity_identifiers
from bods_ftm.utils.dates import normalise_date
from bods_ftm.utils.ids import ftm_id_to_bods_record_id, ftm_id_to_bods_statement_id
from bods_ftm.utils.statements import entity_statement, publication_details

# Maps FTM schema names to BODS entityType.type values
FTM_SCHEMA_TO_ENTITY_TYPE: dict[str, str] = {
    "Company": "registeredEntity",
    "Organization": "legalEntity",
    "LegalEntity": "legalEntity",
    "PublicBody": "stateBody",
}


def ftm_entity_to_bods(
    proxy: EntityProxy,
    config: PublisherConfig,
) -> dict[str, Any] | None:
    """Convert an FTM Company/Organization/LegalEntity/PublicBody proxy to a
    BODS v0.4 entity statement.

    Returns None if the proxy cannot be meaningfully represented as an entity
    statement (e.g. no name).
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

    entity_type_str = FTM_SCHEMA_TO_ENTITY_TYPE.get(proxy.schema.name, "legalEntity")

    # Canonical 0.4: `name` is a single string; alternates go in `alternateNames`.
    all_names = [n for n in proxy.get("name", quiet=True) if n]
    primary_name = all_names[0]
    alternate_names = all_names[1:] + [a for a in proxy.get("alias", quiet=True) if a]

    # Jurisdiction
    jurisdiction_code = proxy.first("jurisdiction", quiet=True)
    jurisdiction: dict[str, str] | None = None
    if jurisdiction_code:
        jurisdiction = {"code": jurisdiction_code.upper()}

    founding = normalise_date(proxy.first("incorporationDate", quiet=True))
    dissolution = normalise_date(proxy.first("dissolutionDate", quiet=True))

    identifiers = extract_entity_identifiers(proxy, jurisdiction_code)
    addresses = _extract_addresses(proxy)

    record_details: dict[str, Any] = {
        "entityType": {"type": entity_type_str},
        "name": primary_name,
        "isComponent": False,
    }

    if alternate_names:
        record_details["alternateNames"] = alternate_names
    if identifiers:
        record_details["identifiers"] = identifiers
    if jurisdiction:
        record_details["jurisdiction"] = jurisdiction
    if founding:
        record_details["foundingDate"] = founding
    if dissolution:
        record_details["dissolutionDate"] = dissolution
    if addresses:
        record_details["addresses"] = addresses

    statement_date = proxy.first("modifiedAt", quiet=True) or config.publication_date

    return entity_statement(
        statement_id, record_id, record_details, pub_details, statement_date
    )


def _extract_addresses(proxy: EntityProxy) -> list[dict[str, Any]]:
    """Build BODS address objects from FTM address and country properties."""
    addresses: list[dict[str, Any]] = []

    country_codes = list(proxy.get("country", quiet=True))
    raw_addresses = list(proxy.get("address", quiet=True))

    if raw_addresses:
        for idx, addr_str in enumerate(raw_addresses):
            addr: dict[str, Any] = {"type": "registered", "address": addr_str}
            if idx < len(country_codes):
                addr["country"] = {"code": country_codes[idx].upper()}
            addresses.append(addr)
    elif country_codes:
        for code in country_codes:
            addresses.append({"type": "registered", "country": {"code": code.upper()}})

    return addresses
