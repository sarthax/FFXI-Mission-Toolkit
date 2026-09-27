"""Machine-readable, review-only patch plans with drift fingerprints."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Mapping, Sequence

from workbench.migrations.generated_output import GeneratedOutput
from workbench.migrations.patch_operations import PatchOperation, preview_patch_operations


@dataclass(frozen=True)
class PatchPlanBuildResult:
    status: str
    output: GeneratedOutput
    target_statuses: tuple[tuple[str,str], ...]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_patch_plan_output(
    plan_id: str,
    target_sources: Mapping[str,str],
    operations: Mapping[str,Sequence[PatchOperation]],
) -> PatchPlanBuildResult:
    targets=[]
    statuses=[]

    for target_path in sorted(operations):
        source_text=target_sources.get(target_path)
        ops=tuple(operations[target_path])
        if source_text is None:
            status="MANUAL_REQUIRED"
            targets.append({
                "target_path":target_path,
                "status":status,
                "source_sha256":None,
                "preview_sha256":None,
                "operations":[asdict(op) for op in ops],
                "results":[],
                "issue":"Target source text was not supplied.",
            })
            statuses.append((target_path,status))
            continue

        preview=preview_patch_operations(source_text,ops)
        status=preview.status
        targets.append({
            "target_path":target_path,
            "status":status,
            "source_sha256":_sha256_text(source_text),
            "preview_sha256":_sha256_text(preview.output),
            "operations":[asdict(op) for op in ops],
            "results":[asdict(result) for result in preview.results],
        })
        statuses.append((target_path,status))

    overall="READY" if targets and all(status=="READY" for _path,status in statuses) else "MANUAL_REQUIRED"
    payload={
        "schema":1,
        "kind":"WORKBENCH_PATCH_PLAN",
        "plan_id":plan_id,
        "status":overall,
        "targets":targets,
    }
    output=GeneratedOutput(
        output_id=f"generated:patch-plan:{plan_id}",
        relative_path=f"proposals/patch-plans/{plan_id}.json",
        artifact_type="PATCH_PLAN",
        content=json.dumps(payload,indent=2,sort_keys=True)+"\n",
        generator="workbench.patch_plan",
        metadata={
            "proposal_only":True,
            "plan_status":overall,
            "target_count":len(targets),
        },
    )
    return PatchPlanBuildResult(overall,output,tuple(statuses))
