#!/usr/bin/env python3
"""Compatibility CLI/import wrapper for Development mission event reconciliation."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from workbench.devtools.missions import event_reconcile as _canonical


def main() -> None:
    ap=argparse.ArgumentParser(description=_canonical.__doc__)
    ap.add_argument("feature_id",help="Canonical mission/quest feature id already emitted to the graph")
    ap.add_argument("--db",type=Path,default=Path("workbench.db"),help="Workbench DB")
    ap.add_argument("--catalog-db",type=Path,default=Path("ffxi_zone_database.db"),help="Indexed source/reference DB")
    ap.add_argument("--write",action="store_true",help="Persist exact support edges; default is preview only")
    args=ap.parse_args()

    con=sqlite3.connect(args.db)
    catalog=sqlite3.connect(args.catalog_db) if args.catalog_db.exists() else None
    try:
        rows=_canonical.reconcile_feature_events(con,args.feature_id,catalog_con=catalog)
        if not rows:
            print("no emitted mission events found for feature")
            return
        for row in rows:
            print(f"{row.event_node}")
            print(f"  source ref: {row.source_ref_status}" + (f" -> {row.source_ref_node}" if row.source_ref_node else ""))
            for check in row.client_checks:
                suffix=f" -> {check.event_record_id}" if check.event_record_id else ""
                print(f"  client {check.snapshot_id}: {check.status} [{check.confidence}]{suffix}")
                if check.reason:
                    print(f"    {check.reason}")
        if not args.write:
            print("preview only; pass --write to persist exact support relationships")
            return
        count=_canonical.persist_event_reconciliation(con,rows)
        print(f"persisted relationships: {count}")
    finally:
        if catalog is not None:
            catalog.close()
        con.close()


if __name__=="__main__":
    main()
else:
    sys.modules[__name__] = _canonical
