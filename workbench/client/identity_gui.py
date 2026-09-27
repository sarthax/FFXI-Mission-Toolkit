"""GUI-facing orchestration for portable client identity snapshots.

Keeps FastAPI routes thin while reusing the existing extraction, manifest-ingestion, and
snapshot-aware EVENT comparison services.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from workbench.client.identity_extract import (
    ExtractionResult,
    ZoneExportRequest,
    extract_client_identity_snapshot,
)
from workbench.client.identity_snapshot import ingest_client_identity_manifest
from workbench.core.services.identity_resolver import compare_event_snapshots, ensure_schema


class ClientSnapshotImportError(ValueError):
    """Actionable validation error safe to surface in the local GUI."""


def safe_snapshot_name(snapshot_id: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", str(snapshot_id or "").strip()).strip(".-_")
    if not value:
        raise ClientSnapshotImportError("Snapshot ID must contain at least one letter or number.")
    return value[:120]


def _metadata(raw: str | None) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def list_client_snapshots(
    db_path: Path,
    *,
    current_snapshot_id: str | None = None,
    current_client_path: str | None = None,
) -> list[dict[str, Any]]:
    """List imported CLIENT snapshots with namespace counts and current-client indication."""
    db_path = Path(db_path)
    if not db_path.is_file():
        return []
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"identity_snapshots", "identity_records"}.issubset(tables):
            return []
        rows = list(con.execute(
            """
            SELECT s.*,
                   SUM(CASE WHEN r.namespace='EVENT' THEN 1 ELSE 0 END) AS event_count,
                   SUM(CASE WHEN r.namespace='ENTITY' THEN 1 ELSE 0 END) AS entity_count,
                   SUM(CASE WHEN r.namespace='DIALOG' THEN 1 ELSE 0 END) AS dialog_count
              FROM identity_snapshots s
              LEFT JOIN identity_records r ON r.snapshot_id=s.snapshot_id
             WHERE UPPER(s.snapshot_type)='CLIENT'
             GROUP BY s.snapshot_id
             ORDER BY COALESCE(s.recorded_at, '') DESC, s.snapshot_id
            """
        ))
    finally:
        con.close()

    current_path = None
    if current_client_path:
        try:
            current_path = str(Path(current_client_path).resolve()).casefold()
        except OSError:
            current_path = str(current_client_path).casefold()

    result: list[dict[str, Any]] = []
    for row in rows:
        meta = _metadata(row["metadata_json"])
        source_path = row["source_location"]
        source_matches = False
        if current_path and source_path:
            try:
                source_matches = str(Path(source_path).resolve()).casefold() == current_path
            except OSError:
                source_matches = str(source_path).casefold() == current_path
        result.append({
            "snapshot_id": row["snapshot_id"],
            "build": row["version"],
            "family": row["family"],
            "region": meta.get("region"),
            "language": meta.get("language"),
            "source_path": source_path,
            "recorded_at": row["recorded_at"],
            "event_count": int(row["event_count"] or 0),
            "entity_count": int(row["entity_count"] or 0),
            "dialog_count": int(row["dialog_count"] or 0),
            "is_current": bool(
                (current_snapshot_id and row["snapshot_id"] == current_snapshot_id)
                or source_matches
            ),
        })
    return result


def _required_client_file(client_root: Path, name: str) -> Path | None:
    candidates = [
        client_root / name,
        client_root / name.upper(),
        client_root / "ROM" / name,
        client_root / "ROM" / name.upper(),
    ]
    return next((path for path in candidates if path.is_file()), None)


def validate_client_snapshot_import(
    *,
    client_root: Path,
    snapshot_id: str,
    xi_tinkerer: Path,
    db_path: Path,
    output_dir: Path,
) -> str:
    """Validate inputs before extraction so the GUI can fail early with actionable errors."""
    client_root = Path(client_root)
    xi_tinkerer = Path(xi_tinkerer)
    db_path = Path(db_path)
    output_dir = Path(output_dir)

    safe_name = safe_snapshot_name(snapshot_id)
    if not client_root.is_dir():
        raise ClientSnapshotImportError(f"FFXI client root does not exist: {client_root}")

    missing = [
        name for name in ("FFXiMain.dll", "FTABLE.DAT", "VTABLE.DAT")
        if _required_client_file(client_root, name) is None
    ]
    if missing:
        raise ClientSnapshotImportError(
            "FFXI client root is missing required file(s): " + ", ".join(missing)
        )
    if not xi_tinkerer.is_file():
        raise ClientSnapshotImportError(
            f"xi-tinkerer is not installed at {xi_tinkerer}. Build/install it before importing."
        )
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ClientSnapshotImportError(
            f"Snapshot output already exists and will not be overwritten: {output_dir}"
        )

    if db_path.is_file():
        con = sqlite3.connect(db_path)
        try:
            tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "identity_snapshots" in tables:
                exists = con.execute(
                    "SELECT 1 FROM identity_snapshots WHERE snapshot_id=?",
                    (str(snapshot_id).strip(),),
                ).fetchone()
                if exists:
                    raise ClientSnapshotImportError(
                        f"Snapshot ID '{snapshot_id}' already exists in workbench.db; choose a new ID."
                    )
        finally:
            con.close()
    return safe_name


def zone_requests_from_database(zone_db: Path) -> list[ZoneExportRequest]:
    """Build the all-zone extraction request list from the toolkit's canonical zone table."""
    zone_db = Path(zone_db)
    if not zone_db.is_file():
        raise ClientSnapshotImportError(
            f"Zone database not found: {zone_db}. Build the toolkit database before importing a client snapshot."
        )
    con = sqlite3.connect(zone_db)
    try:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "zones" not in tables:
            raise ClientSnapshotImportError(
                "Zone database has no 'zones' table. Rebuild zone/item reference data first."
            )
        rows = list(con.execute(
            "SELECT zoneid,name FROM zones WHERE zoneid BETWEEN 0 AND 511 ORDER BY zoneid"
        ))
    finally:
        con.close()
    if not rows:
        raise ClientSnapshotImportError("Zone database contains no zones to extract.")

    requests: list[ZoneExportRequest] = []
    for zone_id, name in rows:
        zone_key = re.sub(r"[^A-Za-z0-9]+", "_", str(name or f"ZONE_{zone_id}")).strip("_").upper()
        requests.append(ZoneExportRequest(zone_id=int(zone_id), zone_key=zone_key or f"ZONE_{zone_id}"))
    return requests


def import_client_snapshot(
    *,
    client_root: Path,
    snapshot_id: str,
    build_label: str,
    region: str | None,
    language: str | None,
    xi_tinkerer: Path,
    db_path: Path,
    zone_db: Path,
    snapshots_root: Path,
) -> dict[str, Any]:
    """Extract all zones, write a portable manifest, then ingest identity rows into workbench.db."""
    snapshot_id = str(snapshot_id or "").strip()
    build_label = str(build_label or "").strip()
    if not snapshot_id:
        raise ClientSnapshotImportError("Snapshot ID is required.")
    if not build_label:
        raise ClientSnapshotImportError("Build label is required.")

    safe_name = safe_snapshot_name(snapshot_id)
    output_dir = Path(snapshots_root) / safe_name
    validate_client_snapshot_import(
        client_root=Path(client_root),
        snapshot_id=snapshot_id,
        xi_tinkerer=Path(xi_tinkerer),
        db_path=Path(db_path),
        output_dir=output_dir,
    )
    zones = zone_requests_from_database(Path(zone_db))

    extraction: ExtractionResult = extract_client_identity_snapshot(
        client_root=Path(client_root),
        output_dir=output_dir,
        snapshot_id=snapshot_id,
        zones=zones,
        xi_tinkerer=Path(xi_tinkerer),
        build=build_label,
        family="RETAIL",
        region=(str(region).strip() or None) if region is not None else None,
        language=(str(language).strip() or None) if language is not None else None,
    )

    con = sqlite3.connect(Path(db_path))
    try:
        ensure_schema(con)
        ingest = ingest_client_identity_manifest(
            con,
            manifest_path=Path(extraction.manifest_path),
            snapshot_root=output_dir,
        )
        con.commit()
    finally:
        con.close()

    return {
        "snapshot_id": snapshot_id,
        "build": build_label,
        "output_dir": str(output_dir),
        "zones_requested": len(zones),
        "resources": len(extraction.resources),
        "extraction_failures": list(extraction.failures),
        "record_count": int(ingest.get("record_count") or 0),
        "ingest_failures": list(ingest.get("failures") or []),
    }


def compare_client_snapshots(
    db_path: Path,
    *,
    source_snapshot_id: str,
    target_snapshot_id: str,
    zone_key: str | None = None,
    minimum_confidence: str = "HIGH",
) -> dict[str, Any]:
    if not Path(db_path).is_file():
        raise ValueError("workbench.db does not exist yet.")
    if not source_snapshot_id or not target_snapshot_id:
        raise ValueError("Source and target snapshots are required.")
    if source_snapshot_id == target_snapshot_id:
        raise ValueError("Source and target snapshots must be different.")
    con = sqlite3.connect(Path(db_path))
    try:
        return compare_event_snapshots(
            con,
            source_snapshot_id=source_snapshot_id,
            target_snapshot_id=target_snapshot_id,
            zone_key=(zone_key.strip() or None) if zone_key else None,
            minimum_confidence=str(minimum_confidence or "HIGH").upper(),
        )
    finally:
        con.close()


def summarize_comparison(report: dict[str, Any]) -> dict[str, int]:
    """Normalize resolver statuses into the GUI summary buckets requested by operators."""
    counts = dict(report.get("counts") or {})
    ambiguous = sum(
        int(counts.get(status, 0))
        for status in ("SOURCE_ID_AMBIGUOUS", "TARGET_ID_AMBIGUOUS")
    )
    low_confidence = int(counts.get("TARGET_ID_LOW_CONFIDENCE", 0))
    unresolved = sum(
        int(counts.get(status, 0))
        for status in ("SOURCE_ID_UNRESOLVED", "TARGET_ID_UNRESOLVED")
    )
    return {
        "total": int(report.get("total") or 0),
        "EXACT": int(counts.get("EXACT", 0)),
        "TARGET_EQUIVALENT": int(counts.get("TARGET_EQUIVALENT", 0)),
        "ambiguous": ambiguous,
        "LOW_CONFIDENCE": low_confidence,
        "unresolved": unresolved,
    }
