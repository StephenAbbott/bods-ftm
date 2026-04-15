from __future__ import annotations

from typing import Any

from followthemoney import model
from followthemoney.proxy import EntityProxy

from bods_ftm.utils.dates import normalise_date
from bods_ftm.utils.ids import bods_statement_id_to_ftm_id


def person_statement_to_ftm(statement: dict[str, Any]) -> EntityProxy | None:
    """Convert a BODS v0.4 person statement to an FTM Person proxy.

    Returns None for unknownPerson statements that have no identifying data.
    """
    details = statement.get("recordDetails", {})

    person_type = details.get("personType", "knownPerson")
    if person_type == "unknownPerson" and not details.get("names"):
        return None

    proxy: EntityProxy = model.make_entity("Person")
    proxy.id = bods_statement_id_to_ftm_id(statement["statementId"])

    # Names
    for name_obj in details.get("names", []):
        full_name = name_obj.get("fullName")
        if full_name:
            proxy.add("name", full_name, quiet=True)

    if not proxy.has("name"):
        return None

    # Birth date
    birth_date = normalise_date(details.get("birthDate"))
    if birth_date:
        proxy.add("birthDate", birth_date, quiet=True)

    # Nationalities
    for nat_obj in details.get("nationalities", []):
        code = nat_obj.get("code")
        if code:
            proxy.add("nationality", code.lower(), quiet=True)

    # Identifiers — map to the most appropriate FTM Person property
    for id_obj in details.get("identifiers", []):
        id_value = id_obj.get("id")
        scheme = id_obj.get("scheme", "")
        if not id_value:
            continue
        ftm_prop = _person_scheme_to_ftm_property(scheme)
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

    # PEP status → position
    political = details.get("politicalExposure", {})
    if isinstance(political, dict) and political.get("status") == "isPep":
        for pep_detail in political.get("details", []):
            reason = pep_detail.get("reason", "")
            if reason:
                proxy.add("position", reason, quiet=True)

    # Source provenance
    statement_date = statement.get("statementDate")
    if statement_date:
        proxy.add("modifiedAt", statement_date, quiet=True)

    pub_details = statement.get("publicationDetails", {})
    publisher = pub_details.get("publisher", {})
    publisher_name = publisher.get("name") if isinstance(publisher, dict) else None
    if publisher_name:
        proxy.add("publisher", publisher_name, quiet=True)

    return proxy


def _person_scheme_to_ftm_property(scheme: str) -> str:
    """Map a BODS identifier scheme for a person to an FTM property name."""
    scheme_upper = scheme.upper()
    if "PASSPORT" in scheme_upper:
        return "passportNumber"
    if "NIN" in scheme_upper or "SSN" in scheme_upper or "NATIONAL" in scheme_upper:
        return "idNumber"
    if "TAX" in scheme_upper:
        return "taxNumber"
    return "idNumber"
