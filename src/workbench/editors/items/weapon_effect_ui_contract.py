"""UI-facing contract for Item Editor weapon-effect presets.

This module is intentionally presentation-only.  It converts the source-backed weapon-effect
model/capability registry into a small JSON-friendly contract a browser panel can render without
reimplementing proc numbering or row generation in JavaScript.
"""
from __future__ import annotations

from . import weapon_effects
from . import weapon_effect_capabilities as caps


ELEMENTAL_PRESETS = tuple(
    {
        "key": f"{name}_damage",
        "label": f"{name.title()} damage",
        "procType": 1,
        "subeffect": value,
        "element": value,
        "defaults": {"chance": 20, "damage": 25},
    }
    for value, name in sorted(weapon_effects.ELEMENTS.items())
    if value
)


def preset_catalog(lineage: str) -> dict:
    family = caps.normalize_lineage(lineage)
    rows = []
    seen = set()
    for key, spec in weapon_effects.PRESETS.items():
        proc_type = int(spec["proc_type"])
        capability = weapon_effects.capability_for(family, proc_type)
        rows.append({
            "key": key,
            "label": spec["label"],
            "procType": proc_type,
            "procTypeLabel": weapon_effects.PROC_TYPES[proc_type],
            "capability": capability,
            "rowsSafeToApply": capability == "row-only",
            "requiresServerCode": bool(spec.get("requires_server_code")) or capability == "server-code-required",
            "defaults": dict(spec.get("defaults") or {}),
            "fields": visible_fields(proc_type),
        })
        seen.add(key)
    for spec in ELEMENTAL_PRESETS:
        if spec["key"] in seen:
            continue
        capability = weapon_effects.capability_for(family, 1)
        rows.append({
            **spec,
            "procTypeLabel": "damage",
            "capability": capability,
            "rowsSafeToApply": capability == "row-only",
            "requiresServerCode": False,
            "fields": visible_fields(1),
        })
    return {
        "lineage": family,
        "presets": rows,
        "applyRule": "Auto-stage only presets with rowsSafeToApply=true.",
        "savePath": "/itemedit/validate -> /itemedit/save-atomic",
        "stagingCollections": ["mods", "latents"],
    }


def visible_fields(proc_type: int) -> list[str]:
    label = weapon_effects.PROC_TYPES.get(int(proc_type), "")
    fields = ["chance"]
    if label in {"damage", "hp heal", "mp heal", "hp drain", "mp drain", "tp drain", "hp+mp drain", "hp+mp+tp drain"}:
        fields.append("damage")
    if label == "damage":
        fields += ["element", "subeffect"]
    elif label in {"debuff", "self buff"}:
        fields += ["status", "power", "duration", "subeffect"]
    elif label in {"dispel", "death"}:
        fields.append("subeffect")
    if label in {"absorb status", "nm specific"}:
        fields.append("serverHandoff")
    return fields


def plan_preset(
    preset: str,
    lineage: str,
    *,
    chance: int | None = None,
    damage: int | None = None,
    status: int | None = None,
    power: int | None = None,
    duration: int | None = None,
    latent_id: int | None = None,
    latent_param: int = 0,
) -> dict:
    overrides = {}
    for key, value in {
        "chance": chance,
        "damage": damage,
        "status": status,
        "power": power,
        "duration": duration,
    }.items():
        if value is not None:
            overrides[key] = int(value)
    if preset in weapon_effects.PRESETS:
        plan = caps.preset_plan(
            preset,
            lineage,
            latent_id=latent_id,
            latent_param=latent_param,
            **overrides,
        )
    else:
        spec = next((row for row in ELEMENTAL_PRESETS if row["key"] == preset), None)
        if spec is None:
            raise ValueError(f"unknown weapon-effect preset: {preset}")
        values = dict(spec["defaults"])
        values.update(overrides)
        rows = weapon_effects.build_mod_rows(
            proc_type=1,
            chance=values["chance"],
            damage=values["damage"],
            subeffect=spec["subeffect"],
            element=spec["element"],
        )
        family = caps.normalize_lineage(lineage)
        capability = weapon_effects.capability_for(family, 1)
        if latent_id is not None:
            rows = [{**row, "latentId": int(latent_id), "latentParam": int(latent_param)} for row in rows]
            target = "latents"
        else:
            target = "mods"
        effect = weapon_effects.inspect_rows(rows)["effect"]
        plan = {
            "preset": preset,
            "lineage": family,
            "procType": 1,
            "procTypeLabel": "damage",
            "capability": capability,
            "rowsSafeToApply": capability == "row-only",
            "targetCollection": target,
            "rows": rows,
            "summary": weapon_effects.summarize_effect(effect),
            "serverHandoff": weapon_effects.export_server_handoff(effect, family),
            "applyRule": (
                "stage rows through existing Item Editor stagedEffects and save-atomic path"
                if capability == "row-only"
                else "do not auto-stage; export/verify server handoff first"
            ),
        }
    plan["ui"] = {
        "fields": visible_fields(plan["procType"]),
        "primaryAction": "stage" if plan["rowsSafeToApply"] else "server-handoff",
        "badge": plan["capability"],
        "requiresConfirmation": plan["rowsSafeToApply"],
    }
    return plan
