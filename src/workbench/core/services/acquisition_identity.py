"""Fail-closed canonical identity reconciliation for acquisition catalog subjects.

The acquisition catalog intentionally preserves source literals.  This service is the
explicit gate between those literals and future shared-graph ITEM / KEY_ITEM nodes.

Rules:
- ITEM and KEY_ITEM are distinct namespaces even when their numeric values match.
- Landsandboat literals/numeric IDs are canonical only when the selected authoritative
  snapshot contains exactly one matching ``enum_definitions`` row.
- Other provider numeric IDs require an explicit, VERIFIED snapshot identity bridge.
- Display names never establish identity.
- Missing or conflicting evidence remains UNRESOLVED / AMBIGUOUS; nothing is guessed.
"""
from __future__ import annotations

from copy import deepcopy
import sqlite3
from typing import Any, Mapping

from workbench.core.services import identity_resolver


VERIFIED = "VERIFIED"
UNRESOLVED = "UNRESOLVED"
AMBIGUOUS = "AMBIGUOUS"
SUPPORTED_NAMESPACES = frozenset({"ITEM", "KEY_ITEM"})

_NAMESPACE_ENUM = {
    "ITEM": ("xi.item", "item"),
    "KEY_ITEM": ("xi.keyitem", "keyitem"),
}
_NAMESPACE_PREFIX = {
    "ITEM": "xi.item.",
    "KEY_ITEM": "xi.keyitem.",
}


def _parse_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(str(value).strip(), 0)
    except (TypeError, ValueError):
        return None


def _qualified_symbol(namespace: str, enum_name: object, symbol: object) -> str | None:
    ns = namespace.upper()
    if ns not in SUPPORTED_NAMESPACES:
        return None
    raw_symbol = str(symbol or "").strip()
    if not raw_symbol:
        return None
    lower_symbol = raw_symbol.casefold()
    prefix = _NAMESPACE_PREFIX[ns]
    if lower_symbol.startswith(prefix):
        return raw_symbol
    enum = str(enum_name or "").strip().casefold()
    if enum in _NAMESPACE_ENUM[ns]:
        return f"{prefix}{raw_symbol}"
    return None


def _authoritative_enum_candidates(
    con: sqlite3.Connection,
    *,
    namespace: str,
    literal: object,
    canonical_snapshot_id: str,
) -> list[dict[str, Any]]:
    """Return namespace-safe enum candidates from one authoritative snapshot."""
    ns = namespace.upper()
    if ns not in SUPPORTED_NAMESPACES:
        return []
    rows = con.execute(
        """SELECT enum_id,enum_name,value,symbol,evidence_id,path,line
           FROM enum_definitions
           WHERE source_snapshot_id=?
           ORDER BY enum_id""",
        (canonical_snapshot_id,),
    ).fetchall()
    numeric = _parse_int(literal)
    text = str(literal or "").strip().casefold()
    symbolic = text.startswith(_NAMESPACE_PREFIX[ns])
    out: list[dict[str, Any]] = []
    for row in rows:
        qualified = _qualified_symbol(ns, row[1], row[3])
        if qualified is None:
            continue
        value = _parse_int(row[2])
        if value is None:
            continue
        if symbolic:
            matched = qualified.casefold() == text
        elif numeric is not None:
            matched = value == numeric
        else:
            matched = False
        if not matched:
            continue
        out.append({
            "canonical_id": str(value),
            "canonical_symbol": qualified,
            "enum_id": row[0],
            "evidence_id": row[4],
            "path": row[5],
            "line": row[6],
        })
    # Duplicate rows that assert the same canonical identity are harmless; conflicting
    # identities are intentionally preserved for the caller to classify as ambiguous.
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in out:
        unique[(row["canonical_id"], row["canonical_symbol"].casefold())] = row
    return list(unique.values())


def _resolve_path(
    con: sqlite3.Connection,
    *,
    subject_kind: str,
    subject_id: object,
    path: Mapping[str, Any],
    canonical_snapshot_id: str,
    provider_snapshots: Mapping[str, str],
) -> dict[str, Any]:
    namespace = str(subject_kind or "").upper()
    base = {
        "namespace": namespace,
        "source_family": path.get("source_family"),
        "source_literal": str(subject_id),
    }
    if namespace not in SUPPORTED_NAMESPACES:
        return {**base, "status": UNRESOLVED, "basis": "UNSUPPORTED_NAMESPACE"}

    family = str(path.get("source_family") or "")
    source_snapshot_id = provider_snapshots.get(family)
    if source_snapshot_id is None and (family == "LSB" or family.startswith("LSB_")):
        source_snapshot_id = canonical_snapshot_id
    if not source_snapshot_id:
        return {**base, "status": UNRESOLVED, "basis": "SOURCE_SNAPSHOT_UNMAPPED"}

    if source_snapshot_id == canonical_snapshot_id:
        candidates = _authoritative_enum_candidates(
            con,
            namespace=namespace,
            literal=subject_id,
            canonical_snapshot_id=canonical_snapshot_id,
        )
        if len(candidates) == 1:
            return {
                **base,
                **candidates[0],
                "status": VERIFIED,
                "basis": "AUTHORITATIVE_ENUM",
                "source_snapshot_id": source_snapshot_id,
                "canonical_snapshot_id": canonical_snapshot_id,
            }
        if len(candidates) > 1:
            return {
                **base,
                "status": AMBIGUOUS,
                "basis": "AUTHORITATIVE_ENUM_CONFLICT",
                "source_snapshot_id": source_snapshot_id,
                "canonical_snapshot_id": canonical_snapshot_id,
                "candidates": candidates,
            }
        return {
            **base,
            "status": UNRESOLVED,
            "basis": "AUTHORITATIVE_ENUM_NOT_FOUND",
            "source_snapshot_id": source_snapshot_id,
            "canonical_snapshot_id": canonical_snapshot_id,
        }

    numeric = _parse_int(subject_id)
    if numeric is None:
        # Same-looking names/symbols across providers are not an identity bridge.
        return {
            **base,
            "status": UNRESOLVED,
            "basis": "CROSS_PROVIDER_LITERAL_NOT_MAPPED",
            "source_snapshot_id": source_snapshot_id,
            "canonical_snapshot_id": canonical_snapshot_id,
        }

    resolution = identity_resolver.resolve_identity(
        con,
        source_snapshot_id=source_snapshot_id,
        target_snapshot_id=canonical_snapshot_id,
        namespace=namespace,
        source_numeric_id=str(numeric),
    )
    if resolution.status in {"EXACT", "TARGET_EQUIVALENT"} and resolution.confidence == "VERIFIED":
        canonical = _authoritative_enum_candidates(
            con,
            namespace=namespace,
            literal=resolution.target_numeric_id,
            canonical_snapshot_id=canonical_snapshot_id,
        )
        if len(canonical) == 1:
            return {
                **base,
                **canonical[0],
                "status": VERIFIED,
                "basis": "VERIFIED_SNAPSHOT_IDENTITY_BRIDGE",
                "source_snapshot_id": source_snapshot_id,
                "canonical_snapshot_id": canonical_snapshot_id,
                "semantic_key": resolution.semantic_key,
                "source_record_id": resolution.source_record_id,
                "target_record_id": resolution.target_record_id,
            }
        if len(canonical) > 1:
            return {
                **base,
                "status": AMBIGUOUS,
                "basis": "CANONICAL_ENUM_CONFLICT_AFTER_BRIDGE",
                "source_snapshot_id": source_snapshot_id,
                "canonical_snapshot_id": canonical_snapshot_id,
                "candidates": canonical,
            }
    return {
        **base,
        "status": AMBIGUOUS if "AMBIGUOUS" in resolution.status else UNRESOLVED,
        "basis": "SNAPSHOT_IDENTITY_BRIDGE_NOT_VERIFIED",
        "source_snapshot_id": source_snapshot_id,
        "canonical_snapshot_id": canonical_snapshot_id,
        "bridge_status": resolution.status,
        "bridge_confidence": resolution.confidence,
    }


def reconcile_acquisition_catalog(
    con: sqlite3.Connection,
    catalog: Mapping[str, Any],
    *,
    canonical_snapshot_id: str,
    provider_snapshots: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Annotate acquisition subjects with canonical identity without guessing.

    The returned catalog is a deep copy.  ``canonical_subjects`` contains only VERIFIED
    identities and is the safe input for a future shared-graph projection.
    """
    provider_snapshots = dict(provider_snapshots or {})
    result = deepcopy(dict(catalog))
    counts = {VERIFIED: 0, UNRESOLVED: 0, AMBIGUOUS: 0}
    canonical_subjects: list[dict[str, Any]] = []

    for subject in result.get("subjects", []):
        namespace = str(subject.get("subject_kind") or "").upper()
        literal = subject.get("subject_id")
        attempts = [
            _resolve_path(
                con,
                subject_kind=namespace,
                subject_id=literal,
                path=path,
                canonical_snapshot_id=canonical_snapshot_id,
                provider_snapshots=provider_snapshots,
            )
            for path in subject.get("paths", [])
        ]
        verified = {
            (row["canonical_id"], row["canonical_symbol"]): row
            for row in attempts
            if row.get("status") == VERIFIED
        }
        any_ambiguous = any(row.get("status") == AMBIGUOUS for row in attempts)
        if len(verified) == 1 and not any_ambiguous:
            identity = dict(next(iter(verified.values())))
            identity["status"] = VERIFIED
            identity["path_attempts"] = attempts
            canonical_subjects.append({
                "namespace": namespace,
                "canonical_id": identity["canonical_id"],
                "canonical_symbol": identity["canonical_symbol"],
                "source_subject_id": str(literal),
                "acquisition_types": list(subject.get("acquisition_types", [])),
            })
        elif len(verified) > 1 or any_ambiguous:
            identity = {
                "status": AMBIGUOUS,
                "namespace": namespace,
                "source_literal": str(literal),
                "basis": "CONFLICTING_IDENTITY_EVIDENCE",
                "path_attempts": attempts,
            }
        else:
            identity = {
                "status": UNRESOLVED,
                "namespace": namespace,
                "source_literal": str(literal),
                "basis": "NO_VERIFIED_IDENTITY_EVIDENCE",
                "path_attempts": attempts,
            }
        subject["canonical_identity"] = identity
        counts[identity["status"]] += 1

    result["identity_reconciliation"] = {
        "canonical_snapshot_id": canonical_snapshot_id,
        "status_counts": counts,
        "fail_closed": True,
        "names_are_identity_evidence": False,
    }
    result["canonical_subjects"] = sorted(
        canonical_subjects,
        key=lambda row: (row["namespace"], int(row["canonical_id"]), row["canonical_symbol"]),
    )
    return result


def verified_canonical_item_ids(catalog: Mapping[str, Any]) -> set[int]:
    """Return only reconciled VERIFIED ITEM IDs; raw numeric literals are ignored."""
    return {
        int(row["canonical_id"])
        for row in catalog.get("canonical_subjects", ())
        if row.get("namespace") == "ITEM"
    }
