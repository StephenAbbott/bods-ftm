from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from followthemoney import model
from followthemoney.proxy import EntityProxy

from bods_ftm.config import PublisherConfig
from bods_ftm.ftm_to_bods.entity_mapper import ftm_entity_to_bods
from bods_ftm.ftm_to_bods.person_mapper import ftm_person_to_bods
from bods_ftm.ftm_to_bods.relationship_mapper import (
    FTM_SCHEMA_TO_INTEREST_TYPE,
    ftm_relationship_to_bods,
)
from bods_ftm.utils.ids import ftm_id_to_bods_statement_id

# FTM schemas that represent entities (nodes in the graph)
_ENTITY_SCHEMAS = frozenset(("Company", "Organization", "LegalEntity", "PublicBody"))
_PERSON_SCHEMAS = frozenset(("Person",))
# FTM schemas that represent relationships (edges in the graph)
_RELATIONSHIP_SCHEMAS = frozenset(FTM_SCHEMA_TO_INTEREST_TYPE.keys())


class FTMToBODSConverter:
    """Convert a stream of FollowTheMoney entities to BODS v0.4 statements.

    Usage::

        config = PublisherConfig(publisher_name="My Publisher")
        converter = FTMToBODSConverter(config)
        bods_statements = converter.convert(ftm_entities)

    The converter performs two passes:

    1. All Company/Organization/Person entities are converted to BODS entity
       and person statements.  A registry of FTM ID → BODS statementId is
       built for use in pass 2.
    2. Ownership, Directorship, and related relationship entities are
       converted to BODS ownership-or-control statements, with
       subject/interestedParty references resolved via the registry.
    """

    def __init__(self, config: PublisherConfig | None = None) -> None:
        self.config = config or PublisherConfig()
        # Maps FTM entity ID → BODS statementId
        self._ftm_id_to_bods_id: dict[str, str] = {}
        # Tracks which BODS statementIds represent person statements
        self._person_statement_ids: set[str] = set()

    def convert(self, ftm_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert a list of FTM entity dicts to a list of BODS statement dicts."""
        proxies = [model.get_proxy(e) for e in ftm_data]
        return self._convert_proxies(proxies)

    def _convert_proxies(self, proxies: list[EntityProxy]) -> list[dict[str, Any]]:
        statements: list[dict[str, Any]] = []

        # Pass 1: entities and persons
        for proxy in proxies:
            bods_stmt: dict[str, Any] | None = None

            if proxy.schema.name in _ENTITY_SCHEMAS:
                bods_stmt = ftm_entity_to_bods(proxy, self.config)
            elif proxy.schema.name in _PERSON_SCHEMAS:
                bods_stmt = ftm_person_to_bods(proxy, self.config)

            if bods_stmt is not None:
                bods_id = bods_stmt["statementId"]
                self._ftm_id_to_bods_id[proxy.id] = bods_id
                if proxy.schema.name in _PERSON_SCHEMAS:
                    self._person_statement_ids.add(bods_id)
                statements.append(bods_stmt)

        # Pass 2: relationships
        for proxy in proxies:
            if proxy.schema.name in _RELATIONSHIP_SCHEMAS:
                bods_stmt = self._convert_relationship(proxy)
                if bods_stmt is not None:
                    statements.append(bods_stmt)

        return statements

    def _convert_relationship(
        self, proxy: EntityProxy
    ) -> dict[str, Any] | None:
        """Convert a relationship proxy, injecting the person-vs-entity hint."""
        bods_stmt = ftm_relationship_to_bods(
            proxy, self._ftm_id_to_bods_id, self.config
        )
        if bods_stmt is None:
            return None

        # Refine interestedParty reference: if the owner resolves to a person
        # statement, use describedByPersonStatement; else describedByEntityStatement
        record = bods_stmt.get("recordDetails", {})
        interested_party = record.get("interestedParty", {})
        if isinstance(interested_party, dict):
            current_ref = interested_party.get(
                "describedByEntityStatement"
            ) or interested_party.get("describedByPersonStatement")
            if current_ref and current_ref in self._person_statement_ids:
                record["interestedParty"] = {"describedByPersonStatement": current_ref}
            elif current_ref:
                record["interestedParty"] = {"describedByEntityStatement": current_ref}

        return bods_stmt

    def convert_file(self, input_path: str | Path, output_path: str | Path) -> int:
        """Read FTM JSONL from input_path, write BODS JSON array to output_path.

        Returns the number of BODS statements written.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        proxies: list[EntityProxy] = []
        with input_path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    proxies.append(model.get_proxy(json.loads(line)))

        statements = self._convert_proxies(proxies)

        with output_path.open("w") as out:
            json.dump(statements, out, indent=2)

        return len(statements)
