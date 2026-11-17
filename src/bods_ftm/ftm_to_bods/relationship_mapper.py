from __future__ import annotations

from typing import Any

from followthemoney.proxy import EntityProxy

from bods_ftm.config import PublisherConfig
from bods_ftm.utils.dates import normalise_date
from bods_ftm.utils.ids import ftm_id_to_bods_statement_id, make_ftm_relationship_id
from bods_ftm.utils.statements import publication_details, relationship_statement

# Maps FTM schema name → default BODS interest type
FTM_SCHEMA_TO_INTEREST_TYPE: dict[str, str] = {
    "Ownership": "shareholding",
    "Directorship": "boardMember",
    "UnknownLink": "unknownInterest",
    "Membership": "otherInfluenceOrControl",
    "Employment": "seniorManagingOfficial",
    "Representation": "otherInfluenceOrControl",
    "Control": "otherInfluenceOrControl",
}

# Each edge schema's (interested party, subject) properties.
_EDGE_PROPS: dict[str, tuple[str, str]] = {
    "Ownership": ("owner", "asset"),
    "Directorship": ("director", "organization"),
    "Control": ("controller", "controlled"),
    "UnknownLink": ("subject", "object"),
    "Membership": ("member", "organization"),
    "Employment": ("employee", "employer"),
    "Representation": ("agent", "client"),
}

# BODS v0.4 interestType codelist. A ``role`` that is already one of these
# (as bods-ftm writes it) is taken as the interest type.
BODS_INTEREST_TYPES: frozenset[str] = frozenset({
    "shareholding", "votingRights", "appointmentOfBoard",
    "otherInfluenceOrControl", "seniorManagingOfficial", "settlor", "trustee",
    "protector", "beneficiaryOfLegalArrangement",
    "rightsToSurplusAssetsOnDissolution", "rightsToProfitOrIncome",
    "rightsGrantedByContract", "conditionalRightsGrantedByContract",
    "controlViaCompanyRulesOrArticles", "controlByLegalFramework",
    "boardMember", "boardChair", "unknownInterest", "unpublishedInterest",
    "enjoymentAndUseOfAssets", "rightToProfitOrIncomeFromAssets", "nominee",
    "nominator",
})
_BODS_INTEREST_TYPES_FOLDED = {t.lower(): t for t in BODS_INTEREST_TYPES}

# ``Control.controlType`` -> BODS interest type, used when ``role`` does not
# name one. ``trust`` is not mapped: it does not say which trust role
# (settlor, trustee, protector or beneficiary), so it stays
# otherInfluenceOrControl. ``indirect`` sets directOrIndirect instead.
_CONTROL_TYPE_TO_INTEREST_TYPE: dict[str, str] = {
    "voting": "votingRights",
    "appointment": "appointmentOfBoard",
    "contractual": "rightsGrantedByContract",
    "nominee": "nominee",
    "state": "controlByLegalFramework",
}

# Refines the default interest type by inspecting the FTM role value
_ROLE_TO_INTEREST_TYPE: dict[str, str] = {
    "shareholding": "shareholding",
    "voting rights": "votingRights",
    "votingrights": "votingRights",
    "beneficial ownership or control": "shareholding",
    "beneficiary": "beneficiaryOfLegalArrangement",
    "settlor": "settlor",
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
    "unknowninterest": "unknownInterest",
    "unknown": "unknownInterest",
}


def ftm_relationship_to_bods(
    proxy: EntityProxy,
    ftm_id_to_record_id: dict[str, str],
    config: PublisherConfig,
) -> dict[str, Any] | None:
    """Convert an FTM edge (Ownership, Control, Directorship, UnknownLink,
    Membership, Employment, Representation) to a BODS v0.4 relationship
    statement.

    ftm_id_to_record_id maps FTM entity IDs to BODS recordIds (the stable
    identity used for inline subject/interestedParty references in canonical
    0.4). Returns None if either side cannot be resolved.
    """
    schema_name = proxy.schema.name
    props = _EDGE_PROPS.get(schema_name)
    if props is None:
        return None
    owner_ids = list(proxy.get(props[0], quiet=True))
    asset_ids = list(proxy.get(props[1], quiet=True))

    if not owner_ids or not asset_ids:
        return None

    owner_record_id = ftm_id_to_record_id.get(owner_ids[0])
    asset_record_id = ftm_id_to_record_id.get(asset_ids[0])
    if not owner_record_id or not asset_record_id:
        return None

    pub_details = publication_details(
        publisher_name=config.publisher_name,
        publisher_uri=config.publisher_uri,
        license_url=config.license_url,
        bods_version=config.bods_version,
    )

    statement_id = ftm_id_to_bods_statement_id(proxy.id)
    record_id = make_ftm_relationship_id(
        "relationship", proxy.id, owner_record_id, asset_record_id
    )

    interest_type = _interest_type(proxy, schema_name)
    interest: dict[str, Any] = {"type": interest_type}

    percentage_str = proxy.first("percentage", quiet=True)
    if percentage_str:
        try:
            pct = float(percentage_str)
            interest["share"] = {"exact": pct}
        except ValueError:
            pass

    status = proxy.first("status", quiet=True)
    if status in ("direct", "indirect", "unknown"):
        interest["directOrIndirect"] = status
    elif schema_name == "Control" and "indirect" in proxy.get(
        "controlType", quiet=True
    ):
        interest["directOrIndirect"] = "indirect"

    if schema_name == "Control":
        details = [
            f"Legal basis: {basis}" for basis in proxy.get("legalBasis", quiet=True)
        ]
        if details:
            interest["details"] = "; ".join(details)

    summary = proxy.first("summary", quiet=True) or ""
    if "beneficial" in summary.lower():
        interest["beneficialOwnershipOrControl"] = True

    start = normalise_date(proxy.first("startDate", quiet=True))
    if start:
        interest["startDate"] = start
    end = normalise_date(proxy.first("endDate", quiet=True))
    if end:
        interest["endDate"] = end

    # Canonical 0.4: subject and interestedParty are strings pointing at
    # recordIds (not nested describedBy* wrappers).
    record_details: dict[str, Any] = {
        "subject": asset_record_id,
        "interestedParty": owner_record_id,
        "interests": [interest],
        "isComponent": False,
    }

    statement_date = proxy.first("modifiedAt", quiet=True) or config.publication_date

    return relationship_statement(
        statement_id, record_id, record_details, pub_details, statement_date
    )


def _interest_type(proxy: EntityProxy, schema_name: str) -> str:
    """The BODS interest type for an FtM edge: its ``role`` when that names a
    BODS type or a known role word, else (for Control) its ``controlType``,
    else the schema's default."""
    default_type = FTM_SCHEMA_TO_INTEREST_TYPE.get(schema_name, "unknownInterest")
    role = (proxy.first("role", quiet=True) or "").strip()
    if role:
        folded = role.lower()
        if folded in _BODS_INTEREST_TYPES_FOLDED:
            return _BODS_INTEREST_TYPES_FOLDED[folded]
        if folded in _ROLE_TO_INTEREST_TYPE:
            return _ROLE_TO_INTEREST_TYPE[folded]
        if folded.replace(" ", "") in _ROLE_TO_INTEREST_TYPE:
            return _ROLE_TO_INTEREST_TYPE[folded.replace(" ", "")]
    if schema_name == "Control":
        for control_type in proxy.get("controlType", quiet=True):
            mapped = _CONTROL_TYPE_TO_INTEREST_TYPE.get(control_type.strip().lower())
            if mapped:
                return mapped
    return default_type
