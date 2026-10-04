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
