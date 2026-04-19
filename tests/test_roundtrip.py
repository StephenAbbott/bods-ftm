from __future__ import annotations

"""Round-trip tests: BODS→FTM→BODS and FTM→BODS→FTM.

These verify that key properties survive the conversion cycle. Some
information loss is expected (documented in the README); these tests focus
on the semantically important fields: names, identifiers, ownership
percentages, and statement envelope structure.
"""

from bods_ftm.bods_to_ftm.converter import BODSToFTMConverter
from bods_ftm.config import PublisherConfig
from bods_ftm.ftm_to_bods.converter import FTMToBODSConverter

from tests.conftest import SAMPLE_BODS_DATASET, SAMPLE_FTM_DATASET

CONFIG = PublisherConfig(publisher_name="Round-trip Test")


class TestBODSToFTMToBODS:
    """BODS v0.4 → FTM → BODS v0.4 round-trip."""

    def _roundtrip(self, bods_data):
        ftm_entities = BODSToFTMConverter().convert(bods_data)
        return FTMToBODSConverter(CONFIG).convert(ftm_entities)

    def test_entity_count_preserved(self):
        result = self._roundtrip(SAMPLE_BODS_DATASET)
        entity_stmts = [s for s in result if s.get("recordType") == "entity"]
        original_entity_stmts = [
            s for s in SAMPLE_BODS_DATASET if s.get("recordType") == "entity"
        ]
        assert len(entity_stmts) == len(original_entity_stmts)

    def test_person_count_preserved(self):
        result = self._roundtrip(SAMPLE_BODS_DATASET)
        person_stmts = [s for s in result if s.get("recordType") == "person"]
        original_person_stmts = [
            s for s in SAMPLE_BODS_DATASET if s.get("recordType") == "person"
        ]
        assert len(person_stmts) == len(original_person_stmts)

    def test_entity_name_survives(self):
        result = self._roundtrip(SAMPLE_BODS_DATASET)
        entity_stmts = [s for s in result if s.get("recordType") == "entity"]
        names = {s["recordDetails"].get("name") for s in entity_stmts}
        assert "Test Company Ltd" in names

    def test_person_name_survives(self):
        result = self._roundtrip(SAMPLE_BODS_DATASET)
        person_stmts = [s for s in result if s.get("recordType") == "person"]
        names = {
            n["fullName"]
            for s in person_stmts
            for n in s["recordDetails"].get("names", [])
        }
        assert "Test Person" in names

    def test_ownership_percentage_survives(self):
        result = self._roundtrip(SAMPLE_BODS_DATASET)
        rel_stmts = [s for s in result if s.get("recordType") == "relationship"]
        percentages = {
            i["share"]["exact"]
            for s in rel_stmts
            for i in s["recordDetails"].get("interests", [])
            if "share" in i
        }
        assert 51.0 in percentages

    def test_jurisdiction_survives(self):
        result = self._roundtrip(SAMPLE_BODS_DATASET)
        entity_stmts = [s for s in result if s.get("recordType") == "entity"]
        jurisdictions = {
            s["recordDetails"].get("jurisdiction", {}).get("code")
            for s in entity_stmts
        }
        assert "GB" in jurisdictions

    def test_bods_version_is_0_4(self):
        result = self._roundtrip(SAMPLE_BODS_DATASET)
        for stmt in result:
            assert stmt["publicationDetails"]["bodsVersion"] == "0.4"


class TestFTMToBODSToFTM:
    """FTM → BODS v0.4 → FTM round-trip."""

    def _roundtrip(self, ftm_data):
        bods_stmts = FTMToBODSConverter(CONFIG).convert(ftm_data)
        return BODSToFTMConverter().convert(bods_stmts)

    def test_entity_schemas_preserved(self):
        result = self._roundtrip(SAMPLE_FTM_DATASET)
        schemas = {e["schema"] for e in result}
        assert "Company" in schemas
        assert "Person" in schemas

    def test_company_name_survives(self):
        result = self._roundtrip(SAMPLE_FTM_DATASET)
        companies = [e for e in result if e["schema"] == "Company"]
        names = {n for e in companies for n in e["properties"].get("name", [])}
        assert "Test Company Ltd" in names

    def test_person_name_survives(self):
        result = self._roundtrip(SAMPLE_FTM_DATASET)
        persons = [e for e in result if e["schema"] == "Person"]
        names = {n for e in persons for n in e["properties"].get("name", [])}
        assert "Test Person" in names

    def test_ownership_relationship_preserved(self):
        result = self._roundtrip(SAMPLE_FTM_DATASET)
        ownership = [e for e in result if e["schema"] in ("Ownership", "Directorship")]
        assert len(ownership) > 0

    def test_percentage_survives(self):
        result = self._roundtrip(SAMPLE_FTM_DATASET)
        ownerships = [e for e in result if e["schema"] == "Ownership"]
        percentages = {
            p for e in ownerships for p in e["properties"].get("percentage", [])
        }
        assert "51.0" in percentages
