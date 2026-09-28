"""Reusable multi-zone progression / hunt framework.

This module models cross-zone staged progression without embedding any named FFXI mission or
system in the universal core. It is structural: reachability means the dependency graph can be
reached, not that gameplay/runtime completion has been proven.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from hashlib import sha1
import sqlite3
from typing import Any, Mapping

from workbench.core import graph as graph_store
from workbench.core.schema import DependencyEdge, Entity, Feature

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
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        logic=str(self.logic).upper()
        if logic not in VALID_GATE_LOGIC:
            raise ValueError(f"Unsupported progression gate logic: {self.logic}")
        object.__setattr__(self,"logic",logic)
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
    evidence_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        completion_logic=str(self.completion_logic).upper()
        if completion_logic not in VALID_GATE_LOGIC:
            raise ValueError(f"Unsupported stage completion logic: {self.completion_logic}")
        object.__setattr__(self,"completion_logic",completion_logic)
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
    fanout_stage_ids: tuple[str, ...]
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
    downstream=defaultdict(set)
    cross_zone=[]
    branch=[]
    convergence=[]
    for stage in model.stages:
        gate=stage.prerequisite_gate
        if gate:
            referenced.update(gate.member_ids)
            for source_id in gate.member_ids:
                downstream[source_id].add(stage.stage_id)
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
    fanout=tuple(sorted(stage_id for stage_id,targets in downstream.items() if len(targets)>1))
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
        fanout,
        tuple(sorted(convergence)),
        terminals,
        dict(sorted(objective_trigger_counts.items())),
        required,
        optional,
        {key:tuple(value) for key,value in sorted(stage_zones.items())},
        completion_ok,
    )


@dataclass(frozen=True)
class ProgressionGraphProjection:
    feature: Feature
    entities: tuple[Entity, ...]
    edges: tuple[DependencyEdge, ...]


def _graph_token(*parts: object) -> str:
    raw="|".join("" if part is None else str(part) for part in parts)
    return sha1(raw.encode("utf-8")).hexdigest()[:16]


def _stage_node(model: MultiZoneProgression, stage_id: str) -> str:
    return f"progression-stage:{model.feature_id}:{stage_id}"


def _objective_node(model: MultiZoneProgression, objective_id: str) -> str:
    return f"progression-objective:{model.feature_id}:{objective_id}"


def _progression_subject_node(feature_id: str, subject: str) -> tuple[str,bool]:
    prefix=subject.split(":",1)[0].casefold()
    if prefix in {"mission_var","mission_status","local_var","timer","trade","progression_var"} or subject in {"mission","player","interaction","message"}:
        return f"progression-subject:{feature_id}:{subject}",True
    return subject,False


def project_progression_graph(
    model: MultiZoneProgression,
    *,
    feature_name: str | None=None,
    source_snapshot_id: str | None=None,
) -> ProgressionGraphProjection:
    """Project a progression model into generic graph nodes and relationships.

    The returned feature is a fallback record only. The persistence helper will not
    overwrite an existing feature with the same id.
    """
    errors=model.validate()
    if errors:
        raise ValueError("; ".join(errors))

    analysis=analyze_progression(model)
    feature=Feature(
        model.feature_id,
        feature_name or str(model.metadata.get("name") or model.feature_id),
        "MULTIZONE_PROGRESSION",
        "multizone_progression",
        source_snapshot_id,
        status="DISCOVERED",
        metadata={
            "progression_id":model.progression_id,
            "structural_status":analysis.status,
            "zone_ids":list(analysis.zone_ids),
            "stage_count":len(model.stages),
            "objective_count":len(model.objectives),
        },
    )

    entities={}
    edges=[]
    objectives={obj.objective_id:obj for obj in model.objectives}

    for stage in model.stages:
        stage_node=_stage_node(model,stage.stage_id)
        entities[stage_node]=Entity(
            stage_node,"PROGRESSION_STAGE",stage.label,{
                "progression_id":model.progression_id,
                "feature_id":model.feature_id,
                "stage_id":stage.stage_id,
                "completion_logic":stage.completion_logic,
                "optional":stage.optional,
                "zones":list(analysis.stage_zone_coverage.get(stage.stage_id,())),
                "metadata":dict(stage.metadata),
            },
        )
        edges.append(DependencyEdge(
            f"progression-has-stage:{_graph_token(model.feature_id,stage.stage_id)}",
            model.feature_id,stage_node,"HAS_STAGE",
            confidence="INFERRED",status="DISCOVERED",
            discovered_by="multizone_progression",
            source_snapshot_id=source_snapshot_id,
        ))

        if stage.prerequisite_gate:
            for prerequisite in stage.prerequisite_gate.member_ids:
                edges.append(DependencyEdge(
                    f"progression-stage-requires:{_graph_token(model.feature_id,stage.stage_id,prerequisite,stage.prerequisite_gate.gate_id)}",
                    stage_node,_stage_node(model,prerequisite),"REQUIRES",
                    evidence_id=(stage.prerequisite_gate.evidence_ids[0] if stage.prerequisite_gate.evidence_ids else (stage.evidence_ids[0] if stage.evidence_ids else None)),
                    confidence="INFERRED",status="DISCOVERED",
                    discovered_by="multizone_progression",
                    notes=(
                        f"gate={stage.prerequisite_gate.gate_id}; "
                        f"logic={stage.prerequisite_gate.logic}"
                    ),
                    source_snapshot_id=source_snapshot_id,
                ))

        for objective_id in stage.objective_ids:
            objective=objectives[objective_id]
            objective_node=_objective_node(model,objective_id)
            entities[objective_node]=Entity(
                objective_node,"PROGRESSION_OBJECTIVE",objective.label,{
                    "progression_id":model.progression_id,
                    "feature_id":model.feature_id,
                    "objective_id":objective.objective_id,
                    "trigger":objective.trigger,
                    "subject":objective.subject,
                    "required_count":objective.required_count,
                    "optional":objective.optional,
                    "zones":list(objective.zones),
                    "conditions":[
                        {"subject":condition.subject,"operator":condition.operator,"value":condition.value}
                        for condition in objective.conditions
                    ],
                    "effects":[
                        {"effect":effect.effect,"subject":effect.subject,"value":effect.value}
                        for effect in objective.effects
                    ],
                    "evidence_ids":list(objective.evidence_ids),
                    "metadata":dict(objective.metadata),
                },
            )
            edges.append(DependencyEdge(
                f"progression-has-objective:{_graph_token(model.feature_id,stage.stage_id,objective_id)}",
                stage_node,objective_node,"HAS_OBJECTIVE",
                evidence_id=(objective.evidence_ids[0] if objective.evidence_ids else (stage.evidence_ids[0] if stage.evidence_ids else None)),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="multizone_progression",
                source_snapshot_id=source_snapshot_id,
            ))

            if objective.subject:
                subject,scoped=_progression_subject_node(model.feature_id,objective.subject)
                entities.setdefault(subject,Entity(
                    subject,"PROGRESSION_SUBJECT",objective.subject,{
                        "scope":"feature" if scoped else "shared",
                        **({"feature_id":model.feature_id} if scoped else {}),
                        "raw_subject":objective.subject,
                    },
                ))
                edges.append(DependencyEdge(
                    f"progression-objective-subject:{_graph_token(model.feature_id,objective_id,subject)}",
                    objective_node,subject,"REFERENCES",
                    evidence_id=(objective.evidence_ids[0] if objective.evidence_ids else None),
                    confidence="INFERRED",status="DISCOVERED",
                    discovered_by="multizone_progression",
                    notes=f"required_count={objective.required_count}",
                    source_snapshot_id=source_snapshot_id,
                ))

            if objective.event:
                event=objective.event
                event_node=(
                    f"progression-event:{model.feature_id}:{event.zone}:"
                    f"{event.actor or '*'}:{event.event_id}"
                )
                entities.setdefault(event_node,Entity(
                    event_node,"PROGRESSION_EVENT",event.key,{
                        "feature_id":model.feature_id,
                        "zone":event.zone,
                        "actor":event.actor,
                        "event_id":event.event_id,
                    },
                ))
                edges.append(DependencyEdge(
                    f"progression-objective-event:{_graph_token(model.feature_id,objective_id,event.key)}",
                    objective_node,event_node,"USES_EVENT",
                    evidence_id=(objective.evidence_ids[0] if objective.evidence_ids else None),
                    confidence="INFERRED",status="DISCOVERED",
                    discovered_by="multizone_progression",
                    source_snapshot_id=source_snapshot_id,
                ))

            for zone in objective.zones:
                zone_node=f"zone:{zone}"
                entities.setdefault(zone_node,Entity(
                    zone_node,"ZONE",zone,{"zone_key":zone},
                ))
                edges.append(DependencyEdge(
                    f"progression-objective-zone:{_graph_token(model.feature_id,objective_id,zone)}",
                    objective_node,zone_node,"LOCATED_IN",
                    confidence="INFERRED",status="DISCOVERED",
                    discovered_by="multizone_progression",
                    source_snapshot_id=source_snapshot_id,
                ))

            for index,condition in enumerate(objective.conditions):
                raw_subject=condition.subject
                subject,scoped=_progression_subject_node(model.feature_id,raw_subject)
                entities.setdefault(subject,Entity(
                    subject,"PROGRESSION_SUBJECT",raw_subject,{
                        "scope":"feature" if scoped else "shared",
                        **({"feature_id":model.feature_id} if scoped else {}),
                        "raw_subject":raw_subject,
                    },
                ))
                edges.append(DependencyEdge(
                    f"progression-objective-requires:{_graph_token(model.feature_id,objective_id,index,subject,condition.operator,condition.value)}",
                    objective_node,subject,"REQUIRES",
                    evidence_id=(condition.evidence_ids[0] if condition.evidence_ids else (objective.evidence_ids[0] if objective.evidence_ids else None)),
                    confidence="INFERRED",status="DISCOVERED",
                    discovered_by="multizone_progression",
                    notes=f"{condition.operator} {condition.value!r}",
                    source_snapshot_id=source_snapshot_id,
                ))

            for index,effect in enumerate(objective.effects):
                raw_subject=effect.subject
                subject,scoped=_progression_subject_node(model.feature_id,raw_subject)
                entities.setdefault(subject,Entity(
                    subject,"PROGRESSION_SUBJECT",raw_subject,{
                        "scope":"feature" if scoped else "shared",
                        **({"feature_id":model.feature_id} if scoped else {}),
                        "raw_subject":raw_subject,
                    },
                ))
                edges.append(DependencyEdge(
                    f"progression-objective-affects:{_graph_token(model.feature_id,objective_id,index,subject,effect.effect,effect.value)}",
                    objective_node,subject,"AFFECTS",
                    evidence_id=(effect.evidence_ids[0] if effect.evidence_ids else (objective.evidence_ids[0] if objective.evidence_ids else None)),
                    confidence="INFERRED",status="DISCOVERED",
                    discovered_by="multizone_progression",
                    notes=f"{effect.effect} {effect.value!r}",
                    source_snapshot_id=source_snapshot_id,
                ))

    if model.completion_gate:
        for stage_id in model.completion_gate.member_ids:
            edges.append(DependencyEdge(
                f"progression-completion-requires:{_graph_token(model.feature_id,stage_id,model.completion_gate.gate_id)}",
                model.feature_id,_stage_node(model,stage_id),"REQUIRES",
                evidence_id=(model.completion_gate.evidence_ids[0] if model.completion_gate.evidence_ids else None),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="multizone_progression",
                notes=f"completion gate={model.completion_gate.gate_id}; logic={model.completion_gate.logic}",
                source_snapshot_id=source_snapshot_id,
            ))

    return ProgressionGraphProjection(feature,tuple(entities.values()),tuple(edges))


def persist_progression_graph(
    con: sqlite3.Connection,
    projection: ProgressionGraphProjection,
    *,
    commit: bool=True,
) -> None:
    existing=con.execute(
        "SELECT 1 FROM features WHERE feature_id=?",
        (projection.feature.feature_id,),
    ).fetchone()
    if existing is None:
        graph_store.insert_record(con,projection.feature)
    for entity in projection.entities:
        exists=con.execute(
            "SELECT 1 FROM entities WHERE entity_id=?",
            (entity.entity_id,),
        ).fetchone()
        if exists is None:
            graph_store.insert_record(con,entity)
    for edge in projection.edges:
        graph_store.insert_record(con,edge)
    if commit:
        con.commit()
