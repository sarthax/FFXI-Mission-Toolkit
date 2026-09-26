#!/usr/bin/env python3
"""CLI for extracting and optionally ingesting portable client identity snapshots."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3

from workbench.client.identity_extract import (
    ZoneExportRequest,
    extract_client_identity_snapshot,
    load_zone_requests,
)
from workbench.client.identity_snapshot import ingest_client_identity_manifest


def _parse_zone(value: str) -> ZoneExportRequest:
    raw = str(value).strip()
    if ":" in raw:
        zone_id, zone_key = raw.split(":", 1)
        return ZoneExportRequest(int(zone_id), zone_key or None)
    return ZoneExportRequest(int(raw), None)


def _zones(args: argparse.Namespace) -> list[ZoneExportRequest]:
    out: list[ZoneExportRequest] = []
    if args.zones_json:
        out.extend(load_zone_requests(args.zones_json))
    out.extend(_parse_zone(x) for x in (args.zone or []))
    if args.all_zones:
        existing = {x.zone_id for x in out}
        out.extend(ZoneExportRequest(i) for i in range(512) if i not in existing)
    # deterministic order and duplicate suppression
    unique: dict[int, ZoneExportRequest] = {}
    for row in out:
        unique[row.zone_id] = row
    return [unique[i] for i in sorted(unique)]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract a portable snapshot of FFXI client event/dialog identities."
    )
    ap.add_argument("--client-root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--snapshot-id", required=True)
    ap.add_argument("--build")
    ap.add_argument("--family", default="RETAIL")
    ap.add_argument("--region")
    ap.add_argument("--language")
    ap.add_argument("--xi-tinkerer", type=Path, required=True)
    ap.add_argument(
        "--zone",
        action="append",
        help="Zone as ID or ID:SEMANTIC_KEY; may be repeated.",
    )
    ap.add_argument("--zones-json", type=Path)
    ap.add_argument(
        "--all-zones",
        action="store_true",
        help="Attempt all zone IDs 0-511; unsupported/missing exports are retained as failures.",
    )
    ap.add_argument(
        "--ingest-db",
        type=Path,
        help="Optional Workbench SQLite DB to ingest the completed snapshot into.",
    )
    args = ap.parse_args()

    zones = _zones(args)
    if not zones:
        ap.error("Select at least one --zone/--zones-json or use --all-zones")

    result = extract_client_identity_snapshot(
        client_root=args.client_root,
        output_dir=args.output,
        snapshot_id=args.snapshot_id,
        zones=zones,
        xi_tinkerer=args.xi_tinkerer,
        build=args.build,
        family=args.family,
        region=args.region,
        language=args.language,
    )
    payload = {
        "status": "EXTRACTED",
        "snapshot_id": result.snapshot_id,
        "build": result.build,
        "client_fingerprint": result.client_fingerprint,
        "manifest_path": result.manifest_path,
        "resource_count": len(result.resources),
        "failure_count": len(result.failures),
        "failures": list(result.failures),
    }

    if args.ingest_db:
        con = sqlite3.connect(args.ingest_db)
        try:
            ingestion = ingest_client_identity_manifest(
                con,
                manifest_path=Path(result.manifest_path),
            )
            con.commit()
        finally:
            con.close()
        payload["ingestion"] = ingestion
        payload["status"] = "EXTRACTED_AND_INGESTED"

    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
