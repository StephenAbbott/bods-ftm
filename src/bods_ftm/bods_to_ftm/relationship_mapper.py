from __future__ import annotations

from typing import Any

from followthemoney import model
from followthemoney.proxy import EntityProxy

from bods_ftm.utils.dates import normalise_date
from bods_ftm.utils.ids import bods_statement_id_to_ftm_id, make_ftm_relationship_id

# FollowTheMoney schema to use for each BODS interest type.
# Directorship is used for roles that represent control through a position;
# Ownership is used for economic/voting interests; UnknownLink for the rest.
INTEREST_TYPE_TO_FTM_SCHEMA: dict[str, str] = {
    "shareholding": "Ownership",
    "votingRights": "Ownership",
    "appointmentOfBoard": "Directorship",
    "seniorManagingOfficial": "Directorship",
    "boardMember": "Directorship",
    "boardChair": "Directorship",
    "otherInfluenceOrControl": "Ownership",
    "settlor": "Ownership",
    "trustee": "Directorship",
    "protector": "Directorship",
    "beneficiaryOfLegalArrangement": "Ownership",
    "rightsToSurplusAssetsOnDissolution": "Ownership",
    "rightsToProfitOrIncome": "Ownership",
    "rightsGrantedByContract": "Ownership",
    "conditionalRightsGrantedByContract": "Ownership",
    "controlViaCompanyRulesOrArticles": "Ownership",
    "controlByLegalFramework": "Ownership",
    "enjoymentAndUseOfAssets": "Ownership",
    "rightToProfitOrIncomeFromAssets": "Ownership",
    "nominee": "Directorship",
    "nominator": "Directorship",
    "unknownInterest": "UnknownLink",
    "unpublishedInterest": "UnknownLink",
}

# For Ownership: which property holds the owner reference
# For Directorship: which property holds the person reference
_OWNER_PROP = {
    "Ownership": "owner",
    "Directorship": "director",
    "UnknownLink": "subject",
}
_ASSET_PROP = {
    "Ownership": "asset",
    "Directorship": "organization",
    "UnknownLink": "object",
}


def ooc_statement_to_ftm(
    statement: dict[str, Any],
    statement_index: dict[str, dict[str, Any]],
) -> list[EntityProxy]:
    """Convert a BODS v0.4 ownership-or-control statement to FTM edge entities.

    One FTM entity is produced per interest in the interests[] array.  This
    preserves the full BODS interest list rather than collapsing to a single
    relationship.

    statement_index maps statementId → statement dict and is used to look up
    the FTM IDs of subject and interestedParty entities.
    """
    details = statement.get("recordDetails", {})
    proxies: list[EntityProxy] = []

    subject_ref = details.get("subject", {})
    subject_stmt_id = subject_ref.get("describedByEntityStatement") if isinstance(subject_ref, dict) else None
    if not subject_stmt_id:
        return []

    asset_ftm_id = bods_statement_id_to_ftm_id(subject_stmt_id)

    interested_party = details.get("interestedParty", {})
    if not isinstance(interested_party, dict):
        return []

    owner_stmt_id = interested_party.get(
        "describedByPersonStatement"
    ) or interested_party.get("describedByEntityStatement")

    # Unspecified interested party — represent as a placeholder LegalEntity
    unspecified = interested_party.get("unspecified")
    if unspecified and not owner_stmt_id:
        owner_ftm_id = _make_unspecified_entity(unspecified, subject_stmt_id)
    elif owner_stmt_id:
        owner_ftm_id = bods_statement_id_to_ftm_id(owner_stmt_id)
    else:
        return []

    interests = details.get("interests", [])
    if not interests:
        # Create a single UnknownLink if no interests are listed
        interests = [{"type": "unknownInterest"}]

    for idx, interest in enumerate(interests):
        interest_type = interest.get("type", "unknownInterest")
        ftm_schema = INTEREST_TYPE_TO_FTM_SCHEMA.get(interest_type, "Ownership")

        rel_id = make_ftm_relationship_id(
            statement["statementId"], str(idx), interest_type
        )

        proxy: EntityProxy = model.make_entity(ftm_schema)
        proxy.id = rel_id

        owner_prop = _OWNER_PROP[ftm_schema]
        asset_prop = _ASSET_PROP[ftm_schema]

        proxy.add(owner_prop, owner_ftm_id, quiet=True)
        proxy.add(asset_prop, asset_ftm_id, quiet=True)

        # Role / interest type as a human-readable label
        proxy.add("role", interest_type, quiet=True)

        # Share / percentage
        share = interest.get("share", {})
        if isinstance(share, dict):
            exact = share.get("exact")
            if exact is not None:
                proxy.add("percentage", str(exact), quiet=True)
            else:
                minimum = share.get("minimum")
                maximum = share.get("maximum")
                if minimum is not None:
                    proxy.add("percentage", str(minimum), quiet=True)
                elif maximum is not None:
                    proxy.add("percentage", str(maximum), quiet=True)

        # Dates
        start = normalise_date(interest.get("startDate"))
        if start:
            proxy.add("startDate", start, quiet=True)
        end = normalise_date(interest.get("endDate"))
        if end:
            proxy.add("endDate", end, quiet=True)

        # Direct / indirect as a status note
        direct_or_indirect = interest.get("directOrIndirect")
        if direct_or_indirect:
            proxy.add("status", direct_or_indirect, quiet=True)

        # Beneficial ownership flag embedded in summary
        boc = interest.get("beneficialOwnershipOrControl")
        if boc is True:
            proxy.add("summary", "beneficial ownership or control", quiet=True)

        # isComponent flag on the OOC statement
        is_component = details.get("isComponent", False)
        if is_component:
            component_ids = details.get("componentStatementIDs", [])
            if component_ids:
                proxy.add(
                    "description",
                    f"Component of indirect chain. Intermediate statements: {', '.join(component_ids)}",
                    quiet=True,
                )

        # Source provenance
        statement_date = statement.get("statementDate")
        if statement_date:
            proxy.add("modifiedAt", statement_date, quiet=True)

        pub_details = statement.get("publicationDetails", {})
        publisher = pub_details.get("publisher", {})
        pub_uri = publisher.get("uri") if isinstance(publisher, dict) else None
        if pub_uri:
            proxy.add("sourceUrl", pub_uri, quiet=True)

        proxies.append(proxy)

    return proxies


def _make_unspecified_entity(unspecified: dict[str, Any], context_id: str) -> str:
    """Create a placeholder LegalEntity FTM ID for an unspecified interested party."""
    reason = unspecified.get("reason", "unknown")
    return make_ftm_relationship_id("unspecified", reason, context_id)
