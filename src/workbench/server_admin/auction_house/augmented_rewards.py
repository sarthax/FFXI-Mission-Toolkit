"""Lineage-aware augmented reward planning (no guessed game binary payloads).

The server's delivery_box.extra is an encoded item-instance payload, not
a generic list of stats. Never silently omit requested augment properties.
"""
from __future__ import annotations
from typing import Any

from .legacy_test_executor import LegacyTestExecutionBlocked


def inspect_augmented_reward(*, family: str, item_id: int,
                             augments: list[dict[str, Any]],
                             serializer_verified: bool = False) -> dict[str, Any]:
    if int(item_id) <= 0 or not augments:
        raise LegacyTestExecutionBlocked("An augmented item requires a valid item ID and nonempty augment plan")
    if str(family).lower() not in {"dsp", "topaz", "lsb"}:
        raise LegacyTestExecutionBlocked("Unknown game-server lineage")
    if len(augments) > 16:
        raise LegacyTestExecutionBlocked("Augment plan exceeds review limit")
    for augment in augments:
        if not isinstance(augment, dict) or not augment.get("stat") or not isinstance(augment.get("value"), int):
            raise LegacyTestExecutionBlocked("Every augment needs a named stat and integer value")
    return {
        "status": "blocked_unverified_serializer",
        "item_id": int(item_id),
        "family": str(family).lower(),
        "requested_augments": augments,
        "delivery_enabled": False,
        "serializer_verified": bool(serializer_verified),
        "blocking_reason": (
            "The game lineage's item extra serializer and delivery-box take semantics "
            "must be verified before writing any augmented item instance."
        ),
        "note": "No ordinary unaugmented item will be substituted for this request.",
    }


def reject_unverified_augmented_bundle(items: list[dict[str, Any]]) -> None:
    """Fail closed before normalization discards custom fields."""
    for item in items:
        if not isinstance(item, dict):
            raise LegacyTestExecutionBlocked("Invalid reward item")
        if any(field in item for field in ("augments", "extra", "custom_stats", "augment_template")):
            raise LegacyTestExecutionBlocked(
                "Augmented reward delivery is not yet verified for this server; "
                "refusing to substitute a plain item."
            )
