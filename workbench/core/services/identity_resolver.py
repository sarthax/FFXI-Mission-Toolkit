"""Snapshot-aware identity resolution for FFXI client/server identifiers.

This service generalizes the legacy ID Drift concept. Numeric identifiers are treated as
snapshot-specific representations of a semantic identity rather than global truth.

The service is intentionally namespace-neutral. EVENT/CSID, NPC, ITEM, SPELL, MOB_SKILL,
MESSAGE_ID, and other identifier families may all use the same persistence and comparison
machinery while providing namespace-specific semantic keys/fingerprints upstream.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import re
import sqlite3
from typing import Any, Iterable


IDENTITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS identity_snapshots (
  snapshot_id TEXT PRIMARY KEY,
  snapshot_type TEXT NOT NULL,
  family TEXT,
  version TEXT,
  recorded_at TEXT,
  source_location TEXT,
  fingerprint TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS identity_records (
  record_id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL,
  namespace TEXT NOT NULL,
  semantic_key TEXT NOT NULL,
  numeric_id TEXT NOT NULL,
  zone_key TEXT,
  actor_key TEXT,
  owner_key TEXT,
  content_fingerprint TEXT,
  evidence_id TEXT,
  confidence TEXT NOT NULL DEFAULT 'UNKNOWN',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  FOREIGN KEY(snapshot_id) REFERENCES identity_snapshots(snapshot_id)
);
CREATE TABLE IF NOT EXISTS identity_mappings (
  mapping_id TEXT PRIMARY KEY,
  namespace TEXT NOT NULL,
  semantic_key TEXT NOT NULL,
  source_snapshot_id TEXT NOT NULL,
  source_numeric_id TEXT NOT NULL,
  target_snapshot_id TEXT NOT NULL,
  target_numeric_id TEXT,
  status TEXT NOT NULL,
  confidence TEXT NOT NULL DEFAULT 'UNKNOWN',
  evidence_ids_json TEXT NOT NULL DEFAULT '[]',
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_identity_records_snapshot_ns
  ON identity_records(snapshot_id, namespace);
CREATE INDEX IF NOT EXISTS idx_identity_records_semantic
  ON identity_records(namespace, semantic_key);
CREATE INDEX IF NOT EXISTS idx_identity_records_numeric
  ON identity_records(snapshot_id, namespace, numeric_id);
CREATE INDEX IF NOT EXISTS idx_identity_records_zone
  ON identity_records(snapshot_id, namespace, zone_key);
CREATE INDEX IF NOT EXISTS idx_identity_mappings_pair
  ON identity_mappings(source_snapshot_id, target_snapshot_id, namespace);
"""


@dataclass(frozen=True)
class IdentitySnapshot:
    snapshot_id: str
    snapshot_type: str
    family: str | None = None
    version: str | None = None
    recorded_at: str | None = None
    source_location: str | None = None
    fingerprint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IdentityRecord:
    record_id: str
    snapshot_id: str
    namespace: str
    semantic_key: str
    numeric_id: str | int
    zone_key: str | None = None
    actor_key: str | None = None
    owner_key: str | None = None
    content_fingerprint: str | None = None
    evidence_id: str | None = None
    confidence: str = "UNKNOWN"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IdentityMapping:
    mapping_id: str
    namespace: str
    semantic_key: str
    source_snapshot_id: str
    source_numeric_id: str
    target_snapshot_id: str
    target_numeric_id: str | None
    status: str
    confidence: str
    evidence_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IdentityResolution:
    status: str
    namespace: str
    source_snapshot_id: str
    target_snapshot_id: str
    source_numeric_id: str
    semantic_key: str | None = None
    target_numeric_id: str | None = None
    confidence: str = "UNKNOWN"
    source_record_id: str | None = None
    target_record_id: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def ensure_schema(con: sqlite3.Connection) -> None:
    con.executescript(IDENTITY_SCHEMA)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _norm(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).strip()


def normalize_text(value: str) -> str:
    """Normalize client dialog/event text for cross-build content fingerprints."""
    value = re.sub(r"[<≺][^>≻]*[>≻]", "", value or "")
    value = re.sub(r"\$\{[^}]+\}", "", value)
    value = re.sub(r"\[[^\]]*/[^\]]*\]", "", value)
    return re.sub(r"[^a-z0-9]", "", value.lower())


def text_fingerprint(value: str) -> str:
    return sha256(normalize_text(value).encode("utf-8")).hexdigest()


def semantic_event_key(
    *,
    zone_key: str,
    content_fingerprint: str,
    actor_key: str | None = None,
    owner_key: str | None = None,
) -> str:
    """Build an event identity key without using the numeric event/CSID itself."""
    parts = [
        "EVENT",
        str(zone_key).strip().upper(),
        str(actor_key or "*").strip().upper(),
        str(owner_key or "*").strip().upper(),
        str(content_fingerprint).strip().lower(),
    ]
    return "|".join(parts)


def register_snapshot(con: sqlite3.Connection, snapshot: IdentitySnapshot) -> None:
    ensure_schema(con)
    con.execute(
        "INSERT OR REPLACE INTO identity_snapshots VALUES (?,?,?,?,?,?,?,?)",
        (
            snapshot.snapshot_id,
            snapshot.snapshot_type.upper(),
            snapshot.family,
            snapshot.version,
            snapshot.recorded_at,
            snapshot.source_location,
            snapshot.fingerprint,
            _json(snapshot.metadata),
        ),
    )


def upsert_record(con: sqlite3.Connection, record: IdentityRecord) -> None:
    ensure_schema(con)
    con.execute(
        "INSERT OR REPLACE INTO identity_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            record.record_id,
            record.snapshot_id,
            record.namespace.upper(),
            record.semantic_key,
            str(record.numeric_id),
            record.zone_key,
            record.actor_key,
            record.owner_key,
            record.content_fingerprint,
            record.evidence_id,
            record.confidence.upper(),
            _json(record.metadata),
        ),
    )


def ingest_dialog_records(
    con: sqlite3.Connection,
    *,
    snapshot_id: str,
    zone_key: str,
    entries: dict[int | str, str],
    actor_key: str | None = None,
    owner_key: str | None = None,
    evidence_id_prefix: str | None = None,
) -> list[IdentityRecord]:
    """Ingest exported client dialog/event-text rows as snapshot-specific EVENT identities.

    This is deliberately conservative: matching dialog content is evidence for semantic
    equivalence, not proof of mission/quest ownership or CSID semantics.
    """
    out: list[IdentityRecord] = []
    for numeric_id, text in sorted(entries.items(), key=lambda item: int(item[0])):
        fingerprint = text_fingerprint(text)
        semantic_key = semantic_event_key(
            zone_key=zone_key,
            actor_key=actor_key,
            owner_key=owner_key,
            content_fingerprint=fingerprint,
        )
        record = IdentityRecord(
            record_id=f"identity:{snapshot_id}:EVENT:{zone_key}:{numeric_id}",
            snapshot_id=snapshot_id,
            namespace="EVENT",
            semantic_key=semantic_key,
            numeric_id=str(numeric_id),
            zone_key=zone_key,
            actor_key=actor_key,
            owner_key=owner_key,
            content_fingerprint=fingerprint,
            evidence_id=(
                f"{evidence_id_prefix}:{numeric_id}" if evidence_id_prefix else None
            ),
            confidence="INFERRED",
            metadata={"text": text, "fingerprint_basis": "normalized_dialog_text"},
        )
        upsert_record(con, record)
        out.append(record)
    return out


def _rows(
    con: sqlite3.Connection,
    snapshot_id: str,
    namespace: str,
    *,
    zone_key: str | None = None,
) -> list[sqlite3.Row]:
    con.row_factory = sqlite3.Row
    sql = (
        "SELECT * FROM identity_records "
        "WHERE snapshot_id=? AND namespace=?"
    )
    params: list[Any] = [snapshot_id, namespace.upper()]
    if zone_key is not None:
        sql += " AND zone_key=?"
        params.append(zone_key)
    return list(con.execute(sql, params))


def compare_snapshots(
    con: sqlite3.Connection,
    source_snapshot_id: str,
    target_snapshot_id: str,
    namespace: str,
    *,
    zone_key: str | None = None,
) -> dict[str, Any]:
    """Compare semantic identities across arbitrary source/target snapshots."""
    ensure_schema(con)
    src = _rows(con, source_snapshot_id, namespace, zone_key=zone_key)
    dst = _rows(con, target_snapshot_id, namespace, zone_key=zone_key)

    src_by_key: dict[str, list[sqlite3.Row]] = {}
    dst_by_key: dict[str, list[sqlite3.Row]] = {}
    for row in src:
        src_by_key.setdefault(row["semantic_key"], []).append(row)
    for row in dst:
        dst_by_key.setdefault(row["semantic_key"], []).append(row)

    stable: list[dict[str, Any]] = []
    drifted: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []

    for key in sorted(set(src_by_key) & set(dst_by_key)):
        srows = src_by_key[key]
        drows = dst_by_key[key]
        if len(srows) != 1 or len(drows) != 1:
            ambiguous.append({
                "semantic_key": key,
                "source_ids": [r["numeric_id"] for r in srows],
                "target_ids": [r["numeric_id"] for r in drows],
            })
            continue
        s, d = srows[0], drows[0]
        row = {
            "semantic_key": key,
            "source_id": s["numeric_id"],
            "target_id": d["numeric_id"],
            "source_record_id": s["record_id"],
            "target_record_id": d["record_id"],
        }
        if s["numeric_id"] == d["numeric_id"]:
            stable.append(row)
        else:
            drifted.append(row)

    return {
        "source_snapshot_id": source_snapshot_id,
        "target_snapshot_id": target_snapshot_id,
        "namespace": namespace.upper(),
        "zone_key": zone_key,
        "stable": stable,
        "drifted": drifted,
        "ambiguous": ambiguous,
        "source_only": sorted(set(src_by_key) - set(dst_by_key)),
        "target_only": sorted(set(dst_by_key) - set(src_by_key)),
    }


def resolve_identity(
    con: sqlite3.Connection,
    *,
    source_snapshot_id: str,
    target_snapshot_id: str,
    namespace: str,
    source_numeric_id: str | int,
    zone_key: str | None = None,
) -> IdentityResolution:
    """Resolve one source representation into the selected target snapshot."""
    ensure_schema(con)
    con.row_factory = sqlite3.Row
    sql = (
        "SELECT * FROM identity_records "
        "WHERE snapshot_id=? AND namespace=? AND numeric_id=?"
    )
    params: list[Any] = [
        source_snapshot_id,
        namespace.upper(),
        str(source_numeric_id),
    ]
    if zone_key is not None:
        sql += " AND zone_key=?"
        params.append(zone_key)
    src = list(con.execute(sql, params))

    base = dict(
        namespace=namespace.upper(),
        source_snapshot_id=source_snapshot_id,
        target_snapshot_id=target_snapshot_id,
        source_numeric_id=str(source_numeric_id),
    )

    if not src:
        return IdentityResolution(
            status="SOURCE_ID_UNRESOLVED",
            reason="No identity record matches the source snapshot/id/context.",
            **base,
        )
    if len(src) > 1:
        return IdentityResolution(
            status="SOURCE_ID_AMBIGUOUS",
            reason="Multiple semantic identities share the source numeric id/context.",
            metadata={"record_ids": [r["record_id"] for r in src]},
            **base,
        )

    source = src[0]
    targets = list(con.execute(
        "SELECT * FROM identity_records "
        "WHERE snapshot_id=? AND namespace=? AND semantic_key=?",
        (target_snapshot_id, namespace.upper(), source["semantic_key"]),
    ))
    if zone_key is not None:
        targets = [r for r in targets if r["zone_key"] == zone_key]

    common = dict(
        semantic_key=source["semantic_key"],
        source_record_id=source["record_id"],
        **base,
    )

    if not targets:
        return IdentityResolution(
            status="TARGET_ID_UNRESOLVED",
            reason="Semantic identity exists in source snapshot but not target snapshot.",
            confidence="UNKNOWN",
            **common,
        )
    if len(targets) > 1:
        return IdentityResolution(
            status="TARGET_ID_AMBIGUOUS",
            reason="Semantic identity maps to multiple target representations.",
            confidence="UNKNOWN",
            metadata={"record_ids": [r["record_id"] for r in targets]},
            **common,
        )

    target = targets[0]
    same = source["numeric_id"] == target["numeric_id"]
    confidence = (
        "VERIFIED"
        if source["confidence"] == "VERIFIED" and target["confidence"] == "VERIFIED"
        else "INFERRED"
    )
    return IdentityResolution(
        status="EXACT" if same else "TARGET_EQUIVALENT",
        target_numeric_id=target["numeric_id"],
        target_record_id=target["record_id"],
        confidence=confidence,
        reason=(
            "Numeric representation is stable across snapshots."
            if same else
            "Semantic identity matches but target snapshot uses a different numeric representation."
        ),
        **common,
    )


def persist_mapping(
    con: sqlite3.Connection,
    resolution: IdentityResolution,
    *,
    evidence_ids: Iterable[str] = (),
) -> IdentityMapping:
    """Persist a resolved or unresolved source->target identity result."""
    ensure_schema(con)
    mapping = IdentityMapping(
        mapping_id=(
            f"identity-map:{resolution.namespace}:"
            f"{resolution.source_snapshot_id}:{resolution.source_numeric_id}:"
            f"{resolution.target_snapshot_id}"
        ),
        namespace=resolution.namespace,
        semantic_key=resolution.semantic_key or "",
        source_snapshot_id=resolution.source_snapshot_id,
        source_numeric_id=resolution.source_numeric_id,
        target_snapshot_id=resolution.target_snapshot_id,
        target_numeric_id=resolution.target_numeric_id,
        status=resolution.status,
        confidence=resolution.confidence,
        evidence_ids=tuple(dict.fromkeys(str(x) for x in evidence_ids if str(x).strip())),
        metadata={
            "source_record_id": resolution.source_record_id,
            "target_record_id": resolution.target_record_id,
            "reason": resolution.reason,
            **resolution.metadata,
        },
    )
    con.execute(
        "INSERT OR REPLACE INTO identity_mappings VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            mapping.mapping_id,
            mapping.namespace,
            mapping.semantic_key,
            mapping.source_snapshot_id,
            mapping.source_numeric_id,
            mapping.target_snapshot_id,
            mapping.target_numeric_id,
            mapping.status,
            mapping.confidence,
            _json(mapping.evidence_ids),
            _json(mapping.metadata),
        ),
    )
    return mapping


def record_dict(record: Any) -> dict[str, Any]:
    return asdict(record)


@dataclass(frozen=True)
class IdentityClosureAssessment:
    status: str
    total: int
    resolved: int
    exact: int
    target_equivalent: int
    unresolved: int
    ambiguous: int
    blocking: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


def assess_identity_closure(
    resolutions: Iterable[IdentityResolution],
    *,
    unresolved_blocks: bool = False,
) -> IdentityClosureAssessment:
    """Aggregate identifier resolutions into a package-readiness dimension.

    TARGET_EQUIVALENT is considered resolved: numeric drift is acceptable when the semantic
    identity has been mapped to the selected target snapshot. Unknown/ambiguous mappings remain
    visible and prevent READY. Callers may choose whether unresolved required identities should
    hard-block package planning or remain MANUAL_REQUIRED.
    """
    rows = list(resolutions)
    exact = sum(r.status == "EXACT" for r in rows)
    equivalent = sum(r.status == "TARGET_EQUIVALENT" for r in rows)
    ambiguous_rows = [
        r for r in rows if r.status in {"SOURCE_ID_AMBIGUOUS", "TARGET_ID_AMBIGUOUS"}
    ]
    unresolved_rows = [
        r for r in rows
        if r.status not in {"EXACT", "TARGET_EQUIVALENT"}
        and r not in ambiguous_rows
    ]
    blocking = tuple(
        f"{r.namespace}:{r.source_snapshot_id}:{r.source_numeric_id}:{r.status}"
        for r in [*ambiguous_rows, *unresolved_rows]
    )
    if not blocking:
        status = "READY"
    elif unresolved_blocks:
        status = "BLOCKED"
    else:
        status = "MANUAL_REQUIRED"
    return IdentityClosureAssessment(
        status=status,
        total=len(rows),
        resolved=exact + equivalent,
        exact=exact,
        target_equivalent=equivalent,
        unresolved=len(unresolved_rows),
        ambiguous=len(ambiguous_rows),
        blocking=blocking,
        notes=(
            "TARGET_EQUIVALENT counts as resolved only because semantic identity mapped across snapshots.",
            "Numeric equality without semantic identity evidence is not sufficient for closure.",
        ),
    )
