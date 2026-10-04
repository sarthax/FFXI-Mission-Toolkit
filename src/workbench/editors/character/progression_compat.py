"""Compatibility bridge that extends the Character Editor progression inspector to DSP/Topaz.

The core inspector stays framework-neutral once it receives MissionStateMachine. This module
registers a legacy machine provider for State Surface's `legacy_reference_scan` mode and teaches
condition evaluation/display about legacy persisted mission/quest state. LSB's exact-definition
path is unchanged.
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
    variables = context.get("variables") or {}
    packed = context.get("packed") or {}
    mission_symbols = context.get("mission_symbols") or {}
    mission_ids = context.get("mission_ids") or {}
    quest_symbols = context.get("quest_symbols") or {}

    if subject.startswith("charvar:"):
        key = subject.split(":", 1)[1]
        return True, variables.get(key, 0), "Variables"

    if subject.startswith("mission_current:"):
        symbol = subject.split(":", 1)[1]
        target = mission_symbols.get(symbol)
        if target is None:
            return False, None, "Mission Flags"
        area_id, _entry_id, _label = target
        area = (packed.get("mission") or {}).get(area_id, {})
        if not area:
            return False, None, "Mission Flags"
        current_id = int(area.get("current", -1))
        return True, mission_ids.get((area_id, current_id), current_id), "Mission Flags"

    if subject.startswith("mission_completed:"):
        symbol = subject.split(":", 1)[1]
        target = mission_symbols.get(symbol)
        if target is None:
            return False, None, "Mission Flags"
        area_id, entry_id, _label = target
        area = (packed.get("mission") or {}).get(area_id, {})
        if not area:
            return False, None, "Mission Flags"
        return True, entry_id in set(area.get("completed", ())), "Mission Flags"

    if subject.startswith("quest_active:"):
        symbol = subject.split(":", 1)[1]
        target = quest_symbols.get(symbol)
        if target is None:
            return False, None, "Mission Flags"
        area_id, entry_id, _label = target
        area = (packed.get("quest") or {}).get(area_id, {})
        if not area:
            return False, None, "Mission Flags"
        return True, entry_id in set(area.get("current", ())), "Mission Flags"

    if subject.startswith("quest_completed:"):
        symbol = subject.split(":", 1)[1]
        target = quest_symbols.get(symbol)
        if target is None:
            return False, None, "Mission Flags"
        area_id, entry_id, _label = target
        area = (packed.get("quest") or {}).get(area_id, {})
        if not area:
            return False, None, "Mission Flags"
        return True, entry_id in set(area.get("completed", ())), "Mission Flags"

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
        "Read-only DSP/Topaz diagnosis. Persisted mission/quest flags and character variables are "
        "evaluated from the selected character; runtime-only interaction/trade requirements remain "
        "instructions rather than database blockers."
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
