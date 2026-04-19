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

# FTM schemas that represent entities (nodes in the graph)
_ENTITY_SCHEMAS = frozenset(("Company", "Organization", "LegalEntity", "PublicBody"))
_PERSON_SCHEMAS = frozenset(("Person",))
# FTM schemas that represent relationships (edges in the graph)
_RELATIONSHIP_SCHEMAS = frozenset(FTM_SCHEMA_TO_INTEREST_TYPE.keys())


class FTMToBODSConverter:
    """Convert a stream of FollowTheMoney entities to BODS v0.4 statements.

    Two passes:

    1. Company/Organization/Person proxies are converted to BODS entity and
       person records. A registry of FTM ID → BODS recordId is built for use
       in pass 2 — recordId is the stable identity that subject and
       interestedParty references resolve against in canonical 0.4.
    2. Ownership/Directorship/UnknownLink proxies become BODS relationship
       records, with subject/interestedParty emitted as recordId strings.
    """

    def __init__(self, config: PublisherConfig | None = None) -> None:
        self.config = config or PublisherConfig()
        # Maps FTM entity ID → BODS recordId
        self._ftm_id_to_record_id: dict[str, str] = {}

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
                self._ftm_id_to_record_id[proxy.id] = bods_stmt["recordId"]
                statements.append(bods_stmt)

        # Pass 2: relationships
        for proxy in proxies:
            if proxy.schema.name in _RELATIONSHIP_SCHEMAS:
                bods_stmt = ftm_relationship_to_bods(
                    proxy, self._ftm_id_to_record_id, self.config
                )
                if bods_stmt is not None:
                    statements.append(bods_stmt)

        return statements

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
