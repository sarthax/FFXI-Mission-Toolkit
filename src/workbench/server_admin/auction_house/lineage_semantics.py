"""Evidence-backed Auction House mutation semantics by server lineage.

Schema compatibility is deliberately not treated as proof that two server families execute
Auction House mutations the same way. These contracts are a fail-closed gate for future write
execution; they do not contain executable SQL and do not mutate server state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SourceEvidence:
    repository: str
    ref: str
    path: str
    proves: str


@dataclass(frozen=True)
class LineageSemantics:
    family: str
    verification: str
    schema_shape: str
    listing_steps: tuple[str, ...]
    purchase_steps: tuple[str, ...]
    seller_settlement: str
    required_tables: tuple[str, ...]
    required_triggers: tuple[str, ...]
    source_evidence: tuple[SourceEvidence, ...]
    writes_allowed_by_semantics: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["source_evidence"] = [asdict(item) for item in self.source_evidence]
        return out


_LSB = LineageSemantics(
    family="lsb",
    verification="verified",
    schema_shape="lsb-compatible",
    listing_steps=(
        "validate auctionable item and listing request",
        "remove the listed item/stack from player inventory",
        "charge the Auction House listing fee",
        "insert the auction_house listing",
        "preserve auction_house_list trigger behavior",
    ),
    purchase_steps=(
        "begin one database transaction",
        "atomically claim one eligible active listing",
        "charge the buyer",
        "grant the purchased item/stack to the buyer",
        "preserve auction_house_buy and delivery_box_insert trigger behavior",
        "commit the database transaction",
    ),
    seller_settlement=(
        "Seller proceeds are delivered through the verified Auction House/delivery-box trigger "
        "path; they must not be modeled as a direct chars.gil edit."
    ),
    required_tables=("auction_house", "item_basic", "chars", "delivery_box"),
    required_triggers=("auction_house_list", "auction_house_buy", "delivery_box_insert"),
    source_evidence=(
        SourceEvidence(
            repository="LandSandBoat/server",
            ref="d9e305b8065eaae2cab9237852fa1cd3c73adb34",
            path="src/map/utils/auctionutils.cpp",
            proves="listing and purchase transaction ordering, buyer charge, and item transfer semantics",
        ),
        SourceEvidence(
            repository="LandSandBoat/server",
            ref="d9e305b8065eaae2cab9237852fa1cd3c73adb34",
            path="sql/triggers.sql",
            proves="auction_house_list, auction_house_buy, and delivery_box_insert trigger semantics",
        ),
    ),
    writes_allowed_by_semantics=True,
    reason="Current LandSandBoat listing, purchase, and seller-settlement behavior is source-verified.",
)

_LEGACY_LISTING_STEPS = (
    "validate auctionable inventory item and listing request in the map-server handler",
    "calculate and validate the Auction House listing fee",
    "check the player's active-listing limit",
    "insert item, stack, seller, timestamp, and price into auction_house",
    "remove the listed quantity from player inventory",
    "deduct the Auction House listing fee from player gil",
)

_LEGACY_PURCHASE_STEPS = (
    "select the cheapest qualifying active auction_house listing",
    "update the claimed listing with buyer, sale price, and sale timestamp",
    "add the purchased item/stack to buyer inventory",
    "debit buyer gil",
    "preserve auction_house_buy and delivery_box_insert seller-settlement triggers",
)

_LEGACY_SETTLEMENT = (
    "Seller proceeds are delivered by auction_house_buy into delivery_box, with delivery_box_insert "
    "assigning the slot; do not model settlement as a direct chars.gil edit."
)

_TOPAZ = LineageSemantics(
    family="topaz",
    verification="source_verified_preview_only",
    schema_shape="legacy-dsp-topaz-compatible",
    listing_steps=_LEGACY_LISTING_STEPS,
    purchase_steps=_LEGACY_PURCHASE_STEPS,
    seller_settlement=_LEGACY_SETTLEMENT,
    required_tables=("auction_house", "item_basic", "chars", "delivery_box"),
    required_triggers=("auction_house_buy", "delivery_box_insert"),
    source_evidence=(
        SourceEvidence(
            repository="project-topaz/topaz",
            ref="release",
            path="src/map/packet_system.cpp",
            proves="application-managed listing and purchase flow, inventory transfer, and buyer/listing gil handling",
        ),
        SourceEvidence(
            repository="project-topaz/topaz",
            ref="release",
            path="sql/triggers.sql",
            proves="auction_house_buy seller proceeds and delivery_box_insert slot assignment",
        ),
    ),
    writes_allowed_by_semantics=False,
    reason=(
        "Topaz mutation behavior is source-verified, but the toolkit does not yet have a lineage-specific "
        "transaction/execution contract covering concurrency, rollback, stale-preview protection, and audit."
    ),
)

_DSP = LineageSemantics(
    family="dsp",
    verification="source_verified_preview_only",
    schema_shape="legacy-dsp-topaz-compatible",
    listing_steps=_LEGACY_LISTING_STEPS,
    purchase_steps=_LEGACY_PURCHASE_STEPS,
    seller_settlement=_LEGACY_SETTLEMENT,
    required_tables=("auction_house", "item_basic", "chars", "delivery_box"),
    required_triggers=("auction_house_buy", "delivery_box_insert"),
    source_evidence=(
        SourceEvidence(
            repository="DarkstarProject/darkstar",
            ref="master",
            path="src/map/packet_system.cpp",
            proves="application-managed listing and purchase flow, inventory transfer, and buyer/listing gil handling",
        ),
        SourceEvidence(
            repository="DarkstarProject/darkstar",
            ref="master",
            path="sql/triggers.sql",
            proves="auction_house_buy seller proceeds and delivery_box_insert slot assignment",
        ),
    ),
    writes_allowed_by_semantics=False,
    reason=(
        "DSP mutation behavior is source-verified, but the toolkit does not yet have a lineage-specific "
        "transaction/execution contract covering concurrency, rollback, stale-preview protection, and audit."
    ),
)

_UNKNOWN = LineageSemantics(
    family="unknown",
    verification="unverified",
    schema_shape="unknown",
    listing_steps=(),
    purchase_steps=(),
    seller_settlement="Unverified.",
    required_tables=(),
    required_triggers=(),
    source_evidence=(),
    writes_allowed_by_semantics=False,
    reason="A concrete, source-verified server lineage is required before Auction House writes can be enabled.",
)

_CONTRACTS = {"lsb": _LSB, "topaz": _TOPAZ, "dsp": _DSP}


def semantics_for_family(family: str | None) -> LineageSemantics:
    return _CONTRACTS.get(str(family or "").strip().lower(), _UNKNOWN)


def evaluate_lineage_semantics(*, profile_family: str | None, schema_family_hint: str | None) -> dict[str, Any]:
    """Evaluate whether a named server lineage and live schema shape agree strongly enough for writes.

    ``auto``/legacy/unknown profiles fail closed. The shared DSP/Topaz legacy schema can never
    identify which lineage is running, and an LSB-shaped schema alone is likewise insufficient.
    """
    family = str(profile_family or "").strip().lower()
    shape = str(schema_family_hint or "").strip().lower()
    contract = semantics_for_family(family)
    issues: list[dict[str, Any]] = []

    if family not in _CONTRACTS:
        issues.append({
            "code": "lineage_not_explicit",
            "message": "The active server profile must explicitly identify lsb, topaz, or dsp; schema shape alone cannot authorize writes.",
            "blocking": True,
        })
    elif shape != contract.schema_shape:
        issues.append({
            "code": "lineage_schema_mismatch",
            "message": f"Profile family {family} expects {contract.schema_shape}, but the live schema was detected as {shape or 'unknown'}.",
            "blocking": True,
        })

    if not contract.writes_allowed_by_semantics:
        issues.append({
            "code": "lineage_execution_contract_incomplete" if contract.verification == "source_verified_preview_only" else "lineage_semantics_unverified",
            "message": contract.reason,
            "blocking": True,
        })

    verified = contract.verification == "verified" and not issues
    return {
        "profile_family": family or "unknown",
        "schema_family_hint": shape or "unknown",
        "contract": contract.as_dict(),
        "issues": issues,
        "source_semantics_verified": contract.verification in {"verified", "source_verified_preview_only"},
        "semantics_verified": verified,
        "writes_allowed_by_semantics": verified and contract.writes_allowed_by_semantics,
    }
