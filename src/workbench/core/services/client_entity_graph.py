"""Mirror snapshot-aware client ENTITY identities into the canonical Workbench graph.

The snapshot resolver remains authoritative for cross-build identity. This mirror only gives
Feature Trace a canonical navigation root when one semantic ENTITY is unambiguous within every
participating snapshot and does not conflict with existing canonical numeric roots.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
import sqlite3
from urllib.parse import quote

from workbench.core import graph
from workbench.core.services.identity_resolver import ensure_schema as ensure_identity_schema


CLIENT_IDENTIFIER_PREFIX = "client_snapshot_entity_id:"
CLIENT_REPRESENTATION_RELATIONSHIP = "CLIENT_REPRESENTATION"

BASE_ENTITY_IDENTIFIER_TYPES = (
    "npcid", "mobid", "entity_id", "runtime_entity_id",
    "server_entity_id", "client_entity_id", "numeric_entity_id",
)


def _existing_roots(con: sqlite3.Connection, numeric_ids: set[str]) -> set[str]:
    if not numeric_ids:
        return set()
    placeholders = ",".join("?" for _ in numeric_ids)
    type_placeholders = ",".join("?" for _ in BASE_ENTITY_IDENTIFIER_TYPES)
    rows = con.execute(
        f"""SELECT DISTINCT entity_id
            FROM entity_identifiers
            WHERE CAST(identifier_value AS TEXT) IN ({placeholders})
              AND (
                    lower(identifier_type) IN ({type_placeholders})
                    OR lower(identifier_type) LIKE ?
                  )""",
        (
            *sorted(numeric_ids),
            *BASE_ENTITY_IDENTIFIER_TYPES,
            CLIENT_IDENTIFIER_PREFIX + "%",
        ),
    ).fetchall()
    return {row[0] for row in rows}


def _semantic_label(rows: list[sqlite3.Row], semantic_key: str) -> str:
    labels = []
    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            metadata = {}
        value = str(metadata.get("semantic_identity") or "").strip()
        if value and value.casefold() not in {x.casefold() for x in labels}:
            labels.append(value)
    if len(labels) == 1:
        return labels[0]
    parts = semantic_key.split("|", 2)
    return parts[-1] if parts else semantic_key


def sync_client_entity_graph(con: sqlite3.Connection) -> dict:
    """Reconcile client ENTITY identity_records into canonical entity_identifiers."""
    ensure_identity_schema(con)
    con.executescript(graph.SCHEMA)
    previous_factory = con.row_factory
    con.row_factory = sqlite3.Row
    counts = {
        "semantic_entities": 0,
        "created_roots": 0,
        "reused_roots": 0,
        "identifiers": 0,
        "ambiguous_semantics": 0,
        "ambiguous_numeric_representations": 0,
        "root_conflicts": 0,
        "removed_stale_identifiers": 0,
        "relationships": 0,
        "removed_stale_relationships": 0,
    }
    try:
        stale = con.execute(
            "SELECT COUNT(*) FROM entity_identifiers WHERE lower(identifier_type) LIKE ?",
            (CLIENT_IDENTIFIER_PREFIX + "%",),
        ).fetchone()[0]
        counts["removed_stale_identifiers"] = int(stale or 0)
        con.execute(
            "DELETE FROM entity_identifiers WHERE lower(identifier_type) LIKE ?",
            (CLIENT_IDENTIFIER_PREFIX + "%",),
        )
        stale_relationships = list(con.execute(
            """SELECT relationship_id,evidence_id
                 FROM entity_relationships
                WHERE relationship=?""",
            (CLIENT_REPRESENTATION_RELATIONSHIP,),
        ))
        counts["removed_stale_relationships"] = len(stale_relationships)
        con.execute(
            "DELETE FROM entity_relationships WHERE relationship=?",
            (CLIENT_REPRESENTATION_RELATIONSHIP,),
        )
        for _relationship_id, evidence_id in stale_relationships:
            if evidence_id:
                con.execute("DELETE FROM evidence WHERE evidence_id=?", (evidence_id,))

        rows = list(con.execute(
            """SELECT record_id,snapshot_id,semantic_key,numeric_id,zone_key,
                      confidence,evidence_id,metadata_json
               FROM identity_records
               WHERE upper(namespace)='ENTITY'
               ORDER BY semantic_key,snapshot_id,numeric_id,record_id"""
        ))
        grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
        numeric_semantics: dict[tuple[str, str], set[str]] = defaultdict(set)
        for row in rows:
            grouped[row["semantic_key"]].append(row)
            numeric_semantics[(str(row["snapshot_id"]), str(row["numeric_id"]))].add(
                str(row["semantic_key"])
            )
        ambiguous_numeric = {
            key for key, semantics in numeric_semantics.items() if len(semantics) > 1
        }

        for semantic_key in sorted(grouped):
            group = grouped[semantic_key]
            by_snapshot: dict[str, set[str]] = defaultdict(set)
            for row in group:
                by_snapshot[str(row["snapshot_id"])].add(str(row["numeric_id"]))

            # Same semantic identity mapping to multiple actor IDs in one snapshot is ambiguous.
            if any(len(values) != 1 for values in by_snapshot.values()):
                counts["ambiguous_semantics"] += 1
                continue

            # One snapshot-local numeric representation claimed by multiple semantic identities
            # is also ambiguous. Fail closed instead of letting deterministic sort order decide.
            if any(
                (snapshot_id, numeric_id) in ambiguous_numeric
                for snapshot_id, values in by_snapshot.items()
                for numeric_id in values
            ):
                counts["ambiguous_numeric_representations"] += 1
                continue

            numeric_ids = {next(iter(values)) for values in by_snapshot.values()}
            roots = _existing_roots(con, numeric_ids)
            if len(roots) > 1:
                counts["root_conflicts"] += 1
                continue
            if roots:
                root = next(iter(roots))
                counts["reused_roots"] += 1
            else:
                digest = sha256(semantic_key.encode("utf-8")).hexdigest()[:20]
                root = f"entity:client-semantic:{digest}"
                metadata = {
                    "identity_source": "client-identity-snapshots",
                    "semantic_key": semantic_key,
                    "snapshots": sorted(by_snapshot),
                    "zone_keys": sorted({
                        str(row["zone_key"]) for row in group if row["zone_key"] is not None
                    }),
                }
                con.execute(
                    """INSERT OR IGNORE INTO entities(
                           entity_id,entity_type,display_name,metadata_json
                       ) VALUES(?,?,?,?)""",
                    (root, "ENTITY", _semantic_label(group, semantic_key),
                     json.dumps(metadata, sort_keys=True)),
                )
                counts["created_roots"] += 1

            for snapshot_id, values in sorted(by_snapshot.items()):
                numeric_id = next(iter(values))
                identifier_type = CLIENT_IDENTIFIER_PREFIX + snapshot_id.casefold()
                con.execute(
                    """INSERT OR IGNORE INTO entity_identifiers(
                           entity_id,identifier_type,identifier_value,source_snapshot_id
                       ) VALUES(?,?,?,?)""",
                    (root, identifier_type, numeric_id, snapshot_id),
                )
                if con.execute("SELECT changes()").fetchone()[0]:
                    counts["identifiers"] += 1
            for row in group:
                record_id = str(row["record_id"])
                snapshot_id = str(row["snapshot_id"])
                evidence_id = "evidence:client-entity-graph:" + sha256(
                    record_id.encode("utf-8")
                ).hexdigest()[:24]
                con.execute(
                    "INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
                    (
                        evidence_id,
                        "CLIENT_IDENTITY",
                        "identity_records",
                        record_id,
                        snapshot_id,
                        "Snapshot-aware client ENTITY identity mirrored into Feature Trace.",
                    ),
                )
                target = "catalog:identity_records:" + quote(record_id, safe="")
                relationship_id = "client-entity-representation:" + sha256(
                    record_id.encode("utf-8")
                ).hexdigest()[:24]
                con.execute(
                    """INSERT OR REPLACE INTO entity_relationships
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        relationship_id,
                        root,
                        target,
                        CLIENT_REPRESENTATION_RELATIONSHIP,
                        evidence_id,
                        str(row["confidence"] or "UNKNOWN").upper(),
                        "DISCOVERED",
                        json.dumps({
                            "record_id": record_id,
                            "snapshot_id": snapshot_id,
                            "zone_key": row["zone_key"],
                            "numeric_id": str(row["numeric_id"]),
                            "semantic_key": semantic_key,
                            "source_evidence_id": row["evidence_id"],
                        }, sort_keys=True),
                        snapshot_id,
                    ),
                )
                counts["relationships"] += 1

            counts["semantic_entities"] += 1

        con.commit()
        return {"status": "OK", **counts}
    finally:
        con.row_factory = previous_factory
