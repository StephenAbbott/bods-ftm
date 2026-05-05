from __future__ import annotations

from followthemoney import model

from bods_ftm.config import PublisherConfig
from bods_ftm.ftm_to_bods.converter import FTMToBODSConverter
from bods_ftm.ftm_to_bods.entity_mapper import ftm_entity_to_bods
from bods_ftm.ftm_to_bods.identifier_mapper import _resolve_scheme
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
        assert stmt["recordType"] == "entity"

    def test_entity_type_is_registered_entity(self):
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        assert stmt["recordDetails"]["entityType"]["type"] == "registeredEntity"

    def test_name_is_mapped(self):
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        # Canonical 0.4: `name` is a single string.
        assert stmt["recordDetails"]["name"] == "Test Company Ltd"

    def test_jurisdiction_has_code_and_name(self):
        """Jurisdiction block must carry both code and human-readable name."""
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        juris = stmt["recordDetails"].get("jurisdiction", {})
        assert juris.get("code") == "GB"
        assert juris.get("name") == "United Kingdom"

    def test_jurisdiction_lowercase_input_resolved(self):
        """FTM 'gb' (lowercase) must produce code='GB', name='United Kingdom'."""
        data = {**SAMPLE_FTM_COMPANY, "properties": {**SAMPLE_FTM_COMPANY["properties"], "jurisdiction": ["gb"]}}
        proxy = model.get_proxy(data)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        juris = stmt["recordDetails"].get("jurisdiction", {})
        assert juris.get("code") == "GB"
        assert juris.get("name") == "United Kingdom"

    def test_registration_number_in_identifiers(self):
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        ids = {i["id"] for i in stmt["recordDetails"].get("identifiers", [])}
        assert "11223344" in ids

    def test_registration_number_uses_gb_coh_for_gb_jurisdiction(self):
        """GB registrationNumber must use 'GB-COH', not 'misc-regnum'."""
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        schemes = {i["scheme"] for i in stmt["recordDetails"].get("identifiers", [])}
        assert "GB-COH" in schemes
        assert "misc-regnum" not in schemes

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
        assert stmt["publicationDetails"]["bodsVersion"] == "0.4"
        assert stmt["publicationDetails"]["publisher"]["name"] == "Test Publisher"

    def test_record_id_and_statement_id_present(self):
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        assert stmt["recordId"]
        assert stmt["statementId"]
        assert stmt["recordType"] == "entity"
        assert stmt["recordStatus"] == "new"


class TestPersonMapper:
    def test_converts_person(self):
        proxy = model.get_proxy(SAMPLE_FTM_PERSON)
        stmt = ftm_person_to_bods(proxy, CONFIG)
        assert stmt is not None
        assert stmt["recordType"] == "person"

    def test_name_is_mapped(self):
        proxy = model.get_proxy(SAMPLE_FTM_PERSON)
        stmt = ftm_person_to_bods(proxy, CONFIG)
        names = [n["fullName"] for n in stmt["recordDetails"]["names"]]
        assert "Test Person" in names

    def test_nationality_has_code_and_name(self):
        """Nationality entries must carry both code and human-readable name."""
        proxy = model.get_proxy(SAMPLE_FTM_PERSON)
        stmt = ftm_person_to_bods(proxy, CONFIG)
        nats = stmt["recordDetails"].get("nationalities", [])
        assert any(n.get("code") == "GB" for n in nats)
        assert any(n.get("name") == "United Kingdom" for n in nats)

    def test_birth_date_mapped(self):
        proxy = model.get_proxy(SAMPLE_FTM_PERSON)
        stmt = ftm_person_to_bods(proxy, CONFIG)
        assert stmt["recordDetails"].get("birthDate") == "1980-06-15"

    def test_returns_none_for_nameless_person(self):
        data = {**SAMPLE_FTM_PERSON, "properties": {}}
        proxy = model.get_proxy(data)
        stmt = ftm_person_to_bods(proxy, CONFIG)
        assert stmt is None


class TestIdentifierSchemeResolution:
    """Unit tests for _resolve_scheme covering the three tiers of resolution."""

    def test_gb_registration_number_uses_gb_coh(self):
        assert _resolve_scheme("registrationNumber", "misc-regnum", "GB") == "GB-COH"

    def test_us_registration_number_uses_us_ein(self):
        assert _resolve_scheme("registrationNumber", "misc-regnum", "US") == "US-EIN"

    def test_unknown_jurisdiction_uses_reg_alpha2(self):
        # KE (Kenya) is not in the hardcoded dict — should fall back to REG-KE.
        assert _resolve_scheme("registrationNumber", "misc-regnum", "KE") == "REG-KE"

    def test_lowercase_jurisdiction_resolved(self):
        # FTM sometimes stores lowercase; should still resolve.
        assert _resolve_scheme("registrationNumber", "misc-regnum", "ke") == "REG-KE"

    def test_no_jurisdiction_returns_default(self):
        assert _resolve_scheme("registrationNumber", "misc-regnum", None) == "misc-regnum"

    def test_non_regnum_property_unaffected(self):
        # taxNumber, leiCode etc. must not be touched by jurisdiction logic.
        assert _resolve_scheme("leiCode", "XI-LEI", "GB") == "XI-LEI"
        assert _resolve_scheme("taxNumber", "misc-tax", "US") == "misc-tax"


class TestRelationshipMapper:
    def _registry(self):
        return {
            "ftm-company-001": "bods-entity-record-001",
            "ftm-person-001": "bods-person-record-001",
        }

    def test_converts_ownership(self):
        proxy = model.get_proxy(SAMPLE_FTM_OWNERSHIP)
        stmt = ftm_relationship_to_bods(proxy, self._registry(), CONFIG)
        assert stmt is not None
        assert stmt["recordType"] == "relationship"

    def test_subject_is_asset_record_id_string(self):
        """Canonical 0.4: subject is a string pointing at a recordId, not a
        nested describedByEntityStatement wrapper."""
        proxy = model.get_proxy(SAMPLE_FTM_OWNERSHIP)
        stmt = ftm_relationship_to_bods(proxy, self._registry(), CONFIG)
        assert stmt["recordDetails"]["subject"] == "bods-entity-record-001"

    def test_interested_party_is_owner_record_id_string(self):
        """Canonical 0.4: interestedParty is a string pointing at a recordId."""
        proxy = model.get_proxy(SAMPLE_FTM_OWNERSHIP)
        stmt = ftm_relationship_to_bods(proxy, self._registry(), CONFIG)
        assert stmt["recordDetails"]["interestedParty"] == "bods-person-record-001"

    def test_percentage_in_share(self):
        proxy = model.get_proxy(SAMPLE_FTM_OWNERSHIP)
        stmt = ftm_relationship_to_bods(proxy, self._registry(), CONFIG)
        interests = stmt["recordDetails"]["interests"]
        assert interests[0]["share"]["exact"] == 51.0

    def test_returns_none_when_entity_not_in_registry(self):
        proxy = model.get_proxy(SAMPLE_FTM_OWNERSHIP)
        stmt = ftm_relationship_to_bods(proxy, {}, CONFIG)
        assert stmt is None

    def test_directorship_maps_to_board_member(self):
        proxy = model.get_proxy(SAMPLE_FTM_DIRECTORSHIP)
        stmt = ftm_relationship_to_bods(proxy, self._registry(), CONFIG)
        assert stmt is not None
        interests = stmt["recordDetails"]["interests"]
        assert interests[0]["type"] == "boardMember"


class TestFTMToBODSConverter:
    def test_converts_full_dataset(self):
        converter = FTMToBODSConverter(CONFIG)
        result = converter.convert(SAMPLE_FTM_DATASET)
        assert len(result) > 0
        types = {s["recordType"] for s in result}
        assert "entity" in types
        assert "person" in types
        assert "relationship" in types

    def test_interested_party_resolves_to_person_record_id(self):
        """Pass 1 registers a Person recordId; pass 2 emits it as the
        interestedParty string. No describedBy* wrapper is produced."""
        converter = FTMToBODSConverter(CONFIG)
        result = converter.convert(SAMPLE_FTM_DATASET)
        persons = [s for s in result if s.get("recordType") == "person"]
        assert persons
        person_record_ids = {s["recordId"] for s in persons}
        relationships = [s for s in result if s.get("recordType") == "relationship"]
        interested_refs = {
            s["recordDetails"]["interestedParty"] for s in relationships
        }
        assert interested_refs & person_record_ids, (
            "At least one relationship's interestedParty must point at a "
            "person record; got refs=%r persons=%r"
            % (interested_refs, person_record_ids)
        )

    def test_file_roundtrip(self, sample_ftm_file, tmp_path):
        output = tmp_path / "out.bods.json"
        converter = FTMToBODSConverter(CONFIG)
        count = converter.convert_file(sample_ftm_file, output)
        assert count > 0
        assert output.exists()


class TestOpenCorporatesUrlIdentifier:
    def test_oc_url_produces_opencorporates_scheme(self):
        """FTM opencorporatesUrl -> BODS OPENCORPORATES scheme identifier."""
        data = {
            **SAMPLE_FTM_COMPANY,
            "id": "ftm-se-001",
            "properties": {
                **SAMPLE_FTM_COMPANY["properties"],
                "opencorporatesUrl": ["https://opencorporates.com/companies/se/556056-6258"],
            },
        }
        proxy = model.get_proxy(data)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        assert stmt is not None
        ids = stmt["recordDetails"].get("identifiers", [])
        oc_ids = [i for i in ids if i.get("scheme") == "OPENCORPORATES"]
        assert len(oc_ids) == 1
        assert oc_ids[0]["id"] == "se/556056-6258"

    def test_oc_url_preserves_uri_field(self):
        oc_url = "https://opencorporates.com/companies/se/556056-6258"
        data = {
            **SAMPLE_FTM_COMPANY,
            "id": "ftm-se-002",
            "properties": {
                **SAMPLE_FTM_COMPANY["properties"],
                "opencorporatesUrl": [oc_url],
            },
        }
        proxy = model.get_proxy(data)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        ids = stmt["recordDetails"].get("identifiers", [])
        oc_ids = [i for i in ids if i.get("scheme") == "OPENCORPORATES"]
        assert oc_ids[0].get("uri") == oc_url

    def test_oc_url_scheme_name_set(self):
        data = {
            **SAMPLE_FTM_COMPANY,
            "id": "ftm-se-003",
            "properties": {
                **SAMPLE_FTM_COMPANY["properties"],
                "opencorporatesUrl": ["https://opencorporates.com/companies/gb/00102498"],
            },
        }
        proxy = model.get_proxy(data)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        ids = stmt["recordDetails"].get("identifiers", [])
        oc_ids = [i for i in ids if i.get("scheme") == "OPENCORPORATES"]
        assert oc_ids[0].get("schemeName") == "OpenCorporates company identifier"

    def test_malformed_oc_url_skipped(self):
        """A URL that doesn't contain the OC companies marker is not surfaced."""
        data = {
            **SAMPLE_FTM_COMPANY,
            "id": "ftm-bad-oc",
            "properties": {
                **SAMPLE_FTM_COMPANY["properties"],
                "opencorporatesUrl": ["https://example.com/not-oc"],
            },
        }
        proxy = model.get_proxy(data)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        ids = stmt["recordDetails"].get("identifiers", [])
        oc_ids = [i for i in ids if i.get("scheme") == "OPENCORPORATES"]
        assert oc_ids == []

    def test_no_oc_url_produces_no_opencorporates_identifier(self):
        proxy = model.get_proxy(SAMPLE_FTM_COMPANY)
        stmt = ftm_entity_to_bods(proxy, CONFIG)
        ids = stmt["recordDetails"].get("identifiers", [])
        oc_ids = [i for i in ids if i.get("scheme") == "OPENCORPORATES"]
        assert oc_ids == []
