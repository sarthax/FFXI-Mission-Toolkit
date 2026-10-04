"""Lineage-aware capability registry for Item Editor weapon effects.

This module stays read-only: it classifies whether an additional-effect preset can be
represented with existing item_mods/item_latents rows, needs target-fork verification, or
requires a server handler change. It deliberately does not mutate a server tree.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from . import weapon_effects


@dataclass(frozen=True)
class SourceProbe:
    lineage: str
    relative_paths: tuple[str, ...]
    markers: tuple[str, ...]
    description: str


PROBES = (
    SourceProbe(
        "LSB",
        ("scripts/globals/additional_effects.lua",),
        (
            "xi.additionalEffect.attack",
            "xi.additionalEffect.procFunctions",
            "SELF_BUFF",
        ),
        "Modern LandSandBoat additional-effect dispatcher",
    ),
    SourceProbe(
        "DSP",
        ("scripts/globals/status.lua", "scripts/globals/additional_effects.lua"),
        ("ITEM_ADDEFFECT_TYPE", "ITEM_ADDEFFECT_CHANCE"),
        "Archived/legacy DarkStar additional-effect definitions",
    ),
    SourceProbe(
        "TOPAZ",
        ("scripts/globals/status.lua", "scripts/globals/additional_effects.lua"),
        ("ITEM_ADDEFFECT_TYPE",),
        "Topaz/DSP-era additional-effect definitions",
    ),
)


def normalize_lineage(lineage: str | None) -> str:
    raw = str(lineage or "").strip().upper()
    aliases = {
        "LANDSANDBOAT": "LSB",
        "LAND SANDBOAT": "LSB",
        "DARKSTAR": "DSP",
        "DARKSTARPROJECT": "DSP",
        "TOPAZ-NEXT": "TOPAZ",
    }
    return aliases.get(raw, raw or "UNKNOWN")


def capability_matrix() -> dict:
    """Return editor-consumable capability metadata for all known proc types."""
    rows = []
    for proc_type, label in sorted(weapon_effects.PROC_TYPES.items()):
        rows.append(
            {
                "procType": proc_type,
                "label": label,
                "LSB": weapon_effects.capability_for("LSB", proc_type),
                "DSP": weapon_effects.capability_for("DSP", proc_type),
                "TOPAZ": weapon_effects.capability_for("TOPAZ", proc_type),
                "requiresServerCode": weapon_effects.requires_server_code(proc_type),
            }
        )
    return {
        "capabilities": rows,
        "states": ("row-only", "verify-lineage", "server-code-required", "unsupported"),
        "writeRule": "Only row-only effects may be auto-staged without source verification.",
    }


def probe_server_tree(server_root: str | Path, lineage: str) -> dict:
    """Inspect a configured server checkout without modifying it.

    The probe is intentionally conservative. Presence of expected symbols is evidence that a
    known handler family exists; it is not proof that an arbitrary requested status/proc is
    implemented.
    """
    root = Path(server_root)
    family = normalize_lineage(lineage)
    probe = next((row for row in PROBES if row.lineage == family), None)
    if probe is None:
        return {
            "lineage": family,
            "supportedLineage": False,
            "sourceFound": False,
            "markers": {},
            "confidence": "unknown",
            "reason": "No source probe is defined for this lineage.",
        }

    found_files = []
    marker_hits = {marker: [] for marker in probe.markers}
    for relative in probe.relative_paths:
        path = root / relative
        if not path.is_file():
            continue
        found_files.append(relative)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for marker in probe.markers:
            if marker in text:
                marker_hits[marker].append(relative)

    hit_count = sum(bool(paths) for paths in marker_hits.values())
    confidence = "source-verified" if found_files and hit_count == len(marker_hits) else (
        "partial" if found_files or hit_count else "missing"
    )
    return {
        "lineage": family,
        "supportedLineage": True,
        "description": probe.description,
        "sourceFound": bool(found_files),
        "files": found_files,
        "markers": marker_hits,
        "confidence": confidence,
        "readOnly": True,
    }


def self_buff_support(server_root: str | Path, lineage: str, status_names: Iterable[str] = ()) -> dict:
    """Probe whether known self-buff handler names are visible in the target checkout.

    This is a handoff aid, not an execution gate: even a textual match cannot prove stacking,
    overwrite, battle-message, or proc semantics.
    """
    family = normalize_lineage(lineage)
    base = probe_server_tree(server_root, family)
    names = [str(name).strip() for name in status_names if str(name).strip()]
    matches = {name: [] for name in names}

    candidates = []
    for relative in base.get("files", []):
        path = Path(server_root) / relative
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        candidates.append((relative, text))

    for name in names:
        pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        for relative, text in candidates:
            if pattern.search(text):
                matches[name].append(relative)

    return {
        **base,
        "kind": "self-buff",
        "requestedStatuses": names,
        "statusNameMatches": matches,
        "handlerVerified": False,
        "capability": "server-code-required",
        "warning": (
            "Textual source matches are advisory only. Verify the exact self-buff proc branch, "
            "status enum, stacking/overwrite behavior, target, duration/power semantics, and "
            "battle message before enabling row application."
        ),
    }


def preset_plan(preset: str, lineage: str, *, latent_id: int | None = None,
                latent_param: int = 0, **overrides) -> dict:
    """Build the exact rows a future UI would stage, plus the fail-closed capability decision."""
    rows = weapon_effects.build_preset_rows(preset, **overrides)
    proc_type_row = next(row for row in rows if row["modId"] == weapon_effects.MOD_ADDEFFECT_TYPE)
    proc_type = int(proc_type_row["value"])
    family = normalize_lineage(lineage)
    capability = weapon_effects.capability_for(family, proc_type)
    if latent_id is not None:
        rows = [{**row, "latentId": int(latent_id), "latentParam": int(latent_param)} for row in rows]
        target = "latents"
    else:
        target = "mods"
    effect = weapon_effects.inspect_rows(rows)["effect"]
    return {
        "preset": preset,
        "lineage": family,
        "procType": proc_type,
        "procTypeLabel": weapon_effects.PROC_TYPES.get(proc_type),
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
