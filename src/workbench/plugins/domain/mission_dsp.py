"""Proposal-only generated outputs for mission representation gaps."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from workbench.migrations.generated_output import GeneratedOutput
from .mission_representation import MissionRepresentationPlan
from .base import PluginFinding


@dataclass(frozen=True)
class MissionPatchProposal:
    requirement_id: str
    target_path: str
    content: str
    rationale: str


def generated_mission_patch_proposals(
    plan: MissionRepresentationPlan,
    proposals: Iterable[MissionPatchProposal],
) -> tuple[GeneratedOutput, ...]:
    """Materialize only proposals that correspond to verified missing requirements.

    These outputs are review artifacts, not target-ready source replacements.
    """
    missing=set(plan.missing_requirement_ids)
    outputs=[]
    for proposal in proposals:
        if proposal.requirement_id not in missing:
            continue
        safe_id=proposal.requirement_id.replace("/","_").replace(":","_")
        outputs.append(GeneratedOutput(
            output_id=f"generated:mission-proposal:{safe_id}",
            relative_path=f"proposals/mission/{safe_id}.lua.patch",
            artifact_type="LUA_PATCH_PROPOSAL",
            content=proposal.content.rstrip()+"\n",
            generator="framework.quest_mission:representation_gap",
            metadata={
                "proposal_only":True,
                "requirement_id":proposal.requirement_id,
                "target_path":proposal.target_path,
                "rationale":proposal.rationale,
            },
        ))
    return tuple(outputs)


def mission_proposal_finding(
    feature_id: str,
    plan: MissionRepresentationPlan,
    proposal_count: int,
) -> PluginFinding:
    """Replace a monolithic source mission artifact with reviewable target proposals."""
    if not plan.missing_requirement_ids:
        return PluginFinding(
            plugin_id="framework.quest_mission",
            subject_id=feature_id,
            finding_type="MIGRATION_RESHAPE",
            status="COMPATIBLE",
            message="Target mission lifecycle requirements are fully represented.",
            metadata={
                "proposed_action":"NOT_REQUIRED",
                "safe_auto":True,
                "resolved_roles":["mission_script"],
                "representation_status":plan.status,
            },
        )
    return PluginFinding(
        plugin_id="framework.quest_mission",
        subject_id=feature_id,
        finding_type="MIGRATION_PROPOSAL",
        status="MANUAL_REQUIRED",
        message="Source mission behavior has been decomposed into explicit target patch proposals for the remaining lifecycle gaps.",
        metadata={
            "proposed_action":"REVIEW_PROPOSALS",
            "proposal_backed_roles":["mission_script"],
            "proposal_count":proposal_count,
            "missing_requirement_ids":list(plan.missing_requirement_ids),
            "representation_status":plan.status,
        },
    )
