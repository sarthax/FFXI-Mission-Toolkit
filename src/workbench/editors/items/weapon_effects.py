"""Structured weapon additional-effect helpers for the Item Editor.

This module deliberately stays above the server-core layer.  It describes the existing
item_mods / item_latents rows used by DSP/Topaz/LSB additional-effect handling and gives the
editor a safe way to build or recognize those bundles without pretending that arbitrary new
core behavior can be created from SQL alone.

Known legacy/common modifier ids are supported directly.  Lineage-specific extensions that
require Lua/C++ work remain explicit handoff cases rather than silently generating rows the
server will not understand.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


# Common DSP/Topaz/LSB additional-effect modifier ids.  These ids are consumed by the
# server's melee additional-effect path, not by the client augment parser.
MOD_ADDEFFECT_TYPE = 431
MOD_SUBEFFECT = 499
MOD_ADDEFFECT_DMG = 500
MOD_ADDEFFECT_CHANCE = 501
MOD_ADDEFFECT_ELEMENT = 950
MOD_ADDEFFECT_STATUS = 951
MOD_ADDEFFECT_POWER = 952
MOD_ADDEFFECT_DURATION = 953


ELEMENTS = {
    0: "none",
    1: "fire",
    2: "ice",
    3: "wind",
    4: "earth",
    5: "lightning",
    6: "water",
    7: "light",
    8: "dark",
}

# Battle-message/visual subeffects used by the established additional-effect path.  The editor
# intentionally exposes the numeric value too because private-server lineages can drift.
SUBEFFECTS = {
    1: "fire damage",
    2: "ice damage",
    3: "wind damage",
    4: "earth damage",
    5: "lightning damage",
    6: "water damage",
    7: "light damage",
    8: "dark damage",
    9: "drain",
    10: "aspir",
    11: "paralysis",
}

# LSB's modern additional_effects.lua defines these proc types.  The first several preserve the
# long-lived DSP/Topaz behavior; later types may require lineage/version verification before use.
PROC_TYPES = {
    1: "damage",
    2: "debuff",
    3: "hp heal",
    4: "mp heal",
    5: "hp drain",
    6: "mp drain",
    7: "tp drain",
    8: "hp+mp drain",
    9: "hp+mp+tp drain",
    10: "dispel",
    11: "absorb status",
    12: "self buff",
    13: "death",
    14: "nm specific",
}


@dataclass(frozen=True)
class EffectField:
    key: str
    mod_id: int
    label: str
    required_for: tuple[str, ...] = ()
    notes: str = ""


FIELDS = (
    EffectField("type", MOD_ADDEFFECT_TYPE, "Proc type", notes="Selects the server additional-effect handler."),
    EffectField("subeffect", MOD_SUBEFFECT, "Visual/message subeffect", notes="Client-visible battle subeffect id."),
    EffectField("damage", MOD_ADDEFFECT_DMG, "Base damage / amount", ("damage", "hp heal", "mp heal", "hp drain", "mp drain", "tp drain")),
    EffectField("chance", MOD_ADDEFFECT_CHANCE, "Proc chance (%)", notes="Rolled on a successful eligible attack."),
    EffectField("element", MOD_ADDEFFECT_ELEMENT, "Element", ("damage",), notes="Used for elemental resist/damage calculations."),
    EffectField("status", MOD_ADDEFFECT_STATUS, "Status effect id", ("debuff",), notes="Server status-effect enum id."),
    EffectField("power", MOD_ADDEFFECT_POWER, "Status power", ("debuff",)),
    EffectField("duration", MOD_ADDEFFECT_DURATION, "Status duration (s)", ("debuff",)),
)

FIELD_BY_KEY = {field.key: field for field in FIELDS}
FIELD_BY_MOD = {field.mod_id: field for field in FIELDS}


def catalog() -> dict:
    """Return editor-facing metadata for the structured additional-effect panel."""
    return {
        "fields": [
            {
                "key": f.key,
                "modId": f.mod_id,
                "label": f.label,
                "requiredFor": list(f.required_for),
                "notes": f.notes,
            }
            for f in FIELDS
        ],
        "procTypes": [{"value": value, "label": label} for value, label in sorted(PROC_TYPES.items())],
        "elements": [{"value": value, "label": label} for value, label in sorted(ELEMENTS.items())],
        "subeffects": [{"value": value, "label": label} for value, label in sorted(SUBEFFECTS.items())],
        "storage": "item_mods or item_latents",
        "clientCoupled": False,
        "coreBoundary": (
            "Existing proc types/fields can be configured here. New proc semantics still require "
            "server Lua/C++ support; the editor must not invent a new type and assume it works."
        ),
    }


def build_mod_rows(*, proc_type: int, chance: int, subeffect: int = 0, damage: int = 0,
                   element: int = 0, status: int = 0, power: int = 0, duration: int = 0) -> list[dict]:
    """Build a normalized item_mods bundle for an always-on weapon additional effect.

    Returned rows intentionally omit itemId so the normal Item Editor write/backup/journal path
    remains the only place that binds rows to a live item.
    """
    proc_type = int(proc_type)
    chance = int(chance)
    if proc_type not in PROC_TYPES:
        raise ValueError(f"unsupported additional-effect proc type: {proc_type}")
    if not 0 <= chance <= 100:
        raise ValueError("proc chance must be between 0 and 100")

    values = {
        "type": proc_type,
        "subeffect": int(subeffect),
        "damage": int(damage),
        "chance": chance,
        "element": int(element),
        "status": int(status),
        "power": int(power),
        "duration": int(duration),
    }
    rows = []
    for field in FIELDS:
        value = values[field.key]
        # Type/chance are structural; preserve any other explicitly non-zero fields only.
        if field.key in {"type", "chance"} or value:
            rows.append({"modId": field.mod_id, "value": value, "field": field.key})
    return rows


def build_latent_rows(*, latent_id: int, latent_param: int, **effect) -> list[dict]:
    """Build the same additional-effect bundle for item_latents conditional storage."""
    latent_id = int(latent_id)
    latent_param = int(latent_param)
    if latent_id < 0:
        raise ValueError("latent id must be non-negative")
    return [
        {**row, "latentId": latent_id, "latentParam": latent_param}
        for row in build_mod_rows(**effect)
    ]


def inspect_rows(rows: Iterable[dict]) -> dict:
    """Recognize additional-effect fields in existing item_mods/item_latents rows.

    Unknown rows are ignored rather than misclassified as weapon behavior.
    """
    effect = {}
    matched = []
    for row in rows:
        mod_id = int(row.get("modId", -1))
        field = FIELD_BY_MOD.get(mod_id)
        if field is None:
            continue
        value = int(row.get("value", 0))
        effect[field.key] = value
        matched.append(mod_id)
    if not matched:
        return {"recognized": False, "effect": {}, "modIds": []}
    proc_type = effect.get("type")
    return {
        "recognized": True,
        "effect": effect,
        "modIds": sorted(set(matched)),
        "procTypeLabel": PROC_TYPES.get(proc_type, f"unknown ({proc_type})" if proc_type is not None else "not set"),
        "elementLabel": ELEMENTS.get(effect.get("element", 0), f"unknown ({effect.get('element')})"),
        "subeffectLabel": SUBEFFECTS.get(effect.get("subeffect", 0), f"unknown ({effect.get('subeffect')})"),
    }


def requires_server_code(proc_type: int) -> bool:
    """Conservative handoff flag for semantics not portable across older DSP/Topaz trees."""
    # The mature legacy path covers damage/debuff/basic drains/dispel. Modern LSB has additional
    # handlers beyond these, but an old DSP/Topaz target must be verified before presenting them
    # as portable row-only configuration.
    return int(proc_type) not in {1, 2, 5, 6, 7, 10}
