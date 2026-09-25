"""Quest/mission representation planning across modular and distributed script layouts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


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
