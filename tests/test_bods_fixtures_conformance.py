"""Conformance tests against the shared bods-fixtures pack.

These tests are the proof that bods-ftm correctly handles the canonical BODS
v0.4 shape used across the wider adapter ecosystem (bods-aml-ai, bods-neo4j,
bods-gql, etc.). Failures here indicate divergence from canonical v0.4 —
either in the converter or in our understanding of the spec.

The pack is the source of truth: see
https://github.com/StephenAbbott/bods-fixtures
"""

from __future__ import annotations

import pytest
from bods_fixtures import list_cases, load

from bods_ftm.bods_to_ftm.converter import BODSToFTMConverter
from bods_ftm.config import PublisherConfig
from bods_ftm.ftm_to_bods.converter import FTMToBODSConverter

ALL_CASES = list_cases()
CONFIG = PublisherConfig(publisher_name="bods-fixtures conformance")


@pytest.mark.parametrize("name", ALL_CASES)
def test_bods_to_ftm_does_not_raise(name):
    """Every fixture must be convertible without exceptions."""
    fixture = load(name)
    BODSToFTMConverter().convert(fixture.statements)


@pytest.mark.parametrize("name", ALL_CASES)
def test_bods_to_ftm_emits_at_least_one_entity_when_fixture_has_records(name):
    """If a fixture contains entity or person records, the converter must emit
    at least one corresponding FTM proxy."""
    fixture = load(name)
    has_subjects = bool(
        fixture.by_record_type("entity") or fixture.by_record_type("person")
    )
    if not has_subjects:
        pytest.skip("fixture contains no entity/person records")
    result = BODSToFTMConverter().convert(fixture.statements)
    assert result, (
        f"{name}: fixture has {len(fixture.by_record_type('entity'))} entity and "
        f"{len(fixture.by_record_type('person'))} person records, but the "
        f"BODS→FTM converter produced 0 FTM proxies. Likely cause: converter "
        f"is dispatching on the BODS v0.3 `statementType` field rather than "
        f"the canonical v0.4 `recordType`."
    )


def test_direct_ownership_produces_company_person_and_ownership():
    """The baseline fixture must produce one Company, one Person, and an
    Ownership relation linking them."""
    fixture = load("core/01-direct-ownership")
    result = BODSToFTMConverter().convert(fixture.statements)
    schemas = [e["schema"] for e in result]
    assert "Company" in schemas, f"missing Company in {schemas}"
    assert "Person" in schemas, f"missing Person in {schemas}"
    assert any(s in schemas for s in ("Ownership", "Directorship")), (
        f"missing Ownership/Directorship in {schemas}"
    )


def test_anonymous_person_preserves_unspecified_reason():
    """The declared-unknown UBO fixture must not be silently dropped — the
    inline interestedParty reason code must reach FTM in some mapped form."""
    fixture = load("edge-cases/11-anonymous-person")
    bods_stmts = fixture.statements
    result = BODSToFTMConverter().convert(bods_stmts)
    serialised = repr(result)
    assert "subjectUnableToConfirmOrIdentifyBeneficialOwner" in serialised, (
        "The unspecifiedReason code must appear somewhere in the FTM output "
        "(notes, description, or a dedicated property). Silently dropping "
        "declared-unknown UBOs understates opacity risk."
    )


def test_circular_ownership_terminates_and_emits_both_edges():
    """A↔B cycle must produce both Ownership edges, not loop forever or
    deduplicate one direction away."""
    fixture = load("edge-cases/10-circular-ownership")
    result = BODSToFTMConverter().convert(fixture.statements)
    ownerships = [e for e in result if e["schema"] == "Ownership"]
    assert len(ownerships) == 2, (
        f"Expected 2 Ownership edges (A→B and B→A), got {len(ownerships)}"
    )


@pytest.mark.parametrize("name", ALL_CASES)
def test_roundtrip_bods_to_ftm_to_bods_preserves_record_count(name):
    """A round trip must preserve the count of entity + person records.
    Relationships may legitimately not round-trip 1:1 (FTM Ownership/Directorship
    semantics differ from BODS interests), but entities and persons must."""
    fixture = load(name)
    ftm = BODSToFTMConverter().convert(fixture.statements)
    back = FTMToBODSConverter(CONFIG).convert(ftm)

    original_entity_count = len(fixture.by_record_type("entity"))
    original_person_count = len(fixture.by_record_type("person"))

    back_entity_count = sum(1 for s in back if s.get("recordType") == "entity")
    back_person_count = sum(1 for s in back if s.get("recordType") == "person")

    # The converter may materialise placeholder LegalEntity proxies to preserve
    # declared-unknown UBO signal (inline unspecifiedReason). Round-tripping
    # those produces extra entity records — expected, not a regression.
    assert back_entity_count >= original_entity_count, (
        f"{name}: entity count dropped {original_entity_count} → {back_entity_count}"
    )
    assert back_person_count == original_person_count, (
        f"{name}: person count {original_person_count} → {back_person_count}"
    )
