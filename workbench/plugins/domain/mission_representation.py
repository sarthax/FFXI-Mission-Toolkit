"""Quest/mission representation planning across modular and distributed script layouts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .mission_state_machine import MissionStateMachine, analyze_state_machine


@dataclass(frozen=True)
class MissionRequirement:
    requirement_id: str
    description: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class MissionRepresentation:
    requirement_id: str
    status: str
    target_evidence: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class MissionRepresentationPlan:
    status: str
    requirements: tuple[MissionRequirement, ...]
    representations: tuple[MissionRepresentation, ...]
    missing_requirement_ids: tuple[str, ...]
    represented_requirement_ids: tuple[str, ...]


def plan_mission_representation(
    requirements: Iterable[MissionRequirement],
    representations: Iterable[MissionRepresentation],
) -> MissionRepresentationPlan:
    reqs=tuple(requirements)
    reps=tuple(representations)
    rep_by_id={r.requirement_id:r for r in reps}
    missing=[]
    represented=[]

    for req in reqs:
        rep=rep_by_id.get(req.requirement_id)
        if rep is None or rep.status not in {"VERIFIED","EQUIVALENT","PRESENT"}:
            missing.append(req.requirement_id)
        else:
            represented.append(req.requirement_id)

    return MissionRepresentationPlan(
        status="READY" if not missing else "MANUAL_REQUIRED",
        requirements=reqs,
        representations=reps,
        missing_requirement_ids=tuple(sorted(missing)),
        represented_requirement_ids=tuple(sorted(represented)),
    )


def requirements_from_state_machine(machine: MissionStateMachine) -> tuple[MissionRequirement, ...]:
    """Project a behavioral state machine into representation requirements.

    This keeps migration planning representation-oriented while letting source
    analyzers describe branching behavior and lifecycle semantics explicitly.
    """
    analysis=analyze_state_machine(machine)
    requirements=[]
    for transition in machine.transitions:
        evidence=tuple(transition.evidence_ids)
        description=f"{transition.from_state} -> {transition.to_state} via {transition.trigger}"
        if transition.event:
            description+=f" [{transition.event.key}]"
        if transition.post_effect_gate:
            subjects=", ".join(condition.subject for condition in transition.post_effect_gate.conditions)
            description+=f" [post-effect {transition.post_effect_gate.logic}: {subjects}]"
        requirements.append(MissionRequirement(
            requirement_id=f"transition:{transition.transition_id}",
            description=description,
            evidence=evidence,
        ))
    for subject,effects in analysis.lifecycle_subjects.items():
        requirements.append(MissionRequirement(
            requirement_id=f"lifecycle:{subject}",
            description=f"Lifecycle for {subject}: {', '.join(effects)}",
        ))
    return tuple(requirements)
