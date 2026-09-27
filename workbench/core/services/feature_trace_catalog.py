"""Catalog and presentation adapters for Feature Trace.

Catalog rows describe indexed knowledge; they never manufacture graph relationships.
The adapters intentionally inspect the available Workbench schema so independently built
server/client/capture indexes can participate without requiring identical tables.
"""
from __future__ import annotations

import json
import sqlite3


CANONICAL_TABLES = (
    ("entities", "entity_id", "entity_type", "display_name", "metadata_json"),
    ("features", "feature_id", "feature_type", "name", "metadata_json"),
    ("capabilities", "capability_id", "capability_type", "name", "notes_json"),
    ("functions", "function_id", "kind", "qualified_name", "notes_json"),
    ("bindings", "binding_id", "binding_system", "lua_name", "notes_json"),
    ("build_targets", "target_id", "build_system", "name", "notes_json"),
    ("artifacts", "artifact_id", "artifact_type", "path", "metadata_json"),
    ("enum_definitions", "enum_id", "format", "symbol", "notes_json"),
)
ID_COLUMNS = ("itemid", "npcid", "mobid", "entity_id", "mission_id", "quest_id", "zoneid", "id", "spellid", "abilityid", "weaponskillid", "traitid", "poolid", "groupid")
NAME_COLUMNS = ("name", "display_name", "mobname", "item_name", "instance_name", "qualified_name", "symbol", "tag", "filename")


def _tables(con):
    return [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]


def _columns(con, table):
    return {r[1].lower(): r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def _json(value):
    try:
        return json.loads(value) if value else {}
    except (TypeError, ValueError):
        return {}


def _catalog_id(table, value):
    return f"catalog:{table}:{value}"


def _indexed_specs(con):
    """Yield real index tables with a stable ID/name pair; schema is the contract."""
    for table in _tables(con):
        if table in {x[0] for x in CANONICAL_TABLES} or table == "entity_relationships":
            continue
        cols = _columns(con, table)
        key = next((cols[x] for x in ID_COLUMNS if x in cols), None)
        name = next((cols[x] for x in NAME_COLUMNS if x in cols), None)
        if key and name:
            yield table, key, name


def search_catalog(con: sqlite3.Connection, term: str, limit: int = 200):
    pattern = f"%{term.casefold()}%"
    rows = []
    for table, key, kind, name, meta in CANONICAL_TABLES:
        columns = _columns(con, table) if table in _tables(con) else {}
        if not {key.lower(), kind.lower(), name.lower()}.issubset(columns):
            continue
        for row in con.execute(f"SELECT {key},{kind},{name} FROM {table} WHERE lower({key}) LIKE ? OR lower({name}) LIKE ? ORDER BY {key} LIMIT ?", (pattern, pattern, limit)):
            rows.append({"node_id": row[0], "node_type": row[1], "display_name": row[2], "domain": "canonical", "source": table, "table": table, "catalog_only": False})
    for table, key, name in _indexed_specs(con):
        for value, display in con.execute(f"SELECT {key},{name} FROM {table} WHERE lower(CAST({key} AS TEXT)) LIKE ? OR lower(COALESCE({name},'')) LIKE ? ORDER BY {key} LIMIT ?", (pattern, pattern, limit)):
            rows.append({"node_id": _catalog_id(table, value), "node_type": table.removeprefix("sql_").removeprefix("lsb_").removeprefix("dsp_").removeprefix("topaz_").upper(), "display_name": display, "domain": table.split("_", 1)[0], "source": table, "table": table, "catalog_only": True, "numeric_id": value})
    rows.sort(key=lambda r: (str(r.get("display_name") or "").casefold(), r["node_id"]))
    return rows[:limit]


def catalog_node(con: sqlite3.Connection, node_id: str):
    if not node_id.startswith("catalog:"):
        return None
    _, table, raw = node_id.split(":", 2)
    if table not in _tables(con):
        return None
    for candidate, key, name in _indexed_specs(con):
        if candidate != table:
            continue
        row = con.execute(f"SELECT {key},{name} FROM {table} WHERE CAST({key} AS TEXT)=?", (raw,)).fetchone()
        if row:
            return {"node_id": node_id, "known": True, "representations": [{"table": table, "node_id": node_id, "node_type": table.upper(), "display_name": row[1], "metadata": {"catalog_only": True, "numeric_id": row[0], "source_table": table}}]}
    return None


def relationship_section(edge):
    rel = (edge.get("relationship") or "").upper()
    if is_runtime_edge(edge):
        return "Runtime / Captures & Packets"
    if any(x in rel for x in ("VALIDAT", "EXPECTED", "OBSERVED")):
        return "Validation"
    if any(x in rel for x in ("ENTITY", "DAT", "CSID", "MODEL", "CLIENT")):
        return "Client"
    if any(x in rel for x in ("LUA", "SQL", "CPP", "CXX", "BIND", "ENUM", "IMPORT")):
        return "Implementation / Server"
    if any(x in rel for x in ("OBTAIN", "DROP", "TRADE", "ITEM", "MISSION", "ACCESS")):
        return "Acquisition / Progression"
    if any(x in rel for x in ("REQUIRE", "SPAWN", "PREREQUISITE", "DEPEND")):
        return "Dependencies / Requirements"
    if any(x in rel for x in ("EVIDENCE", "REFERENCE", "SOURCE", "CONTRADICT")):
        return "Evidence / References"
    return "Other / Unclassified"


def is_runtime_relationship(relationship):
    """Runtime observations are evidence, not semantic traversal topology."""
    rel = (relationship or "").upper()
    return any(x in rel for x in ("PACKET", "CAPTURE", "RUNTIME", "OPCODE"))


def is_runtime_edge(edge):
    if is_runtime_relationship(edge.get("relationship")):
        return True
    if "OBSERV" not in (edge.get("relationship") or "").upper():
        return False
    metadata = edge.get("metadata") or {}
    return (any(key in metadata for key in ("capture_id", "capture", "opcode", "packet_opcode", "entity_id"))
            or str(edge.get("source_node") or "").startswith("capture:")
            or str(edge.get("target_node") or "").startswith("capture:"))


def present_relationships(edges):
    sections = {}
    for edge in edges:
        sections.setdefault(relationship_section(edge), []).append(edge)
    result = []
    for name, members in sections.items():
        if name == "Runtime / Captures & Packets":
            groups = {}
            for edge in members:
                meta = edge.get("metadata") or {}
                opcode = meta.get("opcode") or meta.get("packet_opcode") or edge.get("relationship")
                capture = (meta.get("capture_id") or meta.get("capture") or edge.get("source_snapshot_id")
                           or next((node for node in (edge.get("source_node"), edge.get("target_node"))
                                    if str(node or "").startswith("capture:")), None))
                key = (str(opcode), str(meta.get("direction") or ""))
                group = groups.setdefault(key, {"opcode": opcode, "direction": meta.get("direction"), "observation_count": 0, "capture_ids": set(), "edges": []})
                group["observation_count"] += 1
                if capture is not None:
                    group["capture_ids"].add(str(capture))
                group["edges"].append(edge)
            for group in groups.values():
                group["capture_count"] = len(group.pop("capture_ids"))
            result.append({"name": name, "count": len(members), "runtime_groups": list(groups.values()), "edges": []})
        else:
            result.append({"name": name, "count": len(members), "runtime_groups": [], "edges": members})
    return result
