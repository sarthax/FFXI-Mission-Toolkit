#!/usr/bin/env python3
"""Trace a Workbench feature/entity through the canonical relationship graph.

This is intentionally domain-agnostic. It can start from any canonical node ID (or a
name search) and walk relationships in either direction. A trace is evidence navigation,
not an implementation verdict: absence of a path means the graph has no recorded edge,
not that the underlying game source is proven absent.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from workbench.core.services.feature_trace_catalog import catalog_node, is_runtime_edge, runtime_hierarchy, filter_runtime_observations, provider_relationships, search_catalog
from workbench.core.services import capture_integrity


SCHEMA = 1


def _json_value(raw):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw


def node_info(con: sqlite3.Connection, node_id: str, catalog_con: sqlite3.Connection | None = None) -> dict:
    indexed = catalog_node(con, node_id)
    if indexed is None and catalog_con is not None and catalog_con is not con:
        indexed = catalog_node(catalog_con, node_id)
    if indexed is not None:
        return indexed
    sources = []
    queries = [
        ("entities", "entity_id", "entity_type", "display_name", "metadata_json"),
        ("features", "feature_id", "feature_type", "name", "metadata_json"),
        ("capabilities", "capability_id", "capability_type", "name", "notes_json"),
        ("functions", "function_id", "kind", "qualified_name", "notes_json"),
        ("bindings", "binding_id", "binding_system", "lua_name", "notes_json"),
        ("build_targets", "target_id", "build_system", "name", "notes_json"),
        ("artifacts", "artifact_id", "artifact_type", "path", "metadata_json"),
        ("enum_definitions", "enum_id", "format", "symbol", "notes_json"),
    ]
    available = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table, key, type_col, name_col, meta_col in queries:
        if table not in available:
            continue
        row = con.execute(
            f"SELECT {key}, {type_col}, {name_col}, {meta_col} FROM {table} WHERE {key}=?",
            (node_id,),
        ).fetchone()
        if row:
            sources.append({
                "table": table,
                "node_id": row[0],
                "node_type": row[1],
                "display_name": row[2],
                "metadata": _json_value(row[3]) or {},
            })
    if sources:
        # Preserve all matches but expose the first deterministic representation as primary.
        sources.sort(key=lambda x: (x["table"], x["node_id"]))
        return {"node_id": node_id, "known": True, "representations": sources}
    return {"node_id": node_id, "known": False, "representations": []}


def search_nodes(con: sqlite3.Connection, term: str, catalog_con: sqlite3.Connection | None = None) -> list[dict]:
    """Search graph knowledge and the operational index without merging their facts."""
    sources = [con] if catalog_con is None or catalog_con is con else [con, catalog_con]
    rows, seen = [], set()
    for source in sources:
        for row in search_catalog(source, term):
            key = (row["node_id"], row.get("source"))
            if key not in seen:
                seen.add(key)
                rows.append(row)
    return sorted(rows, key=lambda row: (str(row.get("display_name") or "").casefold(), row["node_id"]))


def _legacy_search_nodes(con: sqlite3.Connection, term: str) -> list[dict]:
    pattern = f"%{term}%"
    matches = []
    queries = [
        ("entities", "entity_id", "entity_type", "display_name"),
        ("features", "feature_id", "feature_type", "name"),
        ("capabilities", "capability_id", "capability_type", "name"),
        ("functions", "function_id", "kind", "qualified_name"),
        ("bindings", "binding_id", "binding_system", "lua_name"),
        ("build_targets", "target_id", "build_system", "name"),
        ("artifacts", "artifact_id", "artifact_type", "path"),
        ("enum_definitions", "enum_id", "format", "symbol"),
    ]
    for table, key, type_col, name_col in queries:
        rows = con.execute(
            f"SELECT {key}, {type_col}, {name_col} FROM {table} "
            f"WHERE {key} LIKE ? OR {name_col} LIKE ? ORDER BY {key}",
            (pattern, pattern),
        ).fetchall()
        for node_id, node_type, display_name in rows:
            matches.append({
                "node_id": node_id,
                "node_type": node_type,
                "display_name": display_name,
                "table": table,
            })
    matches.sort(key=lambda x: (x["node_id"], x["table"]))
    return matches


def trace(con: sqlite3.Connection, root: str, depth: int, direction: str,
          catalog_con: sqlite3.Connection | None = None,
          relationships: set[str] | None = None, include_runtime_edges: bool = False) -> dict:
    queue = deque([(root, 0, [root], [])])
    visited = {root}
    seen_relationships = set()
    edges = []
    runtime_edges = []
    paths = []
    while queue:
        node, level, node_path, edge_path = queue.popleft()
        if level >= depth:
            continue
        params = [node]
        clauses = []
        if direction == "out":
            clauses = ["source_node=?"]
        elif direction == "in":
            clauses = ["target_node=?"]
        else:
            clauses = ["source_node=? OR target_node=?"]
            params = [node, node]
        sql = "SELECT relationship_id, source_node, target_node, relationship, evidence_id, confidence, status, metadata_json, source_snapshot_id FROM entity_relationships WHERE " + " AND ".join(clauses) + " ORDER BY relationship_id"
        rows = con.execute(sql, params).fetchall()
        for rid, src, dst, rel, evidence_id, confidence, status, metadata_json, snapshot_id in rows:
            if rid in seen_relationships:
                continue
            seen_relationships.add(rid)
            if relationships and rel not in relationships:
                continue
            if direction == "out" and src != node:
                continue
            if direction == "in" and dst != node:
                continue
            neighbor = dst if src == node else src
            traversed = "out" if src == node else "in"
            edge = {
                "relationship_id": rid,
                "source_node": src,
                "target_node": dst,
                "relationship": rel,
                "evidence_id": evidence_id,
                "confidence": confidence,
                "status": status,
                "metadata": _json_value(metadata_json) or {},
                "source_snapshot_id": snapshot_id,
                "from_node": node,
                "to_node": neighbor,
                "traversed_direction": traversed,
                "depth": level + 1,
            }
            if is_runtime_edge(edge):
                runtime_edges.append(edge)
                continue
            edges.append(edge)
            if neighbor not in visited:
                visited.add(neighbor)
                next_nodes = node_path + [neighbor]
                next_edges = edge_path + [rid]
                queue.append((neighbor, level + 1, next_nodes, next_edges))
                paths.append({
                    "root": root,
                    "nodes": next_nodes,
                    "edge_ids": next_edges,
                    "depth": level + 1,
                })

    node_ids = sorted(visited)
    hierarchy = runtime_hierarchy(runtime_edges)
    provider_links = provider_relationships(con, root)
    if catalog_con is not None and catalog_con is not con:
        provider_links.extend(
            link for link in provider_relationships(catalog_con, root)
            if link not in provider_links
        )
    result = {
        "schema": SCHEMA,
        "trace_id": f"trace:{root}:{depth}:{direction}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": root,
        "direction": direction,
        "max_depth": depth,
        "relationship_filter": sorted(relationships) if relationships else [],
        "nodes": [node_info(con, n, catalog_con) for n in node_ids],
        "edges": edges,
        "runtime_hierarchy": hierarchy,
        "runtime_observation_count": hierarchy["observation_count"],
        "runtime_group_count": hierarchy["group_count"],
        "runtime_capture_count": hierarchy["capture_count"],
        "provider_relationships": provider_links,
        "paths": paths,
        "notes": [
            "Trace connectivity is not an implementation verdict.",
            "Unrecorded relationships remain UNKNOWN rather than being inferred as absent.",
        ],
    }
    if include_runtime_edges:
        result["_runtime_edges"] = runtime_edges
    return result


def _capture_id_from_runtime_edge(edge: dict):
    meta = edge.get("metadata") or {}
    value = meta.get("capture_id") or meta.get("capture")
    if value is not None:
        text = str(value)
        return int(text.removeprefix("capture:")) if text.removeprefix("capture:").isdigit() else None
    for node in (edge.get("source_node"), edge.get("target_node")):
        text = str(node or "")
        if text.startswith("capture:") and text[8:].isdigit():
            return int(text[8:])
    return None


def _runtime_row_identity(con: sqlite3.Connection, edge: dict):
    """Resolve a runtime graph edge back to its normalized capture table/primary key."""
    meta = edge.get("metadata") or {}
    table = meta.get("capture_table")
    row_key = meta.get("capture_row_key")
    capture_id = _capture_id_from_runtime_edge(edge)
    if table and row_key is not None and capture_id is not None:
        return capture_id, str(table), row_key

    evidence_id = edge.get("evidence_id")
    if not evidence_id:
        return None
    exists = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='evidence'"
    ).fetchone()
    if not exists:
        return None
    row = con.execute(
        "SELECT source,location FROM evidence WHERE evidence_id=?",
        (evidence_id,),
    ).fetchone()
    if not row:
        return None
    source, location = row
    source = str(source or "")
    location = str(location or "")

    if source == "capture_events":
        m = re.match(r"^capture:(\d+):(.+):(\d+)$", location)
        if m:
            return int(m.group(1)), "capture_events", {
                "zone_db": m.group(2), "seq": int(m.group(3)),
            }
    if source == "capture_actions":
        m = re.match(r"^capture:(\d+):action:(.+)$", location)
        if m:
            return int(m.group(1)), "capture_actions", {"action_key": m.group(2)}
    if source == "capture_raw_packets":
        m = re.match(r"^capture:(\d+):packet:(\d+)$", location)
        if m:
            return int(m.group(1)), "capture_raw_packets", {"seq": int(m.group(2))}
    if source == "capture_eventview":
        m = re.match(r"^capture:(\d+):eventview:(.+):(\d+)$", location)
        if m:
            return int(m.group(1)), "capture_eventview", {
                "zone_db": m.group(2), "seq": int(m.group(3)),
            }
    return None


def enrich_runtime_capture_provenance(
    graph_con: sqlite3.Connection,
    capture_con: sqlite3.Connection | None,
    observations: list[dict],
) -> list[dict]:
    if capture_con is None:
        return observations
    out = []
    for edge in observations:
        item = dict(edge)
        identity = _runtime_row_identity(graph_con, item)
        locators = []
        if identity is not None:
            capture_id, target_table, row_key = identity
            locators = capture_integrity.find_row_locators(
                capture_con, capture_id, target_table, row_key
            )
            canonical_key = capture_integrity.canonical_row_key(row_key)
            for locator in locators:
                locator["capture_id"] = capture_id
                locator["normalized_table"] = target_table
                locator["normalized_row_key"] = canonical_key
        item["capture_provenance"] = locators
        out.append(item)
    return out


def runtime_observation_page(con: sqlite3.Connection, root: str, depth: int, direction: str,
                             catalog_con: sqlite3.Connection | None = None, opcode: str | None = None,
                             capture_id: str | None = None, offset: int = 0, limit: int = 100) -> dict:
    traced=trace(con,root,depth,direction,catalog_con,include_runtime_edges=True)
    page=filter_runtime_observations(traced.pop("_runtime_edges",[]),opcode,capture_id,offset,limit)
    page["observations"]=enrich_runtime_capture_provenance(
        con, catalog_con, page["observations"]
    )
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path("workbench.db"))
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--node")
    group.add_argument("--name", help="Case-insensitive partial name/ID search; one match is required.")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--direction", choices=("out", "in", "both"), default="both")
    ap.add_argument("--relationship", action="append", default=[],
                    help="Limit traversal to this relationship; repeat for multiple types.")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    if args.depth < 0:
        ap.error("--depth must be >= 0")

    con = sqlite3.connect(args.db)
    root = args.node
    matches = []
    if args.name:
        matches = search_nodes(con, args.name)
        if len(matches) != 1:
            print(json.dumps({
                "schema": SCHEMA,
                "status": "AMBIGUOUS" if matches else "NOT_FOUND",
                "query": args.name,
                "matches": matches,
            }, indent=2))
            return 2
        root = matches[0]["node_id"]

    result = trace(con, root, args.depth, args.direction, relationships=set(args.relationship) or None)
    con.close()
    output = json.dumps(result, indent=2, sort_keys=True)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
