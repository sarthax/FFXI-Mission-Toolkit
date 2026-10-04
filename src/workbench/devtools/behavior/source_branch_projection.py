"""Source-aware branch evidence for Plain Behavior presentation.

This adapter deliberately does not change the canonical scripted-behavior extractor or Technical
Graph.  It recovers a very small class of presentation relationships directly from the already
selected Lua source: a known named-state alias compared to a literal in an ``if``/``elseif`` whose
direct branch body starts one or more literal events.  Unsupported/dynamic predicates are ignored.
"""
from __future__ import annotations

import re
from typing import Any

from workbench.devtools.behavior.scripted_behavior_lsb_extract import (
    _START_EVENT,
    _close_count,
    _lit_int,
    _open_count,
    _state_aliases,
    _structural_lua_lines,
    extract_hook_blocks,
)

_ALIAS_LITERAL_BRANCH = re.compile(
    r"^\s*(if|elseif)\s+([A-Za-z_][A-Za-z0-9_]*)\s*==\s*"
    r"(-?\d+|true|false|['\"][^'\"]+['\"])\s+then\b"
)


def _literal_value(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] in "'\"" and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


def _direct_start_events(
    raw: list[str], structural: list[str], *, start_index: int, end_index: int, branch_depth: int
) -> list[dict[str, Any]]:
    """Return literal startEvent calls that occur directly in this branch, not nested children."""
    depth = branch_depth
    rows: list[dict[str, Any]] = []
    for index in range(start_index + 1, end_index + 1):
        code = structural[index]
        if depth == branch_depth:
            for match in _START_EVENT.finditer(code):
                rows.append({"event_id": _lit_int(match.group(1)), "line_offset": index})
        depth += _open_count(code) - _close_count(code)
    return rows


def source_state_event_branches(lua: str) -> list[dict[str, Any]]:
    """Recover exact named-state literal guard -> literal event-start relationships.

    The result is presentation evidence only.  Every returned relationship includes the source
    hook/line and canonical state identity derived by the existing state-alias parser.
    """
    rows: list[dict[str, Any]] = []
    for block in extract_hook_blocks(lua):
        raw = block.body.splitlines()
        structural = _structural_lua_lines(block.body)
        aliases = _state_aliases(block.body, start_line=block.start_line)
        depth = 0
        active: dict[str, Any] | None = None

        def finish(end_index: int) -> None:
            nonlocal active
            if active is None:
                return
            events = _direct_start_events(
                raw,
                structural,
                start_index=active["start_index"],
                end_index=max(active["start_index"], end_index),
                branch_depth=active["branch_depth"],
            )
            for event in events:
                state = active["state"]
                rows.append({
                    "hook": block.hook,
                    "state_id": state["state_id"],
                    "state_scope": state["scope"],
                    "state_name": state["name"],
                    "receiver": state["receiver"],
                    "selector_alias": active["alias"],
                    "literal": active["literal"],
                    "event_id": event["event_id"],
                    "guard_line": block.start_line + active["start_index"],
                    "guard_source": raw[active["start_index"]].strip(),
                    "event_line": block.start_line + event["line_offset"],
                    "event_source": raw[event["line_offset"]].strip(),
                    "relationship": "STATE_GUARDS_EVENT_START",
                    "confidence": "VERIFIED",
                })
            active = None

        for index, code in enumerate(structural):
            stripped = code.strip()
            if active is not None and depth == active["branch_depth"]:
                if re.match(r"^(?:elseif\b|else\b|end\b)", stripped):
                    finish(index - 1)

            match = _ALIAS_LITERAL_BRANCH.match(code)
            if match:
                form, alias, literal = match.groups()
                state = aliases.get(alias)
                if state is not None:
                    active = {
                        "alias": alias,
                        "literal": _literal_value(literal),
                        "state": state,
                        "start_index": index,
                        "branch_depth": depth + (1 if form == "if" else 0),
                    }
            depth += _open_count(code) - _close_count(code)

        if active is not None:
            finish(len(raw) - 1)

    return rows


def _effect_node_for_event(graph: dict[str, Any], event_id: Any) -> dict[str, Any] | None:
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict) or node.get("kind") != "effect":
            continue
        meta = node.get("meta") or {}
        if meta.get("effect") == "START_EVENT" and str(meta.get("value")) == str(event_id):
            return node
    return None


def apply_source_branch_evidence(
    projection: dict[str, Any], graph: dict[str, Any], lua: str
) -> dict[str, Any]:
    """Overlay bounded source-proven state->event branches onto a Plain Behavior projection."""
    evidence = source_state_event_branches(lua)
    if not evidence:
        projection["source_branch_evidence"] = []
        return projection

    groups = {
        str((group.get("trigger") or {}).get("technical_label") or ""): group
        for group in projection.get("branch_groups") or []
    }
    nodes = {str(node.get("id")): node for node in graph.get("nodes") or [] if isinstance(node, dict)}

    injected = 0
    for index, row in enumerate(evidence, 1):
        group = groups.get(str(row["hook"]))
        if group is None:
            continue
        state_node_id = f"state-node:{row['state_id']}"
        state_node = nodes.get(state_node_id)
        effect_node = _effect_node_for_event(graph, row["event_id"])
        guard_card = {
            "node_id": state_node_id if state_node is not None else None,
            "kind": "source_guard",
            "label": f"{row['state_name']} = {row['literal']}",
            "technical_label": row["guard_source"],
            "source_line": row["guard_line"],
            "value": row["literal"],
        }
        effect_card = {
            "node_id": effect_node.get("id") if effect_node else None,
            "kind": "effect",
            "label": f"Play cutscene / event {row['event_id']}",
            "technical_label": row["event_source"],
            "source_line": row["event_line"],
            "value": row["event_id"],
        }
        source_branch = {
            "branch_id": f"source-branch:{row['hook']}:{row['guard_line']}:{row['event_id']}:{index}",
            "technical_rule_ids": [],
            "guard_keys": [f"source:{row['state_id']}={row['literal']}"],
            "direct_requirements": [guard_card],
            "display_requirements": [guard_card],
            "requirements": [guard_card],
            "effects": [effect_card],
            "started_event_ids": [row["event_id"]],
            "guard_event_ids": [],
            "children": [],
            "source_line": row["guard_line"],
            "presentation_evidence": "SOURCE_LITERAL_BRANCH",
        }
        # Remove the unguarded START_EVENT card for this event from broad graph-derived roots.
        for branch in group.get("branches") or []:
            branch["effects"] = [
                card for card in branch.get("effects") or []
                if not (
                    str(card.get("value")) == str(row["event_id"])
                    and "START_EVENT" in str(card.get("technical_label") or "")
                )
            ]
        group.setdefault("branches", []).append(source_branch)
        group["branches"].sort(key=lambda branch: (branch.get("source_line") is None, branch.get("source_line") or 0, branch["branch_id"]))
        group["branch_count"] = int(group.get("branch_count") or 0) + 1
        injected += 1

    projection["source_branch_evidence"] = evidence
    projection["summary"]["source_branch_count"] = injected
    projection["summary"]["branch_count"] = sum(int(group.get("branch_count") or 0) for group in projection.get("branch_groups") or [])
    projection["safety"]["source_literal_branch_overlay"] = True
    projection["safety"]["source_literal_branch_scope"] = "known named-state alias == literal with direct literal startEvent only"

    # Rebuild event handoffs so source-proven start branches replace the broad unguarded event rule.
    from workbench.devtools.behavior.plain_view import _event_handoffs
    projection["event_handoffs"] = _event_handoffs(graph, projection.get("branch_groups") or [])
    projection["summary"]["event_handoff_count"] = len(projection["event_handoffs"])
    return projection
