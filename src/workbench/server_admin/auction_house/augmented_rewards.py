"""Lineage-aware augmented reward planning (no guessed game binary payloads).

The server's delivery_box.extra is an encoded item-instance payload, not
a generic list of stats. Never silently omit requested augment properties.
"""
from __future__ import annotations
from typing import Any

from .legacy_test_executor import LegacyTestExecutionBlocked


def inspect_augmented_reward(*, family: str, item_id: int,
                             augments: list[dict[str, Any]],
                             server_root=None) -> dict[str, Any]:
    """Preview validated custom item-instance augments without delivering them.

    Shares the character editor's verified 24-byte inventory-extra codec. The
    Mog delivery-box handoff still needs independently verified persistence.
    """
    from workbench.editors.character.equipment_augments import (
        augment_catalog, decode_augments, encode_augments,
    )

    if int(item_id) <= 0:
        raise LegacyTestExecutionBlocked("An augmented item requires a positive item ID")
    if str(family).lower() not in {"dsp", "topaz", "lsb"}:
        raise LegacyTestExecutionBlocked("Unknown game-server lineage")
    if not server_root:
        raise LegacyTestExecutionBlocked("An active server source root is required for augment verification")
    if not isinstance(augments, list) or not (1 <= len(augments) <= 4):
        raise LegacyTestExecutionBlocked("Choose one to four augment slots")
    catalog = augment_catalog(server_root)
    known = {int(row["id"]): row for row in catalog.get("rows", [])}
    if not known:
        raise LegacyTestExecutionBlocked("Server augment catalog is unavailable or empty")
    pairs: list[tuple[int, int]] = []
    details = []
    for entry in augments:
        if not isinstance(entry, dict):
            raise LegacyTestExecutionBlocked("Each augment must be an ID/value object")
        try:
            aid = int(entry["id"])
            value = int(entry["value"])
        except (KeyError, ValueError, TypeError) as exc:
            raise LegacyTestExecutionBlocked("Each augment needs numeric ID and value") from exc
        if aid <= 0 or aid > 2047 or not 0 <= value <= 31 or aid not in known:
            raise LegacyTestExecutionBlocked(
                "Invalid augment ID/value, or ID not defined in this server's augments.sql"
            )
        pairs.append((aid, value))
        details.append({"id": aid, "value": value, "effects": known[aid]["effects"]})
    extra = encode_augments(bytes(24), pairs)
    decoded = decode_augments(extra)
    if [(r["id"], r["value"]) for r in decoded[:len(pairs)]] != pairs:
        raise LegacyTestExecutionBlocked("Augment payload did not round-trip")
    return {
        "status": "preview_only_delivery_unverified",
        "item_id": int(item_id), "family": str(family).lower(),
        "requested_augments": details,
        "encoded_inventory_extra_hex": extra.hex(),
        "encoded_bytes": len(extra),
        "delivery_enabled": False,
        "serializer_verified": True,
        "blocking_reason": (
            "Inventory item-extra encoding is available, but this server's "
            "Mog delivery_box extra-to-inventory transfer needs runtime verification."
        ),
        "note": "No unaugmented item will be substituted. Custom effects not defined in augments.sql require server support.",
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
