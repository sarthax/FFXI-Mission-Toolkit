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
import sqlite3
from collections import deque
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = 1


def _json_value(raw):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw


def node_info(con: sqlite3.Connection, node_id: str) -> dict:
    sources = []
    queries = [
        ("entities", "entity_id", "entity_type", "display_name", "metadata_json"),
        ("features", "feature_id", "feature_type", "name", "metadata_json"),
        ("capabilities", "capability_id", "capability_type", "name", "notes_json"),
        ("functions", "function_id", "kind", "qualified_name", "notes_json"),
        ("bindings", "binding_id", "binding_system", "lua_name", "notes_json"),
        ("build_targets", "target_id", "build_system", "name", "notes_json"),
        ("artifacts", "artifact_id", "artifact_type", "path", "metadata_json"),
    ]
    for table, key, type_col, name_col, meta_col in queries:
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


def search_nodes(con: sqlite3.Connection, term: str) -> list[dict]:
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
          relationships: set[str] | None = None) -> dict:
    queue = deque([(root, 0, [root], [])])
    visited = {root}
    edges = []
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
    return {
        "schema": SCHEMA,
        "trace_id": f"trace:{root}:{depth}:{direction}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": root,
        "direction": direction,
        "max_depth": depth,
        "relationship_filter": sorted(relationships) if relationships else [],
        "nodes": [node_info(con, n) for n in node_ids],
        "edges": edges,
        "paths": paths,
        "notes": [
            "Trace connectivity is not an implementation verdict.",
            "Unrecorded relationships remain UNKNOWN rather than being inferred as absent.",
        ],
    }


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

    result = trace(con, root, args.depth, args.direction, set(args.relationship) or None)
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
