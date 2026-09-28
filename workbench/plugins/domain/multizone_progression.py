"""Reusable multi-zone progression / hunt framework.

This module models cross-zone staged progression without embedding any named FFXI mission or
system in the universal core. It is structural: reachability means the dependency graph can be
reached, not that gameplay/runtime completion has been proven.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Mapping

from .mission_state_machine import (
    EventIdentity,
    StateCondition,
    TransitionEffect,
    VALID_GATE_LOGIC,
    VALID_TRIGGER_KINDS,
)


@dataclass(frozen=True)
class ProgressionGate:
    gate_id: str
    logic: str
    member_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        logic=str(self.logic).upper()
        if logic not in VALID_GATE_LOGIC:
            raise ValueError(f"Unsupported progression gate logic: {self.logic}")
        if not self.member_ids:
            raise ValueError("ProgressionGate requires at least one member")


@dataclass(frozen=True)
class ProgressionObjective:
    objective_id: str
    label: str
    trigger: str
    zones: tuple[str, ...] = ()
    subject: str | None = None
    required_count: int = 1
    conditions: tuple[StateCondition, ...] = ()
    effects: tuple[TransitionEffect, ...] = ()
    event: EventIdentity | None = None
    evidence_ids: tuple[str, ...] = ()
    optional: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.trigger not in VALID_TRIGGER_KINDS:
            raise ValueError(f"Unsupported objective trigger: {self.trigger}")
        if self.required_count < 1:
            raise ValueError("ProgressionObjective.required_count must be >= 1")


@dataclass(frozen=True)
class ProgressionStage:
    stage_id: str
    label: str
    objective_ids: tuple[str, ...]
    prerequisite_gate: ProgressionGate | None = None
    completion_logic: str = "ALL"
    optional: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.completion_logic not in VALID_GATE_LOGIC:
            raise ValueError(f"Unsupported stage completion logic: {self.completion_logic}")
        if not self.objective_ids:
            raise ValueError("ProgressionStage requires at least one objective")


@dataclass(frozen=True)
class MultiZoneProgression:
    progression_id: str
    feature_id: str
    objectives: tuple[ProgressionObjective, ...]
    stages: tuple[ProgressionStage, ...]
    entry_stage_ids: tuple[str, ...] = ()
    completion_gate: ProgressionGate | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> tuple[str, ...]:
        errors=[]
        objective_ids=[obj.objective_id for obj in self.objectives]
        stage_ids=[stage.stage_id for stage in self.stages]
        objective_set=set(objective_ids)
        stage_set=set(stage_ids)

        if len(objective_ids)!=len(objective_set):
            errors.append("duplicate objective_id")
        if len(stage_ids)!=len(stage_set):
            errors.append("duplicate stage_id")

        memberships=Counter()
        for stage in self.stages:
            for objective_id in stage.objective_ids:
                memberships[objective_id]+=1
                if objective_id not in objective_set:
                    errors.append(f"{stage.stage_id}: unknown objective {objective_id}")
            if stage.prerequisite_gate:
                for member in stage.prerequisite_gate.member_ids:
                    if member not in stage_set:
                        errors.append(f"{stage.stage_id}: unknown prerequisite stage {member}")
                    if member==stage.stage_id:
                        errors.append(f"{stage.stage_id}: self prerequisite")
        for objective_id,count in memberships.items():
            if count>1:
                errors.append(f"objective {objective_id} belongs to multiple stages")
        for objective_id in objective_set:
            if memberships[objective_id]==0:
                errors.append(f"objective {objective_id} is not assigned to a stage")

        for entry in self.entry_stage_ids:
            if entry not in stage_set:
                errors.append(f"unknown entry stage {entry}")
        if self.completion_gate:
            for member in self.completion_gate.member_ids:
                if member not in stage_set:
                    errors.append(f"completion gate references unknown stage {member}")
        return tuple(errors)


@dataclass(frozen=True)
class CrossZoneDependency:
    source_stage_id: str
    target_stage_id: str
    source_zones: tuple[str, ...]
    target_zones: tuple[str, ...]


@dataclass(frozen=True)
class ProgressionAnalysis:
    status: str
    validation_errors: tuple[str, ...]
    reachable_stage_ids: tuple[str, ...]
    unreachable_stage_ids: tuple[str, ...]
    cycle_stage_ids: tuple[str, ...]
    zone_ids: tuple[str, ...]
    cross_zone_dependencies: tuple[CrossZoneDependency, ...]
    branch_stage_ids: tuple[str, ...]
    convergence_stage_ids: tuple[str, ...]
    terminal_stage_ids: tuple[str, ...]
    objective_trigger_counts: Mapping[str, int]
    required_objective_count: int
    optional_objective_count: int
    stage_zone_coverage: Mapping[str, tuple[str, ...]]
    completion_gate_satisfied_structurally: bool


def _stage_zones(model: MultiZoneProgression) -> dict[str, tuple[str, ...]]:
    objectives={obj.objective_id:obj for obj in model.objectives}
    out={}
    for stage in model.stages:
        zones=[]
        for objective_id in stage.objective_ids:
            objective=objectives.get(objective_id)
            if objective is None:
                continue
            for zone in objective.zones:
                if zone not in zones:
                    zones.append(zone)
        out[stage.stage_id]=tuple(zones)
    return out


def _gate_satisfied(gate: ProgressionGate | None, reached: set[str]) -> bool:
    if gate is None:
        return True
    members=set(gate.member_ids)
    if gate.logic=="ALL":
        return members.issubset(reached)
    return bool(members & reached)


def _cycle_nodes(model: MultiZoneProgression) -> tuple[str, ...]:
    graph: dict[str,tuple[str,...]]={}
    for stage in model.stages:
        graph[stage.stage_id]=tuple(stage.prerequisite_gate.member_ids) if stage.prerequisite_gate else ()

    visiting=set()
    visited=set()
    cyclic=set()

    def visit(node: str, stack: list[str]) -> None:
        if node in visited:
            return
        if node in visiting:
            if node in stack:
                cyclic.update(stack[stack.index(node):])
            else:
                cyclic.add(node)
            return
        visiting.add(node)
        stack.append(node)
        for dep in graph.get(node,()):
            if dep in graph:
                visit(dep,stack)
        stack.pop()
        visiting.discard(node)
        visited.add(node)

    for node in graph:
        visit(node,[])
    return tuple(sorted(cyclic))


def analyze_progression(model: MultiZoneProgression) -> ProgressionAnalysis:
    errors=model.validate()
    stages={stage.stage_id:stage for stage in model.stages}
    stage_zones=_stage_zones(model)
    all_stage_ids=set(stages)
    cycle_nodes=set(_cycle_nodes(model))

    if model.entry_stage_ids:
        reached={stage_id for stage_id in model.entry_stage_ids if stage_id in stages}
    else:
        reached={stage.stage_id for stage in model.stages if stage.prerequisite_gate is None}

    changed=True
    while changed:
        changed=False
        for stage in model.stages:
            if stage.stage_id in reached or stage.stage_id in cycle_nodes:
                continue
            if _gate_satisfied(stage.prerequisite_gate,reached):
                reached.add(stage.stage_id)
                changed=True

    referenced=set()
    cross_zone=[]
    branch=[]
    convergence=[]
    for stage in model.stages:
        gate=stage.prerequisite_gate
        if gate:
            referenced.update(gate.member_ids)
            if gate.logic=="ANY" and len(gate.member_ids)>1:
                branch.append(stage.stage_id)
            if gate.logic=="ALL" and len(gate.member_ids)>1:
                convergence.append(stage.stage_id)
            for source_id in gate.member_ids:
                if source_id not in stages:
                    continue
                source_zones=stage_zones.get(source_id,())
                target_zones=stage_zones.get(stage.stage_id,())
                if source_zones and target_zones and set(source_zones)!=set(target_zones):
                    cross_zone.append(CrossZoneDependency(
                        source_id,stage.stage_id,source_zones,target_zones
                    ))

    terminals=tuple(sorted(all_stage_ids-referenced))
    objective_trigger_counts=Counter(obj.trigger for obj in model.objectives)
    required=sum(not obj.optional for obj in model.objectives)
    optional=len(model.objectives)-required
    all_zones=tuple(sorted({zone for zones in stage_zones.values() for zone in zones}))

    completion_ok=_gate_satisfied(model.completion_gate,reached)
    if model.completion_gate is None:
        required_stages={stage.stage_id for stage in model.stages if not stage.optional}
        completion_ok=required_stages.issubset(reached)

    unreachable=all_stage_ids-reached
    if errors:
        status="INVALID"
    elif cycle_nodes:
        status="CYCLIC"
    elif not completion_ok:
        status="PARTIAL"
    elif any(not stages[stage_id].optional for stage_id in unreachable):
        status="PARTIAL"
    else:
        status="STRUCTURALLY_READY"

    return ProgressionAnalysis(
        status,
        errors,
        tuple(sorted(reached)),
        tuple(sorted(unreachable)),
        tuple(sorted(cycle_nodes)),
        all_zones,
        tuple(sorted(cross_zone,key=lambda row:(row.source_stage_id,row.target_stage_id))),
        tuple(sorted(branch)),
        tuple(sorted(convergence)),
        terminals,
        dict(sorted(objective_trigger_counts.items())),
        required,
        optional,
        {key:tuple(value) for key,value in sorted(stage_zones.items())},
        completion_ok,
    )
