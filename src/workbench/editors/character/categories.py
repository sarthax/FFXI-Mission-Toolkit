"""Character Editor category/tab organization.

Tabs are logical administration groups.  Each tab declares the capabilities it owns so the UI
can remain stable while DSP/Topaz/LSB adapters map those capabilities to different physical
schemas.  Unknown detected character tables are surfaced under Advanced instead of disappearing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CharacterTab:
    key: str
    label: str
    capabilities: tuple[str, ...]
    description: str
    always_visible: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


TAB_DEFINITIONS = (
    CharacterTab(
        "character",
        "Character",
        ("identity", "stats"),
        "Core identity, position, nation, GM/admin state and other scalar character fields.",
        True,
    ),
    CharacterTab(
        "inventory",
        "Inventory",
        ("inventory", "equipment", "storage", "delivery"),
        "All bags and storage containers, equipment state and delivery-related character items.",
        True,
    ),
    CharacterTab(
        "profile",
        "Profile",
        ("profile", "appearance", "style"),
        "Rank/fame/profile values plus appearance and style state.",
        True,
    ),
    CharacterTab(
        "jobs-skills",
        "Jobs & Skills",
        ("jobs", "experience", "skills"),
        "Job levels, job EXP and combat/craft/magic skill values.",
    ),
    CharacterTab(
        "currencies",
        "Currencies",
        ("points", "currencies"),
        "Gil-like progression point stores, conquest currencies and other server point tables.",
        True,
    ),
    CharacterTab(
        "missions-quests",
        "Mission Flags",
        ("missions", "assaults", "campaign", "eminence", "quests"),
        "Mission, quest and related story/progression flags, including packed representations.",
        True,
    ),
    CharacterTab(
        "key-items",
        "Key Items",
        ("key_items",),
        "Owned key-item bitsets/records with lineage-specific decoding.",
        True,
    ),
    CharacterTab(
        "spells-abilities",
        "Spells & Abilities",
        ("spells", "blue_spells", "abilities", "weaponskills", "unlocked_weapons"),
        "Learned spells, blue-magic sets, abilities, weaponskills and weapon unlock state.",
    ),
    CharacterTab(
        "merits-jobpoints",
        "Merits & Job Points",
        ("merits", "job_points"),
        "Merit and job-point progression.",
    ),
    CharacterTab(
        "unlocks-travel",
        "Unlocks & Travel",
        ("unlocks", "teleports", "visited_zones", "titles"),
        "Teleport/home-point/waypoint unlocks, visited zones and titles.",
    ),
    CharacterTab(
        "variables",
        "Variables",
        ("variables",),
        "Character variables (charvars) and script-owned persistent state.",
    ),
    CharacterTab(
        "pets-effects",
        "Pets & Effects",
        ("pets", "effects"),
        "Persisted pet and status-effect state where the connected server exposes it.",
    ),
    CharacterTab(
        "advanced",
        "Advanced",
        ("blacklist", "character_other"),
        "Lineage-specific, custom-fork, or otherwise uncategorized character-owned fields.",
    ),
)


def build_tab_manifest(schema, capability_inventory: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    inventory = capability_inventory or {}
    supported = set(inventory.get("supported", ()))
    # Include any raw discovered capabilities even when they were not normalized by inventory.py.
    supported.update((getattr(schema, "capabilities", {}) or {}).keys())

    out = []
    claimed: set[str] = set()
    for tab in TAB_DEFINITIONS:
        present = sorted(cap for cap in tab.capabilities if cap in supported)
        claimed.update(tab.capabilities)
        row = tab.as_dict()
        row["supported_capabilities"] = present
        row["available"] = bool(present) or tab.always_visible
        out.append(row)

    extra = sorted(cap for cap in supported if cap not in claimed and cap != "other")
    for row in out:
        if row["key"] == "advanced":
            row["supported_capabilities"] = sorted(set(row["supported_capabilities"]) | set(extra))
            row["available"] = bool(row["supported_capabilities"])
            break
    return out
