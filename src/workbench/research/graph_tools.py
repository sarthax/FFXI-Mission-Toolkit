"""Read-only typed research tools over the canonical Workbench graph."""
from __future__ import annotations

from collections import deque
from pathlib import Path
import json
import sqlite3
from typing import Any


SEARCH_TABLES=(
    ("entities","entity_id","display_name","entity_type"),
    ("features","feature_id","name","feature_type"),
    ("artifacts","artifact_id","path","artifact_type"),
    ("functions","function_id","qualified_name","kind"),
    ("bindings","binding_id","lua_name","binding_system"),
    ("enum_definitions","enum_id","symbol","format"),
    ("build_targets","target_id","name","build_system"),
    ("capabilities","capability_id","name","capability_type"),
    ("migrations","migration_id","feature_id","status"),
)


class CanonicalGraphReader:
    def __init__(self, db_path: Path):
        self.db_path=Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        con=sqlite3.connect(f"file:{self.db_path}?mode=ro",uri=True)
        con.row_factory=sqlite3.Row
        return con

    def search(self, query: str, *, limit: int = 30) -> dict[str,Any]:
        if not query.strip():
            return {"status":"ERROR","error":"query is required"}
        term=f"%{query.strip()}%"
        rows=[]
        con=self._connect()
        try:
            existing={
                row["name"]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            for table,id_col,label_col,type_col in SEARCH_TABLES:
                if table not in existing:
                    continue
                remaining=max(0,limit-len(rows))
                if not remaining:
                    break
                result=con.execute(
                    f"SELECT {id_col} AS node_id,{label_col} AS label,{type_col} AS node_type "
                    f"FROM {table} WHERE {id_col} LIKE ? OR COALESCE({label_col},'') LIKE ? "
                    f"ORDER BY {label_col},{id_col} LIMIT ?",
                    (term,term,remaining),
                ).fetchall()
                for row in result:
                    rows.append({
                        "node_id":row["node_id"],
                        "label":row["label"],
                        "node_type":row["node_type"],
                        "source_table":table,
                    })
            return {
                "status":"OK",
                "query":query,
                "matches":rows,
                "truncated":len(rows)>=limit,
            }
        finally:
            con.close()

    def trace(
        self,
        root: str,
        *,
        depth: int = 2,
        direction: str = "both",
        relationship: str | None = None,
        max_edges: int = 100,
    ) -> dict[str,Any]:
        if not root:
            return {"status":"ERROR","error":"root is required"}
        if depth < 0 or depth > 6:
            return {"status":"ERROR","error":"depth must be between 0 and 6"}
        if direction not in {"out","in","both"}:
            return {"status":"ERROR","error":"direction must be out, in, or both"}
        if max_edges <= 0 or max_edges > 500:
            return {"status":"ERROR","error":"max_edges must be between 1 and 500"}

        con=self._connect()
        try:
            queue=deque([(root,0)])
            visited_nodes={root}
            seen_edges=set()
            edges=[]
            evidence_ids=set()

            while queue and len(edges)<max_edges:
                node,level=queue.popleft()
                if level>=depth:
                    continue
                clauses=[]
                params=[]
                if direction in {"out","both"}:
                    clauses.append("source_node=?")
                    params.append(node)
                if direction in {"in","both"}:
                    clauses.append("target_node=?")
                    params.append(node)
                where="("+" OR ".join(clauses)+")"
                if relationship:
                    where+=" AND relationship=?"
                    params.append(relationship)
                query=(
                    "SELECT relationship_id,source_node,target_node,relationship,evidence_id,"
                    "confidence,status,metadata_json,source_snapshot_id "
                    f"FROM entity_relationships WHERE {where} ORDER BY relationship_id"
                )
                for row in con.execute(query,tuple(params)).fetchall():
                    rid=row["relationship_id"]
                    if rid in seen_edges:
                        continue
                    seen_edges.add(rid)
                    metadata=json.loads(row["metadata_json"] or "{}")
                    edge={
                        "relationship_id":rid,
                        "source_node":row["source_node"],
                        "target_node":row["target_node"],
                        "relationship":row["relationship"],
                        "evidence_id":row["evidence_id"],
                        "confidence":row["confidence"],
                        "status":row["status"],
                        "metadata":metadata,
                        "source_snapshot_id":row["source_snapshot_id"],
                    }
                    edges.append(edge)
                    if row["evidence_id"]:
                        evidence_ids.add(row["evidence_id"])
                    for next_node in (row["source_node"],row["target_node"]):
                        if next_node not in visited_nodes:
                            visited_nodes.add(next_node)
                            queue.append((next_node,level+1))
                    if len(edges)>=max_edges:
                        break

            evidence=[]
            if evidence_ids:
                placeholders=",".join("?" for _ in evidence_ids)
                for row in con.execute(
                    "SELECT evidence_id,evidence_type,source,location,snapshot,notes "
                    f"FROM evidence WHERE evidence_id IN ({placeholders}) ORDER BY evidence_id",
                    tuple(sorted(evidence_ids)),
                ).fetchall():
                    evidence.append(dict(row))

            return {
                "status":"OK",
                "root":root,
                "depth":depth,
                "direction":direction,
                "relationship_filter":relationship,
                "nodes":sorted(visited_nodes),
                "edges":edges,
                "evidence":evidence,
                "evidence_ids":sorted(evidence_ids),
                "truncated":len(edges)>=max_edges,
            }
        finally:
            con.close()
