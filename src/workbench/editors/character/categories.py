"""Character Editor category/tab organization.

The first six tabs are the primary administration workflow requested for day-to-day character
editing.  Secondary tabs cover distinct character-state domains that do not fit cleanly inside
those six. Unknown/custom-fork tables remain visible under Advanced instead of disappearing.
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
    primary: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


TAB_DEFINITIONS = (
    # Primary editing workflow. Keep this order stable for the GUI.
    CharacterTab(
        "character", "Character", ("identity", "stats"),
        "Core identity, location, nation, job/runtime stats, GM/admin state and other scalar character fields.",
        True, True,
    ),
    CharacterTab(
        "inventory", "Inventory", ("inventory", "equipment", "storage", "delivery"),
        "All carried and Mog House storage: Inventory, Mog Safe/Safe 2, Storage, Mog Locker, Satchel, Sack, Case and Mog Wardrobes 1-8.",
        True, True,
    ),
    CharacterTab(
        "equipment", "Equipped Items", ("equipment",),
        "Currently equipped gear per slot with its per-character augments (core char_inventory.extra layout).",
        True, True,
    ),
    CharacterTab(
        "profile", "Profile", ("profile", "appearance", "style"),
        "Rank, fame, profile values, character appearance and lockstyle state.",
        True, True,
    ),
    CharacterTab(
        "currencies", "Currencies", ("points", "currencies"),
        "Conquest points, seals, guild points, assault points, sparks, accolades and other character point/currency stores.",
        True, True,
    ),
    CharacterTab(
        "missions-quests", "Mission Flags", ("missions", "assaults", "campaign", "eminence", "quests"),
        "Mission, quest, Assault, Campaign and Records of Eminence progression flags, including packed representations.",
        True, True,
    ),
    CharacterTab(
        "key-items", "Key Items", ("key_items",),
        "Owned key-item state with lineage-aware decoding when a verified codec is available.",
        True, True,
    ),

    # Additional groups justified by distinct character-owned data domains.
    CharacterTab(
        "jobs-skills", "Jobs & Skills", ("jobs", "experience", "skills"),
        "Job unlocks/levels, job EXP and combat, craft and magic skill values.",
    ),
    CharacterTab(
        "spells-abilities", "Spells & Abilities", ("spells", "blue_spells", "abilities", "weaponskills", "unlocked_weapons"),
        "Learned spells, blue-magic sets, abilities, weaponskills and weapon unlock state.",
    ),
    CharacterTab(
        "merits-jobpoints", "Merits & Job Points", ("merits", "job_points"),
        "Merit upgrades plus capacity-point and job-point progression.",
    ),
    CharacterTab(
        "unlocks-travel", "Unlocks & Travel", ("unlocks", "teleports", "visited_zones", "titles"),
        "Outposts, runic portals, home points, survival guides, waypoints, visited zones and titles.",
    ),
    CharacterTab(
        "variables", "Variables", ("variables",),
        "Character variables (charvars) and script-owned persistent state.",
    ),
    CharacterTab(
        "pets-effects", "Pets & Effects", ("pets", "effects"),
        "Persisted pet/automaton state and status-effect records where the connected server exposes them.",
    ),
    CharacterTab(
        "advanced", "Advanced", ("blacklist", "history", "runtime_flags", "recasts", "character_other"),
        "Runtime/admin/history data and lineage-specific or custom-fork character tables that do not warrant a primary editing tab.",
    ),
)


def get_tab(key: str) -> CharacterTab:
    for tab in TAB_DEFINITIONS:
        if tab.key == key:
            return tab
    raise KeyError(f"Unknown Character Editor tab: {key}")


def build_tab_manifest(schema, capability_inventory: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    inventory = capability_inventory or {}
    supported = set(inventory.get("supported", ()))
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
