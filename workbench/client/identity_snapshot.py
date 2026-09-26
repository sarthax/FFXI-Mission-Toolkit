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

from workbench.core.services.identity_resolver import (
    IdentitySnapshot,
    ingest_dialog_records,
    register_snapshot,
)


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
