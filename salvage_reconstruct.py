#!/usr/bin/env python3
"""Build a read-only Salvage reconstruction dossier from an ingested capture."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from workbench.domains.salvage_reconstruction import dossier_json
from workbench.runtime.paths import DATABASE_PATH

DB_PATH = DATABASE_PATH


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("capture_id", type=int)
    p.add_argument("--zone", dest="zone_db")
    p.add_argument("--db", type=Path, default=DB_PATH)
    args = p.parse_args()
    con = sqlite3.connect(str(args.db))
    try:
        print(dossier_json(con, args.capture_id, args.zone_db))
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
