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
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

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


ENTITY_OBJECT_TYPES = {"NPC", "MOB", "INSTANCE_ENTITY", "CLIENT_IDENTITY"}


def _numeric_entity_query(query: str) -> int | None:
    """Parse an exact entity-style query without treating arbitrary embedded digits as identity."""
    value = (query or "").strip()
    for prefix in ("npc:", "mob:", "entity:"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):]
            break
    try:
        return int(value, 0)
    except ValueError:
        return None


ENTITY_IDENTIFIER_TYPES = (
    "npcid", "mobid", "entity_id", "runtime_entity_id",
    "server_entity_id", "client_entity_id", "numeric_entity_id",
)


def canonical_entity_candidates(con: sqlite3.Connection, numeric_id: int) -> list[str]:
    """Return every explicit canonical entity root claiming this numeric representation."""
    available = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    if "entity_identifiers" not in available:
        return []
    cols = {r[1] for r in con.execute("PRAGMA table_info(entity_identifiers)")}
    if not {"entity_id", "identifier_value"}.issubset(cols):
        return []

    clauses = ["CAST(identifier_value AS TEXT)=?"]
    params = [str(numeric_id)]
    if "identifier_type" in cols:
        placeholders = ",".join("?" for _ in ENTITY_IDENTIFIER_TYPES)
        clauses.append(
            f"""(
                    lower(COALESCE(identifier_type,'')) IN ({placeholders})
                    OR lower(COALESCE(identifier_type,'')) LIKE 'client_snapshot_entity_id:%'
                )"""
        )
        params.extend(ENTITY_IDENTIFIER_TYPES)
    return [
        row[0] for row in con.execute(
            f"""SELECT DISTINCT entity_id
                  FROM entity_identifiers
                 WHERE {' AND '.join(clauses)}
                 ORDER BY entity_id LIMIT 10""",
            params,
        ).fetchall()
    ]


def canonical_entity_root(con: sqlite3.Connection, numeric_id: int) -> str | None:
    """Resolve one numeric entity representation only when the explicit mapping is unique."""
    roots = canonical_entity_candidates(con, numeric_id)
    return roots[0] if len(roots) == 1 else None


def canonical_entity_identifiers(con: sqlite3.Connection, root: str | None) -> list[dict]:
    if not root:
        return []
    available = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    if "entity_identifiers" not in available:
        return []
    cols = {r[1] for r in con.execute("PRAGMA table_info(entity_identifiers)")}
    snapshot_expr = "source_snapshot_id" if "source_snapshot_id" in cols else "NULL"
    order_snapshot = ",COALESCE(source_snapshot_id,'')" if "source_snapshot_id" in cols else ""
    return [
        {
            "identifier_type": row[0],
            "identifier_value": row[1],
            "source_snapshot_id": row[2],
        }
        for row in con.execute(
            f"""SELECT identifier_type,identifier_value,{snapshot_expr}
                  FROM entity_identifiers
                 WHERE entity_id=?
                 ORDER BY identifier_type,identifier_value{order_snapshot}""",
            (root,),
        ).fetchall()
    ]


def canonical_entity_evidence(con: sqlite3.Connection, root: str | None, limit: int = 100) -> dict:
    """Summarize direct canonical relationships/evidence touching one root, bounded for the UI."""
    if not root:
        return {"relationship_count": 0, "evidence_count": 0, "relationship_counts": [], "rows": [], "truncated": False}
    available = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    if "entity_relationships" not in available:
        return {"relationship_count": 0, "evidence_count": 0, "rows": [], "truncated": False}
    total = con.execute(
        """SELECT COUNT(*) FROM entity_relationships
            WHERE source_node=? OR target_node=?""",
        (root, root),
    ).fetchone()[0]
    evidence_total = con.execute(
        """SELECT COUNT(DISTINCT evidence_id) FROM entity_relationships
            WHERE (source_node=? OR target_node=?) AND evidence_id IS NOT NULL""",
        (root, root),
    ).fetchone()[0]
    relationship_counts = [
        {"relationship": row[0], "count": row[1]}
        for row in con.execute(
            """SELECT relationship,COUNT(*) FROM entity_relationships
                WHERE source_node=? OR target_node=?
                GROUP BY relationship ORDER BY COUNT(*) DESC,relationship""",
            (root, root),
        ).fetchall()
    ]
    evidence_available = "evidence" in available
    if evidence_available:
        rows = con.execute(
            """SELECT r.relationship_id,r.source_node,r.target_node,r.relationship,
                      r.evidence_id,r.confidence,r.status,r.source_snapshot_id,
                      e.evidence_type,e.source,e.location,e.snapshot,e.notes
                 FROM entity_relationships r
                 LEFT JOIN evidence e ON e.evidence_id=r.evidence_id
                WHERE r.source_node=? OR r.target_node=?
                ORDER BY r.relationship,r.relationship_id
                LIMIT ?""",
            (root, root, limit),
        ).fetchall()
    else:
        rows = [
            (*row, None, None, None, None, None)
            for row in con.execute(
                """SELECT relationship_id,source_node,target_node,relationship,
                          evidence_id,confidence,status,source_snapshot_id
                     FROM entity_relationships
                    WHERE source_node=? OR target_node=?
                    ORDER BY relationship,relationship_id
                    LIMIT ?""",
                (root, root, limit),
            ).fetchall()
        ]
    items = []
    for row in rows:
        items.append({
            "relationship_id": row[0],
            "source_node": row[1],
            "target_node": row[2],
            "relationship": row[3],
            "evidence_id": row[4],
            "confidence": row[5],
            "status": row[6],
            "source_snapshot_id": row[7],
            "evidence_type": row[8],
            "evidence_source": row[9],
            "evidence_location": row[10],
            "evidence_snapshot": row[11],
            "evidence_notes": row[12],
        })
    return {
        "relationship_count": int(total or 0),
        "evidence_count": int(evidence_total or 0),
        "relationship_counts": relationship_counts,
        "rows": items,
        "truncated": int(total or 0) > len(items),
    }


def _catalog_entity_id(row: dict) -> int | None:
    if row.get("node_type") not in ENTITY_OBJECT_TYPES:
        return None
    value = row.get("numeric_id")
    if value is not None:
        try:
            return int(value)
        except (TypeError, ValueError):
            pass
    identity = row.get("identity") or {}
    aliases = row.get("aliases") or {}
    for source in (identity, aliases):
        for key in ("npcid", "mobid", "entity_id", "id", "numeric_id"):
            if key in source:
                try:
                    return int(source[key])
                except (TypeError, ValueError):
                    pass
    node_id = str(row.get("node_id") or "")
    if not row.get("catalog_only") and ":" in node_id:
        tail = node_id.rsplit(":", 1)[-1]
        if tail.isdigit():
            return int(tail)
    return None


def _entity_catalog_match(row: dict, numeric_id: int) -> bool:
    resolved = _catalog_entity_id(row)
    if resolved is not None:
        return resolved == numeric_id
    return (
        row.get("node_type") == "CLIENT_IDENTITY"
        and "numeric_id" in (row.get("matched_on") or [])
        and str(numeric_id) in str(row)
    )


def entity_query_diagnostics(
    graph_con: sqlite3.Connection,
    catalog_con: sqlite3.Connection,
    query: str,
) -> dict:
    """Explain why an entity query can or cannot enter canonical traversal."""
    exact_numeric = _numeric_entity_query(query)
    matches = search_nodes(graph_con, query, catalog_con)
    candidate_ids = {exact_numeric} if exact_numeric is not None else {
        value for row in matches
        if (value := _catalog_entity_id(row)) is not None
    }
    mappings = []
    all_roots = set()
    ambiguous_ids = []
    unmapped_ids = []
    for numeric_id in sorted(candidate_ids):
        roots = canonical_entity_candidates(graph_con, numeric_id)
        mappings.append({"numeric_id": numeric_id, "canonical_roots": roots})
        all_roots.update(roots)
        if len(roots) > 1:
            ambiguous_ids.append(numeric_id)
        elif not roots:
            unmapped_ids.append(numeric_id)

    if not candidate_ids:
        status = "NO_ENTITY_MATCH"
        reason = "No indexed entity representation supplied a numeric entity identity for this query."
        action = "Refine the name/ID, rebuild the relevant server/client index, or inspect ordinary search matches."
    elif ambiguous_ids:
        status = "AMBIGUOUS_NUMERIC_MAPPING"
        reason = "At least one numeric entity ID is claimed by multiple canonical roots."
        action = "Review the conflicting entity_identifiers/evidence before canonical traversal."
    elif len(all_roots) > 1:
        status = "MULTIPLE_CANONICAL_ROOTS"
        reason = "The matched numeric IDs resolve to different explicit canonical entities."
        action = "Refine the query or inspect each source representation separately."
    elif unmapped_ids and len(candidate_ids) > 1:
        status = "PARTIALLY_MAPPED"
        reason = "Some matched numeric representations have no canonical identity mapping."
        action = "Use the provider branches below; canonical traversal stays withheld until every matched ID is explicitly bridged."
    elif unmapped_ids:
        status = "NO_CANONICAL_MAPPING"
        reason = "The indexed representation has no explicit canonical entity mapping."
        action = "Use the provider-native Implementation Path or ingest identity evidence before expecting semantic/runtime traversal."
    elif len(all_roots) == 1 and len(candidate_ids) > 1:
        status = "DRIFTED_IDS_ONE_ROOT"
        reason = "Multiple numeric representations are explicitly bridged to one canonical entity."
        action = "Canonical traversal is safe; provider branches remain separate representations."
    else:
        status = "UNIQUE_CANONICAL_MAPPING"
        reason = "The numeric representation resolves to one explicit canonical entity."
        action = "Canonical semantic/runtime traversal is available."

    return {
        "query": query,
        "status": status,
        "reason": reason,
        "next_action": action,
        "candidate_numeric_ids": sorted(candidate_ids),
        "canonical_roots": sorted(all_roots),
        "mappings": mappings,
        "search_match_count": len(matches),
        "ambiguous_numeric_ids": ambiguous_ids,
        "unmapped_numeric_ids": unmapped_ids,
    }


def _entity_capture_ids(evidence_rows: list[dict]) -> list[int]:
    capture_ids=set()
    for row in evidence_rows:
        for node in (row.get("source_node"),row.get("target_node")):
            text=str(node or "")
            if text.startswith("capture:") and text[8:].isdigit():
                capture_ids.add(int(text[8:]))
        snapshot=str(row.get("evidence_snapshot") or row.get("source_snapshot_id") or "")
        if snapshot.startswith("capture:") and snapshot[8:].isdigit():
            capture_ids.add(int(snapshot[8:]))
    return sorted(capture_ids)


def entity_workflow_handoffs(
    numeric_id: int,
    numeric_ids: list[int],
    canonical_root: str | None,
    display_name: str | None,
    evidence_rows: list[dict],
) -> list[dict]:
    """Build navigation-only handoffs for entity research without asserting new evidence."""
    label=(display_name or str(numeric_id)).strip()
    handoffs=[
        {
            "kind":"ENTITY",
            "label":"Entity Dossier",
            "href":f"/entity/{numeric_id}",
            "basis":"Primary entity representation ID.",
        },
        {
            "kind":"BEHAVIOR",
            "label":"Behavior Inspector",
            "href":f"/behavior?q={quote(label,safe='')}",
            "basis":"Search configured server Lua trees by the resolved display name.",
        },
        {
            "kind":"EVENTS",
            "label":"Events / CSID",
            "href":f"/events?q={numeric_id}",
            "basis":"Search client event inventory by entity ID; zone selection may still be required.",
        },
        {
            "kind":"CAPTURES",
            "label":"Capture Evidence",
            "href":f"/captures/query?table=capture_npc_entries&q={numeric_id}",
            "basis":"Query normalized capture entity observations by entity ID.",
        },
        {
            "kind":"PATH_JSON",
            "label":"Path diagnostics JSON",
            "href":f"/features/trace/path.json?q={quote(str(numeric_id),safe='')}",
            "basis":"Read-only machine-readable identity/path diagnostics.",
        },
    ]
    if canonical_root:
        handoffs.insert(1,{
            "kind":"CANONICAL",
            "label":"Canonical Trace",
            "href":f"/features/trace?q={quote(canonical_root,safe='')}",
            "basis":"Explicit canonical identity mapping.",
        })
    for capture_id in _entity_capture_ids(evidence_rows):
        handoffs.append({
            "kind":"CAPTURE",
            "label":f"Capture #{capture_id}",
            "href":f"/captures/{capture_id}",
            "basis":"Direct canonical relationship/evidence references this capture.",
        })
    if len(numeric_ids)>1:
        handoffs.append({
            "kind":"DRIFT",
            "label":"Compare numeric representations",
            "href":f"/features/trace?q={quote(label,safe='')}",
            "basis":"Multiple explicit numeric representations resolve through this entity query.",
        })
    return handoffs


def entity_coverage_cues(path: dict) -> list[dict]:
    """Describe concrete integrity/coverage conditions without inferring implementation absence."""
    cues=[]
    diag=path.get("diagnostics") or {}
    status=diag.get("status")
    if status in {"AMBIGUOUS_NUMERIC_MAPPING","MULTIPLE_CANONICAL_ROOTS"}:
        cues.append({
            "code":"IDENTITY_CONFLICT",
            "level":"ACTION",
            "label":"Identity conflict blocks canonical traversal",
            "detail":diag.get("reason"),
            "basis":"Explicit entity identifier mappings disagree.",
        })
    elif status in {"NO_CANONICAL_MAPPING","PARTIALLY_MAPPED"}:
        cues.append({
            "code":"IDENTITY_BRIDGE_INCOMPLETE",
            "level":"COVERAGE",
            "label":"Canonical identity bridge is incomplete",
            "detail":diag.get("reason"),
            "basis":"Indexed source representations exist, but explicit identity evidence is incomplete.",
        })

    canonical=path.get("canonical") or {}
    if path.get("canonical_mapped") and not canonical.get("known"):
        cues.append({
            "code":"CANONICAL_NODE_METADATA_MISSING",
            "level":"ACTION",
            "label":"Canonical identifier points to a missing entity row",
            "detail":f"Identity resolves to {path.get('canonical_root')}, but node metadata is not indexed.",
            "basis":"Identifier mapping exists independently of canonical entity metadata.",
        })
    if canonical.get("direct_relationship_count",0) and not canonical.get("direct_evidence_count",0):
        cues.append({
            "code":"RELATIONSHIPS_WITHOUT_EVIDENCE_IDS",
            "level":"REVIEW",
            "label":"Direct graph relationships lack evidence IDs",
            "detail":f"{canonical.get('direct_relationship_count',0)} direct relationship(s) are recorded with no evidence ID.",
            "basis":"Canonical graph relationship rows.",
        })

    empty_branches=[
        branch for branch in path.get("branches") or []
        if not branch.get("native_link_count")
    ]
    if empty_branches:
        cues.append({
            "code":"SOURCE_BRANCH_NO_NATIVE_LINKS",
            "level":"COVERAGE",
            "label":"Some source representations have no indexed downstream wiring",
            "detail":f"{len(empty_branches)} of {len(path.get('branches') or [])} provider branch(es) stop at the source record.",
            "basis":"Provider-native schema/source adapters only; this is not proof the implementation is absent.",
        })
    if not path.get("branches"):
        cues.append({
            "code":"NO_SOURCE_REPRESENTATIONS",
            "level":"COVERAGE",
            "label":"No provider representation is currently indexed",
            "detail":"The entity identity can be discussed only from canonical graph data currently loaded.",
            "basis":"Feature Trace provider catalog search.",
        })
    return cues


def entity_implementation_path(
    graph_con: sqlite3.Connection,
    catalog_con: sqlite3.Connection,
    query: str,
    *,
    max_provider_depth: int = 4,
) -> dict | None:
    """Project an exact entity identity across indexed source representations."""
    diagnostics = entity_query_diagnostics(graph_con, catalog_con, query)
    numeric_ids = set(diagnostics["candidate_numeric_ids"])
    if not numeric_ids:
        return None
    if diagnostics["status"] in {"AMBIGUOUS_NUMERIC_MAPPING", "MULTIPLE_CANONICAL_ROOTS", "PARTIALLY_MAPPED"}:
        # Numeric exact queries may still show provider branches even when canonical mapping is
        # withheld. Name queries spanning unrelated/partially mapped IDs remain unresolved.
        if _numeric_entity_query(query) is None:
            return None
        numeric_ids = {_numeric_entity_query(query)}

    numeric_id = sorted(numeric_ids)[0]
    entity_rows = []
    seen_rows = set()
    for candidate in sorted(numeric_ids):
        for row in search_nodes(graph_con, str(candidate), catalog_con):
            if not _entity_catalog_match(row, candidate):
                continue
            key = (row.get("node_id"), row.get("source"))
            if key in seen_rows:
                continue
            seen_rows.add(key)
            entity_rows.append(row)

    mapped_roots = {
        root for candidate in numeric_ids
        for root in canonical_entity_candidates(graph_con, candidate)
    }
    root = next(iter(mapped_roots)) if len(mapped_roots) == 1 and not diagnostics["unmapped_numeric_ids"] else None

    branches = []
    seen_roots = set()
    for row in entity_rows:
        node_id = row["node_id"]
        if node_id in seen_roots:
            continue
        seen_roots.add(node_id)
        branch = {
            "provider": row.get("provider") or ("canonical" if not row.get("catalog_only") else "schema-fallback"),
            "domain": row.get("domain"),
            "root": row,
            "steps": [],
        }
        queue = deque([(node_id, 0)])
        visited = {node_id}
        while queue:
            current, depth = queue.popleft()
            if depth >= max_provider_depth:
                continue
            links = provider_relationships(catalog_con, current)
            for link in links:
                target = link.get("target_node")
                if not target:
                    continue
                info = node_info(graph_con, target, catalog_con)
                rep = (info.get("representations") or [{}])[0]
                branch["steps"].append({
                    "depth": depth + 1,
                    "relationship": link.get("relationship"),
                    "basis": link.get("basis"),
                    "source_node": current,
                    "target_node": target,
                    "target_name": link.get("target_name") or rep.get("display_name") or target,
                    "target_type": link.get("target_type") or rep.get("node_type") or "UNKNOWN",
                    "provider_native": True,
                })
                if target not in visited:
                    visited.add(target)
                    queue.append((target, depth + 1))
        branch["native_link_count"] = len(branch["steps"])
        branch["max_depth"] = max((step["depth"] for step in branch["steps"]), default=0)
        branch["target_count"] = len({step["target_node"] for step in branch["steps"]})
        branches.append(branch)

    branches.sort(key=lambda b: (
        str(b.get("provider") or ""),
        str((b.get("root") or {}).get("table") or ""),
        str((b.get("root") or {}).get("node_id") or ""),
    ))
    provider_counts = Counter(branch["provider"] for branch in branches)
    domain_counts = Counter(branch.get("domain") or "unknown" for branch in branches)
    canonical_node = node_info(graph_con, root, catalog_con) if root else None
    canonical_reps = (canonical_node or {}).get("representations") or []
    canonical_primary = canonical_reps[0] if canonical_reps else {}
    evidence = canonical_entity_evidence(graph_con, root)
    display_name=canonical_primary.get("display_name") or next(
        (row.get("display_name") for row in entity_rows if row.get("display_name")),
        str(numeric_id),
    )
    result = {
        "numeric_id": numeric_id,
        "numeric_ids": sorted(numeric_ids),
        "canonical_root": root,
        "canonical_mapped": root is not None,
        "mapping_status": diagnostics["status"],
        "diagnostics": diagnostics,
        "canonical": {
            "root": root,
            "known": bool((canonical_node or {}).get("known")),
            "display_name": canonical_primary.get("display_name") or root,
            "node_type": canonical_primary.get("node_type") or ("ENTITY" if root else None),
            "representations": canonical_reps,
            "identifiers": canonical_entity_identifiers(graph_con, root),
            "direct_relationship_count": evidence["relationship_count"],
            "direct_evidence_count": evidence["evidence_count"],
            "relationship_counts": evidence["relationship_counts"],
            "direct_evidence": evidence["rows"],
            "evidence_truncated": evidence["truncated"],
        },
        "branches": branches,
        "representation_count": len(entity_rows),
        "provider_counts": [
            {"provider": key, "count": count}
            for key, count in sorted(provider_counts.items())
        ],
        "domain_counts": [
            {"domain": key, "count": count}
            for key, count in sorted(domain_counts.items())
        ],
        "native_link_count": sum(branch["native_link_count"] for branch in branches),
        "notes": [
            "Source/provider rows remain separate representations even when they share one canonical identity.",
            "Provider-native links are exact schema/source relationships, not inferred canonical graph edges.",
            "Canonical traversal is enabled only by explicit entity_identifiers evidence.",
            "Coverage cues describe indexed evidence state only; they do not declare gameplay implementation absent.",
        ],
    }
    result["handoffs"]=entity_workflow_handoffs(
        numeric_id,
        result["numeric_ids"],
        root,
        display_name,
        evidence["rows"],
    )
    result["coverage_cues"]=entity_coverage_cues(result)
    return result

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
          relationships: set[str] | None = None, include_runtime_edges: bool = False,
          max_nodes: int = 5000) -> dict:
    if max_nodes < 1:
        raise ValueError("max_nodes must be >= 1")
    queue = deque([(root, 0, [root], [])])
    visited = {root}
    truncated = False
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
                if len(visited) >= max_nodes:
                    truncated = True
                    queue.clear()
                    break
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
        if truncated:
            break

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
        "max_nodes": max_nodes,
        "truncated": truncated,
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
            "Trace traversal is bounded by max_nodes; truncated=true means more graph nodes exist beyond the returned budget.",
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
    ap.add_argument("--max-nodes", type=int, default=5000,
                    help="Hard traversal budget; results report truncated=true when reached.")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    if args.depth < 0:
        ap.error("--depth must be >= 0")
    if args.max_nodes < 1:
        ap.error("--max-nodes must be >= 1")

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

    result = trace(
        con, root, args.depth, args.direction,
        relationships=set(args.relationship) or None,
        max_nodes=args.max_nodes,
    )
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
