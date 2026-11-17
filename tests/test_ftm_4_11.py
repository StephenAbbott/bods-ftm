"""FollowTheMoney 4.11 alignment: the Control schema, and the cikCode /
irsCode identifier properties (FtM 4.11.0 and 4.11.3)."""

from __future__ import annotations

import copy

import pytest
from followthemoney import model

from bods_ftm.bods_to_ftm.entity_mapper import entity_statement_to_ftm
from bods_ftm.bods_to_ftm.person_mapper import person_statement_to_ftm
from bods_ftm.bods_to_ftm.relationship_mapper import (
    INTEREST_TYPE_TO_FTM_SCHEMA,
    ooc_statement_to_ftm,
)
from bods_ftm.config import PublisherConfig
from bods_ftm.ftm_to_bods.converter import FTMToBODSConverter
from bods_ftm.ftm_to_bods.entity_mapper import ftm_entity_to_bods
from bods_ftm.ftm_to_bods.person_mapper import ftm_person_to_bods
from bods_ftm.ftm_to_bods.relationship_mapper import (
    BODS_INTEREST_TYPES,
    ftm_relationship_to_bods,
)

from tests.conftest import (
    SAMPLE_ENTITY_STATEMENT,
    SAMPLE_OOC_STATEMENT,
    SAMPLE_PERSON_STATEMENT,
)

CONFIG = PublisherConfig()


def _ooc(interest: dict, interested_party: str | None = None) -> dict:
    stmt = copy.deepcopy(SAMPLE_OOC_STATEMENT)
    stmt["recordDetails"]["interests"] = [interest]
    if interested_party is not None:
        stmt["recordDetails"]["interestedParty"] = interested_party
    return stmt


def _entity(record_id: str, entity_type: str, identifiers=None) -> dict:
    stmt = copy.deepcopy(SAMPLE_ENTITY_STATEMENT)
    stmt["recordId"] = record_id
    stmt["statementId"] = record_id + "-stmt"
    stmt["recordDetails"]["entityType"] = {"type": entity_type}
    if identifiers is not None:
        stmt["recordDetails"]["identifiers"] = identifiers
    return stmt


_INDEX = {
    SAMPLE_ENTITY_STATEMENT["recordId"]: SAMPLE_ENTITY_STATEMENT,
    SAMPLE_PERSON_STATEMENT["recordId"]: SAMPLE_PERSON_STATEMENT,
}


def _one(stmt: dict, index: dict | None = None):
    proxies = ooc_statement_to_ftm(stmt, index or _INDEX)
    assert len(proxies) == 1
    return proxies[0]


# --------------------------------------------------------------------------
# BODS -> FtM: which schema each interest becomes
# --------------------------------------------------------------------------


def test_every_bods_interest_type_has_a_schema():
    assert set(INTEREST_TYPE_TO_FTM_SCHEMA) == BODS_INTEREST_TYPES


@pytest.mark.parametrize(
    "interest_type,control_type",
    [
        ("appointmentOfBoard", "appointment"),
        ("controlViaCompanyRulesOrArticles", "contractual"),
        ("rightsGrantedByContract", "contractual"),
        ("conditionalRightsGrantedByContract", "contractual"),
        ("settlor", "trust"),
        ("trustee", "trust"),
        ("protector", "trust"),
        ("beneficiaryOfLegalArrangement", "trust"),
        ("nominee", "nominee"),
        ("nominator", "nominee"),
        ("votingRights", "voting"),
    ],
)
def test_control_interests_become_control(interest_type, control_type):
    proxy = _one(_ooc({"type": interest_type}))
    assert proxy.schema.name == "Control"
    assert proxy.first("controller") == SAMPLE_PERSON_STATEMENT["recordId"]
    assert proxy.first("controlled") == SAMPLE_ENTITY_STATEMENT["recordId"]
    assert proxy.get("controlType") == [control_type]
    assert proxy.first("role") == interest_type


def test_other_influence_is_control_with_no_control_type():
    proxy = _one(_ooc({"type": "otherInfluenceOrControl"}))
    assert proxy.schema.name == "Control"
    assert proxy.get("controlType") == []


def test_voting_rights_with_a_share_stay_ownership():
    proxy = _one(_ooc({"type": "votingRights", "share": {"exact": 30}}))
    assert proxy.schema.name == "Ownership"
    assert proxy.first("percentage") == "30"


def test_beneficiary_share_is_kept_as_text_on_control():
    proxy = _one(
        _ooc(
            {
                "type": "beneficiaryOfLegalArrangement",
                "share": {"minimum": 25, "maximum": 50},
            }
        )
    )
    assert proxy.schema.name == "Control"
    assert "Share: 25-50%" in proxy.get("description")


@pytest.mark.parametrize("entity_type", ["state", "stateBody"])
def test_legal_framework_is_state_control_for_a_state_party(entity_type):
    state = _entity("state-record", entity_type)
    index = {**_INDEX, "state-record": state}
    proxy = _one(_ooc({"type": "controlByLegalFramework"}, "state-record"), index)
    assert proxy.schema.name == "Control"
    assert proxy.get("controlType") == ["state"]


def test_legal_framework_has_no_control_type_for_other_parties():
    proxy = _one(_ooc({"type": "controlByLegalFramework"}))
    assert proxy.schema.name == "Control"
    assert proxy.get("controlType") == []


@pytest.mark.parametrize(
    "interest_type", ["boardMember", "boardChair", "seniorManagingOfficial"]
)
def test_positions_stay_directorships(interest_type):
    assert _one(_ooc({"type": interest_type})).schema.name == "Directorship"


@pytest.mark.parametrize(
    "interest_type",
    [
        "shareholding",
        "rightsToSurplusAssetsOnDissolution",
        "rightsToProfitOrIncome",
        "enjoymentAndUseOfAssets",
        "rightToProfitOrIncomeFromAssets",
    ],
)
def test_economic_interests_stay_ownership(interest_type):
    assert _one(_ooc({"type": interest_type})).schema.name == "Ownership"


# --------------------------------------------------------------------------
# FtM -> BODS: Control edges are read
# --------------------------------------------------------------------------


def _ftm_control(**props):
    proxy = model.make_entity("Control")
    proxy.id = "ctl-1"
    proxy.add("controller", "person-1")
    proxy.add("controlled", "company-1")
    for key, values in props.items():
        proxy.add(key, values)
    return proxy


_IDS = {"person-1": "rec-person", "company-1": "rec-company"}


def test_control_edge_becomes_a_relationship():
    stmt = ftm_relationship_to_bods(_ftm_control(), _IDS, CONFIG)
    assert stmt is not None
    details = stmt["recordDetails"]
    assert details["interestedParty"] == "rec-person"
    assert details["subject"] == "rec-company"
    assert details["interests"][0]["type"] == "otherInfluenceOrControl"


@pytest.mark.parametrize(
    "control_type,interest_type",
    [
        ("voting", "votingRights"),
        ("appointment", "appointmentOfBoard"),
        ("contractual", "rightsGrantedByContract"),
        ("nominee", "nominee"),
        ("state", "controlByLegalFramework"),
        ("trust", "otherInfluenceOrControl"),
    ],
)
def test_control_type_sets_the_interest_type(control_type, interest_type):
    stmt = ftm_relationship_to_bods(
        _ftm_control(controlType=control_type), _IDS, CONFIG
    )
    assert stmt["recordDetails"]["interests"][0]["type"] == interest_type


def test_a_bods_role_wins_over_control_type():
    stmt = ftm_relationship_to_bods(
        _ftm_control(controlType="trust", role="protector"), _IDS, CONFIG
    )
    assert stmt["recordDetails"]["interests"][0]["type"] == "protector"


def test_indirect_control_and_legal_basis():
    stmt = ftm_relationship_to_bods(
        _ftm_control(controlType="indirect", legalBasis="Companies Act s.1"),
        _IDS,
        CONFIG,
    )
    interest = stmt["recordDetails"]["interests"][0]
    assert interest["directOrIndirect"] == "indirect"
    assert interest["details"] == "Legal basis: Companies Act s.1"


def test_converter_keeps_control_edges():
    person = model.make_entity("Person")
    person.id = "person-1"
    person.add("name", "Ada Owner")
    company = model.make_entity("Company")
    company.id = "company-1"
    company.add("name", "Held Ltd")
    control = _ftm_control(controlType="appointment")
    out = FTMToBODSConverter(CONFIG).convert(
        [person.to_dict(), company.to_dict(), control.to_dict()]
    )
    rels = [s for s in out if s["recordType"] == "relationship"]
    assert len(rels) == 1
    assert rels[0]["recordDetails"]["interests"][0]["type"] == "appointmentOfBoard"


@pytest.mark.parametrize(
    "schema,owner,asset",
    [
        ("Membership", "member", "organization"),
        ("Employment", "employee", "employer"),
        ("Representation", "agent", "client"),
    ],
)
def test_other_edges_read_their_own_properties(schema, owner, asset):
    # These used to read subject/object, which they do not have, and were
    # always dropped.
    proxy = model.make_entity(schema)
    proxy.id = "edge-1"
    proxy.add(owner, "person-1")
    proxy.add(asset, "company-1")
    stmt = ftm_relationship_to_bods(proxy, _IDS, CONFIG)
    assert stmt is not None
    assert stmt["recordDetails"]["interestedParty"] == "rec-person"


@pytest.mark.parametrize(
    "interest_type",
    [
        "appointmentOfBoard",
        "settlor",
        "trustee",
        "protector",
        "beneficiaryOfLegalArrangement",
        "nominee",
        "controlByLegalFramework",
        "controlViaCompanyRulesOrArticles",
        "votingRights",
    ],
)
def test_control_interest_types_round_trip(interest_type):
    proxy = _one(_ooc({"type": interest_type}))
    ids = {
        SAMPLE_PERSON_STATEMENT["recordId"]: "rec-person",
        SAMPLE_ENTITY_STATEMENT["recordId"]: "rec-company",
    }
    stmt = ftm_relationship_to_bods(proxy, ids, CONFIG)
    assert stmt["recordDetails"]["interests"][0]["type"] == interest_type


# --------------------------------------------------------------------------
# Identifiers: cikCode and irsCode
# --------------------------------------------------------------------------


def test_ein_and_cik_go_to_their_own_properties():
    stmt = _entity(
        "us-co",
        "registeredEntity",
        [
            {"id": "95-4602243", "scheme": "US-EIN"},
            {"id": "0001059556", "scheme": "US-SEC-CIK"},
        ],
    )
    proxy = entity_statement_to_ftm(stmt)
    assert proxy.get("irsCode") == ["954602243"]
    assert proxy.get("cikCode") == ["0001059556"]
    assert proxy.get("taxNumber") == []
    assert proxy.get("registrationNumber") == []


def test_ein_on_a_schema_without_irs_code_falls_back_to_tax_number():
    stmt = _entity(
        "us-arr", "arrangement", [{"id": "95-4602243", "scheme": "US-EIN"}]
    )
    proxy = entity_statement_to_ftm(stmt)
    assert proxy.schema.name == "LegalEntity"
    assert proxy.get("taxNumber") == ["95-4602243"]


def test_a_value_ftm_refuses_as_an_ein_is_kept_as_tax_number():
    stmt = _entity("us-bad", "registeredEntity", [{"id": "N/A-1", "scheme": "US-EIN"}])
    proxy = entity_statement_to_ftm(stmt)
    assert proxy.get("irsCode") == []
    assert proxy.get("taxNumber") == ["N/A-1"]


def test_person_cik_goes_to_cik_code():
    stmt = copy.deepcopy(SAMPLE_PERSON_STATEMENT)
    stmt["recordDetails"]["identifiers"] = [
        {"id": "0001234567", "scheme": "US-SEC-CIK"}
    ]
    proxy = person_statement_to_ftm(stmt)
    assert proxy.get("cikCode") == ["0001234567"]


def test_ftm_cik_and_irs_codes_become_identifiers():
    company = model.make_entity("Company")
    company.id = "co-1"
    company.add("name", "Moody's Corp")
    company.add("jurisdiction", "us")
    company.add("cikCode", "0001059556")
    company.add("irsCode", "13-3998945")
    stmt = ftm_entity_to_bods(company, CONFIG)
    got = {(i["scheme"], i["id"]) for i in stmt["recordDetails"]["identifiers"]}
    assert ("US-SEC-CIK", "0001059556") in got
    assert ("US-EIN", "133998945") in got


def test_ftm_person_cik_becomes_an_identifier():
    person = model.make_entity("Person")
    person.id = "p-1"
    person.add("name", "Jane Filer")
    person.add("cikCode", "0001234567")
    stmt = ftm_person_to_bods(person, CONFIG)
    got = {(i["scheme"], i["id"]) for i in stmt["recordDetails"]["identifiers"]}
    assert ("US-SEC-CIK", "0001234567") in got


# --------------------------------------------------------------------------
# Percentages: FtM 4.10.1 stopped NumberType.parse corrupting common shapes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("raw,expected", [("25.5", 25.5), ("75", 75.0)])
def test_ownership_percentage_reads_back(raw, expected):
    proxy = model.make_entity("Ownership")
    proxy.id = "own-1"
    proxy.add("owner", "person-1")
    proxy.add("asset", "company-1")
    proxy.add("percentage", raw)
    stmt = ftm_relationship_to_bods(proxy, _IDS, CONFIG)
    assert stmt["recordDetails"]["interests"][0]["share"] == {"exact": expected}
