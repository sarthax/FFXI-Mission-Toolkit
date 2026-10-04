"""Non-executable Auction House execution contracts for legacy DSP/Topaz lineages.

These contracts describe the transaction and consistency rules a future executor must satisfy.
They intentionally contain no SQL and cannot authorize writes by themselves.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutionContract:
    family: str
    schema_shape: str
    status: str
    listing_sequence: tuple[str, ...]
    purchase_sequence: tuple[str, ...]
    concurrency_guards: tuple[str, ...]
    stale_preview_guards: tuple[str, ...]
    inventory_guards: tuple[str, ...]
    settlement_guards: tuple[str, ...]
    rollback_guards: tuple[str, ...]
    audit_guards: tuple[str, ...]
    required_tables: tuple[str, ...]
    required_triggers: tuple[str, ...]
    remaining_gates: tuple[str, ...]
    executor_permitted: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_LEGACY_LISTING_SEQUENCE = (
    "begin one database transaction",
    "re-read the exact item, seller, inventory row, and current active-listing count",
    "reject if the preview fingerprint or auctionability-relevant state changed",
    "validate the legacy listing limit and calculate the lineage-correct listing fee",
    "insert one active auction_house row using the verified legacy column semantics",
    "remove exactly the listed single item or full stack from player inventory",
    "debit exactly the verified listing fee from seller gil",
    "re-read affected rows and verify the expected post-state",
    "commit only after every invariant passes",
    "append the immutable administrative audit record after commit",
)

_LEGACY_PURCHASE_SEQUENCE = (
    "begin one database transaction",
    "re-read the exact previewed auction and reject sold, cancelled, changed, or missing rows",
    "for normal purchase, re-evaluate the cheapest qualifying active row before claiming",
    "atomically claim one qualifying listing so concurrent buyers cannot purchase the same auction",
    "write buyer, sale price, and sale timestamp using the verified legacy row semantics",
    "grant the correct single item or full stack to the buyer when a buyer is present",
    "debit buyer gil exactly once for a normal purchase",
    "allow auction_house_buy and delivery_box_insert to create seller settlement",
    "re-read auction, buyer, and seller-delivery state and verify the expected post-state",
    "commit only after every invariant passes",
    "append the immutable administrative audit record after commit",
)

_CONCURRENCY_GUARDS = (
    "purchase must claim at most one active row",
    "the same auction_id must not be successfully claimed twice",
    "normal purchase must preserve cheapest-qualifying-row behavior under concurrency",
    "listing-limit checks must be repeated inside the transaction",
)

_STALE_PREVIEW_GUARDS = (
    "re-read every mutation-relevant row inside the transaction",
    "compare the current state to the deterministic preview fingerprint",
    "reject rather than auto-refresh when a mutation-relevant value changed",
    "never apply a plan generated for a different server environment or lineage",
)

_INVENTORY_GUARDS = (
    "listing must remove the exact quantity represented by the listing: one item or one full stack",
    "listing must reject insufficient quantity, changed slot ownership, or changed item identity",
    "purchase must grant the exact listed item and stack quantity once",
    "inventory failure must abort the whole transaction",
)

_SETTLEMENT_GUARDS = (
    "seller proceeds must flow through auction_house_buy into delivery_box",
    "delivery_box_insert must assign the delivery slot",
    "the executor must never replace seller settlement with a direct chars.gil edit",
    "settlement verification must confirm exactly one expected seller delivery record",
)

_ROLLBACK_GUARDS = (
    "any failed invariant must roll back auction, inventory, gil, and buyer-state changes together",
    "trigger or delivery-box failure must roll back the owning transaction",
    "post-state verification failure must roll back rather than repair forward",
    "audit failure after commit must be surfaced as a separate integrity alert without replaying the mutation",
)

_AUDIT_GUARDS = (
    "record active environment identity and explicit lineage",
    "record operation, target identifiers, before snapshot, expected after-state, and fingerprint",
    "record administrator confirmation metadata for LIVE environments",
    "record final outcome and rollback/error reason without storing database credentials",
)

_REMAINING_GATES = (
    "implement the lineage-specific transactional adapter without free-form SQL entry",
    "add live-schema integration fixtures for representative DSP and Topaz databases",
    "prove concurrent purchase behavior with two competing buyers",
    "prove stale-preview rejection for listing and purchase",
    "prove rollback across auction, inventory/gil, and delivery-box failure paths",
    "implement append-only audit persistence and verify redaction",
    "complete real-server validation before any executor feature flag can exist",
)


def _legacy_contract(family: str) -> ExecutionContract:
    return ExecutionContract(
        family=family,
        schema_shape="legacy-dsp-topaz-compatible",
        status="specified_non_executable",
        listing_sequence=_LEGACY_LISTING_SEQUENCE,
        purchase_sequence=_LEGACY_PURCHASE_SEQUENCE,
        concurrency_guards=_CONCURRENCY_GUARDS,
        stale_preview_guards=_STALE_PREVIEW_GUARDS,
        inventory_guards=_INVENTORY_GUARDS,
        settlement_guards=_SETTLEMENT_GUARDS,
        rollback_guards=_ROLLBACK_GUARDS,
        audit_guards=_AUDIT_GUARDS,
        required_tables=("auction_house", "item_basic", "chars", "delivery_box"),
        required_triggers=("auction_house_buy", "delivery_box_insert"),
        remaining_gates=_REMAINING_GATES,
        executor_permitted=False,
        reason=(
            f"{family.upper()} source semantics are verified and the required execution contract is now "
            "specified, but no transactional adapter or real-server validation authorizes execution."
        ),
    )


_CONTRACTS = {
    "topaz": _legacy_contract("topaz"),
    "dsp": _legacy_contract("dsp"),
}


def execution_contract_for_family(family: str | None) -> ExecutionContract | None:
    return _CONTRACTS.get(str(family or "").strip().lower())


def evaluate_execution_contract(*, profile_family: str | None, schema_family_hint: str | None) -> dict[str, Any]:
    """Return fail-closed readiness for the legacy execution-contract specification.

    A specified contract is not executable. It only means the required invariants are explicit
    enough to implement and test a future lineage-specific adapter.
    """
    family = str(profile_family or "").strip().lower()
    shape = str(schema_family_hint or "").strip().lower()
    contract = execution_contract_for_family(family)
    issues: list[dict[str, Any]] = []

    if contract is None:
        issues.append({
            "code": "legacy_execution_contract_not_applicable",
            "message": "A DSP or Topaz profile is required for the legacy execution contract.",
            "blocking": True,
        })
    elif shape != contract.schema_shape:
        issues.append({
            "code": "execution_contract_schema_mismatch",
            "message": f"Profile family {family} expects {contract.schema_shape}, but the live schema was detected as {shape or 'unknown'}.",
            "blocking": True,
        })

    if contract is not None:
        issues.append({
            "code": "execution_adapter_not_implemented",
            "message": contract.reason,
            "blocking": True,
        })

    return {
        "profile_family": family or "unknown",
        "schema_family_hint": shape or "unknown",
        "contract": None if contract is None else contract.as_dict(),
        "contract_specified": contract is not None and shape == contract.schema_shape,
        "executor_permitted": False,
        "issues": issues,
    }
