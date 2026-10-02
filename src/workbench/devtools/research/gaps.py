"""Research gap detection over the Workbench graph (read-only).

Reports where the graph cannot currently answer a question, with the next deterministic action:
  - UNRESOLVED_REQUIREMENT: a feature requires a capability with no VERIFIED observation
    (UNKNOWN/MISSING/CONTRADICTED, or never observed at all).
  - ORPHAN_ENTITIES: entities of a type with no relationships at all (nothing links them to a feature/evidence).
  - UNVERIFIED_RELATIONSHIPS: relationships that are only DISCOVERED, never VERIFIED.
  - EMPTY_TABLE: a graph table that feeds analysis (findings, artifacts, ...) has no rows.
It never writes to the graph and never turns UNKNOWN into absent.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

WATCHED_EMPTY = ("findings", "artifacts", "implementations", "validation_runs", "analysis_results", "migrations")
RECOMMEND = {
    "UNKNOWN": "Run a different probe/analyzer for this capability (a miss on a packed binary is not proof of absence).",
    "MISSING": "Confirm with a second source; if still missing the feature needs new implementation.",
    "CONTRADICTED": "Sources disagree; capture or decode ground truth to decide which is right.",
    "NONE": "Never observed: add a probe/analyzer that emits an observation for this capability.",
}


def detect(graph_db: Path) -> dict:
    con = sqlite3.connect(f"file:{Path(graph_db).as_posix()}?mode=ro", uri=True)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        gaps: list[dict] = []
        if {"capability_requirements", "capability_observations"} <= tables:
            for feat, cap, req in con.execute(
                    "SELECT feature_id, capability_id, required FROM capability_requirements"):
                rows = [r[0] for r in con.execute(
                    "SELECT status FROM capability_observations WHERE capability_id=?", (cap,))]
                if "VERIFIED" in rows:
                    continue
                st = next((s for s in ("CONTRADICTED", "MISSING", "UNKNOWN") if s in rows), "NONE")
                gaps.append({"kind": "UNRESOLVED_REQUIREMENT", "subject": feat, "detail": cap,
                             "status": st, "required": bool(req), "recommendation": RECOMMEND[st]})
        for etype, n in con.execute(
                "SELECT entity_type, COUNT(*) FROM entities e WHERE NOT EXISTS ("
                "SELECT 1 FROM entity_relationships r WHERE r.source_node=e.entity_id OR r.target_node=e.entity_id) "
                "GROUP BY entity_type ORDER BY 2 DESC"):
            gaps.append({"kind": "ORPHAN_ENTITIES", "subject": etype, "detail": f"{n} unlinked", "status": "UNKNOWN",
                         "required": False, "recommendation": "Link these to a feature or evidence (e.g. capture/zone import)."})
        for st, n in con.execute(
                "SELECT status, COUNT(*) FROM entity_relationships WHERE status<>'VERIFIED' GROUP BY status"):
            gaps.append({"kind": "UNVERIFIED_RELATIONSHIPS", "subject": st, "detail": f"{n} relationships", "status": st,
                         "required": False, "recommendation": "Promote by a validator that re-checks them against source."})
        for t in WATCHED_EMPTY:
            if t in tables and con.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone() is None:
                gaps.append({"kind": "EMPTY_TABLE", "subject": t, "detail": "0 rows", "status": "UNKNOWN", "required": False,
                             "recommendation": "Run the analyzer that fills this table (feature_package_analyzer / workbench_graph import)."})
    finally:
        con.close()
    counts: dict[str, int] = {}
    for g in gaps:
        counts[g["kind"]] = counts.get(g["kind"], 0) + 1
    return {"gaps": gaps, "counts": counts}
