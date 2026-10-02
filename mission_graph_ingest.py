#!/usr/bin/env python3
"""Compatibility CLI/import wrapper for Development mission graph projection."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from workbench.core import graph as graph_store
from workbench.devtools.missions import graph_ingest as _canonical


def main() -> None:
    ap=argparse.ArgumentParser(description=_canonical.__doc__)
    ap.add_argument("lua",type=Path,help="LSB Mission/Quest Lua source file")
    ap.add_argument("--feature-id",required=True,help="Canonical feature id, e.g. mission:cop:ancient-vows")
    ap.add_argument("--feature-name",help="Human-readable feature name")
    ap.add_argument("--snapshot",help="Source snapshot/build id")
    ap.add_argument("--db",type=Path,default=Path("workbench.db"),help="Workbench DB path")
    ap.add_argument("--write",action="store_true",help="Persist projected records; default is preview only")
    args=ap.parse_args()

    lua=args.lua.read_text(encoding="utf-8",errors="ignore")
    projection=_canonical.extract_and_project_lsb_mission(
        lua,
        feature_id=args.feature_id,
        feature_name=args.feature_name,
        source_path=str(args.lua),
        source_snapshot_id=args.snapshot,
    )

    print(f"feature: {projection.feature.feature_id} ({projection.feature.name})")
    print(f"source: {projection.artifact.path}")
    print(f"entities: {len(projection.entities)}")
    print(f"edges: {len(projection.edges)}")
    print(f"evidence: {len(projection.evidence)}")
    print(f"implementation: {projection.implementation.status}")
    metrics=projection.feature.metadata.get("extraction_metrics") or {}
    if metrics:
        print(
            "extraction: "
            f"handlers {metrics.get('modeled_source_handler_count',0)}/{metrics.get('source_handler_count',0)} modeled; "
            f"{metrics.get('branch_transition_count',0)} branch transitions; "
            f"{metrics.get('event_chains',0)} event chains; "
            f"{metrics.get('unmodeled_source_handler_count',0)} unmodeled handlers"
        )
    if not args.write:
        print("preview only; pass --write to persist")
        return

    con=graph_store.init_db(args.db)
    try:
        _canonical.persist_mission_graph(con,projection)
    finally:
        con.close()
    print(f"persisted to: {args.db}")


if __name__=="__main__":
    main()
else:
    sys.modules[__name__] = _canonical
