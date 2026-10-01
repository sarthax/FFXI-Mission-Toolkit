"""Explicit human-approval state for reviewed patch plans."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from workbench.migrations.generated_output import GeneratedOutput
from workbench.migrations.patch_approval import PatchApprovalResult


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PatchExecutionEligibility:
    status: str
    reason: str


def build_patch_approval_request(
    patch_plan_content: str,
    readiness: PatchApprovalResult,
    *,
    request_id: str,
) -> GeneratedOutput:
    payload={
        "schema":1,
        "kind":"WORKBENCH_PATCH_APPROVAL_REQUEST",
        "request_id":request_id,
        "status":"PENDING",
        "requires_human_approval":True,
        "patch_plan_sha256":_sha256_text(patch_plan_content),
        "technical_readiness":readiness.status,
    }
    return GeneratedOutput(
        output_id=f"generated:patch-approval-request:{request_id}",
        relative_path=f"proposals/approvals/{request_id}.json",
        artifact_type="PATCH_APPROVAL_REQUEST",
        content=json.dumps(payload,indent=2,sort_keys=True)+"\n",
        generator="workbench.patch_approval_request",
        metadata={
            "proposal_only":True,
            "requires_human_approval":True,
            "approval_status":"PENDING",
        },
    )


def assess_patch_execution_eligibility(
    patch_plan_content: str,
    readiness: PatchApprovalResult,
    approval_record: str | Mapping[str,Any] | None,
) -> PatchExecutionEligibility:
    if readiness.status!="READY_FOR_APPROVAL":
        return PatchExecutionEligibility("BLOCKED","Technical patch readiness is not READY_FOR_APPROVAL.")
    if approval_record is None:
        return PatchExecutionEligibility("AWAITING_APPROVAL","No human approval record was supplied.")

    payload=json.loads(approval_record) if isinstance(approval_record,str) else dict(approval_record)
    if payload.get("kind")!="WORKBENCH_PATCH_APPROVAL_REQUEST" or payload.get("schema")!=1:
        return PatchExecutionEligibility("BLOCKED","Unsupported approval record format.")
    if payload.get("patch_plan_sha256")!=_sha256_text(patch_plan_content):
        return PatchExecutionEligibility("BLOCKED","Approval record does not match the reviewed patch plan.")
    if payload.get("status")!="APPROVED":
        return PatchExecutionEligibility("AWAITING_APPROVAL","Patch approval is not APPROVED.")
    return PatchExecutionEligibility(
        "ELIGIBLE_FOR_DETERMINISTIC_APPLY",
        "Technical readiness and matching human approval are both present.",
    )
