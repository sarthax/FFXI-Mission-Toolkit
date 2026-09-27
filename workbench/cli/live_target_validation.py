"""Read-only CLI for validating normalized records against a live target database."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

from workbench.adapters.servers import LogicalRecord, adapter_for
from workbench.migrations.live_target_validation import (
    DBAPITargetReader,
    persist_live_validation,
    validate_live_records,
)


def _record(row: dict) -> LogicalRecord:
    return LogicalRecord(
        logical_type=str(row["logical_type"]),
        identity=tuple((str(k), v) for k, v in row.get("identity", [])),
        fields=dict(row.get("fields") or {}),
        source_family=str(row.get("source_family") or "UNKNOWN"),
        source_table=str(row.get("source_table") or row["logical_type"]),
        notes=tuple(str(x) for x in row.get("notes", [])),
    )


def _load_expected(path: Path) -> tuple[str, list[LogicalRecord], dict]:
    payload=json.loads(path.read_text(encoding="utf-8"))
    logical_type=payload.get("logical_type")
    rows=payload.get("records")
    if not isinstance(logical_type,str) or not logical_type:
        raise ValueError("expected JSON requires logical_type")
    if not isinstance(rows,list):
        raise ValueError("expected JSON requires records[]")
    records=[_record(row) for row in rows]
    if any(row.logical_type != logical_type for row in records):
        raise ValueError("all records must match payload logical_type")
    return logical_type,records,payload


def _connect(args):
    if args.sqlite_db:
        uri=f"file:{Path(args.sqlite_db).resolve()}?mode=ro"
        return sqlite3.connect(uri,uri=True), "qmark", "sqlite"
    try:
        import mysql.connector
    except ImportError as exc:
        raise RuntimeError(
            "mysql-connector-python is required for MySQL/MariaDB live validation"
        ) from exc
    password=os.environ.get(args.password_env)
    if password is None:
        raise RuntimeError(
            f"Environment variable {args.password_env} is not set for the database password"
        )
    con=mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=password,
        database=args.database,
    )
    return con,"format","mysql"


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--expected",type=Path,required=True,
                    help="JSON payload containing logical_type and normalized records[].")
    ap.add_argument("--target-family",required=True,
                    help="DSP, Topaz, Topaz-Next, or LSB.")
    ap.add_argument("--target-root",type=Path,default=Path("."),
                    help="Target source root used only to construct the schema adapter.")

    backend=ap.add_mutually_exclusive_group(required=True)
    backend.add_argument("--sqlite-db",type=Path,
                         help="Read-only SQLite target database, primarily for deterministic/local validation.")
    backend.add_argument("--database",
                         help="MySQL/MariaDB database name.")

    ap.add_argument("--host",default="127.0.0.1")
    ap.add_argument("--port",type=int,default=3306)
    ap.add_argument("--user")
    ap.add_argument("--password-env",default="FFXI_DB_PASSWORD",
                    help="Environment variable containing the MySQL/MariaDB password.")
    ap.add_argument("--target-snapshot-id")
    ap.add_argument("--graph-db",type=Path)
    ap.add_argument("--run-id")
    ap.add_argument("--feature-id")
    ap.add_argument("--source-snapshot-id")
    ap.add_argument("--json",type=Path,help="Optional output JSON path.")
    args=ap.parse_args(argv)

    if args.database and not args.user:
        ap.error("--user is required with --database")

    logical_type,records,input_payload=_load_expected(args.expected)
    adapter=adapter_for(args.target_family,args.target_root)
    con,paramstyle,backend_name=_connect(args)
    try:
        reader=DBAPITargetReader(con,paramstyle=paramstyle)
        result=validate_live_records(
            adapter,
            reader,
            logical_type,
            records,
            target_snapshot_id=args.target_snapshot_id or input_payload.get("target_snapshot_id"),
        )
    finally:
        con.close()

    output={
        **result,
        "target_family":adapter.family,
        "target_adapter_id":adapter.adapter_id,
        "connection_backend":backend_name,
        "credentials_persisted":False,
    }

    if args.graph_db:
        run_id=args.run_id or f"run:live-target:{logical_type}"
        output["canonical_validation"]=persist_live_validation(
            result,
            args.graph_db,
            run_id=run_id,
            feature_id=args.feature_id,
            source_snapshot_id=args.source_snapshot_id or input_payload.get("source_snapshot_id"),
            target_snapshot_id=args.target_snapshot_id or input_payload.get("target_snapshot_id"),
            source=str(args.expected),
            target=f"{backend_name}:{adapter.family}",
        )

    rendered=json.dumps(output,indent=2,sort_keys=True,default=str)
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(rendered+"\n",encoding="utf-8")
    else:
        print(rendered)

    if result["status"] in {"FAILED","CONTRADICTED","MISSING"}:
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
