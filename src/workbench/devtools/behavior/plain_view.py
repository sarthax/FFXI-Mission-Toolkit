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


def _descendants(
    seed: str,
    *,
    nodes: dict[str, dict[str, Any]],
    outgoing: dict[str, list[dict[str, Any]]],
    stop_at_callbacks: bool = False,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return bounded descendants, optionally treating nested callbacks as flow boundaries."""
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
            found.append((node, edge))
            if stop_at_callbacks and node.get("kind") == "callback":
                continue
            queue.append(target)
    return found


def _guard_requirements(
    rule_id: str,
    *,
    nodes: dict[str, dict[str, Any]],
    incoming: dict[str, list[dict[str, Any]]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Collect source-visible guards that feed a rule even though they are upstream edges."""
    rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for edge in incoming.get(rule_id, ()):
        if str(edge.get("kind") or "") != "GUARDS":
            continue
        source_id = str(edge.get("source") or "")
        condition = nodes.get(source_id)
        if condition is None:
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
            if upstream_node is None or upstream_id in seen:
                continue
            seen.add(upstream_id)
            rows.append((upstream_node, upstream))
    return rows


def _card(node: dict[str, Any], lane: str) -> dict[str, Any]:
    return {
        "node_id": node.get("id"),
        "kind": node.get("kind"),
        "label": _human_hook(node) if lane == "trigger" else _human_node(node),
        "technical_label": node.get("label") or node.get("id"),
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


def build_plain_behavior_projection(graph: dict[str, Any]) -> dict[str, Any]:
    """Return an admin-facing view of a technical behavior graph.

    Rule nodes plus raw helper call/callee plumbing are collapsed, but rule guards are deliberately
    retained as requirements. Nested callback nodes are explicit scheduling actions in their parent
    flow and form their own trigger flows, preventing callback effects from being duplicated in the
    scheduling hook. Resolved helper identity, helper inputs/effects, conditions, state, callbacks,
    targets, and exact technical node IDs remain available for evidence drill-down.
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

        def add_visible(node: dict[str, Any], edge: dict[str, Any], *, forced_lane: str | None = None) -> None:
            lane = forced_lane or _lane(node, edge)
            if lane == "trigger" or lane not in lanes:
                return
            node_id = str(node.get("id"))
            if node_id in seen_lane_ids[lane]:
                return
            seen_lane_ids[lane].add(node_id)
            lanes[lane].append(_card(node, lane))

        for node, edge in _descendants(
            str(trigger["id"]), nodes=nodes, outgoing=outgoing, stop_at_callbacks=True
        ):
            if node.get("kind") == "callback":
                add_visible(node, edge, forced_lane="actions")
                continue
            if node.get("kind") in _COLLAPSED_KINDS:
                collapsed.append(_card(node, "actions"))
                if node.get("kind") == "rule":
                    for requirement, guard_edge in _guard_requirements(
                        str(node.get("id")), nodes=nodes, incoming=incoming
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

    return {
        "available": bool(flows),
        "flows": flows,
        "summary": {
            "flow_count": len(flows),
            "collapsed_implementation_nodes": collapsed_total,
            "technical_node_count": len(graph_nodes),
        },
        "safety": {
            "evidence_preserved": True,
            "callback_flows_partitioned": True,
            "collapsed_kinds": sorted(_COLLAPSED_KINDS),
            "semantics": "Projection uses only extracted graph labels/edges; it does not infer runtime outcomes.",
        },
    }
