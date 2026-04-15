from __future__ import annotations

from typing import Any

from followthemoney import model
from followthemoney.proxy import EntityProxy

from bods_ftm.bods_to_ftm.identifier_mapper import bods_scheme_to_ftm_property
from bods_ftm.utils.dates import normalise_date
from bods_ftm.utils.ids import bods_statement_id_to_ftm_id

# Maps BODS entityType.type values to FTM schema names
ENTITY_TYPE_TO_FTM_SCHEMA: dict[str, str] = {
    "registeredEntity": "Company",
    "legalEntity": "Organization",
    "arrangement": "LegalEntity",
    "anonymousEntity": "LegalEntity",
    "unknownEntity": "LegalEntity",
    "state": "PublicBody",
    "stateBody": "PublicBody",
}


def entity_statement_to_ftm(statement: dict[str, Any]) -> EntityProxy | None:
    """Convert a BODS v0.4 entity statement to an FTM entity proxy.

    Returns None if the statement lacks enough data to produce a meaningful
    FTM entity.
    """
    details = statement.get("recordDetails", {})

    entity_type_obj = details.get("entityType", {})
    entity_type_str = (
        entity_type_obj.get("type") if isinstance(entity_type_obj, dict) else entity_type_obj
    )
    ftm_schema = ENTITY_TYPE_TO_FTM_SCHEMA.get(entity_type_str or "", "LegalEntity")

    proxy: EntityProxy = model.make_entity(ftm_schema)
    proxy.id = bods_statement_id_to_ftm_id(statement["statementId"])

    # Names
    for name_obj in details.get("names", []):
        full_name = name_obj.get("fullName")
        if full_name:
            proxy.add("name", full_name, quiet=True)

    if not proxy.has("name"):
        return None

    # Jurisdiction / incorporation
    jurisdiction = details.get("incorporatedInJurisdiction", {})
    if isinstance(jurisdiction, dict):
        juris_code = jurisdiction.get("code")
        if juris_code:
            proxy.add("jurisdiction", juris_code.lower(), quiet=True)

    # Dates
    founding = normalise_date(details.get("foundingDate"))
    if founding:
        proxy.add("incorporationDate", founding, quiet=True)

    dissolution = normalise_date(details.get("dissolutionDate"))
    if dissolution:
        proxy.add("dissolutionDate", dissolution, quiet=True)

    # Identifiers
    for id_obj in details.get("identifiers", []):
        id_value = id_obj.get("id")
        scheme = id_obj.get("scheme", "")
        if id_value:
            ftm_prop = bods_scheme_to_ftm_property(scheme)
            proxy.add(ftm_prop, id_value, quiet=True)

    # Addresses
    for addr_obj in details.get("addresses", []):
        address_str = addr_obj.get("address")
        if address_str:
            proxy.add("address", address_str, quiet=True)
        country_obj = addr_obj.get("country", {})
        if isinstance(country_obj, dict):
            country_code = country_obj.get("code")
            if country_code:
                proxy.add("country", country_code.lower(), quiet=True)

    # Public listing: ticker symbols
    public_listing = details.get("publicListing", {})
    for listing in public_listing.get("securitiesListings", []):
        ticker = listing.get("tickerSymbol")
        if ticker:
            proxy.add("ticker", ticker, quiet=True)

    # Source provenance
    statement_date = statement.get("statementDate")
    if statement_date:
        proxy.add("modifiedAt", statement_date, quiet=True)

    pub_details = statement.get("publicationDetails", {})
    publisher = pub_details.get("publisher", {})
    publisher_name = publisher.get("name") if isinstance(publisher, dict) else None
    if publisher_name:
        proxy.add("publisher", publisher_name, quiet=True)

    pub_uri = publisher.get("uri") if isinstance(publisher, dict) else None
    if pub_uri:
        proxy.add("sourceUrl", pub_uri, quiet=True)

    return proxy
