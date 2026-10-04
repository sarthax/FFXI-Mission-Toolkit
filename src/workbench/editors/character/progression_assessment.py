"""Concise read-only assessment for Character Editor mission/quest progression."""
from __future__ import annotations

from typing import Any


def assess_progression(progression: dict[str, Any]) -> dict[str, Any]:
    """Attach a conservative admin-facing assessment to an inspector result."""
    if not progression.get("available"):
        progression["assessment"] = {
            "state": "UNAVAILABLE",
            "tone": "neutral",
            "summary": progression.get("reason") or "No structured progression model is available.",
            "correction_targets": [],
            "runtime_requirements": 0,
            "persisted_blockers": 0,
        }
        return progression

    diagnosis = str(progression.get("diagnosis") or "")
    primary = progression.get("primary_bundle") or {}
    bundles = progression.get("current_bundles") or []
    blockers = [row for row in progression.get("blockers", ()) if row.get("matches") is False]
    persisted_blockers = list(blockers)
    if not persisted_blockers:
        persisted_blockers = [
            row for row in primary.get("why_blocked", ())
            if row.get("kind") == "persisted_condition"
        ]

    runtime_requirements = list(primary.get("runtime_requirements", ()))
    if not runtime_requirements:
        runtime_requirements = [
            row
            for bundle in bundles
            for row in (bundle.get("runtime_requirements", ()) if isinstance(bundle, dict) else ())
        ]

    correction_targets = sorted({
        str(row.get("editor"))
        for row in persisted_blockers
        if row.get("editor")
    })

    primary_action = progression.get("primary_action") or {}
    primary_eligibility = str(primary_action.get("eligibility") or primary.get("eligibility") or "")
    current_actions = progression.get("current_actions") or []
    current_step = progression.get("current_step")

    if diagnosis == "COMPLETED":
        state, tone = "COMPLETED", "ok"
        summary = "This mission or quest is already completed for the selected character."
    elif persisted_blockers:
        state, tone = "BLOCKED_PERSISTED", "bad"
        summary = "Persisted character state does not match the modeled progression step."
    elif primary_action and primary_eligibility in {"MATCH", "OPEN"}:
        state, tone = "READY", "ok"
        summary = "The modeled next progression action is available from persisted character state."
    elif runtime_requirements and (primary_action or current_actions):
        state, tone = "WAITING_RUNTIME", "warn"
        summary = "Persisted state is consistent, but the next action still depends on runtime input or context."
    elif diagnosis == "INCONSISTENT":
        state, tone = "INCONSISTENT", "warn"
        summary = "No modeled progression section fully matches the selected character state."
    elif current_step is not None and not current_actions:
        state, tone = "NO_MODELED_ACTION", "warn"
        summary = "A current progression step was identified, but no next modeled action was found."
    else:
        state, tone = "UNKNOWN", "neutral"
        summary = "The inspector could not reduce the current evidence to a single progression assessment."

    progression["assessment"] = {
        "state": state,
        "tone": tone,
        "summary": summary,
        "correction_targets": correction_targets,
        "runtime_requirements": len(runtime_requirements),
        "persisted_blockers": len(persisted_blockers),
    }
    return progression
