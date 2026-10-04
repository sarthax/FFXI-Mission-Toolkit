"""Read-only identity expansion for Feature Trace.

Explicit entity_identifiers rows are the authority.  Source representations remain distinct and
are linked as evidence candidates rather than silently collapsed into one graph node.
"""
from __future__ import annotations

import sqlite3

from workbench.devtools.features.trace_generators import RelationshipCandidate, dedupe_candidates


def _tables(con: sqlite3.Connection) -> set[str]:
    return {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def canonical_identity_candidates(graph_con: sqlite3.Connection, canonical_root: str) -> list[RelationshipCandidate]:
    """Expose every explicit identifier attached to one canonical entity root."""
    if "entity_identifiers" not in _tables(graph_con):
        return []
    cols = {row[1] for row in graph_con.execute("PRAGMA table_info(entity_identifiers)")}
    required = {"entity_id", "identifier_type", "identifier_value"}
    if not required.issubset(cols):
        return []
    snapshot_expr = "source_snapshot_id" if "source_snapshot_id" in cols else "NULL"
    rows = []
    for id_type, value, snapshot in graph_con.execute(
        f"SELECT identifier_type,identifier_value,{snapshot_expr} FROM entity_identifiers WHERE entity_id=? ORDER BY identifier_type,identifier_value",
        (canonical_root,),
    ):
        identifier_node = f"identity:{str(id_type).casefold()}:{value}"
        rows.append(RelationshipCandidate(
            canonical_root,
            identifier_node,
            "HAS_IDENTITY_REPRESENTATION",
            "VERIFIED",
            "identity",
            evidence=({
                "kind": "ENTITY_IDENTIFIER",
                "identifier_type": id_type,
                "identifier_value": value,
                "source_snapshot_id": snapshot,
            },),
        ))
    return dedupe_candidates(rows)


def numeric_identity_roots(graph_con: sqlite3.Connection, numeric_id: int | str) -> dict:
    """Resolve a numeric identity without guessing when multiple canonical roots claim it."""
    if "entity_identifiers" not in _tables(graph_con):
        return {"status": "UNAVAILABLE", "numeric_id": str(numeric_id), "roots": []}
    cols = {row[1] for row in graph_con.execute("PRAGMA table_info(entity_identifiers)")}
    if not {"entity_id", "identifier_value"}.issubset(cols):
        return {"status": "UNAVAILABLE", "numeric_id": str(numeric_id), "roots": []}
    roots = [row[0] for row in graph_con.execute(
        "SELECT DISTINCT entity_id FROM entity_identifiers WHERE CAST(identifier_value AS TEXT)=? ORDER BY entity_id",
        (str(numeric_id),),
    )]
    status = "UNMAPPED" if not roots else "RESOLVED" if len(roots) == 1 else "AMBIGUOUS"
    return {"status": status, "numeric_id": str(numeric_id), "roots": roots}


def runtime_identity_evidence(graph_con: sqlite3.Connection, canonical_root: str) -> list[RelationshipCandidate]:
    """Project capture/runtime relationships already recorded against a canonical entity."""
    if "entity_relationships" not in _tables(graph_con):
        return []
    cols = {row[1] for row in graph_con.execute("PRAGMA table_info(entity_relationships)")}
    if not {"source_node", "target_node", "relationship"}.issubset(cols):
        return []
    select = "source_node,target_node,relationship,evidence_id,confidence,status,source_snapshot_id"
    rows = []
    for src, dst, rel, evidence_id, confidence, status, snapshot in graph_con.execute(
        f"SELECT {select} FROM entity_relationships WHERE source_node=? OR target_node=?",
        (canonical_root, canonical_root),
    ):
        text = " ".join(str(v or "") for v in (src, dst, rel, snapshot)).casefold()
        if not any(token in text for token in ("capture", "runtime", "packet", "observation", "client")):
            continue
        other = dst if src == canonical_root else src
        rows.append(RelationshipCandidate(
            canonical_root,
            str(other),
            str(rel),
            str(confidence or "STRONG").upper(),
            "runtime" if any(token in text for token in ("capture", "runtime", "packet", "observation")) else "identity",
            evidence=({"kind": "CANONICAL_RELATIONSHIP", "evidence_id": evidence_id, "status": status, "source_snapshot_id": snapshot},),
        ))
    return dedupe_candidates(rows)
