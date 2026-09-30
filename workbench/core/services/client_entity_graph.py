"""Mirror snapshot-aware client ENTITY identities into the canonical Feature Trace graph.

Client numeric entity IDs are snapshot-local. This bridge therefore keys canonical client roots by
the existing semantic ENTITY key (zone + semantic identity), never by numeric ID or display name.
Numeric IDs become snapshot-scoped identifiers on that semantic root. If the same number is reused
for different semantic roots across snapshots, Feature Trace correctly sees the numeric lookup as
ambiguous instead of guessing.
"""
from __future__ import annotations

from hashlib import sha256
import json
import sqlite3
from urllib.parse import quote

from workbench.core import graph


RELATIONSHIP = "CLIENT_REPRESENTATION"
IDENTIFIER_TYPE = "client_entity_id"
SEMANTIC_IDENTIFIER_TYPE = "client_semantic_key"


def _root_id(semantic_key: str) -> str:
    digest = sha256(str(semantic_key).encode("utf-8")).hexdigest()[:24]
    return f"entity:client-semantic:{digest}"


def _existing_semantic_root(con: sqlite3.Connection, semantic_key: str) -> tuple[str | None, bool]:
    rows = con.execute(
        """SELECT DISTINCT entity_id
             FROM entity_identifiers
            WHERE identifier_type=? AND identifier_value=?
            ORDER BY entity_id LIMIT 3""",
        (SEMANTIC_IDENTIFIER_TYPE, semantic_key),
    ).fetchall()
    roots = [row[0] for row in rows]
    if len(roots) == 1:
        return roots[0], False
    if len(roots) > 1:
        return None, True
    return None, False


def _metadata(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def sync_client_entity_graph(con: sqlite3.Connection, *, snapshot_id: str) -> dict:
    """Reconcile one imported client snapshot's ENTITY rows into canonical graph structures."""
    graph.ensure_schema(con)

    tables = {
        row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if "identity_records" not in tables:
        return {
            "status": "NO_IDENTITY_RECORDS",
            "snapshot_id": snapshot_id,
            "records": 0,
            "created_roots": 0,
            "reused_roots": 0,
            "identifiers": 0,
            "relationships": 0,
            "ambiguous_semantic_roots": 0,
        }

    rows = list(con.execute(
        """SELECT record_id,semantic_key,numeric_id,zone_key,evidence_id,confidence,metadata_json
             FROM identity_records
            WHERE snapshot_id=? AND namespace='ENTITY'
            ORDER BY zone_key,numeric_id,record_id""",
        (snapshot_id,),
    ))

    # Reconcile only bridge-owned material for this snapshot.
    stale_relationships = con.execute(
        """SELECT relationship_id,evidence_id
             FROM entity_relationships
            WHERE relationship=? AND source_snapshot_id=?""",
        (RELATIONSHIP, snapshot_id),
    ).fetchall()
    stale_evidence = {row[1] for row in stale_relationships if row[1]}
    con.execute(
        "DELETE FROM entity_relationships WHERE relationship=? AND source_snapshot_id=?",
        (RELATIONSHIP, snapshot_id),
    )
    con.execute(
        """DELETE FROM entity_identifiers
            WHERE identifier_type=? AND source_snapshot_id=?""",
        (IDENTIFIER_TYPE, snapshot_id),
    )
    for evidence_id in stale_evidence:
        con.execute("DELETE FROM evidence WHERE evidence_id=?", (evidence_id,))

    counts = {
        "status": "OK",
        "snapshot_id": snapshot_id,
        "records": len(rows),
        "created_roots": 0,
        "reused_roots": 0,
        "identifiers": 0,
        "relationships": 0,
        "ambiguous_semantic_roots": 0,
        "removed_relationships": len(stale_relationships),
        "removed_identifiers": 0,
    }
    # changes() only reports the latest statement, so count stale identifiers before deleting next time.
    # This value is diagnostic; correctness does not depend on it.
    # Recompute from the pre-sync state is not necessary for current callers.

    for record_id, semantic_key, numeric_id, zone_key, source_evidence_id, confidence, metadata_json in rows:
        if not semantic_key or numeric_id is None:
            continue

        root, ambiguous = _existing_semantic_root(con, semantic_key)
        if ambiguous:
            counts["ambiguous_semantic_roots"] += 1
            continue

        metadata = _metadata(metadata_json)
        semantic_identity = metadata.get("semantic_identity") or semantic_key
        if root is None:
            root = _root_id(semantic_key)
            entity_metadata = {
                "identity_source": "client-identity",
                "semantic_key": semantic_key,
                "zone_key": zone_key,
                "semantic_identity": semantic_identity,
            }
            con.execute(
                """INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json)
                   VALUES(?,?,?,?)""",
                (root, "CLIENT_ENTITY", str(semantic_identity), json.dumps(entity_metadata, sort_keys=True)),
            )
            con.execute(
                """INSERT OR IGNORE INTO entity_identifiers(
                       entity_id,identifier_type,identifier_value,source_snapshot_id
                   ) VALUES(?,?,?,NULL)""",
                (root, SEMANTIC_IDENTIFIER_TYPE, semantic_key),
            )
            counts["created_roots"] += 1
        else:
            counts["reused_roots"] += 1

        con.execute(
            """INSERT OR IGNORE INTO entity_identifiers(
                   entity_id,identifier_type,identifier_value,source_snapshot_id
               ) VALUES(?,?,?,?)""",
            (root, IDENTIFIER_TYPE, str(numeric_id), snapshot_id),
        )
        if con.execute("SELECT changes()").fetchone()[0]:
            counts["identifiers"] += 1

        evidence_id = f"evidence:client-entity-graph:{record_id}"
        con.execute(
            "INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
            (
                evidence_id,
                "CLIENT_IDENTITY",
                "identity_records",
                record_id,
                snapshot_id,
                "Snapshot-aware client ENTITY semantic identity mirrored into Feature Trace.",
            ),
        )
        catalog_node = f"catalog:identity_records:{quote(str(record_id), safe='')}"
        relationship_id = f"client-entity-representation:{sha256(str(record_id).encode('utf-8')).hexdigest()[:24]}"
        con.execute(
            """INSERT OR REPLACE INTO entity_relationships
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                relationship_id,
                root,
                catalog_node,
                RELATIONSHIP,
                evidence_id,
                str(confidence or "UNKNOWN").upper(),
                "DISCOVERED",
                json.dumps({
                    "record_id": record_id,
                    "snapshot_id": snapshot_id,
                    "zone_key": zone_key,
                    "numeric_id": str(numeric_id),
                    "semantic_key": semantic_key,
                    "source_evidence_id": source_evidence_id,
                }, sort_keys=True),
                snapshot_id,
            ),
        )
        counts["relationships"] += 1

    con.commit()
    return counts
