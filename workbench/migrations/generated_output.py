"""Materialize deterministic generated migration outputs with provenance."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import json
from typing import Any, Iterable


@dataclass(frozen=True)
class GeneratedOutput:
    output_id: str
    relative_path: str
    artifact_type: str
    content: str
    generator: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeneratedOutputRecord:
    output_id: str
    relative_path: str
    artifact_type: str
    generator: str
    sha256: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeneratedOutputResult:
    records: tuple[GeneratedOutputRecord, ...]
    skipped: tuple[str, ...]
    status: str


def _safe_destination(root: Path, relative_path: str) -> Path:
    rel=Path(relative_path.replace("\\","/"))
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"Unsafe generated output path: {relative_path}")
    root=root.resolve()
    destination=(root/rel).resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Generated output escapes package root: {relative_path}") from exc
    return destination


def materialize_generated_outputs(
    outputs: Iterable[GeneratedOutput],
    package_root: Path,
    *,
    overwrite: bool = False,
) -> GeneratedOutputResult:
    records=[]
    skipped=[]
    for output in outputs:
        destination=_safe_destination(package_root,output.relative_path)
        if destination.exists() and not overwrite:
            skipped.append(output.relative_path)
            continue
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(output.content,encoding="utf-8",newline="\n")
        sha=hashlib.sha256(destination.read_bytes()).hexdigest()
        records.append(GeneratedOutputRecord(
            output_id=output.output_id,
            relative_path=destination.relative_to(package_root.resolve()).as_posix(),
            artifact_type=output.artifact_type,
            generator=output.generator,
            sha256=sha,
            metadata=dict(output.metadata),
        ))

    if skipped and records:
        status="PARTIAL"
    elif skipped:
        status="SKIPPED"
    else:
        status="MATERIALIZED"
    return GeneratedOutputResult(tuple(records),tuple(skipped),status)


def write_generated_output_journal(
    package_root: Path,
    result: GeneratedOutputResult,
    filename: str = "WORKBENCH_GENERATED_OUTPUTS.json",
) -> Path:
    package_root.mkdir(parents=True,exist_ok=True)
    payload={
        "schema":1,
        "kind":"WORKBENCH_GENERATED_OUTPUT_JOURNAL",
        "status":result.status,
        "outputs":[
            {
                "output_id":record.output_id,
                "relative_path":record.relative_path,
                "artifact_type":record.artifact_type,
                "generator":record.generator,
                "sha256":record.sha256,
                "metadata":dict(record.metadata),
            }
            for record in result.records
        ],
        "skipped":list(result.skipped),
    }
    path=package_root/filename
    path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return path
