"""Reference inventories for supported FFXI server lineages.

These are not used as blind write schemas.  They are evidence-backed expectations used to
compare a live database against a known DSP, Topaz, or LSB generation.  Runtime DESCRIBE data
always wins when deciding what actually exists on the connected server.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LineageReference:
    family: str
    source_repository: str
    source_ref: str
    character_tables: tuple[str, ...]
    packed_owner: str = "chars"
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# DarkstarProject/darkstar master SQL directory, archived canonical DSP lineage.
DSP = LineageReference(
    family="dsp",
    source_repository="DarkstarProject/darkstar",
    source_ref="master",
    character_tables=(
        "chars", "char_blacklist", "char_effects", "char_equip", "char_exp",
        "char_inventory", "char_jobs", "char_look", "char_merit", "char_pet",
        "char_points", "char_profile", "char_recast", "char_skills", "char_spells",
        "char_stats", "char_storage", "char_style", "char_unlocks", "char_vars",
        "delivery_box",
    ),
    notes="Observed from the archived DSP SQL tree; custom DSP forks may differ.",
)

# Project Topaz dbtool protected-player list on the referenced release lineage.
TOPAZ = LineageReference(
    family="topaz",
    source_repository="kosmika/project-topaz",
    source_ref="release",
    character_tables=(
        "chars", "char_blacklist", "char_effects", "char_equip", "char_exp",
        "char_inventory", "char_jobs", "char_look", "char_merit", "char_pet",
        "char_points", "char_profile", "char_skills", "char_spells", "char_stats",
        "char_storage", "char_style", "char_unlocks", "char_vars", "delivery_box",
    ),
    notes="Derived from the Topaz dbtool protected-player list; fork-specific migrations may add fields/tables.",
)

# Current LandSandBoat dbtool protected-player list.  A few protected tables are character-adjacent
# rather than edited directly, but keeping them in the inventory lets the admin UI show full state
# ownership and backup implications.
LSB = LineageReference(
    family="lsb",
    source_repository="LandSandBoat/server",
    source_ref="base",
    character_tables=(
        "chars", "char_blacklist", "char_chocobos", "char_effects", "char_equip",
        "char_equip_saved", "char_exp", "char_fishing_contest_history", "char_flags",
        "char_history", "char_inventory", "char_jobs", "char_job_points", "char_look",
        "char_merit", "char_monstrosity", "char_pet", "char_points", "char_profile",
        "char_skills", "char_spells", "char_stats", "char_storage", "char_style",
        "char_unlocks", "char_vars", "delivery_box",
    ),
    notes="Current LSB protected-player SQL inventory from tools/dbtool.py on base.",
)

REFERENCES = {ref.family: ref for ref in (DSP, TOPAZ, LSB)}


def get_reference(family: str) -> LineageReference | None:
    return REFERENCES.get(str(family or "").lower())


def compare_schema(schema, family: str) -> dict[str, Any]:
    """Compare runtime character tables to the selected lineage reference."""
    ref = get_reference(family)
    present = set(getattr(schema, "tables", {}) or {})
    if ref is None:
        return {
            "family": family or "unknown",
            "reference_available": False,
            "present": sorted(present),
            "expected": [],
            "missing_expected": [],
            "extra_present": sorted(present),
        }

    expected = set(ref.character_tables)
    return {
        "family": ref.family,
        "reference_available": True,
        "source_repository": ref.source_repository,
        "source_ref": ref.source_ref,
        "present": sorted(present),
        "expected": sorted(expected),
        "missing_expected": sorted(expected - present),
        "extra_present": sorted(present - expected),
        "packed_owner": ref.packed_owner,
        "notes": ref.notes,
    }
