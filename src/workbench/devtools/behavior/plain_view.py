"""Evidence-preserving projection for the Behavior Inspector Plain Behavior view.

This module turns the technical behavior graph into a smaller admin-facing projection without
inventing gameplay semantics. It deliberately removes implementation scaffolding while keeping
the exact technical node IDs needed for drill-down into the graph inspector.
"""
from __future__ import annotations

from collections import deque
from typing import Any


_TRIGGER_KINDS = {"hook", "callback"}
_REQUIREMENT_KINDS = {"condition", "helper_input"}
_RESULT_KINDS = {"state", "target", "helper_effect"}
_COLLAPSED_KINDS = {"rule", "helper_call", "shared_helper_callee"}
_GUARD_EDGE_KINDS = {"GUARDS", "STATE_GUARD", "STATE_READ", "EVENT_GUARD", "EVENT_OUTCOME_GUARD"}


def _human_hook(node: dict[str, Any]) -> str:
    raw = str(node.get("label") or node.get("id") or "Behavior")
    low = raw.lower()
    mappings = (
        (("ontrigger",), "Player interacts with this actor"),
        (("ontrade",), "Player trades an item"),
        (("onmobdeath", "ondeath"), "Actor is defeated"),
        (("onmobspawn", "onspawn"), "Actor spawns"),
        (("onmobfight", "onfight"), "During combat"),
        (("onmobengaged", "onengaged"), "Combat starts"),
        (("onmobdisengage", "ondisengage"), "Combat ends"),
        (("oneventfinish",), "A cutscene or event finishes"),
        (("oneventupdate",), "A cutscene or event updates"),
        (("timer",), "A timer or delayed action fires"),
        (("queue",), "A queued action fires"),
        (("listener",), "A registered game event fires"),
    )
    for needles, label in mappings:
        if any(needle in low for needle in needles):
            return label
    return raw.rsplit(":", 1)[-1].rsplit(".", 1)[-1].replace("_", " ").replace("-", " ")


def _human_node(node: dict[str, Any]) -> str:
    meta = node.get("meta") or {}
    raw = str(node.get("label") or meta.get("value") or node.get("id") or "Behavior step")
    low = raw.lower()
    value = "" if meta.get("value") is None else str(meta.get("value"))

    if node.get("kind") == "callback":
        callback_type = str(meta.get("callback_type") or raw).lower()
        if "listener" in callback_type:
            event = meta.get("callback_event")
            return f"Register event listener{': ' + str(event) if event else ''}"
        if "queue" in callback_type:
            return "Queue a delayed action"
        return "Schedule a timer / delayed action"
    if node.get("kind") == "state":
        return f"Character/game state: {raw.rsplit(':', 1)[-1]}"
    if node.get("kind") == "event":
        return f"Event / CSID {meta.get('event_id') if meta.get('event_id') is not None else value or raw}"
    if node.get("kind") == "event_outcome":
        selector = meta.get("selector") or "outcome"
        literal = meta.get("literal") if meta.get("literal") is not None else value
        return f"{selector} = {literal}"
    if node.get("kind") == "condition":
        upper = raw.upper()
        subject = raw
        for operator in (
            "EVENT_OUTCOME_EQUALS", "EVENT_ID_EQUALS", "STATE_EQUALS", "READS_STATE",
            "HAS_KEY_ITEM", "NOT_HAS_KEY_ITEM", "HAS_ITEM", "TRADE_HAS_EXACTLY", "TRADE_HAS",
        ):
            if operator in upper:
                subject = raw[:upper.index(operator)].strip()
                if operator == "EVENT_ID_EQUALS":
                    return f"Event / CSID = {value}"
                if operator == "EVENT_OUTCOME_EQUALS":
                    return f"{subject.rsplit(':', 1)[-1] or 'outcome'} = {value}"
                if operator == "STATE_EQUALS":
                    return f"{subject.rsplit(':', 1)[-1]} = {value}"
                if operator == "READS_STATE":
                    return f"Reads {subject.rsplit(':', 1)[-1]}"
                if operator == "HAS_KEY_ITEM":
                    return f"Has key item{': ' + value if value else ''}"
                if operator == "NOT_HAS_KEY_ITEM":
                    return f"Does not have key item{': ' + value if value else ''}"
                if operator == "HAS_ITEM":
                    return f"Has item{': ' + value if value else ''}"
                if operator == "TRADE_HAS_EXACTLY":
                    return f"Trade exactly{': ' + value if value else ''}"
                if operator == "TRADE_HAS":
                    return f"Trade contains{': ' + value if value else ''}"
    checks = (
        ("getcharvar", "Check character progress"),
        ("haskeyitem", "Requires a key item"),
        ("hasitem", "Requires an item"),
    )
    for needle, label in checks:
        if needle in low:
            return f"{label}{': ' + value if value else ''}"
    effects = (
        ("setcharvar", "Update character progress"),
        ("givekeyitem", "Give key item"),
        ("addkeyitem", "Give key item"),
        ("delkeyitem", "Remove key item"),
        ("giveitem", "Give item"),
        ("additem", "Give item"),
        ("delitem", "Remove item"),
        ("startevent", "Play cutscene / event"),
        ("completemission", "Complete mission"),
        ("addmission", "Start / advance mission"),
        ("completequest", "Complete quest"),
        ("addquest", "Start quest"),
    )
    for needle, label in effects:
        if needle in low:
            return f"{label}{' ' + value if value and needle == 'startevent' else ': ' + value if value else ''}"
    if "title" in low:
        return f"Change title{': ' + value if value else ''}"
    if "gil" in low:
        return f"Change gil{': ' + value if value else ''}"
    if "despawn" in low:
        return "Despawn or disable an actor"
    if "spawn" in low:
        return "Spawn or enable an actor"
    if "status" in low:
        return f"Change actor status{': ' + value if value else ''}"
    return raw.rsplit(":", 1)[-1].rsplit(".", 1)[-1].replace("_", " ").replace("-", " ")


def _lane(node: dict[str, Any], edge: dict[str, Any] | None = None) -> str:
    kind = str(node.get("kind") or "")
    meta = node.get("meta") or {}
    text = f"{node.get('label') or ''} {meta.get('effect') or ''} {meta.get('value') or ''}".lower()
    edge_kind = str((edge or {}).get("kind") or "").lower()
    if kind in _TRIGGER_KINDS or kind == "subject":
        return "trigger"
    if kind in _REQUIREMENT_KINDS or "read" in edge_kind or any(
        needle in text for needle in ("getcharvar", "hasitem", "haskeyitem", "getquest", "getcurrentmission")
    ):
        return "requirements"
    if kind in _RESULT_KINDS or "write" in edge_kind or any(
        needle in text
        for needle in (
            "setcharvar", "give", "additem", "delitem", "addmission", "completemission",
            "addquest", "completequest", "title",
        )
    ):
        return "results"
    return "actions"


def _source_line(node: dict[str, Any]) -> int | None:
    meta = node.get("meta") or {}
    nested = meta.get("metadata") or {}
    for value in (nested.get("source_line"), meta.get("source_line")):
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            continue
    return None


def _in_ranges(node: dict[str, Any], ranges: tuple[tuple[int, int], ...]) -> bool:
    line = _source_line(node)
    return line is not None and any(start <= line <= end for start, end in ranges)


def _scheduled_callback_ranges(
    seed: str,
    *,
    nodes: dict[str, dict[str, Any]],
    outgoing: dict[str, list[dict[str, Any]]],
) -> tuple[tuple[int, int], ...]:
    ranges: list[tuple[int, int]] = []
    for edge in outgoing.get(seed, ()):
        target = nodes.get(str(edge.get("target") or ""))
        if target is None or target.get("kind") != "callback":
            continue
        source_lines = (target.get("meta") or {}).get("source_lines")
        if not isinstance(source_lines, (list, tuple)) or len(source_lines) != 2:
            continue
        try:
            ranges.append((int(source_lines[0]), int(source_lines[1])))
        except (TypeError, ValueError):
            continue
    return tuple(ranges)


def _descendants(
    seed: str,
    *,
    nodes: dict[str, dict[str, Any]],
    outgoing: dict[str, list[dict[str, Any]]],
    stop_at_callbacks: bool = False,
    blocked_source_ranges: tuple[tuple[int, int], ...] = (),
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return bounded descendants while respecting callback presentation boundaries."""
    found: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen = {seed}
    queue: deque[str] = deque([seed])
    while queue:
        current = queue.popleft()
        for edge in outgoing.get(current, ()):
            target = str(edge.get("target") or "")
            if not target or target in seen:
                continue
            seen.add(target)
            node = nodes.get(target)
            if node is None:
                continue
            if node.get("kind") == "callback":
                found.append((node, edge))
                if stop_at_callbacks:
                    continue
            elif blocked_source_ranges and _in_ranges(node, blocked_source_ranges):
                continue
            else:
                found.append((node, edge))
            queue.append(target)
    return found


def _guard_requirements(
    rule_id: str,
    *,
    nodes: dict[str, dict[str, Any]],
    incoming: dict[str, list[dict[str, Any]]],
    blocked_source_ranges: tuple[tuple[int, int], ...] = (),
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Collect source-visible guards that feed a rule even though they are upstream edges."""
    rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for edge in incoming.get(rule_id, ()):
        if str(edge.get("kind") or "") != "GUARDS":
            continue
        source_id = str(edge.get("source") or "")
        condition = nodes.get(source_id)
        if condition is None or _in_ranges(condition, blocked_source_ranges):
            continue
        if source_id not in seen:
            seen.add(source_id)
            rows.append((condition, edge))
        for upstream in incoming.get(source_id, ()):
            upstream_kind = str(upstream.get("kind") or "")
            if upstream_kind not in _GUARD_EDGE_KINDS:
                continue
            upstream_id = str(upstream.get("source") or "")
            upstream_node = nodes.get(upstream_id)
            if upstream_node is None or upstream_id in seen or _in_ranges(upstream_node, blocked_source_ranges):
                continue
            seen.add(upstream_id)
            rows.append((upstream_node, upstream))
    return rows


def _card(node: dict[str, Any], lane: str) -> dict[str, Any]:
    meta = node.get("meta") or {}
    return {
        "node_id": node.get("id"),
        "kind": node.get("kind"),
        "label": _human_hook(node) if lane == "trigger" else _human_node(node),
        "technical_label": node.get("label") or node.get("id"),
        "source_line": _source_line(node),
        "value": meta.get("value"),
    }


def _summary(trigger_label: str, lanes: dict[str, list[dict[str, Any]]]) -> str:
    parts = [trigger_label.rstrip(".") + "."]
    if lanes["requirements"]:
        labels = [row["label"] for row in lanes["requirements"][:2]]
        suffix = f" (+{len(lanes['requirements']) - 2} more)" if len(lanes["requirements"]) > 2 else ""
        parts.append("Checks " + "; ".join(labels) + suffix + ".")
    if lanes["actions"]:
        labels = [row["label"] for row in lanes["actions"][:2]]
        suffix = f" (+{len(lanes['actions']) - 2} more)" if len(lanes["actions"]) > 2 else ""
        parts.append("Then " + "; ".join(labels) + suffix + ".")
    if lanes["results"]:
        labels = [row["label"] for row in lanes["results"][:2]]
        suffix = f" (+{len(lanes['results']) - 2} more)" if len(lanes["results"]) > 2 else ""
        parts.append("Results: " + "; ".join(labels) + suffix + ".")
    return " ".join(parts)


def _condition_signature(node: dict[str, Any]) -> str:
    meta = node.get("meta") or {}
    return f"{node.get('label') or node.get('id')}|{meta.get('value')!r}"


def _dedupe_cards(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("label") or ""), str(row.get("technical_label") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _branch_groups(
    triggers: list[dict[str, Any]],
    *,
    nodes: dict[str, dict[str, Any]],
    outgoing: dict[str, list[dict[str, Any]]],
    incoming: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Build a branch tree using only exact rule guards and rule-emitted effects.

    A child branch is nested under another branch only when its direct guard set is a strict
    superset of the parent guard set. This preserves source-proven event -> outcome -> nested guard
    structure without treating sibling effects as ordered execution steps.
    """
    result: list[dict[str, Any]] = []
    for trigger in triggers:
        callback_ranges = _scheduled_callback_ranges(str(trigger["id"]), nodes=nodes, outgoing=outgoing)
        rule_nodes = []
        for edge in outgoing.get(str(trigger["id"]), ()):
            target = nodes.get(str(edge.get("target") or ""))
            if target is not None and target.get("kind") == "rule":
                rule_nodes.append(target)

        grouped: dict[tuple[str, ...], dict[str, Any]] = {}
        for rule in rule_nodes:
            rid = str(rule["id"])
            direct_guards: list[dict[str, Any]] = []
            guard_keys: list[str] = []
            for edge in incoming.get(rid, ()):
                if str(edge.get("kind") or "") != "GUARDS":
                    continue
                condition = nodes.get(str(edge.get("source") or ""))
                if condition is None or _in_ranges(condition, callback_ranges):
                    continue
                direct_guards.append(condition)
                guard_keys.append(_condition_signature(condition))
            key = tuple(sorted(set(guard_keys)))
            entry = grouped.setdefault(key, {
                "branch_id": rid,
                "technical_rule_ids": [],
                "guard_keys": list(key),
                "direct_requirements": [],
                "requirements": [],
                "effects": [],
                "started_event_ids": [],
                "guard_event_ids": [],
                "children": [],
                "source_line": _source_line(rule),
            })
            entry["technical_rule_ids"].append(rid)
            entry["direct_requirements"].extend(_card(row, "requirements") for row in direct_guards)
            entry["requirements"].extend(
                _card(row, "requirements")
                for row, _edge in _guard_requirements(
                    rid, nodes=nodes, incoming=incoming, blocked_source_ranges=callback_ranges
                )
            )
            for guard in direct_guards:
                label = str(guard.get("label") or "")
                if "EVENT_ID_EQUALS" in label.upper():
                    value = (guard.get("meta") or {}).get("value")
                    if value is not None and value not in entry["guard_event_ids"]:
                        entry["guard_event_ids"].append(value)
            for edge in outgoing.get(rid, ()):
                if str(edge.get("kind") or "") != "EMITS":
                    continue
                effect = nodes.get(str(edge.get("target") or ""))
                if effect is None or _in_ranges(effect, callback_ranges):
                    continue
                card = _card(effect, _lane(effect, edge))
                entry["effects"].append(card)
                meta = effect.get("meta") or {}
                if meta.get("effect") == "START_EVENT" and meta.get("value") is not None:
                    event_id = meta.get("value")
                    if event_id not in entry["started_event_ids"]:
                        entry["started_event_ids"].append(event_id)

        branches = list(grouped.values())
        for branch in branches:
            branch["direct_requirements"] = _dedupe_cards(branch["direct_requirements"])
            branch["requirements"] = _dedupe_cards(branch["requirements"])
            branch["effects"] = _dedupe_cards(branch["effects"])

        by_id = {branch["branch_id"]: branch for branch in branches}
        parent_for: dict[str, str] = {}
        for branch in branches:
            keys = set(branch["guard_keys"])
            if not keys:
                continue
            candidates = [
                candidate for candidate in branches
                if candidate is not branch
                and candidate["guard_keys"]
                and set(candidate["guard_keys"]) < keys
            ]
            if candidates:
                parent = max(candidates, key=lambda row: (len(row["guard_keys"]), -(row.get("source_line") or 0)))
                parent_for[branch["branch_id"]] = parent["branch_id"]

        roots: list[dict[str, Any]] = []
        for branch in branches:
            parent_id = parent_for.get(branch["branch_id"])
            parent = by_id.get(parent_id) if parent_id else None
            if parent is None:
                branch["display_requirements"] = list(branch["direct_requirements"])
                roots.append(branch)
                continue
            parent_keys = set(parent["guard_keys"])
            branch["display_requirements"] = [
                row for row in branch["direct_requirements"]
                if not any(key.startswith(str(row.get("technical_label") or "") + "|") for key in parent_keys)
            ]
            if not branch["display_requirements"]:
                branch["display_requirements"] = list(branch["direct_requirements"])
            parent["children"].append(branch)

        def sort_tree(rows: list[dict[str, Any]]) -> None:
            rows.sort(key=lambda row: (row.get("source_line") is None, row.get("source_line") or 0, row["branch_id"]))
            for row in rows:
                sort_tree(row["children"])

        sort_tree(roots)
        result.append({
            "trigger": _card(trigger, "trigger"),
            "branches": roots,
            "branch_count": len(branches),
        })
    return result


def _flatten_branches(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    stack = list(reversed(rows))
    while stack:
        row = stack.pop()
        result.append(row)
        stack.extend(reversed(row.get("children") or []))
    return result


def _event_handoffs(graph: dict[str, Any], branch_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    starts: dict[str, list[dict[str, str]]] = {}
    handlers: dict[str, list[dict[str, str]]] = {}
    for group in branch_groups:
        trigger = group.get("trigger") or {}
        trigger_id = str(trigger.get("node_id") or "")
        trigger_label = str(trigger.get("label") or trigger_id)
        for branch in _flatten_branches(group.get("branches") or []):
            ref = {"branch_id": str(branch.get("branch_id")), "trigger_id": trigger_id, "trigger_label": trigger_label}
            for event_id in branch.get("started_event_ids") or []:
                starts.setdefault(str(event_id), []).append(ref)
            for event_id in branch.get("guard_event_ids") or []:
                handlers.setdefault(str(event_id), []).append(ref)

    rows: list[dict[str, Any]] = []
    for link in graph.get("event_links") or []:
        event_id = link.get("event_id")
        key = str(event_id)
        start_refs = starts.get(key, [])
        handler_refs = handlers.get(key, [])
        if not start_refs or not handler_refs:
            continue
        rows.append({
            "event_id": event_id,
            "relationship": link.get("relationship") or "SHARED_EVENT_ID_ACROSS_HOOKS",
            "ordering": link.get("ordering") or "UNPROVEN",
            "evidence_basis": link.get("evidence_basis") or "same literal event identity appears across hooks",
            "start_branches": start_refs,
            "handler_branches": handler_refs,
        })
    return rows


def build_plain_behavior_projection(graph: dict[str, Any]) -> dict[str, Any]:
    """Return an admin-facing view of a technical behavior graph.

    The compatibility `flows` contract remains available, while `branch_groups` is the preferred
    presentation for complex mission/instance logic. Branch nesting is derived only from exact
    rule guard-set containment. Cross-hook event matches remain identity handoffs with explicitly
    unproven ordering rather than causal execution edges.
    """
    graph_nodes = [row for row in graph.get("nodes", ()) if isinstance(row, dict) and row.get("id")]
    nodes = {str(row["id"]): row for row in graph_nodes}
    outgoing: dict[str, list[dict[str, Any]]] = {}
    incoming: dict[str, list[dict[str, Any]]] = {}
    for edge in graph.get("edges", ()):
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        outgoing.setdefault(source, []).append(edge)
        incoming.setdefault(target, []).append(edge)

    triggers = [row for row in graph_nodes if row.get("kind") in _TRIGGER_KINDS]
    if not triggers:
        triggers = [row for row in graph_nodes if row.get("kind") == "subject"][:1]

    flows: list[dict[str, Any]] = []
    collapsed_total = 0
    for trigger in triggers:
        lanes: dict[str, list[dict[str, Any]]] = {"requirements": [], "actions": [], "results": []}
        seen_lane_ids: dict[str, set[str]] = {key: set() for key in lanes}
        collapsed: list[dict[str, Any]] = []
        callback_ranges = _scheduled_callback_ranges(str(trigger["id"]), nodes=nodes, outgoing=outgoing)

        def add_visible(node: dict[str, Any], edge: dict[str, Any], *, forced_lane: str | None = None) -> None:
            if callback_ranges and node.get("kind") != "callback" and _in_ranges(node, callback_ranges):
                return
            lane = forced_lane or _lane(node, edge)
            if lane == "trigger" or lane not in lanes:
                return
            node_id = str(node.get("id"))
            if node_id in seen_lane_ids[lane]:
                return
            seen_lane_ids[lane].add(node_id)
            lanes[lane].append(_card(node, lane))

        for node, edge in _descendants(
            str(trigger["id"]), nodes=nodes, outgoing=outgoing,
            stop_at_callbacks=True, blocked_source_ranges=callback_ranges,
        ):
            if node.get("kind") == "callback":
                add_visible(node, edge, forced_lane="actions")
                continue
            if node.get("kind") in _COLLAPSED_KINDS:
                collapsed.append(_card(node, "actions"))
                if node.get("kind") == "rule":
                    for requirement, guard_edge in _guard_requirements(
                        str(node.get("id")), nodes=nodes, incoming=incoming,
                        blocked_source_ranges=callback_ranges,
                    ):
                        add_visible(requirement, guard_edge, forced_lane="requirements")
                continue
            add_visible(node, edge)

        trigger_card = _card(trigger, "trigger")
        collapsed_total += len(collapsed)
        flows.append({
            "trigger": trigger_card,
            "requirements": lanes["requirements"],
            "actions": lanes["actions"],
            "results": lanes["results"],
            "summary": _summary(trigger_card["label"], lanes),
            "collapsed_implementation_nodes": collapsed,
            "collapsed_count": len(collapsed),
        })

    branch_groups = _branch_groups(triggers, nodes=nodes, outgoing=outgoing, incoming=incoming)
    handoffs = _event_handoffs(graph, branch_groups)
    return {
        "available": bool(flows),
        "presentation": "branch_tree_v1",
        "flows": flows,
        "branch_groups": branch_groups,
        "event_handoffs": handoffs,
        "summary": {
            "flow_count": len(flows),
            "branch_group_count": len(branch_groups),
            "branch_count": sum(group.get("branch_count", 0) for group in branch_groups),
            "event_handoff_count": len(handoffs),
            "collapsed_implementation_nodes": collapsed_total,
            "technical_node_count": len(graph_nodes),
        },
        "safety": {
            "evidence_preserved": True,
            "branch_nesting_from_guard_containment_only": True,
            "cross_hook_ordering_inferred": False,
            "callback_flows_partitioned": True,
            "callback_overlap_filtered_by_source_span": True,
            "collapsed_kinds": sorted(_COLLAPSED_KINDS),
            "semantics": "Projection uses only extracted graph labels/edges/source spans; cross-hook event identity does not imply runtime order.",
        },
    }
