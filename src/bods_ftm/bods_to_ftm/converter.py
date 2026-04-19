from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from followthemoney.proxy import EntityProxy

from bods_ftm.bods_to_ftm.entity_mapper import entity_statement_to_ftm
from bods_ftm.bods_to_ftm.person_mapper import person_statement_to_ftm
from bods_ftm.bods_to_ftm.relationship_mapper import ooc_statement_to_ftm


class BODSToFTMConverter:
    """Convert a BODS v0.4 dataset to a stream of FollowTheMoney entity proxies.

    Usage::

        converter = BODSToFTMConverter()
        ftm_entities = converter.convert(bods_statements)

    Two passes:

    1. ``recordType: entity`` and ``recordType: person`` records are converted
       first. The latest statement per ``recordId`` wins so that a record
       updated multiple times produces one FTM proxy.
    2. ``recordType: relationship`` records are converted, resolving
       ``subject`` and ``interestedParty`` recordId strings against the
       record index built in pass 1.
    """

    def convert(self, bods_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [proxy.to_dict() for proxy in self._iter_proxies(bods_data)]

    def _iter_proxies(
        self, bods_data: list[dict[str, Any]]
    ) -> Iterator[EntityProxy]:
        # Index by recordId. Last statement wins for any given recordId,
        # matching BODS 0.4 semantics where later statements update earlier
        # ones.
        record_index: dict[str, dict[str, Any]] = {}
        for s in bods_data:
            record_id = s.get("recordId")
            if record_id:
                record_index[record_id] = s

        emitted_records: set[str] = set()

        # Pass 1: entities and persons (one FTM proxy per unique recordId)
        for record_id, statement in record_index.items():
            record_type = statement.get("recordType")
            if record_type == "entity":
                proxy = entity_statement_to_ftm(statement)
            elif record_type == "person":
                proxy = person_statement_to_ftm(statement)
            else:
                continue
            if proxy is not None:
                emitted_records.add(record_id)
                yield proxy

        # Pass 2: relationships
        for statement in bods_data:
            if statement.get("recordType") != "relationship":
                continue
            # Skip component statements — intermediate hops in indirect chains.
            # The non-component top-level statement captures the full chain;
            # emitting components separately produces duplicate FTM edges.
            if statement.get("recordDetails", {}).get("isComponent", False):
                continue
            for proxy in ooc_statement_to_ftm(statement, record_index):
                yield proxy

    def convert_file(self, input_path: str | Path, output_path: str | Path) -> int:
        input_path = Path(input_path)
        output_path = Path(output_path)

        with input_path.open() as fh:
            bods_data = json.load(fh)

        count = 0
        with output_path.open("w") as out:
            for proxy in self._iter_proxies(bods_data):
                out.write(json.dumps(proxy.to_dict()) + "\n")
                count += 1

        return count
