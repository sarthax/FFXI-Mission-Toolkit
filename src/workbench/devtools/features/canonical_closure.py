"""Fail-closed provider-record links into exact canonical Workbench nodes.

These relationships are presentation/navigation evidence only. They bridge literal node IDs
already stored by provider records into the canonical graph without creating graph edges or
performing name/numeric inference.
"""
from __future__ import annotations

import sqlite3


_CANONICAL_TARGETS = (
    ("entities", "entity_id", "entity_type", "display_name"),
    ("features", "feature_id", "feature_type", "name"),
    ("capabilities", "capability_id", "capability_type", "name"),
    ("functions", "function_id", "kind", "qualified_name"),
    ("bindings", "binding_id", "binding_system", "lua_name"),
    ("build_targets", "target_id", "build_system", "name"),
    ("artifacts", "artifact_id", "artifact_type", "path"),
    ("enum_definitions", "enum_id", "format", "symbol"),
)

_PROVIDER_CANONICAL_FIELDS = {
    "research_sessions": (
        ("feature_root", "RESEARCH_FEATURE_ROOT", "features"),
        ("entity_root", "RESEARCH_ENTITY_ROOT", "entities"),
    ),
    "research_proposals": (
        ("subject_id", "RESEARCH_PROPOSAL_SUBJECT", None),
    ),
    "validation_runs": (
        ("feature_id", "VALIDATES_FEATURE", "features"),
    ),
    "validation_results": (
        ("subject_id", "VALIDATION_SUBJECT", None),
    ),
    "migrations": (
        ("feature_id", "MIGRATES_FEATURE", "features"),
    ),
    "migration_actions": (
        ("artifact_id", "MIGRATION_ACTION_ARTIFACT", "artifacts"),
    ),
}

_SOURCE_KEYS = {
    "research_sessions": "research_session_id",
    "research_proposals": "proposal_id",
    "validation_runs": "run_id",
    "validation_results": "validation_id",
    "migrations": "migration_id",
    "migration_actions": "action_id",
}


def _tables(con: sqlite3.Connection) -> set[str]:
    return {row[0] for row in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )}


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    except sqlite3.DatabaseError:
        return set()


def _catalog_source_identity(provider_con: sqlite3.Connection, node_id: str):
    if not str(node_id).startswith("catalog:"):
        return None
    try:
        _, table, raw = str(node_id).split(":", 2)
    except ValueError:
        return None
    if table not in _PROVIDER_CANONICAL_FIELDS or table not in _tables(provider_con):
        return None
    key = _SOURCE_KEYS[table]
    if key not in _columns(provider_con, table):
        return None
    rows = provider_con.execute(
        f"SELECT {key} FROM {table} WHERE CAST({key} AS TEXT)=? LIMIT 2",
        (raw,),
    ).fetchall()
    if len(rows) != 1:
        return None
    return table, key, rows[0][0]


def _canonical_match(
    graph_con: sqlite3.Connection,
    literal_id: str,
    required_table: str | None,
):
    available = _tables(graph_con)
    matches = []
    for table, key, type_col, name_col in _CANONICAL_TARGETS:
        if required_table is not None and table != required_table:
            continue
        if table not in available:
            continue
        cols = _columns(graph_con, table)
        if not {key, type_col, name_col}.issubset(cols):
            continue
        rows = graph_con.execute(
            f"SELECT {key},{type_col},{name_col} FROM {table} WHERE CAST({key} AS TEXT)=? LIMIT 2",
            (literal_id,),
        ).fetchall()
        if len(rows) > 1:
            return None
        if len(rows) == 1:
            matches.append((table, rows[0]))
    if len(matches) != 1:
        return None
    table, row = matches[0]
    return {
        "table": table,
        "node_id": row[0],
        "node_type": row[1],
        "display_name": row[2] or row[0],
    }


def provider_canonical_relationships(
    graph_con: sqlite3.Connection,
    provider_con: sqlite3.Connection,
    node_id: str,
) -> list[dict]:
    """Bridge literal provider IDs to unique canonical graph nodes without inference."""
    source = _catalog_source_identity(provider_con, node_id)
    if source is None:
        return []
    table, key, key_value = source
    cols = _columns(provider_con, table)
    fields = [row for row in _PROVIDER_CANONICAL_FIELDS[table] if row[0] in cols]
    if not fields:
        return []

    select = ",".join(field for field, _relationship, _required in fields)
    rows = provider_con.execute(
        f"SELECT {select} FROM {table} WHERE CAST({key} AS TEXT)=? LIMIT 2",
        (str(key_value),),
    ).fetchall()
    if len(rows) != 1:
        return []

    links = []
    for (field, relationship, required_table), value in zip(fields, rows[0]):
        if value in (None, ""):
            continue
        literal_id = str(value)
        target = _canonical_match(graph_con, literal_id, required_table)
        if target is None:
            continue
        links.append({
            "relationship": relationship,
            "source_node": node_id,
            "target_node": target["node_id"],
            "target_name": target["display_name"],
            "target_type": target["node_type"],
            "provider_native": True,
            "cross_store": True,
            "basis": f"{table}.{field} stores exact canonical node id {literal_id}",
            "adapter": "canonical-closure",
        })
    return links
