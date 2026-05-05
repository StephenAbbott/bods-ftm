from __future__ import annotations

from bods_ftm.bods_to_ftm.converter import BODSToFTMConverter
from bods_ftm.bods_to_ftm.entity_mapper import entity_statement_to_ftm
from bods_ftm.bods_to_ftm.person_mapper import person_statement_to_ftm
from bods_ftm.bods_to_ftm.relationship_mapper import ooc_statement_to_ftm

from tests.conftest import (
    SAMPLE_BODS_DATASET,
    SAMPLE_ENTITY_STATEMENT,
    SAMPLE_OOC_STATEMENT,
    SAMPLE_PERSON_STATEMENT,
)


# Canonical 0.4 uses recordId for identity; build an index the way the
# converter does so the raw relationship mapper can resolve references.
_RECORD_INDEX = {
    SAMPLE_ENTITY_STATEMENT["recordId"]: SAMPLE_ENTITY_STATEMENT,
    SAMPLE_PERSON_STATEMENT["recordId"]: SAMPLE_PERSON_STATEMENT,
}


class TestEntityMapper:
    def test_converts_registered_entity(self):
        proxy = entity_statement_to_ftm(SAMPLE_ENTITY_STATEMENT)
        assert proxy is not None
        assert proxy.schema.name == "Company"
        assert proxy.first("name") == "Test Company Ltd"

    def test_maps_gb_coh_to_registration_number(self):
        proxy = entity_statement_to_ftm(SAMPLE_ENTITY_STATEMENT)
        assert proxy is not None
        assert "11223344" in list(proxy.get("registrationNumber", quiet=True))

    def test_maps_lei_to_lei_code(self):
        proxy = entity_statement_to_ftm(SAMPLE_ENTITY_STATEMENT)
        assert proxy is not None
        assert "213800TEST0000001A80" in list(proxy.get("leiCode", quiet=True))

    def test_maps_jurisdiction(self):
        proxy = entity_statement_to_ftm(SAMPLE_ENTITY_STATEMENT)
        assert proxy is not None
        assert proxy.first("jurisdiction") == "gb"

    def test_maps_founding_date(self):
        proxy = entity_statement_to_ftm(SAMPLE_ENTITY_STATEMENT)
        assert proxy is not None
        assert proxy.first("incorporationDate") == "2010-01-01"

    def test_maps_address(self):
        proxy = entity_statement_to_ftm(SAMPLE_ENTITY_STATEMENT)
        assert proxy is not None
        assert "1 Test Street" in list(proxy.get("address", quiet=True))

    def test_uses_record_id_as_ftm_id(self):
        """FTM identity comes from recordId (the stable BODS 0.4 identity),
        not statementId (which changes per update)."""
        proxy = entity_statement_to_ftm(SAMPLE_ENTITY_STATEMENT)
        assert proxy is not None
        assert proxy.id == "test-entity-record-0001"

    def test_returns_none_for_nameless_entity(self):
        stmt = {
            **SAMPLE_ENTITY_STATEMENT,
            "recordDetails": {
                **SAMPLE_ENTITY_STATEMENT["recordDetails"],
                "name": "",
            },
        }
        proxy = entity_statement_to_ftm(stmt)
        assert proxy is None

    def test_legalentity_type_maps_to_organization(self):
        stmt = {
            **SAMPLE_ENTITY_STATEMENT,
            "statementId": "test-entity-legal",
            "recordId": "test-entity-legal-record",
            "recordDetails": {
                **SAMPLE_ENTITY_STATEMENT["recordDetails"],
                "entityType": {"type": "legalEntity"},
            },
        }
        proxy = entity_statement_to_ftm(stmt)
        assert proxy is not None
        assert proxy.schema.name == "Organization"

    def test_state_type_maps_to_publicbody(self):
        stmt = {
            **SAMPLE_ENTITY_STATEMENT,
            "statementId": "test-entity-state",
            "recordId": "test-entity-state-record",
            "recordDetails": {
                **SAMPLE_ENTITY_STATEMENT["recordDetails"],
                "entityType": {"type": "stateBody"},
            },
        }
        proxy = entity_statement_to_ftm(stmt)
        assert proxy is not None
        assert proxy.schema.name == "PublicBody"


class TestPersonMapper:
    def test_converts_person(self):
        proxy = person_statement_to_ftm(SAMPLE_PERSON_STATEMENT)
        assert proxy is not None
        assert proxy.schema.name == "Person"
        assert proxy.first("name") == "Test Person"

    def test_maps_nationality(self):
        proxy = person_statement_to_ftm(SAMPLE_PERSON_STATEMENT)
        assert proxy is not None
        assert "gb" in list(proxy.get("nationality", quiet=True))

    def test_maps_birth_date(self):
        proxy = person_statement_to_ftm(SAMPLE_PERSON_STATEMENT)
        assert proxy is not None
        assert proxy.first("birthDate") == "1980-06-15"

    def test_uses_record_id_as_ftm_id(self):
        proxy = person_statement_to_ftm(SAMPLE_PERSON_STATEMENT)
        assert proxy is not None
        assert proxy.id == "test-person-record-0001"

    def test_returns_none_for_unknown_person_without_name(self):
        stmt = {
            **SAMPLE_PERSON_STATEMENT,
            "recordDetails": {
                **SAMPLE_PERSON_STATEMENT["recordDetails"],
                "personType": "unknownPerson",
                "names": [],
            },
        }
        proxy = person_statement_to_ftm(stmt)
        assert proxy is None


class TestRelationshipMapper:
    def test_converts_shareholding_to_ownership(self):
        proxies = ooc_statement_to_ftm(SAMPLE_OOC_STATEMENT, _RECORD_INDEX)
        assert len(proxies) == 1
        assert proxies[0].schema.name == "Ownership"

    def test_maps_percentage(self):
        proxies = ooc_statement_to_ftm(SAMPLE_OOC_STATEMENT, _RECORD_INDEX)
        assert proxies[0].first("percentage") == "51.0"

    def test_maps_owner_and_asset_ids(self):
        proxies = ooc_statement_to_ftm(SAMPLE_OOC_STATEMENT, _RECORD_INDEX)
        proxy = proxies[0]
        assert "test-person-record-0001" in list(proxy.get("owner", quiet=True))
        assert "test-entity-record-0001" in list(proxy.get("asset", quiet=True))

    def test_maps_direct_status(self):
        proxies = ooc_statement_to_ftm(SAMPLE_OOC_STATEMENT, _RECORD_INDEX)
        assert proxies[0].first("status") == "direct"

    def test_beneficial_ownership_sets_summary(self):
        proxies = ooc_statement_to_ftm(SAMPLE_OOC_STATEMENT, _RECORD_INDEX)
        assert "beneficial" in (proxies[0].first("summary") or "")

    def test_multiple_interests_produce_multiple_proxies(self):
        stmt = {
            **SAMPLE_OOC_STATEMENT,
            "statementId": "test-rel-stmt-multi",
            "recordId": "test-rel-record-multi",
            "recordDetails": {
                **SAMPLE_OOC_STATEMENT["recordDetails"],
                "interests": [
                    {"type": "shareholding", "share": {"exact": 51.0}},
                    {"type": "votingRights", "share": {"exact": 51.0}},
                ],
            },
        }
        proxies = ooc_statement_to_ftm(stmt, _RECORD_INDEX)
        assert len(proxies) == 2

    def test_board_member_maps_to_directorship(self):
        stmt = {
            **SAMPLE_OOC_STATEMENT,
            "statementId": "test-rel-stmt-board",
            "recordId": "test-rel-record-board",
            "recordDetails": {
                **SAMPLE_OOC_STATEMENT["recordDetails"],
                "interests": [{"type": "boardMember"}],
            },
        }
        proxies = ooc_statement_to_ftm(stmt, _RECORD_INDEX)
        assert proxies[0].schema.name == "Directorship"

    def test_skips_statement_with_unresolved_subject(self):
        stmt = {
            **SAMPLE_OOC_STATEMENT,
            "recordDetails": {
                **SAMPLE_OOC_STATEMENT["recordDetails"],
                "subject": "nonexistent-record-id",
            },
        }
        proxies = ooc_statement_to_ftm(stmt, _RECORD_INDEX)
        assert proxies == []


class TestBODSToFTMConverter:
    def test_converts_full_dataset(self):
        converter = BODSToFTMConverter()
        result = converter.convert(SAMPLE_BODS_DATASET)
        assert len(result) > 0
        schemas = {e["schema"] for e in result}
        assert "Company" in schemas
        assert "Person" in schemas
        assert "Ownership" in schemas

    def test_file_roundtrip(self, sample_bods_file, tmp_path):
        output = tmp_path / "out.jsonl"
        converter = BODSToFTMConverter()
        count = converter.convert_file(sample_bods_file, output)
        assert count > 0
        assert output.exists()


class TestOpenCorporatesIdentifier:
    def test_opencorporates_scheme_sets_oc_url(self):
        """BODS OPENCORPORATES identifier -> FTM opencorporatesUrl property."""
        stmt = {
            **SAMPLE_ENTITY_STATEMENT,
            "statementId": "test-oc-stmt-001",
            "recordId": "test-oc-record-001",
            "recordDetails": {
                **SAMPLE_ENTITY_STATEMENT["recordDetails"],
                "identifiers": [
                    {
                        "id": "se/556056-6258",
                        "scheme": "OPENCORPORATES",
                        "schemeName": "OpenCorporates company identifier",
                        "uri": "https://opencorporates.com/companies/se/556056-6258",
                    }
                ],
            },
        }
        proxy = entity_statement_to_ftm(stmt)
        assert proxy is not None
        oc_urls = list(proxy.get("opencorporatesUrl", quiet=True))
        assert "https://opencorporates.com/companies/se/556056-6258" in oc_urls

    def test_opencorporates_constructs_url_from_id_when_no_uri(self):
        """When the uri field is absent, the URL is constructed from id."""
        stmt = {
            **SAMPLE_ENTITY_STATEMENT,
            "statementId": "test-oc-stmt-002",
            "recordId": "test-oc-record-002",
            "recordDetails": {
                **SAMPLE_ENTITY_STATEMENT["recordDetails"],
                "identifiers": [
                    {"id": "gb/00102498", "scheme": "OPENCORPORATES"},
                ],
            },
        }
        proxy = entity_statement_to_ftm(stmt)
        assert proxy is not None
        oc_urls = list(proxy.get("opencorporatesUrl", quiet=True))
        assert "https://opencorporates.com/companies/gb/00102498" in oc_urls

    def test_opencorporates_does_not_pollute_registration_number(self):
        """OPENCORPORATES id must not be written to registrationNumber."""
        stmt = {
            **SAMPLE_ENTITY_STATEMENT,
            "statementId": "test-oc-stmt-003",
            "recordId": "test-oc-record-003",
            "recordDetails": {
                **SAMPLE_ENTITY_STATEMENT["recordDetails"],
                "identifiers": [
                    {"id": "se/556056-6258", "scheme": "OPENCORPORATES"},
                ],
            },
        }
        proxy = entity_statement_to_ftm(stmt)
        assert proxy is not None
        reg_nums = list(proxy.get("registrationNumber", quiet=True))
        assert "se/556056-6258" not in reg_nums

    def test_gleif_qcc_scheme_skipped(self):
        """QCC Code (Qichacha GEI) has no FtM equivalent; must not pollute registrationNumber."""
        stmt = {
            **SAMPLE_ENTITY_STATEMENT,
            "statementId": "test-qcc-stmt-001",
            "recordId": "test-qcc-record-001",
            "recordDetails": {
                **SAMPLE_ENTITY_STATEMENT["recordDetails"],
                "identifiers": [
                    {"id": "QCC-EXAMPLE-001", "scheme": "QCC Code"},
                ],
            },
        }
        proxy = entity_statement_to_ftm(stmt)
        assert proxy is not None
        reg_nums = list(proxy.get("registrationNumber", quiet=True))
        assert "QCC-EXAMPLE-001" not in reg_nums

    def test_iso_10383_mic_scheme_skipped(self):
        """ISO-10383 MIC has no FtM equivalent; must not pollute registrationNumber."""
        stmt = {
            **SAMPLE_ENTITY_STATEMENT,
            "statementId": "test-mic-stmt-001",
            "recordId": "test-mic-record-001",
            "recordDetails": {
                **SAMPLE_ENTITY_STATEMENT["recordDetails"],
                "identifiers": [
                    {"id": "XSTO", "scheme": "ISO-10383"},
                ],
            },
        }
        proxy = entity_statement_to_ftm(stmt)
        assert proxy is not None
        reg_nums = list(proxy.get("registrationNumber", quiet=True))
        assert "XSTO" not in reg_nums

    def test_iso_9362_bic_scheme_skipped(self):
        """ISO-9362 BIC has no FtM equivalent; must not pollute registrationNumber."""
        stmt = {
            **SAMPLE_ENTITY_STATEMENT,
            "statementId": "test-bic-stmt-001",
            "recordId": "test-bic-record-001",
            "recordDetails": {
                **SAMPLE_ENTITY_STATEMENT["recordDetails"],
                "identifiers": [
                    {"id": "ESSESESS", "scheme": "ISO-9362"},
                ],
            },
        }
        proxy = entity_statement_to_ftm(stmt)
        assert proxy is not None
        reg_nums = list(proxy.get("registrationNumber", quiet=True))
        assert "ESSESESS" not in reg_nums
