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
    "teleports", "variables", "missions", "quests", "key_items", "titles",
    "visited_zones", "abilities", "weaponskills", "appearance", "style", "pets",
    "effects", "stats", "blacklist", "delivery",
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


def _representation(schema, capability: str, tables: list[str]) -> str:
    packed = getattr(schema, "packed_profile_fields", {}) or {}
    if capability in packed:
        return "packed_profile_blob"
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
    packed = getattr(schema, "packed_profile_fields", {}) or {}
    out: list[CapabilityInventory] = []

    logical_to_physical = {
        "experience": caps.get("jobs", []),
        "equipment": caps.get("inventory", []),
        "storage": caps.get("inventory", []),
        "job_points": caps.get("points", []),
        "currencies": caps.get("points", []),
        "teleports": caps.get("unlocks", []),
        "missions": ["char_profile"] if "missions" in packed else [],
        "quests": ["char_profile"] if "quests" in packed else [],
        "key_items": ["char_profile"] if "key_items" in packed else [],
        "titles": ["char_profile"] if "titles" in packed else [],
        "visited_zones": ["char_profile"] if "visited_zones" in packed else [],
        "abilities": ["char_profile"] if "abilities" in packed else [],
        "weaponskills": ["char_profile"] if "weaponskills" in packed else [],
    }

    for capability in CAPABILITY_ORDER:
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
            notes = "Binary/packed representation must be decoded and round-trip verified before writes."

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
