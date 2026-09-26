"""Installed-client extraction for portable identity snapshots.

This module wraps the existing xi-tinkerer export-dat workflow. It does not retain the full
FFXI installation: selected zone dialog/event tables and stable client-index file hashes are
materialized into a portable snapshot directory plus manifest.

Build/version is caller supplied because filename/version heuristics are not authoritative.
The manifest's content hashes provide an independent fingerprint of the extracted client.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import re
from typing import Callable, Iterable, Any

from .identity_snapshot import ClientIdentityManifest, file_sha256, write_manifest


def dat_id_for_zone(zone_id: int) -> int:
    if 0 <= int(zone_id) <= 255:
        return 6420 + int(zone_id)
    if 256 <= int(zone_id) <= 511:
        return 85590 + (int(zone_id) - 256)
    raise ValueError(f"Unsupported FFXI zone id: {zone_id}")


@dataclass(frozen=True)
class ZoneExportRequest:
    zone_id: int
    zone_key: str | None = None


@dataclass(frozen=True)
class ExportedResource:
    kind: str
    relative_path: str
    sha256: str
    size: int
    zone_id: int | None = None
    zone_key: str | None = None
    dat_id: int | None = None
    dat_path: str | None = None


@dataclass(frozen=True)
class ExtractionResult:
    snapshot_id: str
    output_dir: str
    build: str | None
    client_fingerprint: str
    resources: tuple[ExportedResource, ...]
    failures: tuple[dict[str, Any], ...]
    manifest_path: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_index_file(client_root: Path, name: str) -> Path | None:
    """Find the canonical client index file without assuming one exact casing/layout."""
    candidates = [
        client_root / name,
        client_root / "ROM" / name,
        client_root / name.upper(),
        client_root / "ROM" / name.upper(),
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _run_export(
    xi_tinkerer: Path,
    client_root: Path,
    dat_id: int,
    output_path: Path,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> tuple[bool, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    proc = runner(
        [
            str(xi_tinkerer),
            "export-dat",
            str(client_root),
            "--dat-id",
            str(dat_id),
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    return (
        bool(getattr(proc, "returncode", 1) == 0 and output_path.exists()),
        ((getattr(proc, "stdout", "") or "") + "\n" + (getattr(proc, "stderr", "") or "")).strip(),
    )


def _run_export_path(
    xi_tinkerer: Path,
    client_root: Path,
    dat_path: str,
    output_path: Path,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> tuple[bool, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    proc = runner(
        [
            str(xi_tinkerer),
            "export-dat",
            str(client_root),
            "--dat-path",
            str(dat_path),
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    return (
        bool(getattr(proc, "returncode", 1) == 0 and output_path.exists()),
        ((getattr(proc, "stdout", "") or "") + "\n" + (getattr(proc, "stderr", "") or "")).strip(),
    )


def load_zone_event_paths(path: Path) -> dict[int, list[str]]:
    """Parse vendored zone->event DAT mappings without a YAML dependency."""
    raw = Path(path).read_text(encoding="utf-8", errors="ignore")
    out: dict[int, list[str]] = {}
    current_zone: int | None = None
    for line in raw.splitlines():
        m_zone = re.match(r"\s*-\s*id:\s*(\d+)\s*$", line)
        if m_zone:
            current_zone = int(m_zone.group(1))
            continue
        if current_zone is None:
            continue
        m_event = re.match(r'\s*events:\s*"([^"]+)"\s*$', line)
        if m_event:
            out.setdefault(current_zone, []).append(m_event.group(1))
    return out


def _snapshot_fingerprint(resources: Iterable[ExportedResource], build: str | None) -> str:
    h = sha256()
    h.update(str(build or "UNKNOWN").encode("utf-8"))
    for row in sorted(resources, key=lambda r: (r.kind, r.relative_path)):
        h.update(row.kind.encode("utf-8"))
        h.update(row.relative_path.encode("utf-8"))
        h.update(row.sha256.encode("ascii"))
    return h.hexdigest()


def extract_client_identity_snapshot(
    *,
    client_root: Path,
    output_dir: Path,
    snapshot_id: str,
    zones: Iterable[ZoneExportRequest],
    xi_tinkerer: Path,
    build: str | None = None,
    family: str = "RETAIL",
    region: str | None = None,
    language: str | None = None,
    runner: Callable[..., Any] = subprocess.run,
    event_map_path: Path | None = None,
) -> ExtractionResult:
    """Extract a portable identity snapshot from one installed FFXI client.

    Failed/unsupported zone exports are retained in the manifest instead of aborting the
    entire snapshot, allowing old clients with incomplete resource coverage to remain useful.
    """
    client_root = Path(client_root)
    output_dir = Path(output_dir)
    xi_tinkerer = Path(xi_tinkerer)

    if not client_root.is_dir():
        raise FileNotFoundError(f"FFXI client root not found: {client_root}")
    if not xi_tinkerer.exists():
        raise FileNotFoundError(f"xi-tinkerer executable not found: {xi_tinkerer}")
    if not str(snapshot_id).strip():
        raise ValueError("snapshot_id is required")

    output_dir.mkdir(parents=True, exist_ok=True)
    resources: list[ExportedResource] = []
    failures: list[dict[str, Any]] = []
    if event_map_path is None:
        event_map_path = (
            Path(__file__).resolve().parents[2]
            / "vendor" / "FFXI-Resources" / "scripts" / "events" / "dats.yaml"
        )
    event_paths = load_zone_event_paths(event_map_path) if Path(event_map_path).is_file() else {}

    # Preserve hashes (and optionally copies) of the client resource index files. These hashes
    # are important even when build labels are supplied manually.
    for index_name in ("FTABLE.DAT", "VTABLE.DAT"):
        source = _find_index_file(client_root, index_name)
        if source is None:
            failures.append({"kind": "CLIENT_INDEX", "name": index_name, "error": "not found"})
            continue
        rel = Path("index") / index_name
        dest = output_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        resources.append(
            ExportedResource(
                kind="CLIENT_INDEX",
                relative_path=rel.as_posix(),
                sha256=file_sha256(dest),
                size=dest.stat().st_size,
            )
        )

    for request in zones:
        zone_id = int(request.zone_id)
        dat_id = dat_id_for_zone(zone_id)
        zone_key = request.zone_key or f"ZONE_{zone_id}"
        rel = Path("dialog") / f"{zone_id:03d}_{zone_key}.yml"
        dest = output_dir / rel
        ok, diagnostic = _run_export(
            xi_tinkerer,
            client_root,
            dat_id,
            dest,
            runner=runner,
        )
        if not ok:
            failures.append({
                "kind": "DIALOG",
                "zone_id": zone_id,
                "zone_key": zone_key,
                "dat_id": dat_id,
                "error": diagnostic or "xi-tinkerer export failed",
            })
            if dest.exists():
                dest.unlink()
            continue
        resources.append(
            ExportedResource(
                kind="DIALOG",
                relative_path=rel.as_posix(),
                sha256=file_sha256(dest),
                size=dest.stat().st_size,
                zone_id=zone_id,
                zone_key=zone_key,
                dat_id=dat_id,
            )
        )

        for event_index, event_dat_path in enumerate(event_paths.get(zone_id, [])):
            suffix = "" if event_index == 0 else f"_variant{event_index}"
            event_rel = Path("events") / f"{zone_id:03d}_{zone_key}{suffix}.yml"
            event_dest = output_dir / event_rel
            event_ok, event_diag = _run_export_path(
                xi_tinkerer,
                client_root,
                event_dat_path,
                event_dest,
                runner=runner,
            )
            if not event_ok:
                failures.append({
                    "kind": "EVENT_RESOURCE",
                    "zone_id": zone_id,
                    "zone_key": zone_key,
                    "dat_path": event_dat_path,
                    "error": event_diag or "xi-tinkerer event export failed",
                })
                if event_dest.exists():
                    event_dest.unlink()
                continue
            resources.append(
                ExportedResource(
                    kind="EVENT_RESOURCE",
                    relative_path=event_rel.as_posix(),
                    sha256=file_sha256(event_dest),
                    size=event_dest.stat().st_size,
                    zone_id=zone_id,
                    zone_key=zone_key,
                    dat_path=event_dat_path,
                )
            )

    fingerprint = _snapshot_fingerprint(resources, build)
    manifest = ClientIdentityManifest(
        snapshot_id=snapshot_id,
        build=build,
        family=family,
        region=region,
        language=language,
        extracted_at=_utc_now(),
        source_path=str(client_root),
        files=tuple(asdict(r) for r in resources),
        metadata={
            "client_fingerprint": fingerprint,
            "extractor": "workbench.client.identity_extract",
            "xi_tinkerer": str(xi_tinkerer),
            "failures": failures,
        },
    )
    manifest_path = output_dir / "identity_snapshot.json"
    write_manifest(manifest_path, manifest)

    return ExtractionResult(
        snapshot_id=snapshot_id,
        output_dir=str(output_dir),
        build=build,
        client_fingerprint=fingerprint,
        resources=tuple(resources),
        failures=tuple(failures),
        manifest_path=str(manifest_path),
    )


def load_zone_requests(path: Path) -> list[ZoneExportRequest]:
    """Load [{zone_id, zone_key?}, ...] from JSON for CLI/GUI callers."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Zone request file must contain a JSON list")
    return [
        ZoneExportRequest(zone_id=int(row["zone_id"]), zone_key=row.get("zone_key"))
        for row in raw
    ]
