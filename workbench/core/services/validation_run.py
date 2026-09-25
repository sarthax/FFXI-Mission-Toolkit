"""Deterministic multi-validator orchestration for Workbench validation runs."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from typing import Iterable

from workbench.core import graph
from workbench.core.schema import ValidationRun, ValidationResult


@dataclass(frozen=True)
class ValidationSpec:
    validation_id: str
    validation_type: str
    subject_id: str
    script: str
    args: tuple[str, ...] = ()
    dimension: str | None = None
    required: bool = True
    source: str | None = None
    target: str | None = None
    timeout_seconds: int = 120


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def execute_validation(spec: ValidationSpec, run_id: str) -> ValidationResult:
    try:
        completed=subprocess.run(
            [sys.executable,spec.script,*spec.args],
            capture_output=True,
            text=True,
            timeout=spec.timeout_seconds,
        )
        status="VERIFIED" if completed.returncode==0 else "FAILED"
        notes=completed.stdout.splitlines()[-10:]+completed.stderr.splitlines()[-5:]
    except subprocess.TimeoutExpired as exc:
        status="FAILED"
        notes=[f"Validator timed out after {spec.timeout_seconds} seconds."]
        if exc.stdout:
            notes.extend(str(exc.stdout).splitlines()[-5:])
        if exc.stderr:
            notes.extend(str(exc.stderr).splitlines()[-5:])
    return ValidationResult(
        validation_id=spec.validation_id,
        validation_type=spec.validation_type,
        subject_id=spec.subject_id,
        status=status,
        source=spec.source,
        target=spec.target,
        notes=notes,
        run_id=run_id,
    )


def _dimension_summary(
    specs: tuple[ValidationSpec, ...],
    results: tuple[ValidationResult, ...],
) -> dict[str, dict]:
    result_by_id={r.validation_id:r for r in results}
    out={}
    for spec in specs:
        dimension=spec.dimension or spec.validation_type.lower()
        row=out.setdefault(dimension,{"required":False,"results":[],"status":"UNKNOWN"})
        row["required"]=row["required"] or spec.required
        result=result_by_id[spec.validation_id]
        row["results"].append({
            "validation_id":result.validation_id,
            "status":result.status,
            "required":spec.required,
        })
    for row in out.values():
        required=[item["status"] for item in row["results"] if item["required"]]
        considered=required or [item["status"] for item in row["results"]]
        if considered and all(status=="VERIFIED" for status in considered):
            row["status"]="VERIFIED"
        elif any(status=="FAILED" for status in considered):
            row["status"]="FAILED"
        else:
            row["status"]="UNKNOWN"
    return out


def run_validation_suite(
    specs: Iterable[ValidationSpec],
    *,
    run_id: str,
    name: str,
    source_snapshot_id: str | None = None,
    target_snapshot_id: str | None = None,
    feature_id: str | None = None,
    graph_db: Path | None = None,
) -> dict:
    spec_list=tuple(specs)
    started=_now()
    results=tuple(execute_validation(spec,run_id) for spec in spec_list)
    dimensions=_dimension_summary(spec_list,results)

    required_results=[
        result
        for spec,result in zip(spec_list,results)
        if spec.required
    ]
    if any(result.status=="FAILED" for result in required_results):
        overall="FAILED"
    elif required_results and all(result.status=="VERIFIED" for result in required_results):
        overall="VERIFIED"
    elif not required_results and results and all(result.status=="VERIFIED" for result in results):
        overall="VERIFIED"
    else:
        overall="UNKNOWN"

    finished=_now()
    run=ValidationRun(
        run_id=run_id,
        name=name,
        source_snapshot_id=source_snapshot_id,
        target_snapshot_id=target_snapshot_id,
        feature_id=feature_id,
        status=overall,
        started_at=started,
        finished_at=finished,
        metadata={
            "validator_count":len(spec_list),
            "required_count":sum(1 for spec in spec_list if spec.required),
            "dimensions":dimensions,
        },
    )

    if graph_db is not None:
        con=graph.init_db(graph_db)
        try:
            graph.insert_record(con,run)
            for result in results:
                graph.insert_record(con,result)
            con.commit()
        finally:
            con.close()

    return {
        "schema":1,
        "kind":"WORKBENCH_VALIDATION_SUITE",
        "validation_run":asdict(run),
        "validation_results":[asdict(result) for result in results],
        "dimensions":dimensions,
    }


def specs_from_payload(payload: dict) -> tuple[ValidationSpec, ...]:
    specs=[]
    for i,row in enumerate(payload.get("validators",[]),start=1):
        script=row.get("script")
        if not script:
            raise ValueError(f"Validator #{i} is missing script")
        validation_type=str(row.get("validation_type") or Path(script).stem.upper())
        validation_id=str(row.get("validation_id") or f"{validation_type.lower()}:{i}")
        subject_id=str(row.get("subject_id") or "validation-suite")
        specs.append(ValidationSpec(
            validation_id=validation_id,
            validation_type=validation_type,
            subject_id=subject_id,
            script=str(script),
            args=tuple(str(arg) for arg in row.get("args",[])),
            dimension=row.get("dimension"),
            required=bool(row.get("required",True)),
            source=row.get("source"),
            target=row.get("target"),
            timeout_seconds=int(row.get("timeout_seconds",120)),
        ))
    return tuple(specs)
