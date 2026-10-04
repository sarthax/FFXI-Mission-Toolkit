"""Read-only transition bundle projection for Character Editor progression diagnosis.

The progression inspector already identifies candidate actions from normalized mission/quest
state machines. This module groups each action into the admin-facing transition units used by
the Character Editor without inventing new gameplay semantics.
"""
from __future__ import annotations

from typing import Any


_STATE_EFFECTS = {"SET_STATE", "SET_VAR", "SET_CHANNEL"}
_REWARD_EFFECTS = {"GRANT", "GRANT_TITLE", "REISSUE"}
_REMOVAL_EFFECTS = {"CONSUME", "REMOVE", "COMPLETE_TRADE"}
_COMPLETION_EFFECTS = {"COMPLETE"}
_NEXT_EFFECTS = {"START", "ENTER", "EXIT", "TELEPORT", "CLIENT_TRANSPORT"}
_TIMER_EFFECTS = {"START_TIMER", "CANCEL_TIMER"}
_PERSISTENT_EFFECTS = (
    _STATE_EFFECTS
    | _REWARD_EFFECTS
    | _REMOVAL_EFFECTS
    | _COMPLETION_EFFECTS
    | _TIMER_EFFECTS
)


def _effect_rows(action: dict[str, Any], names: set[str]) -> list[dict[str, Any]]:
    return [row for row in action.get("effects", ()) if str(row.get("effect") or "") in names]


def _why_blocked(action: dict[str, Any]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for condition in action.get("conditions", ()):
        if condition.get("matches") is False:
            reasons.append({
                "kind": "persisted_condition",
                "subject": condition.get("subject"),
                "operator": condition.get("operator"),
                "expected": condition.get("expected"),
                "actual": condition.get("actual"),
                "editor": condition.get("editor"),
            })
        elif condition.get("matches") is None and condition.get("runtime_only"):
            reasons.append({
                "kind": "runtime_requirement",
                "subject": condition.get("subject"),
                "operator": condition.get("operator"),
                "expected": condition.get("expected"),
                "actual": None,
                "editor": None,
            })
    return reasons


def _known_current_values(action: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for condition in action.get("conditions", ()):
        subject = condition.get("subject")
        if subject and condition.get("resolved"):
            values[str(subject)] = condition.get("actual")
    return values


def _projected_changes(action: dict[str, Any]) -> list[dict[str, Any]]:
    """Describe the direct modeled result of an action without claiming the write has occurred."""
    current = _known_current_values(action)
    projected: list[dict[str, Any]] = []
    for effect in action.get("effects", ()):
        name = str(effect.get("effect") or "")
        subject = effect.get("subject")
        value = effect.get("value")
        if name in _STATE_EFFECTS:
            projected.append({
                "kind": "state_change",
                "effect": name,
                "subject": subject,
                "before": current.get(str(subject)) if subject is not None else None,
                "before_known": subject is not None and str(subject) in current,
                "after": value,
            })
        elif name in _REWARD_EFFECTS:
            projected.append({
                "kind": "grant",
                "effect": name,
                "subject": subject,
                "before": current.get(str(subject)) if subject is not None else None,
                "before_known": subject is not None and str(subject) in current,
                "after": value if value is not None else True,
            })
        elif name in _REMOVAL_EFFECTS:
            projected.append({
                "kind": "removal",
                "effect": name,
                "subject": subject,
                "before": current.get(str(subject)) if subject is not None else None,
                "before_known": subject is not None and str(subject) in current,
                "after": False if name in {"CONSUME", "REMOVE"} else "completed",
            })
        elif name in _COMPLETION_EFFECTS:
            projected.append({
                "kind": "completion",
                "effect": name,
                "subject": subject,
                "before": current.get(str(subject)) if subject is not None else None,
                "before_known": subject is not None and str(subject) in current,
                "after": "completed",
            })
        elif name in _NEXT_EFFECTS:
            projected.append({
                "kind": "next_activation",
                "effect": name,
                "subject": subject,
                "before": None,
                "before_known": False,
                "after": value if value is not None else "activated",
            })
        elif name in _TIMER_EFFECTS:
            projected.append({
                "kind": "timer",
                "effect": name,
                "subject": subject,
                "before": None,
                "before_known": False,
                "after": value if value is not None else ("cancelled" if name == "CANCEL_TIMER" else "started"),
            })
    return projected


def build_transition_bundle(action: dict[str, Any]) -> dict[str, Any]:
    """Group one normalized progression action into an evidence-preserving transition unit."""
    conditions = list(action.get("conditions", ()))
    persisted = [row for row in conditions if not row.get("runtime_only")]
    runtime = [row for row in conditions if row.get("runtime_only")]
    effects = list(action.get("effects", ()))
    persistent_effects = [
        row for row in effects if str(row.get("effect") or "") in _PERSISTENT_EFFECTS
    ]

    blocked = _why_blocked(action)
    correction_targets = sorted({
        str(row.get("editor"))
        for row in blocked
        if row.get("kind") == "persisted_condition" and row.get("editor")
    })

    return {
        "transition_id": action.get("transition_id"),
        "trigger": action.get("trigger"),
        "eligibility": action.get("eligibility"),
        "event": action.get("event"),
        "preconditions": persisted,
        "runtime_requirements": runtime,
        "persistent_effects": persistent_effects,
        "state_changes": _effect_rows(action, _STATE_EFFECTS),
        "rewards": _effect_rows(action, _REWARD_EFFECTS),
        "removals": _effect_rows(action, _REMOVAL_EFFECTS),
        "completion": _effect_rows(action, _COMPLETION_EFFECTS),
        "next_activation": _effect_rows(action, _NEXT_EFFECTS),
        "timers": _effect_rows(action, _TIMER_EFFECTS),
        "projected_changes": _projected_changes(action),
        "projection_is_read_only": True,
        "why_blocked": blocked,
        "correction_targets": correction_targets,
        "source_lines": action.get("source_lines"),
        "implementation_status": action.get("implementation_status"),
        "logical_event_chain": bool(action.get("logical_event_chain")),
    }


def annotate_transition_bundles(progression: dict[str, Any]) -> dict[str, Any]:
    """Attach bundles to an inspector result and expose the primary/current bundle set."""
    if not progression.get("available"):
        return progression

    seen: set[int] = set()
    actions: list[dict[str, Any]] = []

    def collect(rows) -> None:
        for row in rows or ():
            if not isinstance(row, dict):
                continue
            identity = id(row)
            if identity in seen:
                continue
            seen.add(identity)
            row["transition_bundle"] = build_transition_bundle(row)
            actions.append(row)

    for section in progression.get("sections", ()):
        collect(section.get("actions", ()) if isinstance(section, dict) else ())
    collect(progression.get("unsectioned_actions", ()))
    collect(progression.get("current_actions", ()))
    primary = progression.get("primary_action")
    collect((primary,) if isinstance(primary, dict) else ())

    progression["current_bundles"] = [
        row["transition_bundle"]
        for row in progression.get("current_actions", ())
        if isinstance(row, dict) and row.get("transition_bundle")
    ]
    progression["primary_bundle"] = (
        primary.get("transition_bundle") if isinstance(primary, dict) else None
    )
    progression.setdefault("summary", {})["transition_bundle_count"] = len(actions)
    return progression
