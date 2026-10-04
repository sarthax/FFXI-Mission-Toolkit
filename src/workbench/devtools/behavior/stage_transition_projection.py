"""Conservative stage-transition presentation evidence for Behavior Inspector.

This module does not change canonical scripted-behavior extraction. It composes two already
bounded facts for Clarified Flow: a source-proven named-state literal -> literal Event/CSID start,
and a direct literal write to that exact same canonical state inside a matching event-handler
branch. Cross-hook execution order remains explicitly unproven.
"""
from __future__ import annotations

import re
from typing import Any

from workbench.devtools.behavior.scripted_behavior_lsb_extract import (
    _close_count,
    _named_state_accesses,
    _open_count,
    _structural_lua_lines,
    extract_hook_blocks,
)

_LITERAL_BRANCH = re.compile(r"^\s*(if|elseif)\s+([A-Za-z_][A-Za-z0-9_]*)\s*==\s*(-?\d+)\s+then\b")


def _direct_event_state_writes(lua: str, event_ids: set[str]) -> list[dict[str, Any]]:
    """Return direct state writes in literal event-handler branches.

    Nested option/state/resource branches are deliberately excluded. A literal branch is only
    retained later when its event ID is already present in the projection's cross-hook event
    handoffs, so unrelated numeric branches cannot manufacture lifecycle links.
    """
    rows: list[dict[str, Any]] = []
    for block in extract_hook_blocks(lua):
        if block.hook not in {"onEventFinish", "onEventUpdate"}:
            continue
        raw = block.body.splitlines()
        structural = _structural_lua_lines(block.body)
        depth = 0
        active: dict[str, Any] | None = None

        def finish(end_index: int) -> None:
            nonlocal active
            if active is None:
                return
            event_id = str(active["event_id"])
            if event_id not in event_ids:
                active = None
                return
            branch_depth = int(active["branch_depth"])
            current_depth = branch_depth
            for index in range(int(active["start_index"]) + 1, end_index + 1):
                code = structural[index]
                if current_depth == branch_depth:
                    for access in _named_state_accesses(raw[index], start_line=block.start_line + index):
                        if access.get("access") != "WRITE":
                            continue
                        rows.append({
                            "hook": block.hook,
                            "event_id": active["event_id"],
                            "state_id": access.get("state_id"),
                            "state_name": access.get("name"),
                            "state_scope": access.get("scope"),
                            "receiver": access.get("receiver"),
                            "value": access.get("value"),
                            "source_line": access.get("line"),
                            "source": access.get("source_line"),
                            "relationship": "EVENT_HANDLER_DIRECT_STATE_WRITE",
                            "confidence": "VERIFIED",
                        })
                current_depth += _open_count(code) - _close_count(code)
            active = None

        for index, code in enumerate(structural):
            stripped = code.strip()
            if active is not None and depth == active["branch_depth"]:
                if re.match(r"^(?:elseif\b|else\b|end\b)", stripped):
                    finish(index - 1)
            match = _LITERAL_BRANCH.match(code)
            if match and active is None:
                form, _selector, literal = match.groups()
                active = {
                    "event_id": int(literal),
                    "start_index": index,
                    "branch_depth": depth + (1 if form == "if" else 0),
                }
            depth += _open_count(code) - _close_count(code)
        if active is not None:
            finish(len(raw) - 1)
    return rows


def _stage_value_continuity_links(lifecycles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compose exact same-state literal continuity without claiming execution order.

    A source lifecycle participates only when its direct handler evidence has exactly one unique
    next value. That value must identify exactly one lifecycle start for the same canonical state.
    Ambiguous writes and ambiguous destinations fail closed and emit no link.
    """
    starts: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in lifecycles:
        state_id = str(row.get("state_id") or "")
        from_value = str(row.get("from_value")) if row.get("from_value") is not None else ""
        if state_id and from_value:
            starts.setdefault((state_id, from_value), []).append(row)

    links: list[dict[str, Any]] = []
    for row in lifecycles:
        state_id = str(row.get("state_id") or "")
        values = {
            str(write.get("value"))
            for write in row.get("handler_writes") or []
            if isinstance(write, dict) and write.get("value") is not None
        }
        if not state_id or len(values) != 1:
            continue
        next_value = next(iter(values))
        targets = starts.get((state_id, next_value), [])
        if len(targets) != 1:
            continue
        target = targets[0]
        if target is row:
            continue
        links.append({
            "state_id": state_id,
            "state_name": row.get("state_name"),
            "from_value": row.get("from_value"),
            "via_event_id": row.get("event_id"),
            "next_value": next_value,
            "next_event_id": target.get("event_id"),
            "relationship": "SAME_STATE_LITERAL_CONTINUITY",
            "ordering": "UNPROVEN",
            "evidence_basis": "one verified direct handler write equals one verified start literal for the same canonical state",
        })
    return links


def apply_stage_transition_evidence(
    projection: dict[str, Any], lua: str
) -> dict[str, Any]:
    """Attach fail-closed stage lifecycle rows to an existing Plain Behavior projection."""
    starts = [row for row in projection.get("source_branch_evidence") or [] if isinstance(row, dict)]
    handoffs = {
        str(row.get("event_id")): row
        for row in projection.get("event_handoffs") or []
        if isinstance(row, dict) and row.get("event_id") is not None
    }
    relevant_events = set(handoffs)
    writes = _direct_event_state_writes(lua, relevant_events)

    lifecycles: list[dict[str, Any]] = []
    for start in starts:
        event_id = str(start.get("event_id"))
        handoff = handoffs.get(event_id)
        state_id = str(start.get("state_id") or "")
        if handoff is None or not state_id:
            continue
        matching = [
            row for row in writes
            if str(row.get("event_id")) == event_id
            and str(row.get("state_id") or "") == state_id
        ]
        if not matching:
            continue
        lifecycles.append({
            "state_id": state_id,
            "state_name": start.get("state_name"),
            "from_value": start.get("literal"),
            "event_id": start.get("event_id"),
            "start_hook": start.get("hook"),
            "start_guard_line": start.get("guard_line"),
            "start_event_line": start.get("event_line"),
            "handler_writes": matching,
            "handler_branches": list(handoff.get("handler_branches") or []),
            "relationship": "STAGE_EVENT_IDENTITY_HANDLER_WRITE",
            "ordering": handoff.get("ordering") or "UNPROVEN",
            "evidence_basis": "verified literal stage guard starts this event; matching literal event handler directly writes the same canonical state",
        })

    chain_links = _stage_value_continuity_links(lifecycles)
    projection["stage_lifecycles"] = lifecycles
    projection["stage_chain_links"] = chain_links
    projection.setdefault("summary", {})["stage_lifecycle_count"] = len(lifecycles)
    projection["summary"]["stage_chain_link_count"] = len(chain_links)
    projection.setdefault("safety", {})["stage_lifecycle_cross_hook_ordering"] = "UNPROVEN"
    projection["safety"]["stage_lifecycle_scope"] = "verified literal named-state event start + direct same-state write in matching literal event handler"
    projection["safety"]["stage_chain_ordering"] = "UNPROVEN"
    projection["safety"]["stage_chain_scope"] = "unique direct next-state literal matched to one verified start literal for the same canonical state"
    return projection
