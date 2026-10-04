"""Character-aware mission/quest progression inspector.

This module projects the existing structural mission/quest state-machine extraction into an
admin-facing snapshot: current feature state, persisted variables, the eligible section/action,
and blockers. It is intentionally read-only; mutation remains in the existing guarded editors.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from workbench.devtools.missions.mission_lsb_extract import chain_event_transitions, correlate_lsb_handlers
from workbench.devtools.missions.quest_lsb_extract import chain_quest_event_transitions, correlate_lsb_quest_handlers


_PROGRESS_EFFECTS = {
    "SET_STATE", "SET_VAR", "SET_CHANNEL", "GRANT", "CONSUME", "REMOVE", "REISSUE",
    "COMPLETE", "START", "GRANT_TITLE", "COMPLETE_TRADE", "TELEPORT", "START_TIMER",
}


def _feature_var_name(kind: str, area_id: int, entry_id: int, key: str) -> str:
    prefix = "Quest" if kind == "quest" else "Mission"
    return f"{prefix}[{int(area_id)}][{int(entry_id)}]{key}"


def _target_status(kind: str, area_id: int, entry_id: int, packed: dict[str, Any]) -> str | None:
    area = (packed.get(kind) or {}).get(int(area_id), {})
    if not area:
        return None
    if kind == "quest":
        if int(entry_id) in set(area.get("completed", ())):
            return "QUEST_COMPLETED"
        if int(entry_id) in set(area.get("current", ())):
            return "QUEST_ACCEPTED"
        return "QUEST_AVAILABLE"
    if int(entry_id) in set(area.get("completed", ())):
        return "MISSION_COMPLETED"
    if int(area.get("current", -1)) == int(entry_id):
        return "MISSION_CURRENT"
    return "MISSION_NOT_CURRENT"


def _iter_catalog_rows(catalog: dict[str, Any]) -> Iterable[tuple[int, int, dict[str, Any]]]:
    for raw_area, rows in (catalog.get("areas") or {}).items():
        try:
            area_id = int(raw_area)
        except (TypeError, ValueError):
            continue
        if not isinstance(rows, dict):
            continue
        for raw_id, row in rows.items():
            if not isinstance(row, dict):
                continue
            try:
                entry_id = int(row.get("id", raw_id))
            except (TypeError, ValueError):
                continue
            yield area_id, entry_id, row


def _catalog_indexes(catalog: dict[str, Any]) -> tuple[dict[str, tuple[int, int, str]], dict[tuple[int, int], str]]:
    by_symbol: dict[str, tuple[int, int, str]] = {}
    by_id: dict[tuple[int, int], str] = {}
    for area_id, entry_id, row in _iter_catalog_rows(catalog):
        symbol = str(row.get("symbol") or "").strip()
        label = str(row.get("label") or symbol or entry_id)
        if symbol:
            by_symbol[symbol] = (area_id, entry_id, label)
            by_id[(area_id, entry_id)] = symbol
    return by_symbol, by_id


def _compare(actual: Any, operator: str, expected: Any) -> bool | None:
    try:
        if operator == "EQ": return actual == expected
        if operator == "NE": return actual != expected
        if operator == "LT": return actual < expected
        if operator == "LE": return actual <= expected
        if operator == "GT": return actual > expected
        if operator == "GE": return actual >= expected
        if operator == "HAS": return bool(actual)
        if operator == "LACKS": return not bool(actual)
        if operator == "COMPLETE": return bool(actual) == bool(expected)
        if operator == "IN": return actual in expected
    except (TypeError, ValueError):
        return None
    return None


def _condition_value(
    subject: str,
    *,
    kind: str,
    area_id: int,
    entry_id: int,
    variables: dict[str, Any],
    packed: dict[str, Any],
    mission_symbols: dict[str, tuple[int, int, str]],
    mission_ids: dict[tuple[int, int], str],
    quest_symbols: dict[str, tuple[int, int, str]],
) -> tuple[bool, Any, str | None]:
    if subject == "quest_status":
        return True, _target_status("quest", area_id, entry_id, packed), "Mission Flags"
    if subject.startswith("quest_var:"):
        key = subject.split(":", 1)[1]
        storage = _feature_var_name("quest", area_id, entry_id, key)
        return True, variables.get(storage, 0), "Variables"
    if subject.startswith("mission_var:"):
        key = subject.split(":", 1)[1]
        storage = _feature_var_name("mission", area_id, entry_id, key)
        return True, variables.get(storage, 0), "Variables"
    if subject.startswith("key_item:"):
        symbol = subject.split(":", 1)[1]
        known = packed.get("key_items", {})
        if symbol in known:
            return True, bool(known[symbol]), "Key Items"
        return False, None, "Key Items"
    if subject.startswith("quest:"):
        symbol = subject.split(":", 1)[1]
        target = quest_symbols.get(symbol)
        if target is None:
            return False, None, "Mission Flags"
        q_area, q_id, _ = target
        area = (packed.get("quest") or {}).get(q_area, {})
        if not area:
            return False, None, "Mission Flags"
        return True, q_id in set(area.get("completed", ())), "Mission Flags"
    if subject.startswith("mission:") and subject.endswith(":current"):
        parts = subject.split(":")
        expected_area = int(area_id)
        area = (packed.get("mission") or {}).get(expected_area, {})
        if not area:
            return False, None, "Mission Flags"
        current_id = int(area.get("current", -1))
        return True, mission_ids.get((expected_area, current_id), current_id), "Mission Flags"
    if subject.startswith("mission:"):
        symbol = subject.split(":", 1)[1]
        target = mission_symbols.get(symbol)
        if target is None:
            return False, None, "Mission Flags"
        m_area, m_id, _ = target
        area = (packed.get("mission") or {}).get(m_area, {})
        if not area:
            return False, None, "Mission Flags"
        return True, m_id in set(area.get("completed", ())), "Mission Flags"
    return False, None, None


def _condition_row(
    condition,
    *,
    kind: str,
    area_id: int,
    entry_id: int,
    variables: dict[str, Any],
    packed: dict[str, Any],
    mission_symbols: dict[str, tuple[int, int, str]],
    mission_ids: dict[tuple[int, int], str],
    quest_symbols: dict[str, tuple[int, int, str]],
) -> dict[str, Any]:
    subject = str(condition.subject)
    expected = condition.value
    resolved, actual, editor = _condition_value(
        subject,
        kind=kind,
        area_id=area_id,
        entry_id=entry_id,
        variables=variables,
        packed=packed,
        mission_symbols=mission_symbols,
        mission_ids=mission_ids,
        quest_symbols=quest_symbols,
    )
    match = _compare(actual, condition.operator, expected) if resolved else None
    return {
        "subject": subject,
        "operator": condition.operator,
        "expected": expected,
        "actual": actual if resolved else None,
        "resolved": resolved,
        "matches": match,
        "editor": editor,
    }


def _gate_rows(gate, **context) -> list[dict[str, Any]]:
    if gate is None:
        return []
    return [_condition_row(condition, **context) for condition in gate.conditions]


def _gate_state(rows: list[dict[str, Any]], logic: str = "ALL") -> str:
    if not rows:
        return "OPEN"
    known = [row.get("matches") for row in rows]
    if logic == "ANY":
        if any(value is True for value in known): return "MATCH"
        if all(value is False for value in known): return "BLOCKED"
        return "PARTIAL"
    if any(value is False for value in known): return "BLOCKED"
    if all(value is True for value in known): return "MATCH"
    return "PARTIAL"


def _action_row(transition, **context) -> dict[str, Any]:
    gate_rows = _gate_rows(transition.gate, **context)
    effects = [
        {"effect": effect.effect, "subject": effect.subject, "value": effect.value}
        for effect in transition.effects
    ]
    event = None
    if transition.event is not None:
        event = {
            "zone": transition.event.zone,
            "actor": transition.event.actor,
            "event_id": transition.event.event_id,
        }
    is_progression = any(effect["effect"] in _PROGRESS_EFFECTS for effect in effects)
    return {
        "transition_id": transition.transition_id,
        "trigger": transition.trigger,
        "event": event,
        "effects": effects,
        "conditions": gate_rows,
        "eligibility": _gate_state(gate_rows, transition.gate.logic if transition.gate else "ALL"),
        "progression": is_progression,
        "implementation_status": transition.implementation_status,
        "section_index": transition.metadata.get("section_index"),
        "source_lines": transition.metadata.get("section_source_lines"),
        "logical_event_chain": bool(transition.metadata.get("logical_event_chain")),
    }


def _section_conditions(transition, **context) -> list[dict[str, Any]]:
    rows = []
    for raw in transition.metadata.get("section_eligibility_conditions", ()) or ():
        class _Condition:
            subject = raw.get("subject")
            operator = raw.get("operator")
            value = raw.get("value")
        rows.append(_condition_row(_Condition(), **context))
    return rows


def _machine_for_surface(surface: dict[str, Any], root: Path):
    summary = surface.get("summary") or {}
    if summary.get("selection_mode") != "exact_lsb_definition":
        return None
    files = surface.get("files") or []
    if not files:
        return None
    source_path = root / str(files[0].get("path") or "")
    try:
        lua = source_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    target = surface.get("target") or {}
    kind = str(target.get("kind") or "")
    feature_id = f"{kind}:{int(target.get('area_id', 0))}:{int(target.get('entry_id', 0))}"
    if kind == "quest":
        return chain_quest_event_transitions(correlate_lsb_quest_handlers(lua, feature_id=feature_id))
    if kind == "mission":
        return chain_event_transitions(correlate_lsb_handlers(lua, feature_id=feature_id))
    return None


def build_progression_inspector(
    surface: dict[str, Any],
    server_root: Path | str,
    *,
    variables: dict[str, Any],
    packed: dict[str, Any],
    mission_catalog: dict[str, Any],
    quest_catalog: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate an exact LSB mission/quest state machine against one character snapshot."""
    root = Path(server_root).resolve()
    target = surface.get("target") or {}
    kind = str(target.get("kind") or "")
    area_id = int(target.get("area_id", 0))
    entry_id = int(target.get("entry_id", 0))
    symbol = str(target.get("symbol") or "")
    status = _target_status(kind, area_id, entry_id, packed)
    machine = _machine_for_surface(surface, root)
    if machine is None:
        return {
            "available": False,
            "status": status or "UNKNOWN",
            "reason": "No exact structural mission/quest state machine is available for this source layout.",
            "read_only": True,
        }

    mission_symbols, mission_ids = _catalog_indexes(mission_catalog)
    quest_symbols, _quest_ids = _catalog_indexes(quest_catalog)
    context = {
        "kind": kind,
        "area_id": area_id,
        "entry_id": entry_id,
        "variables": variables,
        "packed": packed,
        "mission_symbols": mission_symbols,
        "mission_ids": mission_ids,
        "quest_symbols": quest_symbols,
    }

    feature_vars: list[dict[str, Any]] = []
    seen_vars: set[str] = set()
    for channel in machine.channels:
        prefix = f"{kind}_var:"
        if not channel.channel_id.startswith(prefix):
            continue
        key = channel.channel_id.split(":", 1)[1]
        if key in seen_vars:
            continue
        seen_vars.add(key)
        storage = _feature_var_name(kind, area_id, entry_id, key)
        feature_vars.append({
            "key": key,
            "storage_key": storage,
            "value": variables.get(storage, 0),
            "known_values": list(channel.values),
            "editor": "Variables",
        })

    sections: dict[int, dict[str, Any]] = {}
    unsectioned: list[dict[str, Any]] = []
    for transition in machine.transitions:
        action = _action_row(transition, **context)
        raw_index = transition.metadata.get("section_index")
        if raw_index is None:
            unsectioned.append(action)
            continue
        index = int(raw_index)
        section = sections.setdefault(index, {
            "section_index": index,
            "source_lines": transition.metadata.get("section_source_lines"),
            "conditions": [],
            "actions": [],
            "eligibility_status": transition.metadata.get("section_eligibility_status"),
        })
        if not section["conditions"]:
            section["conditions"] = _section_conditions(transition, **context)
        section["actions"].append(action)

    ordered_sections = []
    for index in sorted(sections):
        section = sections[index]
        section["eligibility"] = _gate_state(section["conditions"], "ALL")
        section["actions"].sort(key=lambda row: (not row["progression"], row["eligibility"] != "MATCH", str(row["transition_id"])))
        ordered_sections.append(section)

    target_completed = status in {"QUEST_COMPLETED", "MISSION_COMPLETED"}
    matched_sections = [row for row in ordered_sections if row["eligibility"] in {"MATCH", "OPEN"}]
    current_section = None
    if not target_completed and matched_sections:
        # Prefer the most specific eligible section; on ties, later source sections generally
        # represent later progression states in LSB's interaction framework.
        current_section = max(matched_sections, key=lambda row: (len(row["conditions"]), row["section_index"]))
    elif not target_completed and ordered_sections:
        # No section fully matches. Show the nearest candidate so admins can see exactly what is off.
        current_section = min(
            ordered_sections,
            key=lambda row: (
                sum(cond.get("matches") is False for cond in row["conditions"]),
                sum(cond.get("matches") is None for cond in row["conditions"]),
                -row["section_index"],
            ),
        )

    current_actions: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if current_section is not None:
        current_actions = [row for row in current_section["actions"] if row["eligibility"] in {"MATCH", "OPEN"}]
        if not current_actions:
            current_actions = current_section["actions"][:3]
        for condition in current_section["conditions"]:
            if condition.get("matches") is False:
                blockers.append(condition)
        # Handler-level conditions explain why a specific transition is not currently available.
        if not blockers and current_actions and not any(row["progression"] for row in current_actions):
            for action in current_section["actions"]:
                if action["progression"] and action["eligibility"] == "BLOCKED":
                    blockers.extend(cond for cond in action["conditions"] if cond.get("matches") is False)

    primary_action = next((row for row in current_actions if row["progression"]), current_actions[0] if current_actions else None)
    diagnosis = "COMPLETED" if target_completed else (
        "CURRENT" if current_section is not None and current_section["eligibility"] in {"MATCH", "OPEN"} else "INCONSISTENT"
    )

    return {
        "available": True,
        "read_only": True,
        "status": status or "UNKNOWN",
        "diagnosis": diagnosis,
        "symbol": symbol,
        "feature_vars": feature_vars,
        "current_step": current_section,
        "primary_action": primary_action,
        "current_actions": current_actions[:8],
        "blockers": blockers,
        "sections": ordered_sections,
        "unsectioned_actions": unsectioned,
        "summary": {
            "section_count": len(ordered_sections),
            "transition_count": len(machine.transitions),
            "current_section": current_section.get("section_index") if current_section else None,
            "eligible_action_count": len(current_actions),
            "blocker_count": len(blockers),
        },
        "note": "Read-only diagnosis. Use the existing guarded Character Editor surfaces for any state change.",
    }
