#!/usr/bin/env python3
"""Compatibility CLI for single validators and multi-validator Workbench suites."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workbench.core.services.validation_run import (
    ValidationSpec,
    execute_validation,
    run_validation_suite,
    specs_from_payload,
)


def run(script,args,run_id=None):
    """Legacy single-validator compatibility wrapper."""
    rid=run_id or f"run:{Path(script).stem}"
    result=execute_validation(
        ValidationSpec(
            validation_id=f"{Path(script).stem}:{' '.join(args)}",
            validation_type=Path(script).stem.upper(),
            subject_id=" ".join(args) or script,
            script=script,
            args=tuple(args),
        ),
        rid,
    )
    return {
        "run_id":result.run_id,
        "validation_id":result.validation_id,
        "validation_type":result.validation_type,
        "subject_id":result.subject_id,
        "status":result.status,
        "evidence_id":result.evidence_id,
        "source":result.source,
        "target":result.target,
        "notes":result.notes,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--suite",type=Path,help="JSON suite manifest containing validators[].")
    ap.add_argument("--graph-db",type=Path,help="Persist suite ValidationRun/ValidationResult records.")
    ap.add_argument("--name",default="validation suite")
    ap.add_argument("--feature-id")
    ap.add_argument("--source-snapshot-id")
    ap.add_argument("--target-snapshot-id")
    ap.add_argument("script",nargs="?")
    ap.add_argument("args",nargs="*")
    a=ap.parse_args()

    if a.suite:
        payload=json.loads(a.suite.read_text(encoding="utf-8"))
        specs=specs_from_payload(payload)
        run_id=a.run_id or payload.get("run_id") or f"run:{a.suite.stem}"
        out=run_validation_suite(
            specs,
            run_id=run_id,
            name=payload.get("name") or a.name,
            source_snapshot_id=a.source_snapshot_id or payload.get("source_snapshot_id"),
            target_snapshot_id=a.target_snapshot_id or payload.get("target_snapshot_id"),
            feature_id=a.feature_id or payload.get("feature_id"),
            graph_db=a.graph_db,
        )
        print(json.dumps(out,indent=2))
        if out["validation_run"]["status"]=="FAILED":
            raise SystemExit(1)
        return

    if not a.script:
        ap.error("script is required unless --suite is supplied")
    r=run(a.script,a.args,a.run_id)
    out={"schema":2,"validation":r}
    if a.run_id:
        out["validation_run"]={"run_id":a.run_id,"name":Path(a.script).stem,"status":r["status"]}
    print(json.dumps(out,indent=2))
    if r["status"]=="FAILED":
        raise SystemExit(1)


if __name__=="__main__":
    raise SystemExit(main())
