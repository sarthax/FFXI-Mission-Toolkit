"""Normalized Character Editor capability inventory.

The UI consumes this report; server adapters/decoders own the physical representation.
Unknowns remain explicit and read-only until verified.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

CAPABILITY_ORDER = (
    "identity", "profile", "jobs", "experience", "skills", "inventory", "equipment",
    "storage", "spells", "merits", "job_points", "points", "currencies", "unlocks",
    "teleports", "variables", "missions", "assaults", "campaign", "eminence", "quests",
    "key_items", "blue_spells", "titles", "visited_zones", "abilities", "weaponskills",
    "unlocked_weapons", "appearance", "style", "pets", "effects", "stats", "blacklist",
    "delivery",
)


@dataclass(frozen=True)
class CapabilityInventory:
    capability: str
    supported: bool
    storage: tuple[str, ...]
    representation: str
    codec_status: str
    write_status: str
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _packed_storage(schema, capability: str) -> list[str]:
    packed = getattr(schema, "packed_fields", None)
    if packed is None:
        packed = getattr(schema, "packed_profile_fields", {}) or {}
    location = packed.get(capability)
    if not location:
        return []
    table = str(location).split(".", 1)[0]
    return [table]


def _representation(schema, capability: str, tables: list[str]) -> str:
    packed = getattr(schema, "packed_fields", None)
    if packed is None:
        packed = getattr(schema, "packed_profile_fields", {}) or {}
    if capability in packed:
        return "packed_blob"
    if not tables:
        return "unknown"
    binary = []
    for name in tables:
        table = schema.table(name) if hasattr(schema, "table") else None
        if table:
            binary.extend(table.binary_columns)
    if binary:
        return "row_table_with_binary_fields"
    if len(tables) > 1:
        return "multi_table_rows"
    return "row_table"


def build_inventory(schema, adapter_family: str = "unknown") -> list[CapabilityInventory]:
    caps = getattr(schema, "capabilities", {}) or {}
    out: list[CapabilityInventory] = []

    logical_to_physical = {
        "experience": caps.get("jobs", []),
        "equipment": caps.get("inventory", []),
        "storage": caps.get("inventory", []),
        "currencies": caps.get("points", []),
        "teleports": caps.get("unlocks", []),
    }

    packed_caps = {
        "missions", "assaults", "campaign", "eminence", "quests", "key_items", "blue_spells",
        "titles", "visited_zones", "abilities", "weaponskills", "unlocked_weapons",
    }

    for capability in CAPABILITY_ORDER:
        if capability in packed_caps:
            tables = _packed_storage(schema, capability)
        else:
            tables = list(logical_to_physical.get(capability, caps.get(capability, [])))
        supported = bool(tables)
        rep = _representation(schema, capability, tables)

        # Foundation is intentionally read-only. A capability becomes writable only when its
        # lineage-specific encoder and transactional validation are explicitly registered.
        codec_status = "pending"
        write_status = "blocked_unverified"
        notes = ""
        if not supported:
            codec_status = "not_detected"
            write_status = "unsupported"
        elif rep == "row_table":
            codec_status = "scalar_or_row_review"
        elif "blob" in rep or "binary" in rep:
            codec_status = "decoder_required"
            location = (getattr(schema, "packed_fields", {}) or {}).get(capability)
            notes = "Binary/packed representation must be decoded and round-trip verified before writes."
            if location:
                notes += f" Physical field: {location}."

        if adapter_family == "unknown" and supported:
            notes = (notes + " " if notes else "") + "Server lineage is not confidently identified."

        out.append(CapabilityInventory(
            capability=capability,
            supported=supported,
            storage=tuple(tables),
            representation=rep,
            codec_status=codec_status,
            write_status=write_status,
            notes=notes,
        ))
    return out


def inventory_summary(schema, adapter_family: str = "unknown") -> dict[str, Any]:
    rows = build_inventory(schema, adapter_family)
    return {
        "adapter": adapter_family,
        "supported": [row.capability for row in rows if row.supported],
        "blocked_writes": [row.capability for row in rows if row.supported and row.write_status != "writable"],
        "capabilities": [row.as_dict() for row in rows],
    }
