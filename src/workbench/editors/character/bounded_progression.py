"""Bounded progression projection for the Character Editor.

Turns the full structural inspector result into a deliberately small previous/current/next
view. The full inspector remains attached for explicit evidence drill-downs; this projection
must never recursively expand Feature Trace or Behavior Trace relationships.
"""
from __future__ import annotations

from typing import Any


def _step(section: dict[str, Any] | None, relation: str) -> dict[str, Any] | None:
    if not section:
        return None
    actions = [
        row for row in section.get("actions", ())
        if isinstance(row, dict) and row.get("progression")
    ]
    actions.sort(
        key=lambda row: (
            -int(row.get("progression_score", 0)),
            row.get("eligibility") == "BLOCKED",
            str(row.get("transition_id") or ""),
        )
    )
    primary = actions[0] if actions else None
    return {
        "relation": relation,
        "section_index": section.get("section_index"),
        "eligibility": section.get("eligibility"),
        "conditions": list(section.get("conditions", ())),
        "primary_action": primary,
        "action_count": len(actions),
        "source_lines": section.get("source_lines"),
    }


def build_bounded_progression(progression: dict[str, Any]) -> dict[str, Any]:
    """Project at most one previous, current and next structural step.

    Blocked alternatives are counted, not expanded. This keeps the Character Editor focused on
    progression while leaving the complete section/action model available for explicit trace
    drill-downs.
    """
    if not progression.get("available"):
        return {
            "available": False,
            "steps": [],
            "blocked_alternatives": 0,
            "trace_policy": "on_demand",
        }

    sections = [
        row for row in progression.get("sections", ())
        if isinstance(row, dict)
    ]
    sections.sort(key=lambda row: int(row.get("section_index", -1)))
    current = progression.get("current_step")
    current_index = current.get("section_index") if isinstance(current, dict) else None

    previous = None
    next_step = None
    if current_index is not None:
        previous_candidates = [
            row for row in sections
            if int(row.get("section_index", -1)) < int(current_index)
        ]
        next_candidates = [
            row for row in sections
            if int(row.get("section_index", -1)) > int(current_index)
        ]
        if previous_candidates:
            previous = previous_candidates[-1]
        if next_candidates:
            # Prefer the nearest non-blocked structural step. If every future section is blocked,
            # retain the nearest one so the UI can explain the gate without expanding its graph.
            next_step = next(
                (row for row in next_candidates if row.get("eligibility") != "BLOCKED"),
                next_candidates[0],
            )

    steps = [
        step for step in (
            _step(previous, "previous"),
            _step(current, "current"),
            _step(next_step, "next"),
        )
        if step is not None
    ]
    visible_indexes = {step["section_index"] for step in steps}
    blocked_alternatives = sum(
        1 for row in sections
        if row.get("eligibility") == "BLOCKED"
        and row.get("section_index") not in visible_indexes
    )

    return {
        "available": True,
        "steps": steps,
        "previous": _step(previous, "previous"),
        "current": _step(current, "current"),
        "next": _step(next_step, "next"),
        "blocked_alternatives": blocked_alternatives,
        "visible_step_count": len(steps),
        "max_visible_steps": 3,
        "trace_policy": "on_demand",
        "trace_scope": "selected_step_or_edge",
    }


def annotate_bounded_progression(progression: dict[str, Any]) -> dict[str, Any]:
    progression["bounded"] = build_bounded_progression(progression)
    return progression
