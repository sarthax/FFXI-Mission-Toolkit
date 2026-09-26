"""Dependency-closure and user scope-review model for migration packages.

This layer is deliberately conservative:
- migration actions are the reviewed roots supplied by upstream analysis;
- graph traversal discovers transitive dependencies but does not assume target equivalence;
- user decisions are stored separately from discovered graph evidence;
- exclusions and equivalence overrides require an explicit reason;
- package creation can require a frozen/reviewable scope before assembly.

It does not mutate source or target repositories.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
import hashlib
import json
import sqlite3
from typing import Any, Iterable


DEPENDENCY_RELATIONSHIPS = {
    "REQUIRES",
    "IMPORTS",
    "REFERENCES",
    "USES_ID",
    "USES_PACKET",
    "USES_ENUM",
    "USES_CLIENT_CAPABILITY",
    "BINDS",
    "BUILDS_INTO",
    "CALLS",
    "IMPLEMENTED_BY",
    "HANDLED_BY",
}

USER_DECISIONS = {
    "AUTO",
    "INCLUDE",
    "EXCLUDE",
    "QUESTIONABLE",
    "TARGET_EQUIVALENT",
    "NOT_REQUIRED",
}

RESOLVED_DISPOSITIONS = {
    "INCLUDE",
    "EXCLUDE",
    "TARGET_EQUIVALENT",
    "NOT_REQUIRED",
}


@dataclass(frozen=True)
class ScopeItem:
    node_id: str
    depth: int
    parent_node: str | None
    relationship: str | None
    relationship_id: str | None
    confidence: str
    graph_status: str
    evidence_id: str | None
    source_snapshot_id: str | None
    node_kind: str
    display_name: str | None
    artifact_type: str | None
    artifact_path: str | None
    root_action_id: str | None
    root_action: str | None
    root_action_status: str | None
    recommendation: str
    user_decision: str
    effective_decision: str
    reason: str | None
    tags: tuple[str, ...]
    review_required: bool
    discovery_path: tuple[str, ...]


def ensure_scope_schema(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS package_scope_decisions (
            migration_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            decision TEXT NOT NULL DEFAULT 'AUTO',
            reason TEXT,
            tags_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (migration_id, node_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS package_scope_reviews (
            migration_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'DRAFT',
            reviewed_at TEXT,
            notes TEXT,
            scope_hash TEXT
        )
    """)
    review_columns = {
        row[1] for row in con.execute("PRAGMA table_info(package_scope_reviews)").fetchall()
    }
    if "scope_hash" not in review_columns:
        con.execute("ALTER TABLE package_scope_reviews ADD COLUMN scope_hash TEXT")
    con.commit()


def _json_value(raw: str | None, fallback):
    if raw is None:
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _node_info(con: sqlite3.Connection, node_id: str) -> dict[str, Any]:
    probes = (
        ("artifacts", "artifact_id", "artifact_type", "path"),
        ("features", "feature_id", "feature_type", "name"),
        ("entities", "entity_id", "entity_type", "display_name"),
        ("capabilities", "capability_id", "capability_type", "name"),
        ("functions", "function_id", "kind", "qualified_name"),
        ("bindings", "binding_id", "binding_system", "lua_name"),
        ("enum_definitions", "enum_id", "format", "symbol"),
        ("build_targets", "target_id", "build_system", "name"),
    )
    for table, key, type_col, label_col in probes:
        row = con.execute(
            f"SELECT {type_col}, {label_col} FROM {table} WHERE {key}=?",
            (node_id,),
        ).fetchone()
        if row is not None:
            return {
                "node_kind": table[:-1].upper() if table.endswith("s") else table.upper(),
                "display_name": row[1],
                "artifact_type": row[0] if table == "artifacts" else None,
                "artifact_path": row[1] if table == "artifacts" else None,
            }
    return {
        "node_kind": "UNKNOWN",
        "display_name": None,
        "artifact_type": None,
        "artifact_path": None,
    }


def _decisions(con: sqlite3.Connection, migration_id: str) -> dict[str, dict[str, Any]]:
    ensure_scope_schema(con)
    rows = con.execute(
        "SELECT node_id, decision, reason, tags_json FROM package_scope_decisions "
        "WHERE migration_id=?",
        (migration_id,),
    ).fetchall()
    return {
        row[0]: {
            "decision": row[1],
            "reason": row[2],
            "tags": tuple(str(x) for x in _json_value(row[3], [])),
        }
        for row in rows
    }


def save_scope_decision(
    con: sqlite3.Connection,
    migration_id: str,
    node_id: str,
    decision: str,
    *,
    reason: str | None = None,
    tags: Iterable[str] = (),
) -> None:
    ensure_scope_schema(con)
    normalized = decision.strip().upper()
    if normalized not in USER_DECISIONS:
        raise ValueError(f"Unsupported scope decision: {decision}")
    clean_reason = (reason or "").strip() or None
    if normalized in {"EXCLUDE", "TARGET_EQUIVALENT", "NOT_REQUIRED"} and not clean_reason:
        raise ValueError(f"{normalized} requires an explicit reason.")
    clean_tags = sorted({str(tag).strip() for tag in tags if str(tag).strip()})
    con.execute(
        "INSERT INTO package_scope_decisions(migration_id,node_id,decision,reason,tags_json,updated_at) "
        "VALUES(?,?,?,?,?,CURRENT_TIMESTAMP) "
        "ON CONFLICT(migration_id,node_id) DO UPDATE SET "
        "decision=excluded.decision, reason=excluded.reason, tags_json=excluded.tags_json, "
        "updated_at=CURRENT_TIMESTAMP",
        (migration_id, node_id, normalized, clean_reason, json.dumps(clean_tags)),
    )
    con.commit()


def set_scope_review_status(
    con: sqlite3.Connection,
    migration_id: str,
    status: str,
    *,
    notes: str | None = None,
    scope_hash: str | None = None,
) -> None:
    ensure_scope_schema(con)
    normalized = status.strip().upper()
    if normalized not in {"DRAFT", "REVIEWED"}:
        raise ValueError("Scope review status must be DRAFT or REVIEWED")
    reviewed_at = "CURRENT_TIMESTAMP" if normalized == "REVIEWED" else "NULL"
    con.execute(
        f"INSERT INTO package_scope_reviews(migration_id,status,reviewed_at,notes,scope_hash) "
        f"VALUES(?,?,{reviewed_at},?,?) "
        f"ON CONFLICT(migration_id) DO UPDATE SET status=excluded.status, "
        f"reviewed_at={reviewed_at}, notes=excluded.notes, scope_hash=excluded.scope_hash",
        (migration_id, normalized, notes, scope_hash if normalized == "REVIEWED" else None),
    )
    con.commit()


def scope_review_record(con: sqlite3.Connection, migration_id: str) -> dict[str, Any]:
    ensure_scope_schema(con)
    row = con.execute(
        "SELECT status, reviewed_at, notes, scope_hash FROM package_scope_reviews WHERE migration_id=?",
        (migration_id,),
    ).fetchone()
    if row is None:
        return {"status": "DRAFT", "reviewed_at": None, "notes": None, "scope_hash": None}
    return {"status": row[0], "reviewed_at": row[1], "notes": row[2], "scope_hash": row[3]}


def build_dependency_scope(
    con: sqlite3.Connection,
    migration_id: str,
    *,
    max_depth: int = 6,
    max_nodes: int = 1000,
    relationships: set[str] | None = None,
) -> dict[str, Any]:
    if max_depth < 0 or max_depth > 12:
        raise ValueError("max_depth must be between 0 and 12")
    relationship_types = relationships or DEPENDENCY_RELATIONSHIPS
    decisions = _decisions(con, migration_id)

    action_rows = con.execute(
        "SELECT action_id, action, artifact_id, status, reason FROM migration_actions "
        "WHERE migration_id=? ORDER BY action_id",
        (migration_id,),
    ).fetchall()
    roots = []
    root_meta = {}
    for action_id, action, artifact_id, status, reason in action_rows:
        if not artifact_id:
            continue
        roots.append(artifact_id)
        root_meta[artifact_id] = {
            "action_id": action_id,
            "action": action,
            "status": status,
            "reason": reason,
        }

    queue = deque()
    discovered: dict[str, dict[str, Any]] = {}
    for root in roots:
        queue.append((root, 0, None, None, None, "VERIFIED", "DISCOVERED", None, None, (root,)))
        discovered.setdefault(root, {})

    truncated = False
    while queue:
        (
            node_id, depth, parent_node, relationship, relationship_id,
            confidence, graph_status, evidence_id, source_snapshot_id, path,
        ) = queue.popleft()
        existing = discovered.get(node_id)
        if existing and existing.get("depth", 999999) <= depth:
            if existing.get("populated"):
                continue
        discovered[node_id] = {
            "depth": depth,
            "parent_node": parent_node,
            "relationship": relationship,
            "relationship_id": relationship_id,
            "confidence": confidence or "UNKNOWN",
            "graph_status": graph_status or "UNKNOWN",
            "evidence_id": evidence_id,
            "source_snapshot_id": source_snapshot_id,
            "path": path,
            "populated": True,
        }
        if len(discovered) >= max_nodes:
            truncated = True
            break
        if depth >= max_depth:
            continue
        rows = con.execute(
            "SELECT relationship_id, source_node, target_node, relationship, evidence_id, "
            "confidence, status, source_snapshot_id "
            "FROM entity_relationships WHERE source_node=? ORDER BY relationship_id",
            (node_id,),
        ).fetchall()
        for row in rows:
            rel = row[3]
            if rel not in relationship_types:
                continue
            target = row[2]
            if target in path:
                continue
            next_depth = depth + 1
            prior = discovered.get(target)
            if prior and prior.get("depth", 999999) <= next_depth:
                continue
            queue.append((
                target, next_depth, node_id, rel, row[0], row[5], row[6],
                row[4], row[7], path + (target,),
            ))

    items = []
    counts = {}
    unresolved = []
    for node_id, row in sorted(discovered.items(), key=lambda item: (item[1]["depth"], item[0])):
        info = _node_info(con, node_id)
        root = root_meta.get(node_id)
        if root:
            if root["action"] == "NOT_REQUIRED":
                recommendation = "NOT_REQUIRED"
            elif root["status"] in {"BLOCKED", "FAILED"}:
                recommendation = "QUESTIONABLE"
            else:
                recommendation = "INCLUDE"
        else:
            recommendation = "QUESTIONABLE"

        saved = decisions.get(node_id, {})
        user_decision = saved.get("decision", "AUTO")
        effective = recommendation if user_decision == "AUTO" else user_decision
        reason = saved.get("reason")
        if reason is None and root and recommendation == "NOT_REQUIRED":
            reason = root.get("reason")
        tags = saved.get("tags", ())
        review_required = effective == "QUESTIONABLE"
        # A newly discovered non-artifact dependency cannot be satisfied merely by saying
        # "INCLUDE": there is nothing materializable yet. The graph must resolve it to an
        # artifact or the reviewer must explicitly classify it as target-equivalent/not-required/
        # excluded with a reason.
        if effective == "INCLUDE" and not root and info["node_kind"] != "ARTIFACT":
            review_required = True
        if effective in {"EXCLUDE", "TARGET_EQUIVALENT", "NOT_REQUIRED"} and not reason:
            review_required = True
        if review_required:
            unresolved.append(node_id)
        counts[effective] = counts.get(effective, 0) + 1

        items.append(ScopeItem(
            node_id=node_id,
            depth=row["depth"],
            parent_node=row["parent_node"],
            relationship=row["relationship"],
            relationship_id=row["relationship_id"],
            confidence=row["confidence"],
            graph_status=row["graph_status"],
            evidence_id=row["evidence_id"],
            source_snapshot_id=row["source_snapshot_id"],
            node_kind=info["node_kind"],
            display_name=info["display_name"],
            artifact_type=info["artifact_type"],
            artifact_path=info["artifact_path"],
            root_action_id=root["action_id"] if root else None,
            root_action=root["action"] if root else None,
            root_action_status=root["status"] if root else None,
            recommendation=recommendation,
            user_decision=user_decision,
            effective_decision=effective,
            reason=reason,
            tags=tuple(tags),
            review_required=review_required,
            discovery_path=tuple(row["path"]),
        ))

    scope_fingerprint_payload = [
        {
            "node_id": item.node_id,
            "parent_node": item.parent_node,
            "relationship": item.relationship,
            "relationship_id": item.relationship_id,
            "confidence": item.confidence,
            "graph_status": item.graph_status,
            "evidence_id": item.evidence_id,
            "source_snapshot_id": item.source_snapshot_id,
            "recommendation": item.recommendation,
            "user_decision": item.user_decision,
            "effective_decision": item.effective_decision,
            "reason": item.reason,
            "tags": list(item.tags),
        }
        for item in items
    ]
    scope_hash = hashlib.sha256(
        json.dumps(scope_fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    review = scope_review_record(con, migration_id)
    if review["status"] == "REVIEWED" and review.get("scope_hash") != scope_hash:
        review = {**review, "status": "STALE"}

    closure_status = "COMPLETE"
    if truncated:
        closure_status = "BLOCKED"
    elif unresolved:
        closure_status = "MANUAL_REQUIRED"
    elif any(item.effective_decision == "EXCLUDE" for item in items):
        closure_status = "COMPLETE_WITH_USER_EXCLUSIONS"
    elif any(item.effective_decision in {"TARGET_EQUIVALENT", "NOT_REQUIRED"} for item in items):
        closure_status = "COMPLETE_WITH_REVIEWED_EXCLUSIONS"

    if review["status"] != "REVIEWED":
        package_gate = "REVIEW_REQUIRED"
    elif closure_status in {"BLOCKED", "MANUAL_REQUIRED"}:
        package_gate = closure_status
    elif closure_status == "COMPLETE_WITH_USER_EXCLUSIONS":
        package_gate = "MANUAL_REQUIRED"
    else:
        package_gate = "READY"

    return {
        "schema": 1,
        "kind": "WORKBENCH_PACKAGE_DEPENDENCY_SCOPE",
        "migration_id": migration_id,
        "max_depth": max_depth,
        "max_nodes": max_nodes,
        "truncated": truncated,
        "root_count": len(roots),
        "discovered_count": len(items),
        "counts": counts,
        "closure_status": closure_status,
        "package_gate": package_gate,
        "review": review,
        "scope_hash": scope_hash,
        "unresolved_node_ids": unresolved,
        "items": [asdict(item) for item in items],
        "notes": [
            "Graph discovery does not prove target equivalence.",
            "New transitive dependencies default to QUESTIONABLE until explicitly resolved.",
            "User decisions are review metadata and do not rewrite source evidence.",
            "Non-artifact transitive dependencies cannot be resolved by INCLUDE alone; they must resolve to a packageable artifact or receive an explicit reviewed disposition.",
        ],
    }
