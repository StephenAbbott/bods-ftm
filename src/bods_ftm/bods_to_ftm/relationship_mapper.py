from __future__ import annotations

from typing import Any

from followthemoney import model
from followthemoney.proxy import EntityProxy

from bods_ftm.utils.dates import normalise_date
from bods_ftm.utils.ids import bods_record_id_to_ftm_id, make_ftm_relationship_id

# FollowTheMoney schema to use for each BODS interest type.
#
# FtM 4.11 added a ``Control`` schema (controller -> controlled, with a free
# ``controlType``) for control that is not ownership. The split:
#
# * ``Ownership`` - economic interests, which carry a percentage.
# * ``Control``   - control without ownership: board appointment, rights under
#   the articles or a contract, a legal framework, trust roles, nominees.
#   ``votingRights`` is Control *unless* the interest states a share, in which
#   case it stays Ownership so the percentage survives (Control has no
#   ``percentage`` property) - the way OpenSanctions models voting stakes.
# * ``Directorship`` - positions held: board member, chair, senior managing
#   official.
# * ``UnknownLink`` - unknown or unpublished interests.
INTEREST_TYPE_TO_FTM_SCHEMA: dict[str, str] = {
    "shareholding": "Ownership",
    "votingRights": "Control",  # Ownership when a share is stated
    "appointmentOfBoard": "Control",
    "seniorManagingOfficial": "Directorship",
    "boardMember": "Directorship",
    "boardChair": "Directorship",
    "otherInfluenceOrControl": "Control",
    "settlor": "Control",
    "trustee": "Control",
    "protector": "Control",
    "beneficiaryOfLegalArrangement": "Control",
    "rightsToSurplusAssetsOnDissolution": "Ownership",
    "rightsToProfitOrIncome": "Ownership",
    "rightsGrantedByContract": "Control",
    "conditionalRightsGrantedByContract": "Control",
    "controlViaCompanyRulesOrArticles": "Control",
    "controlByLegalFramework": "Control",
    "enjoymentAndUseOfAssets": "Ownership",
    "rightToProfitOrIncomeFromAssets": "Ownership",
    "nominee": "Control",
    "nominator": "Control",
    "unknownInterest": "UnknownLink",
    "unpublishedInterest": "UnknownLink",
}

# ``Control.controlType`` for each BODS interest type routed to Control. A type
# with no entry gets no controlType rather than a near miss: the BODS interest
# type is always kept in ``role``. ``controlByLegalFramework`` is ``state`` only
# when the interested party is a state or state body (see
# ``_control_type``); otherwise it is left unset - a legal framework is not a
# contract.
INTEREST_TYPE_TO_CONTROL_TYPE: dict[str, str] = {
    "votingRights": "voting",
    "appointmentOfBoard": "appointment",
    "settlor": "trust",
    "trustee": "trust",
    "protector": "trust",
    "beneficiaryOfLegalArrangement": "trust",
    "rightsGrantedByContract": "contractual",
    "conditionalRightsGrantedByContract": "contractual",
    "controlViaCompanyRulesOrArticles": "contractual",
    "nominee": "nominee",
    "nominator": "nominee",
}

_STATE_ENTITY_TYPES = frozenset({"state", "stateBody"})

_OWNER_PROP = {
    "Ownership": "owner",
    "Directorship": "director",
    "Control": "controller",
    "UnknownLink": "subject",
}
_ASSET_PROP = {
    "Ownership": "asset",
    "Directorship": "organization",
    "Control": "controlled",
    "UnknownLink": "object",
}


def ftm_schema_for_interest(interest: dict[str, Any]) -> str:
    """The FtM schema a BODS interest becomes."""
    interest_type = interest.get("type", "unknownInterest")
    schema = INTEREST_TYPE_TO_FTM_SCHEMA.get(interest_type, "Ownership")
    if interest_type == "votingRights" and _share_value(interest) is not None:
        return "Ownership"
    return schema


def _share_value(interest: dict[str, Any]) -> Any:
    share = interest.get("share")
    if not isinstance(share, dict):
        return None
    for key in ("exact", "minimum", "maximum"):
        if share.get(key) is not None:
            return share[key]
    return None


def _share_text(share: dict[str, Any]) -> str | None:
    """A BODS share in words, for schemas with no percentage property."""
    if share.get("exact") is not None:
        return f"Share: {share['exact']}%"
    low = share.get("minimum")
    high = share.get("maximum")
    if low is not None and high is not None:
        return f"Share: {low}-{high}%"
    if low is not None:
        return f"Share: at least {low}%"
    if high is not None:
        return f"Share: up to {high}%"
    return None


def _control_type(
    interest_type: str, interested_party: dict[str, Any] | None
) -> str | None:
    if interest_type == "controlByLegalFramework":
        if interested_party is None:
            return None
        entity_type = interested_party.get("recordDetails", {}).get("entityType")
        type_str = entity_type.get("type") if isinstance(entity_type, dict) else entity_type
        return "state" if type_str in _STATE_ENTITY_TYPES else None
    return INTEREST_TYPE_TO_CONTROL_TYPE.get(interest_type)


def ooc_statement_to_ftm(
    statement: dict[str, Any],
    record_index: dict[str, dict[str, Any]],
) -> list[EntityProxy]:
    """Convert a BODS v0.4 relationship statement to FTM edge entities (and
    a placeholder LegalEntity owner if the interestedParty is an inline
    Unspecified Record).

    record_index maps recordId → statement and is used to verify that
    subject/interestedParty references resolve. The FTM ID for an entity is
    its recordId (passed through unchanged).

    One FTM entity is produced per interest in the interests[] array.
    """
    details = statement.get("recordDetails", {})
    proxies: list[EntityProxy] = []

    subject_ref = details.get("subject")
    if not isinstance(subject_ref, str) or subject_ref not in record_index:
        return []
    asset_ftm_id = bods_record_id_to_ftm_id(subject_ref)

    interested_party = details.get("interestedParty")
    owner_ftm_id: str | None = None
    unspecified_reason: str | None = None
    unspecified_description: str | None = None
    placeholder_owner: EntityProxy | None = None

    if isinstance(interested_party, str):
        if interested_party not in record_index:
            return []
        owner_ftm_id = bods_record_id_to_ftm_id(interested_party)
    elif isinstance(interested_party, dict):
        unspecified_reason = interested_party.get("reason")
        unspecified_description = interested_party.get("description")
        if unspecified_reason:
            placeholder_owner, owner_ftm_id = _make_unspecified_owner(
                unspecified_reason, unspecified_description, subject_ref
            )

    if owner_ftm_id is None:
        return []

    if placeholder_owner is not None:
        proxies.append(placeholder_owner)

    interests = details.get("interests", [])
    if not interests:
        # No declared interests (common when interestedParty is unspecified) —
        # emit a single UnknownLink so the inline reason is preserved.
        interests = [{"type": "unknownInterest"}]

    for idx, interest in enumerate(interests):
        interest_type = interest.get("type", "unknownInterest")
        ftm_schema = ftm_schema_for_interest(interest)

        rel_id = make_ftm_relationship_id(
            statement["statementId"], str(idx), interest_type
        )

        proxy: EntityProxy = model.make_entity(ftm_schema)
        proxy.id = rel_id

        owner_prop = _OWNER_PROP[ftm_schema]
        asset_prop = _ASSET_PROP[ftm_schema]

        proxy.add(owner_prop, owner_ftm_id, quiet=True)
        proxy.add(asset_prop, asset_ftm_id, quiet=True)
        proxy.add("role", interest_type, quiet=True)

        if ftm_schema == "Control":
            control_type = _control_type(
                interest_type,
                record_index.get(interested_party)
                if isinstance(interested_party, str)
                else None,
            )
            if control_type:
                proxy.add("controlType", control_type, quiet=True)

        share = interest.get("share", {})
        if isinstance(share, dict) and ftm_schema != "Ownership":
            share_text = _share_text(share)
            if share_text:
                proxy.add("description", share_text, quiet=True)
        elif isinstance(share, dict):
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

        start = normalise_date(interest.get("startDate"))
        if start:
            proxy.add("startDate", start, quiet=True)
        end = normalise_date(interest.get("endDate"))
        if end:
            proxy.add("endDate", end, quiet=True)

        direct_or_indirect = interest.get("directOrIndirect")
        if direct_or_indirect:
            proxy.add("status", direct_or_indirect, quiet=True)

        if interest.get("beneficialOwnershipOrControl") is True:
            proxy.add("summary", "beneficial ownership or control", quiet=True)

        # Inline-unspecified interestedParty: preserve the reason code and
        # description on the relationship as well as on the placeholder owner.
        # FATF treats declared-unknown UBOs as a material signal — silently
        # dropping the reason understates opacity risk.
        if unspecified_reason:
            description_parts = [
                f"Unspecified interestedParty (reason: {unspecified_reason})"
            ]
            if unspecified_description:
                description_parts.append(unspecified_description)
            proxy.add("description", " — ".join(description_parts), quiet=True)

        is_component = details.get("isComponent", False)
        if is_component:
            component_ids = details.get("componentStatementIDs", [])
            if component_ids:
                proxy.add(
                    "description",
                    f"Component of indirect chain. Intermediate statements: {', '.join(component_ids)}",
                    quiet=True,
                )

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


def _make_unspecified_owner(
    reason: str, description: str | None, subject_record_id: str
) -> tuple[EntityProxy, str]:
    """Emit a placeholder LegalEntity standing in for an unspecified interested
    party. The reason code and any description are preserved so the
    declared-unknown UBO is not silently dropped during conversion."""
    ftm_id = make_ftm_relationship_id("unspecified", reason, subject_record_id)
    proxy = model.make_entity("LegalEntity")
    proxy.id = ftm_id
    proxy.add("name", f"Unspecified beneficial owner ({reason})", quiet=True)
    notes_parts = [f"BODS unspecifiedReason: {reason}"]
    if description:
        notes_parts.append(description)
    proxy.add("notes", " — ".join(notes_parts), quiet=True)
    return proxy, ftm_id
