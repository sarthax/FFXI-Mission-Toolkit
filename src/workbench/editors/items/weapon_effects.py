"""Structured weapon additional-effect helpers for the Item Editor.

This module deliberately stays above the server-core layer. It describes the existing
item_mods / item_latents rows used by DSP/Topaz/LSB additional-effect handling and gives the
editor a safe way to build or recognize those bundles without pretending that arbitrary new
core behavior can be created from SQL alone.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

MOD_ADDEFFECT_TYPE = 431
MOD_SUBEFFECT = 499
MOD_ADDEFFECT_DMG = 500
MOD_ADDEFFECT_CHANCE = 501
MOD_ADDEFFECT_ELEMENT = 950
MOD_ADDEFFECT_STATUS = 951
MOD_ADDEFFECT_POWER = 952
MOD_ADDEFFECT_DURATION = 953

ELEMENTS = {0: "none", 1: "fire", 2: "ice", 3: "wind", 4: "earth", 5: "lightning", 6: "water", 7: "light", 8: "dark"}
SUBEFFECTS = {
    1: "fire damage", 2: "ice damage", 3: "wind damage", 4: "earth damage", 5: "lightning damage",
    6: "water damage", 7: "light damage", 8: "dark damage / dispel", 9: "sleep", 10: "poison",
    11: "paralysis / amnesia", 12: "blind", 13: "silence", 14: "petrify", 15: "plague", 16: "stun",
    17: "curse", 18: "attack/defense/evasion down", 19: "death", 20: "shield", 21: "hp drain",
    22: "mp/tp drain", 23: "haste",
}
PROC_TYPES = {
    1: "damage", 2: "debuff", 3: "hp heal", 4: "mp heal", 5: "hp drain", 6: "mp drain", 7: "tp drain",
    8: "hp+mp drain", 9: "hp+mp+tp drain", 10: "dispel", 11: "absorb status", 12: "self buff",
    13: "death", 14: "nm specific",
}

SERVER_REFERENCES = {
    "LSB": {
        "additional_effects": "scripts/globals/additional_effects.lua",
        "attack_dispatch": "xi.additionalEffect.attack",
        "proc_registry": "xi.additionalEffect.procFunctions",
        "self_buff_handler": "xi.additionalEffect.procFunctions[xi.additionalEffect.procType.SELF_BUFF]",
        "status_api": "attacker:addStatusEffect(...) / attacker:hasStatusEffect(...) / attacker:delStatusEffect(...)",
        "notes": "Current LSB SELF_BUFF handler explicitly handles Blink and Haste. New self-buffs must extend that handler or add a deliberate proc function.",
    },
    "DSP": {
        "mod_enum": "scripts/globals/status.lua",
        "legacy_type_comment": "ITEM_ADDEFFECT_TYPE: 1=status/dmg/hp drain, 2=mp drain, 3=tp drain, 4=dispel, 5=self-buff, 6=instant death",
        "status_api": "target:addStatusEffect(...) style Lua/core API",
        "notes": "DSP is archived and predates modern LSB proc numbering. Verify the target fork's additional-effect dispatcher before writing type ids.",
    },
    "Topaz": {
        "notes": "Topaz inherits the legacy DSP-era item modifier model but fork/version behavior can drift. Verify the active server tree before enabling modern proc types.",
    },
}

LINEAGE_CAPABILITIES = {
    "LSB": {
        "damage": "row-only", "debuff": "row-only", "hp heal": "row-only", "mp heal": "row-only",
        "hp drain": "row-only", "mp drain": "row-only", "tp drain": "row-only", "hp+mp drain": "row-only",
        "hp+mp+tp drain": "row-only", "dispel": "row-only", "absorb status": "verify-lineage",
        "self buff": "server-code-required", "death": "verify-lineage", "nm specific": "server-code-required",
    },
    "DSP": {
        "damage": "verify-lineage", "debuff": "verify-lineage", "hp drain": "verify-lineage", "mp drain": "verify-lineage",
        "tp drain": "verify-lineage", "dispel": "verify-lineage", "self buff": "server-code-required", "death": "verify-lineage",
    },
    "TOPAZ": {
        "damage": "verify-lineage", "debuff": "verify-lineage", "hp drain": "verify-lineage", "mp drain": "verify-lineage",
        "tp drain": "verify-lineage", "dispel": "verify-lineage", "self buff": "server-code-required", "death": "verify-lineage",
    },
}

PRESETS = {
    "fire_damage": {"label": "Fire damage", "proc_type": 1, "subeffect": 1, "element": 1, "defaults": {"chance": 20, "damage": 25}},
    "ice_damage": {"label": "Ice damage", "proc_type": 1, "subeffect": 2, "element": 2, "defaults": {"chance": 20, "damage": 25}},
    "hp_drain": {"label": "HP drain", "proc_type": 5, "subeffect": 21, "element": 8, "defaults": {"chance": 20, "damage": 20}},
    "mp_drain": {"label": "MP drain", "proc_type": 6, "subeffect": 22, "element": 8, "defaults": {"chance": 20, "damage": 10}},
    "tp_drain": {"label": "TP drain", "proc_type": 7, "subeffect": 22, "element": 8, "defaults": {"chance": 20, "damage": 100}},
    "dispel": {"label": "Dispel", "proc_type": 10, "subeffect": 8, "defaults": {"chance": 20}},
    "self_buff": {"label": "Self buff", "proc_type": 12, "defaults": {"chance": 20, "power": 1, "duration": 30}, "requires_server_code": True},
    "absorb_status": {"label": "Absorb status", "proc_type": 11, "defaults": {"chance": 20}},
    "death": {"label": "Instant death", "proc_type": 13, "subeffect": 19, "defaults": {"chance": 1}},
    "nm_specific": {"label": "NM-specific scripted behavior", "proc_type": 14, "defaults": {"chance": 100}, "requires_server_code": True},
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
    EffectField("status", MOD_ADDEFFECT_STATUS, "Status effect id", ("debuff", "self buff"), notes="Server status-effect enum id."),
    EffectField("power", MOD_ADDEFFECT_POWER, "Status power", ("debuff", "self buff")),
    EffectField("duration", MOD_ADDEFFECT_DURATION, "Status duration (s)", ("debuff", "self buff")),
)
FIELD_BY_MOD = {field.mod_id: field for field in FIELDS}


def capability_for(lineage: str, proc_type: int) -> str:
    lineage = str(lineage).upper()
    label = PROC_TYPES.get(int(proc_type))
    if label is None:
        return "unsupported"
    caps = LINEAGE_CAPABILITIES.get(lineage)
    if caps is None:
        return "verify-lineage"
    return caps.get(label, "verify-lineage")


def rows_safe_to_apply(lineage: str, proc_type: int) -> bool:
    return capability_for(lineage, proc_type) == "row-only"


def catalog() -> dict:
    return {
        "fields": [{"key": f.key, "modId": f.mod_id, "label": f.label, "requiredFor": list(f.required_for), "notes": f.notes} for f in FIELDS],
        "procTypes": [{"value": value, "label": label} for value, label in sorted(PROC_TYPES.items())],
        "elements": [{"value": value, "label": label} for value, label in sorted(ELEMENTS.items())],
        "subeffects": [{"value": value, "label": label} for value, label in sorted(SUBEFFECTS.items())],
        "presets": [{"key": key, **value} for key, value in PRESETS.items()],
        "serverReferences": SERVER_REFERENCES,
        "lineageCapabilities": LINEAGE_CAPABILITIES,
        "storage": "item_mods or item_latents",
        "clientCoupled": False,
        "coreBoundary": "Existing proc types/fields can be configured here. New proc semantics still require server Lua/C++ support; the editor must not invent a new type and assume it works.",
    }


def build_mod_rows(*, proc_type: int, chance: int, subeffect: int = 0, damage: int = 0,
                   element: int = 0, status: int = 0, power: int = 0, duration: int = 0) -> list[dict]:
    proc_type = int(proc_type)
    chance = int(chance)
    if proc_type not in PROC_TYPES:
        raise ValueError(f"unsupported additional-effect proc type: {proc_type}")
    if not 0 <= chance <= 100:
        raise ValueError("proc chance must be between 0 and 100")
    values = {"type": proc_type, "subeffect": int(subeffect), "damage": int(damage), "chance": chance,
              "element": int(element), "status": int(status), "power": int(power), "duration": int(duration)}
    rows = []
    for field in FIELDS:
        value = values[field.key]
        if field.key in {"type", "chance"} or value:
            rows.append({"modId": field.mod_id, "value": value, "field": field.key})
    return rows


def build_preset_rows(preset: str, **overrides) -> list[dict]:
    try:
        spec = PRESETS[preset]
    except KeyError as exc:
        raise ValueError(f"unknown weapon-effect preset: {preset}") from exc
    values = dict(spec.get("defaults") or {})
    for key in ("proc_type", "subeffect", "element", "status", "power", "duration", "damage", "chance"):
        if key in spec:
            values[key] = spec[key]
    values.update(overrides)
    return build_mod_rows(**values)


def build_latent_rows(*, latent_id: int, latent_param: int, **effect) -> list[dict]:
    latent_id = int(latent_id)
    latent_param = int(latent_param)
    if latent_id < 0:
        raise ValueError("latent id must be non-negative")
    return [{**row, "latentId": latent_id, "latentParam": latent_param} for row in build_mod_rows(**effect)]


def build_self_buff_blueprint(*, status: int, chance: int = 20, power: int = 1,
                              duration: int = 30, subeffect: int = 0, lineage: str = "LSB") -> dict:
    lineage = str(lineage).upper()
    modern_rows = build_mod_rows(proc_type=12, chance=chance, subeffect=subeffect, status=status, power=power, duration=duration)
    reference = SERVER_REFERENCES.get(lineage, SERVER_REFERENCES["Topaz"])
    return {
        "kind": "self_buff", "lineage": lineage, "modernLsbRows": modern_rows,
        "rowsAreSafeToApply": rows_safe_to_apply(lineage, 12), "capability": capability_for(lineage, 12),
        "requiresServerCode": True, "serverReference": reference,
        "implementationContract": {
            "trigger": "successful eligible weapon attack after ITEM_ADDEFFECT_CHANCE roll", "target": "attacker/self",
            "statusId": int(status), "power": int(power), "durationSeconds": int(duration),
            "message": "additional-effect self-buff battle message/subeffect",
            "stacking": "must be defined explicitly per status; do not blindly overwrite existing effects",
        },
        "localAgentTasks": [
            "Verify the active lineage's ITEM_ADDEFFECT_TYPE numbering before changing SQL.",
            "Locate the weapon additional-effect attack dispatcher and self-buff proc handler.",
            "Add/verify the requested status branch, including stacking/overwrite rules.",
            "Apply the status to the attacker using the lineage's addStatusEffect API.",
            "Return the correct additional-effect subeffect/message tuple.",
            "Add a focused server regression for proc chance, duration, power, and stacking behavior.",
        ],
    }


def summarize_effect(effect: dict) -> str:
    proc_type = int(effect.get("type", 0) or 0)
    label = PROC_TYPES.get(proc_type, f"proc {proc_type}")
    chance = int(effect.get("chance", 0) or 0)
    parts = [f"{chance}% {label}"]
    if effect.get("element"):
        parts.append(ELEMENTS.get(int(effect["element"]), f"element {effect['element']}"))
    if effect.get("damage"):
        parts.append(f"amount {int(effect['damage'])}")
    if effect.get("status"):
        parts.append(f"status {int(effect['status'])}")
    if effect.get("power"):
        parts.append(f"power {int(effect['power'])}")
    if effect.get("duration"):
        parts.append(f"{int(effect['duration'])}s")
    return " · ".join(parts)


def export_server_handoff(effect: dict, lineage: str) -> dict:
    proc_type = int(effect.get("type", 0) or 0)
    lineage = str(lineage).upper()
    return {
        "lineage": lineage, "procType": proc_type,
        "procTypeLabel": PROC_TYPES.get(proc_type, f"unknown ({proc_type})"),
        "capability": capability_for(lineage, proc_type), "rowsAreSafeToApply": rows_safe_to_apply(lineage, proc_type),
        "effect": dict(effect), "summary": summarize_effect(effect),
        "serverReference": SERVER_REFERENCES.get(lineage, SERVER_REFERENCES["Topaz"]),
        "warning": "Verify proc numbering and handler semantics in the active server tree before applying generated rows.",
    }


def inspect_rows(rows: Iterable[dict]) -> dict:
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
        "recognized": True, "effect": effect, "modIds": sorted(set(matched)),
        "procTypeLabel": PROC_TYPES.get(proc_type, f"unknown ({proc_type})" if proc_type is not None else "not set"),
        "elementLabel": ELEMENTS.get(effect.get("element", 0), f"unknown ({effect.get('element')})"),
        "subeffectLabel": SUBEFFECTS.get(effect.get("subeffect", 0), f"unknown ({effect.get('subeffect')})"),
        "summary": summarize_effect(effect),
    }


def requires_server_code(proc_type: int) -> bool:
    return int(proc_type) not in {1, 2, 5, 6, 7, 10}
