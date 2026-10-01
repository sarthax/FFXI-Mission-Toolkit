"""Generic presentation-state helpers for dependency graph explorers.

These functions never alter closure records.  They derive the initial disclosure,
branch visibility, and directed root path from a canonical closure projection.
"""
from __future__ import annotations

from collections import deque
from typing import Any


def edge_key(edge: dict[str, Any]) -> str:
    return str(edge.get("edge_id") or f"{edge.get('source_node')}|{edge.get('relationship')}|{edge.get('target_node')}")


def _outgoing(projection: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    return [edge for edge in projection.get("edges", []) if edge.get("source_node") == node_id]


def direct_dependencies(projection: dict[str, Any], node_id: str) -> set[str]:
    """Return immediate prerequisite nodes, retaining any gate between parent and child."""
    node_types = {node["node_id"]: node.get("node_type") for node in projection.get("nodes", [])}
    result: set[str] = set()
    for edge in _outgoing(projection, node_id):
        target = edge["target_node"]
        result.add(target)
        if node_types.get(target) == "REQUIREMENT_GATE":
            result.update(child["target_node"] for child in _outgoing(projection, target))
    return result


def visible_nodes(projection: dict[str, Any], expanded: set[str]) -> set[str]:
    """Return union of branches reachable from root through explicitly expanded nodes."""
    root = projection["root"]
    node_types = {node["node_id"]: node.get("node_type") for node in projection.get("nodes", [])}
    visible: set[str] = set()

    def walk(node_id: str, ancestry: set[str]) -> None:
        visible.add(node_id)
        if node_id not in expanded or node_id in ancestry:
            return
        for edge in _outgoing(projection, node_id):
            target = edge["target_node"]
            visible.add(target)
            if node_types.get(target) == "REQUIREMENT_GATE":
                for child in _outgoing(projection, target):
                    visible.add(child["target_node"])
                    walk(child["target_node"], ancestry | {node_id, target})
            else:
                walk(target, ancestry | {node_id})

    walk(root, set())
    return visible


def path_from_root(projection: dict[str, Any], target: str) -> tuple[set[str], set[str]]:
    """Return a shortest directed root path as node IDs and edge keys."""
    root = projection["root"]
    queue = deque([(root, [root], [])])
    seen = {root}
    while queue:
        node_id, nodes, edges = queue.popleft()
        if node_id == target:
            return set(nodes), set(edges)
        for edge in _outgoing(projection, node_id):
            child = edge["target_node"]
            if child not in seen:
                seen.add(child)
                queue.append((child, [*nodes, child], [*edges, edge_key(edge)]))
    return set(), set()


def initial_presentation(projection: dict[str, Any]) -> dict[str, Any]:
    expanded = {projection["root"]}
    return {
        "initial_expanded": sorted(expanded),
        "initial_visible_nodes": sorted(visible_nodes(projection, expanded)),
    }
