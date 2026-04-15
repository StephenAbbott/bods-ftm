from __future__ import annotations

import uuid
from typing import Any

from bods_ftm.utils.dates import today_iso


def make_statement_id() -> str:
    """Generate a fresh UUID for a new BODS statement."""
    return str(uuid.uuid4())


def publication_details(
    publisher_name: str,
    publisher_uri: str | None = None,
    license_url: str = "https://creativecommons.org/publicdomain/zero/1.0/",
    bods_version: str = "0.4.0",
) -> dict[str, Any]:
    """Build a BODS publicationDetails block."""
    publisher: dict[str, Any] = {"name": publisher_name}
    if publisher_uri:
        publisher["uri"] = publisher_uri
    return {
        "publicationDate": today_iso(),
        "bodsVersion": bods_version,
        "license": license_url,
        "publisher": publisher,
    }


def entity_statement(
    statement_id: str,
    record_details: dict[str, Any],
    pub_details: dict[str, Any],
    statement_date: str | None = None,
) -> dict[str, Any]:
    """Wrap record_details in a BODS v0.4 entity statement envelope."""
    return {
        "statementId": statement_id,
        "statementType": "entityStatement",
        "statementDate": statement_date or today_iso(),
        "publicationDetails": pub_details,
        "recordDetails": record_details,
    }


def person_statement(
    statement_id: str,
    record_details: dict[str, Any],
    pub_details: dict[str, Any],
    statement_date: str | None = None,
) -> dict[str, Any]:
    """Wrap record_details in a BODS v0.4 person statement envelope."""
    return {
        "statementId": statement_id,
        "statementType": "personStatement",
        "statementDate": statement_date or today_iso(),
        "publicationDetails": pub_details,
        "recordDetails": record_details,
    }


def ooc_statement(
    statement_id: str,
    record_details: dict[str, Any],
    pub_details: dict[str, Any],
    statement_date: str | None = None,
) -> dict[str, Any]:
    """Wrap record_details in a BODS v0.4 ownership-or-control statement envelope."""
    return {
        "statementId": statement_id,
        "statementType": "ownershipOrControlStatement",
        "statementDate": statement_date or today_iso(),
        "publicationDetails": pub_details,
        "recordDetails": record_details,
    }
