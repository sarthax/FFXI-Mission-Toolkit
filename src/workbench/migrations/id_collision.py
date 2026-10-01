"""Generic identifier/content collision analysis for normalized server records.

The analyzer operates on ServerAdapter LogicalRecord output, so physical SQL schemas stay
outside this layer. Identity namespaces are scoped by logical record type and identity field.
Semantic equivalence is based on normalized non-identity fields, never on names alone.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
from typing import Any, Iterable

from workbench.adapters.servers.base import LogicalRecord


@dataclass(frozen=True)
class CollisionFinding:
    classification: str
    logical_type: str
    source_identity: tuple[tuple[str, Any], ...] | None
    target_identity: tuple[tuple[str, Any], ...] | None
    identifier_namespaces: tuple[str, ...]
    confidence: str
    status: str
    source_fingerprint: str | None = None
    target_fingerprint: str | None = None
    notes: tuple[str, ...] = ()


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _stable(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_stable(v) for v in value]
    if isinstance(value, set):
        return sorted((_stable(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True, default=str))
    return value


def _fingerprint(record: LogicalRecord) -> str:
    identity_names = {name for name, _value in record.identity}
    semantic = {
        key: _stable(value)
        for key, value in record.fields.items()
        if key not in identity_names
    }
    payload = {
        "logical_type": record.logical_type,
        "semantic_fields": semantic,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _identity_complete(record: LogicalRecord) -> bool:
    return bool(record.identity) and all(value is not None for _name, value in record.identity)


def _namespaces(record: LogicalRecord) -> tuple[str, ...]:
    return tuple(f"{record.logical_type}:{name}" for name, _value in record.identity)


def _by_type(records: Iterable[LogicalRecord]) -> dict[str, list[LogicalRecord]]:
    out: dict[str, list[LogicalRecord]] = {}
    for record in records:
        out.setdefault(record.logical_type, []).append(record)
    return out


def analyze_collisions(
    source: Iterable[LogicalRecord],
    target: Iterable[LogicalRecord],
    *,
    source_snapshot_id: str | None = None,
    target_snapshot_id: str | None = None,
) -> dict[str, Any]:
    """Compare normalized source and target records for migration identity risk.

    Classifications:
    - EXACT_IDENTITY_EQUIVALENT: same logical identity and same non-identity content.
    - ID_CONTENT_COLLISION: same logical identity but different non-identity content.
    - CONTENT_RENUMBER_CANDIDATE: identical semantic content exists under a different identity.
    - SOURCE_IDENTITY_AMBIGUOUS / TARGET_IDENTITY_AMBIGUOUS: duplicate identity in one snapshot.
    - SOURCE_IDENTITY_UNRESOLVED / TARGET_IDENTITY_UNRESOLVED: identity has null/missing components.
    - SOURCE_ONLY / TARGET_ONLY: no deterministic counterpart was established.

    CONTENT_RENUMBER_CANDIDATE is VERIFIED only as byte-for-byte normalized semantic-field
    equivalence. It does not assert that the records represent the same gameplay entity.
    """
    src_by_type = _by_type(source)
    dst_by_type = _by_type(target)
    findings: list[CollisionFinding] = []

    for logical_type in sorted(set(src_by_type) | set(dst_by_type)):
        src = src_by_type.get(logical_type, [])
        dst = dst_by_type.get(logical_type, [])

        src_complete = [r for r in src if _identity_complete(r)]
        dst_complete = [r for r in dst if _identity_complete(r)]

        for r in src:
            if not _identity_complete(r):
                findings.append(CollisionFinding(
                    "SOURCE_IDENTITY_UNRESOLVED", logical_type, r.identity, None,
                    _namespaces(r), "UNKNOWN", "UNKNOWN",
                    source_fingerprint=_fingerprint(r),
                    notes=("One or more source identity components are null or unavailable.",),
                ))
        for r in dst:
            if not _identity_complete(r):
                findings.append(CollisionFinding(
                    "TARGET_IDENTITY_UNRESOLVED", logical_type, None, r.identity,
                    _namespaces(r), "UNKNOWN", "UNKNOWN",
                    target_fingerprint=_fingerprint(r),
                    notes=("One or more target identity components are null or unavailable.",),
                ))

        src_ids: dict[tuple[tuple[str, Any], ...], list[LogicalRecord]] = {}
        dst_ids: dict[tuple[tuple[str, Any], ...], list[LogicalRecord]] = {}
        for r in src_complete:
            src_ids.setdefault(r.identity, []).append(r)
        for r in dst_complete:
            dst_ids.setdefault(r.identity, []).append(r)

        for identity, rows in sorted(src_ids.items(), key=lambda item: repr(item[0])):
            if len(rows) > 1:
                findings.append(CollisionFinding(
                    "SOURCE_IDENTITY_AMBIGUOUS", logical_type, identity, None,
                    _namespaces(rows[0]), "VERIFIED", "CONTRADICTED",
                    notes=(f"{len(rows)} source records share the same logical identity.",),
                ))
        for identity, rows in sorted(dst_ids.items(), key=lambda item: repr(item[0])):
            if len(rows) > 1:
                findings.append(CollisionFinding(
                    "TARGET_IDENTITY_AMBIGUOUS", logical_type, None, identity,
                    _namespaces(rows[0]), "VERIFIED", "CONTRADICTED",
                    notes=(f"{len(rows)} target records share the same logical identity.",),
                ))

        # Only unique identities participate in deterministic one-to-one comparison.
        src_unique = {k: v[0] for k, v in src_ids.items() if len(v) == 1}
        dst_unique = {k: v[0] for k, v in dst_ids.items() if len(v) == 1}
        matched_src: set[tuple[tuple[str, Any], ...]] = set()
        matched_dst: set[tuple[tuple[str, Any], ...]] = set()

        for identity in sorted(set(src_unique) & set(dst_unique), key=repr):
            s = src_unique[identity]
            t = dst_unique[identity]
            sf = _fingerprint(s)
            tf = _fingerprint(t)
            matched_src.add(identity)
            matched_dst.add(identity)
            if sf == tf:
                classification = "EXACT_IDENTITY_EQUIVALENT"
                status = "COMPATIBLE"
                notes = ("Same logical identity and same normalized non-identity content.",)
            else:
                classification = "ID_CONTENT_COLLISION"
                status = "CONTRADICTED"
                notes = ("Same logical identity is occupied by different normalized content.",)
            findings.append(CollisionFinding(
                classification, logical_type, identity, identity, _namespaces(s),
                "VERIFIED", status, sf, tf, notes,
            ))

        src_remaining = {k: r for k, r in src_unique.items() if k not in matched_src}
        dst_remaining = {k: r for k, r in dst_unique.items() if k not in matched_dst}
        dst_by_fp: dict[str, list[tuple[tuple[tuple[str, Any], ...], LogicalRecord]]] = {}
        for identity, record in dst_remaining.items():
            dst_by_fp.setdefault(_fingerprint(record), []).append((identity, record))

        remapped_src: set[tuple[tuple[str, Any], ...]] = set()
        remapped_dst: set[tuple[tuple[str, Any], ...]] = set()
        for s_identity, s in src_remaining.items():
            sf = _fingerprint(s)
            candidates = dst_by_fp.get(sf, [])
            if len(candidates) == 1:
                t_identity, t = candidates[0]
                findings.append(CollisionFinding(
                    "CONTENT_RENUMBER_CANDIDATE", logical_type, s_identity, t_identity,
                    tuple(sorted(set(_namespaces(s)) | set(_namespaces(t)))),
                    "INFERRED", "DISCOVERED", sf, sf,
                    ("Normalized semantic fields are identical under different identities; semantic entity equivalence remains unverified.",),
                ))
                remapped_src.add(s_identity)
                remapped_dst.add(t_identity)

        for identity, record in src_remaining.items():
            if identity in remapped_src:
                continue
            findings.append(CollisionFinding(
                "SOURCE_ONLY", logical_type, identity, None, _namespaces(record),
                "VERIFIED", "DISCOVERED", source_fingerprint=_fingerprint(record),
                notes=("No deterministic target counterpart was established.",),
            ))
        for identity, record in dst_remaining.items():
            if identity in remapped_dst:
                continue
            findings.append(CollisionFinding(
                "TARGET_ONLY", logical_type, None, identity, _namespaces(record),
                "VERIFIED", "DISCOVERED", target_fingerprint=_fingerprint(record),
                notes=("No deterministic source counterpart was established.",),
            ))

    summary: dict[str, int] = {}
    for finding in findings:
        summary[finding.classification] = summary.get(finding.classification, 0) + 1

    return {
        "schema": 1,
        "analysis_type": "ID_CONTENT_COLLISION",
        "source_snapshot_id": source_snapshot_id,
        "target_snapshot_id": target_snapshot_id,
        "summary": dict(sorted(summary.items())),
        "findings": [asdict(f) for f in findings],
    }
