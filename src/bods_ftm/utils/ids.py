from __future__ import annotations

import uuid

# Fixed namespace for deterministic UUID5 generation from FTM IDs
_BODS_FTM_NAMESPACE = uuid.UUID("b6e3f5a2-0c1d-4e8f-9b7a-3d2c1e0f4a5b")


def ftm_id_to_bods_record_id(ftm_id: str) -> str:
    """Generate a deterministic BODS recordId from an FTM entity ID."""
    return str(uuid.uuid5(_BODS_FTM_NAMESPACE, f"bods-record:{ftm_id}"))


def ftm_id_to_bods_statement_id(ftm_id: str) -> str:
    """Generate a deterministic BODS statementId from an FTM entity ID."""
    return str(uuid.uuid5(_BODS_FTM_NAMESPACE, f"bods:{ftm_id}"))


def bods_record_id_to_ftm_id(record_id: str) -> str:
    """Use a BODS recordId directly as an FTM entity ID.

    BODS recordIds are alphanumeric (typically short hex strings or UUIDs);
    FTM accepts alphanumeric, hyphens and dots, so a recordId is a valid FTM
    ID without modification.
    """
    return record_id


def bods_statement_id_to_ftm_id(statement_id: str) -> str:
    """Deprecated: use bods_record_id_to_ftm_id instead.

    Kept for backwards compatibility with code that hasn't migrated to using
    recordId for entity identity. In canonical BODS 0.4, recordId is the
    stable identity across multiple statements; statementId changes per
    update.
    """
    return statement_id


def make_ftm_relationship_id(*parts: str) -> str:
    """Generate a deterministic FTM entity ID for a relationship entity."""
    seed = ":".join(p for p in parts if p)
    return str(uuid.uuid5(_BODS_FTM_NAMESPACE, seed))
