"""Portable client identity-snapshot ingestion helpers.

The first supported source is xi-tinkerer dialog/event-text export. Extraction from an
installed client can remain a separate step; once exported, the data can be retained and
re-ingested without requiring the original FFXI installation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from workbench.client.event_fingerprint import parse_event_export

from workbench.core.services.identity_resolver import (
    IdentitySnapshot,
    ingest_dialog_records,
    ingest_entity_identity_records,
    ingest_event_structure_records,
    register_snapshot,
)
from workbench.core.services.client_entity_graph import sync_client_entity_graph


@dataclass(frozen=True)
class ClientIdentityManifest:
    snapshot_id: str
    build: str | None = None
    family: str = "RETAIL"
    region: str | None = None
    language: str | None = None
    extracted_at: str | None = None
    source_path: str | None = None
    files: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


def file_sha256(path: Path) -> str:
    h = sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_dialog_export(path: Path) -> dict[int, str]:
    """Parse xi-tinkerer YAML-like dialog export without requiring PyYAML."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    entries: dict[int, str] = {}
    i = 0
    while i < len(lines):
        match = re.match(r"^\s{2}(\d+):\s*(.*)$", lines[i])
        if not match:
            i += 1
            continue
        idx = int(match.group(1))
        value = match.group(2).strip()
        if value == "|-":
            block: list[str] = []
            i += 1
            while i < len(lines) and (lines[i].startswith("    ") or not lines[i].strip()):
                if lines[i].strip():
                    block.append(lines[i].strip())
                i += 1
            entries[idx] = " ".join(block)
            continue
        if value.startswith("'") and value.endswith("'") and len(value) >= 2:
            value = value[1:-1].replace("''", "'")
        entries[idx] = value
        i += 1
    return entries



def parse_entity_export(path: Path) -> dict[int, str]:
    """Parse xi-tinkerer entity-name YAML-like export without requiring PyYAML."""
    lines=Path(path).read_text(encoding="utf-8").splitlines()
    out: dict[int,str]={}
    current_id: int | None=None
    for line in lines:
        m_id=re.match(r"^\s*-\s*id:\s*(\d+)\s*$",line)
        if m_id:
            current_id=int(m_id.group(1))
            continue
        if current_id is None:
            continue
        m_name=re.match(r"^\s*name:\s*(.*?)\s*$",line)
        if not m_name:
            continue
        value=m_name.group(1).strip()
        if len(value)>=2 and value[0]==value[-1] and value[0] in {"'",'"'}:
            value=value[1:-1]
        value=value.replace("''","'").strip()
        if value:
            out[current_id]=value
        current_id=None
    return out

def write_manifest(path: Path, manifest: ClientIdentityManifest) -> None:
    Path(path).write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def read_manifest(path: Path) -> ClientIdentityManifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    raw["files"] = tuple(raw.get("files") or ())
    return ClientIdentityManifest(**raw)


def ingest_dialog_export(
    con: sqlite3.Connection,
    *,
    snapshot_id: str,
    zone_key: str,
    export_path: Path,
    build: str | None = None,
    family: str = "RETAIL",
    actor_key: str | None = None,
    owner_key: str | None = None,
) -> dict[str, Any]:
    """Register a client snapshot and ingest one exported zone dialog table."""
    export_path = Path(export_path)
    digest = file_sha256(export_path)
    register_snapshot(
        con,
        IdentitySnapshot(
            snapshot_id=snapshot_id,
            snapshot_type="CLIENT",
            family=family,
            version=build,
            source_location=str(export_path),
            fingerprint=digest,
            metadata={
                "extractor": "xi-tinkerer-dialog-export",
                "zone_key": zone_key,
            },
        ),
    )
    entries = parse_dialog_export(export_path)
    records = ingest_dialog_records(
        con,
        snapshot_id=snapshot_id,
        zone_key=zone_key,
        entries=entries,
        actor_key=actor_key,
        owner_key=owner_key,
        evidence_id_prefix=f"client-dialog:{snapshot_id}:{zone_key}",
    )
    return {
        "snapshot_id": snapshot_id,
        "zone_key": zone_key,
        "entry_count": len(records),
        "source_file": str(export_path),
        "sha256": digest,
    }


def ingest_client_identity_manifest(
    con: sqlite3.Connection,
    *,
    manifest_path: Path,
    snapshot_root: Path | None = None,
) -> dict[str, Any]:
    """Ingest every supported resource from one portable client snapshot manifest.

    The client snapshot is registered once using the manifest-level fingerprint, then each
    zone export contributes identity records without replacing snapshot provenance.
    """
    manifest_path = Path(manifest_path)
    manifest = read_manifest(manifest_path)
    root = Path(snapshot_root) if snapshot_root is not None else manifest_path.parent
    fingerprint = str(manifest.metadata.get("client_fingerprint") or "")
    register_snapshot(
        con,
        IdentitySnapshot(
            snapshot_id=manifest.snapshot_id,
            snapshot_type="CLIENT",
            family=manifest.family,
            version=manifest.build,
            recorded_at=manifest.extracted_at,
            source_location=manifest.source_path,
            fingerprint=fingerprint or None,
            metadata={
                "region": manifest.region,
                "language": manifest.language,
                "manifest_path": str(manifest_path),
                **dict(manifest.metadata),
            },
        ),
    )

    zones: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    record_count = 0
    dialog_entries_by_zone: dict[str, dict[int, str]] = {}
    for item in manifest.files:
        if str(item.get("kind") or "").upper() != "DIALOG":
            continue
        rel = item.get("relative_path")
        zone_key = item.get("zone_key")
        if not rel or not zone_key:
            continue
        dialog_path = root / str(rel)
        if dialog_path.is_file():
            dialog_entries_by_zone[str(zone_key)] = parse_dialog_export(dialog_path)
    for item in manifest.files:
        kind = str(item.get("kind") or "").upper()
        if kind not in {"DIALOG", "ENTITY", "EVENT_RESOURCE"}:
            continue
        rel = item.get("relative_path")
        zone_key = item.get("zone_key")
        zone_id = item.get("zone_id")
        if not rel or not zone_key:
            failures.append({
                "kind": kind,
                "zone_id": zone_id,
                "error": "manifest entry missing relative_path or zone_key",
            })
            continue
        path = root / str(rel)
        if not path.is_file():
            failures.append({
                "kind": kind,
                "zone_id": zone_id,
                "zone_key": zone_key,
                "error": f"snapshot resource missing: {path}",
            })
            continue

        if kind == "DIALOG":
            entries = parse_dialog_export(path)
            records = ingest_dialog_records(
                con,
                snapshot_id=manifest.snapshot_id,
                zone_key=str(zone_key),
                entries=entries,
                evidence_id_prefix=f"client-dialog:{manifest.snapshot_id}:{zone_key}",
            )
        elif kind == "ENTITY":
            entities=parse_entity_export(path)
            records=ingest_entity_identity_records(
                con,
                snapshot_id=manifest.snapshot_id,
                zone_key=str(zone_key),
                entities=entities,
                evidence_id_prefix=f"client-entity:{manifest.snapshot_id}:{zone_key}",
                confidence="HIGH",
                metadata={
                    "identity_basis":"client_entity_name_table",
                    "source_resource":str(rel),
                },
            )
        else:
            event_resources = parse_event_export(path)
            records = ingest_event_structure_records(
                con,
                snapshot_id=manifest.snapshot_id,
                zone_key=str(zone_key),
                resources=event_resources,
                evidence_id_prefix=f"client-event:{manifest.snapshot_id}:{zone_key}",
                dialog_entries=dialog_entries_by_zone.get(str(zone_key)),
            )

        record_count += len(records)
        zones.append({
            "kind": kind,
            "zone_id": zone_id,
            "zone_key": zone_key,
            "entry_count": len(records),
            "relative_path": rel,
        })

    entity_graph = sync_client_entity_graph(con)
    return {
        "snapshot_id": manifest.snapshot_id,
        "build": manifest.build,
        "client_fingerprint": fingerprint or None,
        "zones": zones,
        "record_count": record_count,
        "failures": failures,
        "entity_graph": entity_graph,
    }
