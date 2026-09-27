#!/usr/bin/env python3
"""CLI for static read-only PE/COFF client binary indexing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workbench.client.binary_index import index_binary, write_index
from workbench.core.services.client_binary_graph import ingest_client_binary_index


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("binary",type=Path)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--label")
    ap.add_argument("--client-build")
    ap.add_argument("--min-string-length",type=int,default=5)
    ap.add_argument("--max-strings",type=int,default=25000)
    ap.add_argument("--graph-db",type=Path)
    ap.add_argument("--source-snapshot-id")
    args=ap.parse_args()

    payload=index_binary(
        args.binary,
        label=args.label,
        client_build=args.client_build,
        min_string_length=args.min_string_length,
        max_strings=args.max_strings,
    )
    if args.output:
        write_index(payload,args.output)
    if args.graph_db:
        payload["graph_ingest"]=ingest_client_binary_index(
            payload,
            args.graph_db,
            source_snapshot_id=args.source_snapshot_id,
        )
    print(json.dumps(payload,indent=2,sort_keys=True))


if __name__=="__main__":
    main()
