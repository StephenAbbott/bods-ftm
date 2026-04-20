# bods-ftm

Bidirectional converter between [Beneficial Ownership Data Standard (BODS) v0.4](https://standard.openownership.org/en/0.4.0/) and the [FollowTheMoney (FtM)](https://followthemoney.tech/) data model used by [OpenSanctions](https://www.opensanctions.org/) and [OpenAleph](https://openaleph.org/).

## Motivation

[OpenSanctions](https://www.opensanctions.org/), [OpenAleph](https://openaleph.org/) and the broader investigative data ecosystem publish a large number of datasets in FollowTheMoney format — including company registries, ownership structures, sanctions lists and politically exposed person (PEP) data. 

The [Data and Research Center library](https://dataresearchcenter.org/library/) catalogues many of them. Any dataset in that library that contains ownership information can, in principle, be converted into BODS v0.4 for use by beneficial ownership transparency tools, registers and policy analysis.

Earlier work ([opensanctions/bods-ftm](https://github.com/opensanctions/bods-ftm), [pudo-attic/opensanctions-kyb-graph-old](https://github.com/pudo-attic/opensanctions-kyb-graph-old)) showed how to map [Open Ownership](https://www.openownership.org/) BODS v0.2 data into FtM. BODS v0.4 introduced significant structural changes — including the `recordDetails` nesting, the `isComponent` / `componentStatementIDs` pattern for indirect chains, and a richer `entityType` object — that make a fresh mapping necessary. This repository fills that gap.

## What it converts

| BODS v0.4 | FollowTheMoney |
|---|---|
| `entityStatement` (`registeredEntity`) | `Company` |
| `entityStatement` (`legalEntity`) | `Organization` |
| `entityStatement` (`arrangement`, `anonymousEntity`, `unknownEntity`) | `LegalEntity` |
| `entityStatement` (`state`, `stateBody`) | `PublicBody` |
| `personStatement` | `Person` |
| `ownershipOrControlStatement` with shareholding / voting rights interest | `Ownership` |
| `ownershipOrControlStatement` with board / directorship interest | `Directorship` |
| `ownershipOrControlStatement` with unknown interest | `UnknownLink` |

Full interest-type mapping is in [`src/bods_ftm/bods_to_ftm/relationship_mapper.py`](src/bods_ftm/bods_to_ftm/relationship_mapper.py).

## Installation

```bash
pip install .
```

For development (includes pytest):

```bash
pip install ".[dev]"
```

## Usage

### BODS v0.4 → FollowTheMoney

```bash
bods-ftm bods-to-ftm examples/sample_bods.json -o output.ftm.jsonl
```

### FollowTheMoney → BODS v0.4

```bash
bods-ftm ftm-to-bods examples/sample_ftm.jsonl \
  -o output.bods.json \
  --publisher-name "My Organisation" \
  --publisher-uri "https://example.com" \
  --license-url "https://creativecommons.org/publicdomain/zero/1.0/"
```

### Options

| Flag | Command | Description |
|------|---------|-------------|
| `-o / --output` | both | Output file path |
| `--publisher-name` | `ftm-to-bods` | BODS publisher name |
| `--publisher-uri` | `ftm-to-bods` | BODS publisher URI |
| `--license-url` | `ftm-to-bods` | BODS license URL (default: CC0) |
| `-v / --verbose` | both | Debug logging |
| `-q / --quiet` | both | Errors only |

### Python API

```python
from bods_ftm.bods_to_ftm.converter import BODSToFTMConverter
from bods_ftm.ftm_to_bods.converter import FTMToBODSConverter
from bods_ftm.config import PublisherConfig

# BODS → FTM
converter = BODSToFTMConverter()
ftm_entities = converter.convert(bods_statements)   # list[dict] → list[dict]
converter.convert_file("input.bods.json", "output.ftm.jsonl")

# FTM → BODS
config = PublisherConfig(
    publisher_name="My Organisation",
    publisher_uri="https://example.com",
)
converter = FTMToBODSConverter(config)
bods_statements = converter.convert(ftm_entities)   # list[dict] → list[dict]
converter.convert_file("input.ftm.jsonl", "output.bods.json")
```

## How the mapping works

### BODS → FTM

1. **First pass — entities and persons.** Each `entityStatement` is converted to a typed FTM node (`Company`, `Organization`, etc.) using the `entityType.type` value. Each `personStatement` becomes an FTM `Person`. The BODS `statementId` is used directly as the FTM entity ID, preserving the reference.

2. **Second pass — relationships.** Each `ownershipOrControlStatement` is converted to one FTM edge entity per entry in its `interests[]` array. The `interests[].type` value determines whether the edge is `Ownership`, `Directorship`, or `UnknownLink`. The subject/interestedParty BODS IDs resolve to the FTM IDs from pass 1.

3. **Indirect chains.** `isComponent: true` statements (which represent intermediate hops in an indirect ownership chain) are skipped. The top-level statement that holds `componentStatementIDs` already captures the full indirect relationship; emitting the component hops separately would produce duplicate edges in FTM graph tools.

### FTM → BODS

1. **First pass — nodes.** `Company`, `Organization`, `LegalEntity`, and `PublicBody` entities become BODS `entityStatement`s. `Person` entities become BODS `personStatement`s. FTM entity IDs are mapped to BODS `statementId`s via a deterministic UUID5 hash, so the same FTM input always produces the same BODS IDs.

2. **Second pass — edges.** `Ownership`, `Directorship`, and `UnknownLink` entities become BODS `ownershipOrControlStatement`s. The FTM `role` property is inspected to refine the BODS `interests[].type` (e.g. `"board member"` → `boardMember`). Whether the `interestedParty` reference uses `describedByPersonStatement` or `describedByEntityStatement` is determined automatically from the type of entity produced in pass 1.

### Identifier mapping

BODS uses [org-id.guide](https://org-id.guide/) scheme codes (e.g. `GB-COH`, `XI-LEI`) while FTM uses named properties (`registrationNumber`, `leiCode`). The full scheme ↔ property mapping is in [`src/bods_ftm/bods_to_ftm/identifier_mapper.py`](src/bods_ftm/bods_to_ftm/identifier_mapper.py) and its FTM→BODS counterpart.

## Known limitations and information loss

Some BODS concepts have no direct FTM equivalent and are handled as described below.

| BODS concept | Behaviour in FTM output |
|---|---|
| `interests[]` multiple entries on one OOC | One FTM edge entity per interest |
| `isComponent` / `componentStatementIDs` (indirect chain) | Component hops are skipped; top-level statement sets `description` noting the chain |
| `replacesStatements` (temporal versioning) | Dropped — no FTM equivalent |
| `publicationDetails` | Publisher name/URI mapped to FTM `publisher` / `sourceUrl` |
| `politicalExposure` PEP reason | Mapped to FTM `position` property |
| `interestedParty.unspecified` | Represented as a synthetic `LegalEntity` FTM node with the unspecified reason in its ID |

Some FTM concepts are similarly lossy in the BODS direction.

| FTM concept | Behaviour in BODS output |
|---|---|
| Multiple `name` values | All mapped to BODS `names[]` array |
| `role` on Ownership/Directorship | Inspected to refine `interests[].type`; values not in the mapping table default to `shareholding` / `boardMember` |
| `datasets` / `referredTo` | Dropped |
| `Employment`, `Membership`, `Representation` | Converted to OOC with `seniorManagingOfficial` / `otherInfluenceOrControl` interest type |

## Project structure

```
src/bods_ftm/
├── bods_to_ftm/
│   ├── converter.py          # BODSToFTMConverter — two-pass orchestrator
│   ├── entity_mapper.py      # entityStatement → FTM Company/Organization/...
│   ├── person_mapper.py      # personStatement → FTM Person
│   ├── relationship_mapper.py# ownershipOrControlStatement → FTM Ownership/Directorship/UnknownLink
│   └── identifier_mapper.py  # BODS scheme codes → FTM property names
├── ftm_to_bods/
│   ├── converter.py          # FTMToBODSConverter — two-pass orchestrator
│   ├── entity_mapper.py      # FTM Company/Organization/... → entityStatement
│   ├── person_mapper.py      # FTM Person → personStatement
│   ├── relationship_mapper.py# FTM Ownership/Directorship/... → ownershipOrControlStatement
│   └── identifier_mapper.py  # FTM property names → BODS scheme codes
├── utils/
│   ├── dates.py              # Date normalisation helpers
│   ├── ids.py                # Deterministic ID generation (UUID5)
│   └── statements.py         # BODS statement envelope builders
├── cli.py                    # Click CLI entry point
└── config.py                 # PublisherConfig dataclass
```

## Testing

```bash
pytest
```

The test suite covers unit-level mappers, the full converter pipeline, and bidirectional round-trip properties (BODS→FTM→BODS and FTM→BODS→FTM).

### Conformance against the shared BODS v0.4 fixture pack

`tests/test_bods_fixtures_conformance.py` runs the bidirectional converter against every case in the canonical [**bods-v04-fixtures**](https://pypi.org/project/bods-v04-fixtures/) pack via the [**pytest-bods-v04-fixtures**](https://pypi.org/project/pytest-bods-v04-fixtures/) plugin. Tests are parametrized by fixture name so a failure like `[edge-cases/11-anonymous-person]` points straight at the offending case.

Conformance checks include: every canonical fixture maps without exception; entity/person counts round-trip; declared-unknown UBOs (inline `unspecifiedReason`) reach the FTM output rather than being silently dropped; and circular ownership produces both mirrored edges.

## Related work

- [opensanctions/bods-ftm](https://github.com/opensanctions/bods-ftm) — archived BODS v0.2 → FtM converter (predecessor to this project)
- [opensanctions/graph](https://github.com/opensanctions/graph) — OpenSanctions graph pipeline, handles BODS and GLEIF inputs
- [openownership/bods-gleif-pipeline](https://github.com/openownership/bods-gleif-pipeline) — reference BODS v0.4 producer (GLEIF Level 1 & 2)
- [OpenOwnership BODS data explorer](https://bods-data.openownership.org/) — browse published BODS v0.4 datasets
- [Data Research Center FtM library](https://dataresearchcenter.org/library/) — catalogue of FtM datasets that can be converted to BODS using this tool

## License

MIT
