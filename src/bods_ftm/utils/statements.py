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
    bods_version: str = "0.4",
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


def _record_envelope(
    record_type: str,
    statement_id: str,
    record_id: str,
    record_details: dict[str, Any],
    pub_details: dict[str, Any],
    statement_date: str | None,
) -> dict[str, Any]:
    return {
        "statementId": statement_id,
        "declarationSubject": record_id,
        "statementDate": statement_date or today_iso(),
        "publicationDetails": pub_details,
        "recordId": record_id,
        "recordStatus": "new",
        "recordType": record_type,
        "recordDetails": record_details,
    }


def entity_statement(
    statement_id: str,
    record_id: str,
    record_details: dict[str, Any],
    pub_details: dict[str, Any],
    statement_date: str | None = None,
) -> dict[str, Any]:
    """Build a canonical BODS v0.4 entity statement (recordType: entity)."""
    return _record_envelope(
        "entity", statement_id, record_id, record_details, pub_details, statement_date
    )


def person_statement(
    statement_id: str,
    record_id: str,
    record_details: dict[str, Any],
    pub_details: dict[str, Any],
    statement_date: str | None = None,
) -> dict[str, Any]:
    """Build a canonical BODS v0.4 person statement (recordType: person)."""
    return _record_envelope(
        "person", statement_id, record_id, record_details, pub_details, statement_date
    )


def relationship_statement(
    statement_id: str,
    record_id: str,
    record_details: dict[str, Any],
    pub_details: dict[str, Any],
    statement_date: str | None = None,
) -> dict[str, Any]:
    """Build a canonical BODS v0.4 relationship statement (recordType: relationship)."""
    return _record_envelope(
        "relationship", statement_id, record_id, record_details, pub_details, statement_date
    )


# Backwards-compatible alias for the old name used by some FTM→BODS code paths.
ooc_statement = relationship_statement
