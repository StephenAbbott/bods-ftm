from __future__ import annotations

import pytest

from followthemoney import model

from bods_ftm.config import PublisherConfig
from bods_ftm.ftm_to_bods.converter import FTMToBODSConverter
from bods_ftm.ftm_to_bods.entity_mapper import ftm_entity_to_bods
from bods_ftm.ftm_to_bods.person_mapper import ftm_person_to_bods
from bods_ftm.ftm_to_bods.relationship_mapper import ftm_relationship_to_bods

from tests.conftest import (
    SAMPLE_FTM_COMPANY,
    SAMPLE_FTM_DATASET,
    SAMPLE_FTM_DIRECTORSHIP,
    SAMPLE_FTM_OWNERSHIP,
    SAMPLE_FTM_PERSON,
)

CONFIG = PublisherConfig(publisher_name="Test Publisher")


class TestEntityMapper:
    def test_converts_company(self):
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        assert stmt is not None
        assert stmt["statementType"] == "entityStatement"

    def test_entity_type_is_registered_entity(self):
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        assert stmt["recordDetails"]["entityType"]["type"] == "registeredEntity"

    def test_name_is_mapped(self):
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        names = [n["fullName"] for n in stmt["recordDetails"]["names"]]
        assert "Test Company Ltd" in names

    def test_jurisdiction_code_is_uppercased(self):
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        juris = stmt["recordDetails"].get("incorporatedInJurisdiction", {})
        assert juris.get("code") == "GB"

    def test_registration_number_in_identifiers(self):
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        ids = {i["id"] for i in stmt["recordDetails"].get("identifiers", [])}
        assert "11223344" in ids

    def test_founding_date_mapped(self):
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        assert stmt["recordDetails"].get("foundingDate") == "2010-01-01"

    def test_returns_none_for_nameless_company(self):
        data = {**SAMPLE_FTM_COMPANY, "properties": {}}
        proxy = model.get_proxy(data)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        assert stmt is None

    def test_organization_schema_maps_to_legal_entity(self):
        data = {**SAMPLE_FTM_COMPANY, "id": "org-001", "schema": "Organization"}
        proxy = model.get_proxy(data)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        assert stmt is not None
        assert stmt["recordDetails"]["entityType"]["type"] == "legalEntity"

    def test_publication_details_present(self):
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        assert "publicationDetails" in stmt
        assert stmt["publicationDetails"]["bodsVersion"] == "0.4.0"
        assert stmt["publicationDetails"]["publisher"]["name"] == "Test Publisher"


class TestPersonMapper:
    def test_converts_person(self):
        proxy = model.get_proxy(SAMPLE_FTM_PERSON)
        stmt = ftm_person_to_bods(proxy, CONFIG)
        assert stmt is not None
        assert stmt["statementType"] == "personStatement"

    def test_name_is_mapped(self):
        proxy = model.get_proxy(SAMPLE_FTM_PERSON)
        stmt = ftm_person_to_bods(proxy, CONFIG)
        names = [n["fullName"] for n in stmt["recordDetails"]["names"]]
        assert "Test Person" in names

    def test_nationality_is_uppercased(self):
        proxy = model.get_proxy(SAMPLE_FTM_PERSON)
        stmt = ftm_person_to_bods(proxy, CONFIG)
        nats = [n["code"] for n in stmt["recordDetails"].get("nationalities", [])]
        assert "GB" in nats

    def test_birth_date_mapped(self):
        proxy = model.get_proxy(SAMPLE_FTM_PERSON)
        stmt = ftm_person_to_bods(proxy, CONFIG)
        assert stmt["recordDetails"].get("birthDate") == "1980-06-15"

    def test_returns_none_for_nameless_person(self):
        data = {**SAMPLE_FTM_PERSON, "properties": {}}
        proxy = model.get_proxy(data)
        stmt = ftm_person_to_bods(proxy, CONFIG)
        assert stmt is None


class TestRelationshipMapper:
    def test_converts_ownership(self):
        ftm_to_bods = {
            "ftm-company-001": "bods-entity-001",
            "ftm-person-001": "bods-person-001",
        }
        proxy = model.get_proxy(SAMPLE_FTM_OWNERSHIP)
        stmt = ftm_relationship_to_bods(proxy, ftm_to_bods, CONFIG)
        assert stmt is not None
        assert stmt["statementType"] == "ownershipOrControlStatement"

    def test_subject_reference_is_asset(self):
        ftm_to_bods = {
            "ftm-company-001": "bods-entity-001",
            "ftm-person-001": "bods-person-001",
        }
        proxy = model.get_proxy(SAMPLE_FTM_OWNERSHIP)
        stmt = ftm_relationship_to_bods(proxy, ftm_to_bods, CONFIG)
        subject = stmt["recordDetails"]["subject"]
        assert subject.get("describedByEntityStatement") == "bods-entity-001"

    def test_interested_party_reference(self):
        ftm_to_bods = {
            "ftm-company-001": "bods-entity-001",
            "ftm-person-001": "bods-person-001",
        }
        proxy = model.get_proxy(SAMPLE_FTM_OWNERSHIP)
        stmt = ftm_relationship_to_bods(proxy, ftm_to_bods, CONFIG)
        ip = stmt["recordDetails"]["interestedParty"]
        # owner is a person but schema is Ownership so defaults to entity ref;
        # FTMToBODSConverter refines this — here we test the raw mapper
        assert "bods-person-001" in (
            ip.get("describedByEntityStatement") or ip.get("describedByPersonStatement") or ""
        )

    def test_percentage_in_share(self):
        ftm_to_bods = {
            "ftm-company-001": "bods-entity-001",
            "ftm-person-001": "bods-person-001",
        }
        proxy = model.get_proxy(SAMPLE_FTM_OWNERSHIP)
        stmt = ftm_relationship_to_bods(proxy, ftm_to_bods, CONFIG)
        interests = stmt["recordDetails"]["interests"]
        assert interests[0]["share"]["exact"] == 51.0

    def test_returns_none_when_entity_not_in_registry(self):
        proxy = model.get_proxy(SAMPLE_FTM_OWNERSHIP)
        stmt = ftm_relationship_to_bods(proxy, {}, CONFIG)
        assert stmt is None

    def test_directorship_maps_to_board_member(self):
        ftm_to_bods = {
            "ftm-company-001": "bods-entity-001",
            "ftm-person-001": "bods-person-001",
        }
        proxy = model.get_proxy(SAMPLE_FTM_DIRECTORSHIP)
        stmt = ftm_relationship_to_bods(proxy, ftm_to_bods, CONFIG)
        assert stmt is not None
        interests = stmt["recordDetails"]["interests"]
        assert interests[0]["type"] == "boardMember"


class TestFTMToBODSConverter:
    def test_converts_full_dataset(self):
        converter = FTMToBODSConverter(CONFIG)
        result = converter.convert(SAMPLE_FTM_DATASET)
        assert len(result) > 0
        types = {s["statementType"] for s in result}
        assert "entityStatement" in types
        assert "personStatement" in types
        assert "ownershipOrControlStatement" in types

    def test_person_interested_party_reference_is_refined(self):
        """The converter should use describedByPersonStatement for Person owners."""
        converter = FTMToBODSConverter(CONFIG)
        result = converter.convert(SAMPLE_FTM_DATASET)
        ooc_stmts = [s for s in result if s["statementType"] == "ownershipOrControlStatement"]
        # At least one OOC from ownership should have a person reference
        person_refs = [
            s for s in ooc_stmts
            if "describedByPersonStatement" in s["recordDetails"]["interestedParty"]
        ]
        assert len(person_refs) > 0

    def test_file_roundtrip(self, sample_ftm_file, tmp_path):
        output = tmp_path / "out.bods.json"
        converter = FTMToBODSConverter(CONFIG)
        count = converter.convert_file(sample_ftm_file, output)
        assert count > 0
        assert output.exists()
