#!/usr/bin/env python3
"""Extract one LSB mission/quest Lua source into canonical Workbench graph evidence.

Preview is the default. Pass --write to persist records to the selected Workbench DB.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from workbench.core import graph as graph_store
from workbench.plugins.domain.mission_graph_emit import (
    extract_and_project_lsb_mission,
    persist_mission_graph,
)


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("lua",type=Path,help="LSB Mission/Quest Lua source file")
    ap.add_argument("--feature-id",required=True,help="Canonical feature id, e.g. mission:cop:ancient-vows")
    ap.add_argument("--feature-name",help="Human-readable feature name")
    ap.add_argument("--snapshot",help="Source snapshot/build id")
    ap.add_argument("--db",type=Path,default=Path("workbench.db"),help="Workbench DB path")
    ap.add_argument("--write",action="store_true",help="Persist projected records; default is preview only")
    args=ap.parse_args()

    lua=args.lua.read_text(encoding="utf-8",errors="ignore")
    projection=extract_and_project_lsb_mission(
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
    if not args.write:
        print("preview only; pass --write to persist")
        return

    con=graph_store.init_db(args.db)
    try:
        persist_mission_graph(con,projection)
    finally:
        con.close()
    print(f"persisted to: {args.db}")


if __name__=="__main__":
    main()
