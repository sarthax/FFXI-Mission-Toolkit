#!/usr/bin/env python3
"""Export one exact-root Feature Trace for an independently reviewed P0 audit.

No Workbench host import, server connection, indexing, SQLite migration or writes.
Both existing databases are opened SQLite read-only/query-only; the raw evidence
is written only to an operator-selected NEW file outside the Git checkout.
The JSON is private observation material, NOT a scored first-screen acceptance.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from audit_feature_trace_relevance import audit_edge_ids

CASES = {
    "absolute-virtue": ("implementation", "entity"),
    "wotg-cait-sith": ("mission", "mission"),
    "ordinary-npc": ("implementation", "entity"),
}
DIRECTIONS = ("both", "out", "in")
MAX_NODES = 500


def open_readonly(path: Path) -> sqlite3.Connection:
    """Reject missing databases rather than silently constructing an empty one."""
    db = path.expanduser().resolve(strict=True)
    if not db.is_file():
        raise ValueError("Expected an existing SQLite database file")
    con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        return con
    except Exception:
        con.close()
        raise


def output_path(path: Path, *, repo: Path = ROOT) -> Path:
    selected = path.expanduser().resolve()
    if selected.is_relative_to(repo.resolve()):
        raise ValueError("Private trace exports must be stored outside the Toolkit Git checkout")
    if not selected.parent.is_dir():
        raise ValueError("Destination directory does not exist")
    if selected.exists():
        raise FileExistsError("Refusing to overwrite a previously exported trace")
    return selected


def collect(graph_con, catalog_con, *, case_id: str, root: str, depth: int = 1,
            direction: str = "both", service=None) -> dict:
    """Use the real Feature Trace facade with an exact, known, unambiguous ID."""
    if case_id not in CASES:
        raise ValueError("Unknown P0 campaign case")
    expected_mode, expected_kind = CASES[case_id]
    if not isinstance(root, str) or not root.strip() or root != root.strip() or root.startswith("@"):
        raise ValueError("Provide an exact canonical root ID from the Toolkit, not a search or @mode query")
    if isinstance(depth, bool) or not isinstance(depth, int) or depth not in (1, 2):
        raise ValueError("Audit depth must be 1 or 2")
    if direction not in DIRECTIONS:
        raise ValueError("Unsupported traversal direction")
    if service is None:
        from workbench.devtools.features import trace as service

    info = service.node_info(graph_con, root, catalog_con)
    if not isinstance(info, dict) or not info.get("known") or info.get("node_id") != root:
        raise ValueError("Exact root not found; resolve identity in Feature Trace before exporting")
    representations = info.get("representations") or []
    # Several source representations for the SAME explicit canonical node are normal:
    # do not confuse them with an unresolved name/numeric identity collision.
    if not representations or any(rep.get("node_id", root) != root for rep in representations):
        raise ValueError("Exact root has missing or conflicting source representations")

    result = service.trace(graph_con, root, depth, direction, catalog_con,
                           max_nodes=MAX_NODES, mode=expected_mode)
    if result.get("root") != root or result.get("root_kind") != expected_kind:
        raise ValueError("Trace root identity/kind differs from the named P0 case")
    if (result.get("trace_mode") or {}).get("id") != expected_mode:
        raise ValueError("Trace mode changed unexpectedly")
    edges = result.get("edges")
    if not isinstance(edges, list):
        raise ValueError("No edge list in Trace response; do not invent empty evidence")
    # Enforce stable identity before handing data to the existing audit scorer.
    # Generated IDs are audit-only hashes, never canonical graph relationships.
    ids = audit_edge_ids({"edges": edges})
    return {
        "schema": "feature-trace-relevance-export-v1",
        "case_id": case_id,
        "root": root,
        "root_kind": expected_kind,
        "mode": expected_mode,
        "depth": depth,
        "direction": direction,
        "max_nodes": MAX_NODES,
        "truncated": bool(result.get("truncated")),
        "edges": edges,
        "edge_audit_ids": ids,
        "nodes": result.get("nodes") or [],
        "paths": result.get("paths") or [],
        "provider_relationships": result.get("provider_relationships") or [],
        "evidence_boundary": (
            "Read-only local source/index evidence, not runtime verification. "
            "Initial visible edges and source correctness require independent manual annotations."
        ),
    }


def write_new(output: Path, exported: dict, *, repo: Path = ROOT) -> None:
    target = output_path(output, repo=repo)
    serialized = json.dumps(exported, ensure_ascii=False, indent=2, default=str) + "\n"
    with target.open("x", encoding="utf-8") as handle:
        handle.write(serialized)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=tuple(CASES), required=True)
    parser.add_argument("--root", required=True, help="Exact, uniquely resolved Feature Trace root ID")
    parser.add_argument("--graph-db", type=Path, default=ROOT / "workbench.db")
    parser.add_argument("--catalog-db", type=Path, default=ROOT / "ffxi_zone_database.db")
    parser.add_argument("--depth", type=int, default=1, choices=(1, 2))
    parser.add_argument("--direction", choices=DIRECTIONS, default="both")
    parser.add_argument("--output", type=Path, required=True, help="New private JSON file outside Git checkout")
    args = parser.parse_args(argv)

    # Validate export location first so no DB is opened for an unsafe destination.
    target = output_path(args.output)
    if not args.graph_db.is_file() or not args.catalog_db.is_file():
        parser.error("Both graph and catalog databases must already exist; no indexing is performed")
    graph = open_readonly(args.graph_db)
    try:
        catalog = open_readonly(args.catalog_db)
        try:
            export = collect(graph, catalog, case_id=args.case, root=args.root,
                             depth=args.depth, direction=args.direction)
        finally:
            catalog.close()
    finally:
        graph.close()
    write_new(target, export)
    # Do not print source filenames, exact entity IDs, SQL records or edge details.
    print(json.dumps({
        "status": "EXPORTED_NOT_REVIEWED",
        "case_id": args.case,
        "mode": export["mode"],
        "root_kind": export["root_kind"],
        "edge_count": len(export["edges"]),
        "truncated": export["truncated"],
        "source_review_required": True,
        "initial_visible_edges_unverified": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
