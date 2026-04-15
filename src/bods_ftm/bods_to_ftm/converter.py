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

    The converter performs two passes over the input:

    1. Entity and person statements are converted first so that their FTM IDs
       are available when resolving subject/interestedParty references in OOC
       statements.
    2. Ownership-or-control statements are then converted, resolving subject
       and interestedParty references to the FTM IDs generated in pass 1.
    """

    def convert(self, bods_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert a list of BODS statements to a list of FTM entity dicts.

        Returns serialised entity dicts suitable for writing as JSONL.
        """
        return [proxy.to_dict() for proxy in self._iter_proxies(bods_data)]

    def _iter_proxies(
        self, bods_data: list[dict[str, Any]]
    ) -> Iterator[EntityProxy]:
        """Yield FTM entity proxies from BODS statements."""
        # Index all statements by statementId for reference resolution
        statement_index: dict[str, dict[str, Any]] = {
            s["statementId"]: s for s in bods_data if "statementId" in s
        }

        # Pass 1: entities and persons
        for statement in bods_data:
            stmt_type = statement.get("statementType")
            if stmt_type == "entityStatement":
                proxy = entity_statement_to_ftm(statement)
                if proxy is not None:
                    yield proxy
            elif stmt_type == "personStatement":
                proxy = person_statement_to_ftm(statement)
                if proxy is not None:
                    yield proxy

        # Pass 2: ownership-or-control relationships
        for statement in bods_data:
            if statement.get("statementType") == "ownershipOrControlStatement":
                # Skip component statements — they represent intermediate hops in
                # an indirect chain.  The top-level statement (isComponent: False)
                # already captures the full indirect relationship; emitting the
                # components separately would produce duplicate edges in FTM graph
                # tools.
                if statement.get("recordDetails", {}).get("isComponent", False):
                    continue
                for proxy in ooc_statement_to_ftm(statement, statement_index):
                    yield proxy

    def convert_file(self, input_path: str | Path, output_path: str | Path) -> int:
        """Read BODS JSON from input_path, write FTM JSONL to output_path.

        Returns the number of FTM entities written.
        """
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
