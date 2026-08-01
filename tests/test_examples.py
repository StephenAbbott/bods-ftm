"""The shipped examples must actually convert.

Found 2026-07-31 during the followthemoney 4.x upgrade smoke test: the
previous ``examples/sample_bods.json`` predated the canonical BODS 0.4
envelope (``statementType`` instead of ``recordType``, no ``recordId``,
``names[]``/``incorporatedInJurisdiction`` on entities), so the README's
documented CLI walkthrough produced **0 FTM entities** from the repo's own
example. These tests pin the example to the converter so it cannot rot
again.
"""

from __future__ import annotations

import json
from pathlib import Path

from bods_ftm.bods_to_ftm.converter import BODSToFTMConverter

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _shipped_statements() -> list[dict]:
    return json.loads((EXAMPLES / "sample_bods.json").read_text())


def test_shipped_bods_example_converts_to_entities():
    entities = BODSToFTMConverter().convert(_shipped_statements())
    assert len(entities) > 0, (
        "examples/sample_bods.json converted to zero FTM entities — the "
        "shipped example has drifted from the canonical BODS 0.4 envelope"
    )
    schemas = sorted(e["schema"] for e in entities)
    # The example's story: Jane Smith owns 75% of Acme Holdings Ltd (shares
    # + voting rights) and sits on its board; Holdings owns 100% of Acme
    # Trading Ltd.
    assert schemas == [
        "Company",
        "Company",
        "Directorship",
        "Ownership",
        "Ownership",
        "Ownership",
        "Person",
    ]


def test_shipped_ftm_example_is_the_cli_output_for_the_bods_example():
    # examples/sample_ftm.jsonl documents the bods-to-ftm output for
    # examples/sample_bods.json (and feeds the ftm-to-bods walkthrough).
    # Conversion is deterministic (uuid5 relationship ids, statementDate
    # provenance), so the pair must stay regenerable:
    #   bods-ftm bods-to-ftm examples/sample_bods.json \
    #       -o examples/sample_ftm.jsonl
    shipped = [
        json.loads(line)
        for line in (EXAMPLES / "sample_ftm.jsonl").read_text().splitlines()
        if line.strip()
    ]
    regenerated = BODSToFTMConverter().convert(_shipped_statements())
    assert shipped == regenerated, (
        "examples/sample_ftm.jsonl is stale — regenerate it with: "
        "bods-ftm bods-to-ftm examples/sample_bods.json "
        "-o examples/sample_ftm.jsonl"
    )
