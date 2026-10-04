"""Compatibility bridge that extends the Character Editor progression inspector to DSP/Topaz.

The core inspector stays framework-neutral once it receives MissionStateMachine.  This module
registers a legacy machine provider for State Surface's `legacy_reference_scan` mode and teaches
condition evaluation/display about legacy charvars.  LSB's exact-definition path is unchanged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from workbench.devtools.missions.legacy_progression_extract import extract_legacy_progression

from . import progression_inspector as _base

_ORIGINAL_MACHINE = _base._machine_for_surface
_ORIGINAL_CONDITION_VALUE = _base._condition_value
_ORIGINAL_BUILD = _base.build_progression_inspector
_PATCHED = False


def _machine_for_surface(surface: dict[str, Any], root: Path):
    machine = _ORIGINAL_MACHINE(surface, root)
    if machine is not None:
        return machine
    summary = surface.get("summary") or {}
    if summary.get("selection_mode") != "legacy_reference_scan":
        return None
    files = []
    for row in surface.get("files") or ():
        rel = str(row.get("path") or "").strip()
        if rel:
            files.append(root / rel)
    if not files:
        return None
    target = surface.get("target") or {}
    feature_id = f"{target.get('kind')}:{int(target.get('area_id', 0))}:{int(target.get('entry_id', 0))}"
    return extract_legacy_progression(files, feature_id=feature_id)


def _condition_value(subject: str, **context):
    if subject.startswith("charvar:"):
        key = subject.split(":", 1)[1]
        variables = context.get("variables") or {}
        return True, variables.get(key, 0), "Variables"
    return _ORIGINAL_CONDITION_VALUE(subject, **context)


def _build(surface: dict[str, Any], server_root, **kwargs):
    result = _ORIGINAL_BUILD(surface, server_root, **kwargs)
    summary = surface.get("summary") or {}
    if not result.get("available") or summary.get("selection_mode") != "legacy_reference_scan":
        return result

    root = Path(server_root).resolve()
    machine = _machine_for_surface(surface, root)
    if machine is None:
        return result
    variables = kwargs.get("variables") or {}
    existing = {str(row.get("storage_key") or "") for row in result.get("feature_vars") or ()}
    rows = list(result.get("feature_vars") or ())
    for channel in machine.channels:
        if not channel.channel_id.startswith("charvar:"):
            continue
        key = channel.channel_id.split(":", 1)[1]
        if key in existing:
            continue
        existing.add(key)
        rows.append({
            "key": key,
            "storage_key": key,
            "value": variables.get(key, 0),
            "known_values": list(channel.values),
            "editor": "Variables",
        })
    result["feature_vars"] = rows
    result["source_adapter"] = "DSP/Topaz legacy handlers"
    result["note"] = (
        "Read-only legacy diagnosis. Handler guards/effects are normalized from target-matched "
        "DSP/Topaz Lua; use guarded Character Editor surfaces for state changes."
    )
    return result


def install() -> None:
    global _PATCHED
    if _PATCHED:
        return
    _base._machine_for_surface = _machine_for_surface
    _base._condition_value = _condition_value
    _base.build_progression_inspector = _build
    _PATCHED = True


install()
