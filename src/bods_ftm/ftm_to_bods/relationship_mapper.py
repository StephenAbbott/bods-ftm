from __future__ import annotations

from typing import Any

from followthemoney.proxy import EntityProxy

from bods_ftm.config import PublisherConfig
from bods_ftm.utils.dates import normalise_date
from bods_ftm.utils.ids import ftm_id_to_bods_statement_id, make_ftm_relationship_id
from bods_ftm.utils.statements import ooc_statement, publication_details

# Maps FTM schema name → default BODS interest type
FTM_SCHEMA_TO_INTEREST_TYPE: dict[str, str] = {
    "Ownership": "shareholding",
    "Directorship": "boardMember",
    "UnknownLink": "unknownInterest",
    "Membership": "otherInfluenceOrControl",
    "Employment": "seniorManagingOfficial",
    "Representation": "otherInfluenceOrControl",
}

# Refines the default interest type by inspecting the FTM role value
_ROLE_TO_INTEREST_TYPE: dict[str, str] = {
    # Ownership refinements
    "shareholding": "shareholding",
    "voting rights": "votingRights",
    "votingrights": "votingRights",
    "beneficial ownership or control": "shareholding",
    "beneficiary": "beneficiaryOfLegalArrangement",
    "settlor": "settlor",
    # Directorship refinements
    "boardmember": "boardMember",
    "board member": "boardMember",
    "boardchair": "boardChair",
    "board chair": "boardChair",
    "chair": "boardChair",
    "director": "boardMember",
    "seniormanagingofficials": "seniorManagingOfficial",
    "senior managing official": "seniorManagingOfficial",
    "ceo": "seniorManagingOfficial",
    "cfo": "seniorManagingOfficial",
    "trustee": "trustee",
    "protector": "protector",
    "nominee": "nominee",
    "nominator": "nominator",
    # Generic
    "unknowninterest": "unknownInterest",
    "unknown": "unknownInterest",
}


def ftm_relationship_to_bods(
    proxy: EntityProxy,
    ftm_id_to_bods_id: dict[str, str],
    config: PublisherConfig,
) -> dict[str, Any] | None:
    """Convert an FTM Ownership, Directorship, or UnknownLink proxy to a BODS
    v0.4 ownership-or-control statement.

    ftm_id_to_bods_id maps FTM entity IDs to BODS statementIds for the
    entities already converted in the first pass.  Returns None if either
    the subject or interestedParty cannot be resolved.
    """
    schema_name = proxy.schema.name

    # Determine owner and asset FTM IDs based on schema
    if schema_name == "Ownership":
        owner_ids = list(proxy.get("owner", quiet=True))
        asset_ids = list(proxy.get("asset", quiet=True))
    elif schema_name == "Directorship":
        owner_ids = list(proxy.get("director", quiet=True))
        asset_ids = list(proxy.get("organization", quiet=True))
    elif schema_name in ("UnknownLink", "Membership", "Employment", "Representation"):
        owner_ids = list(proxy.get("subject", quiet=True))
        asset_ids = list(proxy.get("object", quiet=True))
        if not owner_ids:
            owner_ids = list(proxy.get("subject", quiet=True))
    else:
        return None

    if not owner_ids or not asset_ids:
        return None

    owner_ftm_id = owner_ids[0]
    asset_ftm_id = asset_ids[0]

    # Resolve to BODS statement IDs
    owner_bods_id = ftm_id_to_bods_id.get(owner_ftm_id)
    asset_bods_id = ftm_id_to_bods_id.get(asset_ftm_id)

    if not owner_bods_id or not asset_bods_id:
        return None

    pub_details = publication_details(
        publisher_name=config.publisher_name,
        publisher_uri=config.publisher_uri,
        license_url=config.license_url,
        bods_version=config.bods_version,
    )

    statement_id = ftm_id_to_bods_statement_id(proxy.id)

    # Determine whether the owner BODS id belongs to a person or entity.
    # We use the presence of the statement in the context to decide; without
    # it, we default to entityStatement reference (callers can refine).
    # The converter passes `is_person_id` via a separate registry — see
    # FTMToBODSConverter for how this is managed.
    # Here we use the FTM schema: Ownership.owner / Directorship.director
    # usually points to a Person.  We leave the caller to inject this via
    # owner_is_person.
    owner_is_person = schema_name in ("Directorship",)

    if owner_is_person:
        interested_party = {"describedByPersonStatement": owner_bods_id}
    else:
        interested_party = {"describedByEntityStatement": owner_bods_id}

    # Interest type
    default_type = FTM_SCHEMA_TO_INTEREST_TYPE.get(schema_name, "unknownInterest")
    role = proxy.first("role", quiet=True) or ""
    interest_type = _ROLE_TO_INTEREST_TYPE.get(role.lower().replace(" ", ""), default_type)
    # Also check the exact role string
    if role.lower() in _ROLE_TO_INTEREST_TYPE:
        interest_type = _ROLE_TO_INTEREST_TYPE[role.lower()]

    interest: dict[str, Any] = {"type": interest_type}

    # Percentage
    percentage_str = proxy.first("percentage", quiet=True)
    if percentage_str:
        try:
            pct = float(percentage_str)
            interest["share"] = {"exact": pct}
        except ValueError:
            pass

    # Direct / indirect
    status = proxy.first("status", quiet=True)
    if status in ("direct", "indirect", "unknown"):
        interest["directOrIndirect"] = status

    # Beneficial ownership flag
    summary = proxy.first("summary", quiet=True) or ""
    if "beneficial" in summary.lower():
        interest["beneficialOwnershipOrControl"] = True

    # Dates
    start = normalise_date(proxy.first("startDate", quiet=True))
    if start:
        interest["startDate"] = start
    end = normalise_date(proxy.first("endDate", quiet=True))
    if end:
        interest["endDate"] = end

    record_details: dict[str, Any] = {
        "subject": {"describedByEntityStatement": asset_bods_id},
        "interestedParty": interested_party,
        "interests": [interest],
        "isComponent": False,
        "componentStatementIDs": [],
    }

    statement_date = proxy.first("modifiedAt", quiet=True) or config.publication_date

    return ooc_statement(statement_id, record_details, pub_details, statement_date)
