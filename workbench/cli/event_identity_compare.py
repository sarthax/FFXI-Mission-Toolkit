#!/usr/bin/env python3
"""Compare EVENT identities between two ingested client snapshots."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sqlite3
import sys

from workbench.core.services.identity_resolver import compare_event_snapshots


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Compare snapshot-aware FFXI EVENT identities across two client snapshots."
    )
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--source", required=True, help="Source identity snapshot id")
    ap.add_argument("--target", required=True, help="Target identity snapshot id")
    ap.add_argument("--zone", help="Optional semantic zone key")
    ap.add_argument("--minimum-confidence", default="HIGH")
    ap.add_argument("--format", choices=("json", "csv"), default="json")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    try:
        report = compare_event_snapshots(
            con,
            source_snapshot_id=args.source,
            target_snapshot_id=args.target,
            zone_key=args.zone,
            minimum_confidence=args.minimum_confidence,
        )
    finally:
        con.close()

    if args.format == "json":
        rendered = json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0

    fields = [
        "zone_key",
        "source_actor_key",
        "source_event_id",
        "target_event_id",
        "status",
        "confidence",
        "match_basis",
        "source_record_id",
        "target_record_id",
        "reason",
    ]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fh = args.output.open("w", encoding="utf-8", newline="")
        close = True
    else:
        fh = sys.stdout
        close = False
    try:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["rows"])
    finally:
        if close:
            fh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
