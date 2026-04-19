from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Sample BODS v0.4 data — canonical recordType / recordDetails envelope.
# ---------------------------------------------------------------------------

SAMPLE_ENTITY_STATEMENT = {
    "statementId": "test-entity-stmt-0001",
    "declarationSubject": "test-entity-record-0001",
    "statementDate": "2024-01-15",
    "publicationDetails": {
        "publicationDate": "2024-01-15",
        "bodsVersion": "0.4",
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        "publisher": {"name": "Test Publisher", "uri": "https://test.example.com"},
    },
    "recordId": "test-entity-record-0001",
    "recordStatus": "new",
    "recordType": "entity",
    "recordDetails": {
        "entityType": {"type": "registeredEntity"},
        "name": "Test Company Ltd",
        "identifiers": [
            {"id": "11223344", "scheme": "GB-COH"},
            {"id": "213800TEST0000001A80", "scheme": "XI-LEI"},
        ],
        "jurisdiction": {"code": "GB", "name": "United Kingdom"},
        "foundingDate": "2010-01-01",
        "addresses": [
            {"type": "registered", "address": "1 Test Street", "country": {"code": "GB"}}
        ],
        "isComponent": False,
    },
}

SAMPLE_PERSON_STATEMENT = {
    "statementId": "test-person-stmt-0001",
    "declarationSubject": "test-person-record-0001",
    "statementDate": "2024-01-15",
    "publicationDetails": {
        "publicationDate": "2024-01-15",
        "bodsVersion": "0.4",
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        "publisher": {"name": "Test Publisher"},
    },
    "recordId": "test-person-record-0001",
    "recordStatus": "new",
    "recordType": "person",
    "recordDetails": {
        "personType": "knownPerson",
        "names": [{"fullName": "Test Person"}],
        "nationalities": [{"code": "GB"}],
        "birthDate": "1980-06-15",
        "isComponent": False,
    },
}

SAMPLE_OOC_STATEMENT = {
    "statementId": "test-rel-stmt-0001",
    "declarationSubject": "test-rel-record-0001",
    "statementDate": "2024-01-15",
    "publicationDetails": {
        "publicationDate": "2024-01-15",
        "bodsVersion": "0.4",
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        "publisher": {"name": "Test Publisher"},
    },
    "recordId": "test-rel-record-0001",
    "recordStatus": "new",
    "recordType": "relationship",
    "recordDetails": {
        "subject": "test-entity-record-0001",
        "interestedParty": "test-person-record-0001",
        "interests": [
            {
                "type": "shareholding",
                "share": {"exact": 51.0},
                "directOrIndirect": "direct",
                "beneficialOwnershipOrControl": True,
                "startDate": "2010-01-01",
            }
        ],
        "isComponent": False,
    },
}

SAMPLE_BODS_DATASET = [
    SAMPLE_ENTITY_STATEMENT,
    SAMPLE_PERSON_STATEMENT,
    SAMPLE_OOC_STATEMENT,
]


# ---------------------------------------------------------------------------
# Sample FTM data
# ---------------------------------------------------------------------------

SAMPLE_FTM_COMPANY = {
    "id": "ftm-company-001",
    "schema": "Company",
    "properties": {
        "name": ["Test Company Ltd"],
        "jurisdiction": ["gb"],
        "registrationNumber": ["11223344"],
        "incorporationDate": ["2010-01-01"],
        "address": ["1 Test Street"],
        "country": ["gb"],
    },
}

SAMPLE_FTM_PERSON = {
    "id": "ftm-person-001",
    "schema": "Person",
    "properties": {
        "name": ["Test Person"],
        "nationality": ["gb"],
        "birthDate": ["1980-06-15"],
    },
}

SAMPLE_FTM_OWNERSHIP = {
    "id": "ftm-ownership-001",
    "schema": "Ownership",
    "properties": {
        "owner": ["ftm-person-001"],
        "asset": ["ftm-company-001"],
        "percentage": ["51"],
        "startDate": ["2010-01-01"],
        "role": ["shareholding"],
        "status": ["direct"],
        "summary": ["beneficial ownership or control"],
    },
}

SAMPLE_FTM_DIRECTORSHIP = {
    "id": "ftm-directorship-001",
    "schema": "Directorship",
    "properties": {
        "director": ["ftm-person-001"],
        "organization": ["ftm-company-001"],
        "role": ["board member"],
        "startDate": ["2010-01-01"],
    },
}

SAMPLE_FTM_DATASET = [
    SAMPLE_FTM_COMPANY,
    SAMPLE_FTM_PERSON,
    SAMPLE_FTM_OWNERSHIP,
    SAMPLE_FTM_DIRECTORSHIP,
]


# ---------------------------------------------------------------------------
# File-based fixtures
# ---------------------------------------------------------------------------


def write_jsonl(records: list[dict], filepath: Path) -> None:
    """Write a list of dicts as newline-delimited JSON."""
    with open(filepath, "w") as fh:
        for record in records:
            fh.write(json.dumps(record) + "\n")


@pytest.fixture
def sample_bods_file(tmp_path):
    """Temporary file containing the sample BODS dataset as a JSON array."""
    path = tmp_path / "sample.bods.json"
    with open(path, "w") as fh:
        json.dump(SAMPLE_BODS_DATASET, fh)
    return path


@pytest.fixture
def sample_ftm_file(tmp_path):
    """Temporary file containing the sample FTM dataset as JSONL."""
    path = tmp_path / "sample.ftm.jsonl"
    write_jsonl(SAMPLE_FTM_DATASET, path)
    return path
