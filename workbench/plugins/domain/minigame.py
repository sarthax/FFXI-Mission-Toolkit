"""Reusable minigame / puzzle framework.

Models temporary-state interactions, timers, scoring, outcomes and reset lifecycle outside
workbench.core. Structural readiness is not runtime/gameplay correctness.
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
    StateCondition,
    TransitionEffect,
    VALID_TRIGGER_KINDS,
)

VALID_RESULTS={"WIN","LOSS","DRAW","ABORT","TIMEOUT"}


@dataclass(frozen=True)
class MinigameTimer:
    timer_id: str
    duration_seconds: float | None = None
    repeatable: bool = False
    expiry_outcome_ids: tuple[str,...] = ()
    evidence_ids: tuple[str,...] = ()
    metadata: Mapping[str,Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.duration_seconds is not None and self.duration_seconds <= 0:
            raise ValueError("MinigameTimer.duration_seconds must be positive")
        if len(self.expiry_outcome_ids)!=len(set(self.expiry_outcome_ids)):
            raise ValueError("MinigameTimer expiry_outcome_ids must be unique")


@dataclass(frozen=True)
class MinigameInteraction:
    interaction_id: str
    label: str
    trigger: str
    subject: str | None = None
    conditions: tuple[StateCondition,...] = ()
    effects: tuple[TransitionEffect,...] = ()
    starts_timers: tuple[str,...] = ()
    cancels_timers: tuple[str,...] = ()
    score_delta: int | float = 0
    evidence_ids: tuple[str,...] = ()
    optional: bool = False
    metadata: Mapping[str,Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        trigger=str(self.trigger).upper()
        if trigger not in VALID_TRIGGER_KINDS:
            raise ValueError(f"Unsupported minigame interaction trigger: {self.trigger}")
        object.__setattr__(self,"trigger",trigger)
        if len(self.starts_timers)!=len(set(self.starts_timers)):
            raise ValueError("MinigameInteraction starts_timers must be unique")
        if len(self.cancels_timers)!=len(set(self.cancels_timers)):
            raise ValueError("MinigameInteraction cancels_timers must be unique")


@dataclass(frozen=True)
class MinigameOutcome:
    outcome_id: str
    label: str
    result: str
    conditions: tuple[StateCondition,...] = ()
    effects: tuple[TransitionEffect,...] = ()
    evidence_ids: tuple[str,...] = ()
    metadata: Mapping[str,Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        result=str(self.result).upper()
        if result not in VALID_RESULTS:
            raise ValueError(f"Unsupported minigame outcome result: {self.result}")
        object.__setattr__(self,"result",result)


@dataclass(frozen=True)
class MinigameReset:
    reset_id: str
    label: str
    trigger: str
    clears_subjects: tuple[str,...] = ()
    cancels_timers: tuple[str,...] = ()
    reset_score: bool = True
    evidence_ids: tuple[str,...] = ()
    metadata: Mapping[str,Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        trigger=str(self.trigger).upper()
        if trigger not in VALID_TRIGGER_KINDS:
            raise ValueError(f"Unsupported minigame reset trigger: {self.trigger}")
        object.__setattr__(self,"trigger",trigger)
        if len(self.clears_subjects)!=len(set(self.clears_subjects)):
            raise ValueError("MinigameReset clears_subjects must be unique")
        if len(self.cancels_timers)!=len(set(self.cancels_timers)):
            raise ValueError("MinigameReset cancels_timers must be unique")


@dataclass(frozen=True)
class MinigameModel:
    minigame_id: str
    feature_id: str
    interactions: tuple[MinigameInteraction,...]
    outcomes: tuple[MinigameOutcome,...]
    timers: tuple[MinigameTimer,...] = ()
    resets: tuple[MinigameReset,...] = ()
    state_subjects: tuple[str,...] = ()
    repeatable: bool = True
    metadata: Mapping[str,Any] = field(default_factory=dict)

    def validate(self) -> tuple[str,...]:
        errors=[]
        interaction_ids=[row.interaction_id for row in self.interactions]
        outcome_ids=[row.outcome_id for row in self.outcomes]
        timer_ids=[row.timer_id for row in self.timers]
        reset_ids=[row.reset_id for row in self.resets]
        if not interaction_ids:
            errors.append("minigame requires at least one interaction")
        if not outcome_ids:
            errors.append("minigame requires at least one outcome")
        for label,values in (
            ("interaction_id",interaction_ids),
            ("outcome_id",outcome_ids),
            ("timer_id",timer_ids),
            ("reset_id",reset_ids),
            ("state_subject",list(self.state_subjects)),
        ):
            if len(values)!=len(set(values)):
                errors.append(f"duplicate {label}")

        timer_set=set(timer_ids)
        outcome_set=set(outcome_ids)
        for row in self.interactions:
            for timer_id in (*row.starts_timers,*row.cancels_timers):
                if timer_id not in timer_set:
                    errors.append(f"{row.interaction_id}: unknown timer {timer_id}")
        for reset in self.resets:
            for timer_id in reset.cancels_timers:
                if timer_id not in timer_set:
                    errors.append(f"{reset.reset_id}: unknown timer {timer_id}")
        for timer in self.timers:
            for outcome_id in timer.expiry_outcome_ids:
                if outcome_id not in outcome_set:
                    errors.append(f"{timer.timer_id}: unknown expiry outcome {outcome_id}")
        return tuple(errors)


@dataclass(frozen=True)
class TimerLifecycle:
    timer_id: str
    started: bool
    cancellable: bool
    expiry_outcomes: tuple[str,...]
    structurally_closed: bool


@dataclass(frozen=True)
class MinigameAnalysis:
    status: str
    validation_errors: tuple[str,...]
    interaction_trigger_counts: Mapping[str,int]
    result_counts: Mapping[str,int]
    timer_lifecycles: tuple[TimerLifecycle,...]
    mutable_state_subjects: tuple[str,...]
    reset_state_coverage: tuple[str,...]
    missing_reset_subjects: tuple[str,...]
    timer_reset_coverage: tuple[str,...]
    missing_reset_timers: tuple[str,...]
    score_rule_count: int
    score_reset_present: bool
    has_win: bool
    has_loss: bool
    structural_gaps: tuple[str,...]


def _mutable_subjects(model: MinigameModel) -> set[str]:
    subjects=set(model.state_subjects)
    for interaction in model.interactions:
        for effect in interaction.effects:
            if effect.effect in {"SET_VAR","SET_CHANNEL","SET_STATE"}:
                subjects.add(effect.subject)
    for outcome in model.outcomes:
        for effect in outcome.effects:
            if effect.effect in {"SET_VAR","SET_CHANNEL","SET_STATE"}:
                subjects.add(effect.subject)
    return subjects


def analyze_minigame(model: MinigameModel) -> MinigameAnalysis:
    errors=model.validate()
    starts=Counter(timer_id for row in model.interactions for timer_id in row.starts_timers)
    cancels=Counter(timer_id for row in model.interactions for timer_id in row.cancels_timers)
    any_reset_cancels={timer_id for row in model.resets for timer_id in row.cancels_timers}
    reset_cancels=(
        set.intersection(*(set(row.cancels_timers) for row in model.resets))
        if model.resets else set()
    )
    reset_subjects=(
        set.intersection(*(set(row.clears_subjects) for row in model.resets))
        if model.resets else set()
    )
    mutable=_mutable_subjects(model)

    timer_rows=[]
    gaps=[]
    for timer in model.timers:
        started=starts[timer.timer_id]>0
        cancellable=cancels[timer.timer_id]>0 or timer.timer_id in any_reset_cancels
        expiry=tuple(timer.expiry_outcome_ids)
        closed=started and (cancellable or bool(expiry))
        timer_rows.append(TimerLifecycle(timer.timer_id,started,cancellable,expiry,closed))
        if not started:
            gaps.append(f"timer_not_started:{timer.timer_id}")
        elif not closed:
            gaps.append(f"timer_lifecycle_open:{timer.timer_id}")

    score_rule_count=sum(1 for row in model.interactions if row.score_delta!=0)
    score_reset_present=bool(model.resets) and all(row.reset_score for row in model.resets)
    missing_subjects=tuple(sorted(mutable-reset_subjects)) if model.repeatable else ()
    missing_timers=tuple(sorted(set(starts)-reset_cancels)) if model.repeatable else ()

    if model.repeatable:
        if not model.resets:
            gaps.append("repeatable_without_reset")
        if missing_subjects:
            gaps.append("reset_state_incomplete")
        if missing_timers:
            gaps.append("reset_timer_incomplete")
        if score_rule_count and not score_reset_present:
            gaps.append("score_reset_missing")

    results=Counter(row.result for row in model.outcomes)
    has_win=results["WIN"]>0
    has_loss=(results["LOSS"]+results["TIMEOUT"]+results["ABORT"])>0
    if not has_win:
        gaps.append("win_outcome_missing")
    if not has_loss:
        gaps.append("loss_or_timeout_outcome_missing")

    if errors:
        status="INVALID"
    elif gaps:
        status="PARTIAL"
    else:
        status="STRUCTURALLY_READY"

    return MinigameAnalysis(
        status,
        errors,
        dict(sorted(Counter(row.trigger for row in model.interactions).items())),
        dict(sorted(results.items())),
        tuple(timer_rows),
        tuple(sorted(mutable)),
        tuple(sorted(reset_subjects)),
        missing_subjects,
        tuple(sorted(reset_cancels)),
        missing_timers,
        score_rule_count,
        score_reset_present,
        has_win,
        has_loss,
        tuple(gaps),
    )


@dataclass(frozen=True)
class MinigameGraphProjection:
    feature: Feature
    entities: tuple[Entity,...]
    edges: tuple[DependencyEdge,...]


def _token(*parts: object) -> str:
    raw="|".join("" if part is None else str(part) for part in parts)
    return sha1(raw.encode("utf-8")).hexdigest()[:16]


def _state_subject(feature_id: str, subject: str) -> tuple[str,bool]:
    prefix=subject.split(":",1)[0].casefold()
    if prefix in {"minigame_var","local_var","timer","score","state","trade"} or subject in {"player","interaction","message"}:
        return f"minigame-subject:{feature_id}:{subject}",True
    return subject,False


def project_minigame_graph(
    model: MinigameModel,
    *,
    feature_name: str | None=None,
    source_snapshot_id: str | None=None,
) -> MinigameGraphProjection:
    errors=model.validate()
    if errors:
        raise ValueError("; ".join(errors))
    analysis=analyze_minigame(model)
    feature=Feature(
        model.feature_id,
        feature_name or str(model.metadata.get("name") or model.feature_id),
        "MINIGAME",
        "minigame",
        source_snapshot_id,
        status="DISCOVERED",
        metadata={
            "minigame_id":model.minigame_id,
            "structural_status":analysis.status,
            "interaction_count":len(model.interactions),
            "timer_count":len(model.timers),
            "outcome_count":len(model.outcomes),
            "repeatable":model.repeatable,
        },
    )
    entities={}
    edges=[]
    timer_nodes={}
    outcome_nodes={}

    for timer in model.timers:
        node=f"minigame-timer:{model.feature_id}:{timer.timer_id}"
        timer_nodes[timer.timer_id]=node
        entities[node]=Entity(node,"MINIGAME_TIMER",timer.timer_id,{
            "feature_id":model.feature_id,
            "timer_id":timer.timer_id,
            "duration_seconds":timer.duration_seconds,
            "repeatable":timer.repeatable,
            "expiry_outcome_ids":list(timer.expiry_outcome_ids),
            "metadata":dict(timer.metadata),
        })
        edges.append(DependencyEdge(
            f"minigame-has-timer:{_token(model.feature_id,timer.timer_id)}",
            model.feature_id,node,"HAS_TIMER",
            evidence_id=(timer.evidence_ids[0] if timer.evidence_ids else None),
            confidence="INFERRED",status="DISCOVERED",
            discovered_by="minigame_framework",source_snapshot_id=source_snapshot_id,
        ))

    for outcome in model.outcomes:
        node=f"minigame-outcome:{model.feature_id}:{outcome.outcome_id}"
        outcome_nodes[outcome.outcome_id]=node
        entities[node]=Entity(node,"MINIGAME_OUTCOME",outcome.label,{
            "feature_id":model.feature_id,
            "outcome_id":outcome.outcome_id,
            "result":outcome.result,
            "metadata":dict(outcome.metadata),
        })
        edges.append(DependencyEdge(
            f"minigame-has-outcome:{_token(model.feature_id,outcome.outcome_id)}",
            model.feature_id,node,"HAS_OUTCOME",
            evidence_id=(outcome.evidence_ids[0] if outcome.evidence_ids else None),
            confidence="INFERRED",status="DISCOVERED",
            discovered_by="minigame_framework",source_snapshot_id=source_snapshot_id,
        ))
        for index,condition in enumerate(outcome.conditions):
            subject,scoped=_state_subject(model.feature_id,condition.subject)
            entities.setdefault(subject,Entity(subject,"MINIGAME_SUBJECT",condition.subject,{
                "scope":"feature" if scoped else "shared",
                **({"feature_id":model.feature_id} if scoped else {}),
                "raw_subject":condition.subject,
            }))
            edges.append(DependencyEdge(
                f"minigame-outcome-requires:{_token(model.feature_id,outcome.outcome_id,index,subject,condition.operator,condition.value)}",
                node,subject,"REQUIRES",
                evidence_id=(condition.evidence_ids[0] if condition.evidence_ids else (outcome.evidence_ids[0] if outcome.evidence_ids else None)),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="minigame_framework",
                notes=f"{condition.operator} {condition.value!r}",
                source_snapshot_id=source_snapshot_id,
            ))
        for index,effect in enumerate(outcome.effects):
            subject,scoped=_state_subject(model.feature_id,effect.subject)
            entities.setdefault(subject,Entity(subject,"MINIGAME_SUBJECT",effect.subject,{
                "scope":"feature" if scoped else "shared",
                **({"feature_id":model.feature_id} if scoped else {}),
                "raw_subject":effect.subject,
            }))
            edges.append(DependencyEdge(
                f"minigame-outcome-affects:{_token(model.feature_id,outcome.outcome_id,index,subject,effect.effect,effect.value)}",
                node,subject,"AFFECTS",
                evidence_id=(effect.evidence_ids[0] if effect.evidence_ids else (outcome.evidence_ids[0] if outcome.evidence_ids else None)),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="minigame_framework",
                notes=f"{effect.effect} {effect.value!r}",
                source_snapshot_id=source_snapshot_id,
            ))

    for timer in model.timers:
        timer_node=timer_nodes[timer.timer_id]
        for outcome_id in timer.expiry_outcome_ids:
            edges.append(DependencyEdge(
                f"minigame-timer-outcome:{_token(model.feature_id,timer.timer_id,outcome_id)}",
                timer_node,outcome_nodes[outcome_id],"EXPIRES_TO",
                evidence_id=(timer.evidence_ids[0] if timer.evidence_ids else None),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="minigame_framework",source_snapshot_id=source_snapshot_id,
            ))

    for interaction in model.interactions:
        node=f"minigame-interaction:{model.feature_id}:{interaction.interaction_id}"
        entities[node]=Entity(node,"MINIGAME_INTERACTION",interaction.label,{
            "feature_id":model.feature_id,
            "interaction_id":interaction.interaction_id,
            "trigger":interaction.trigger,
            "subject":interaction.subject,
            "score_delta":interaction.score_delta,
            "optional":interaction.optional,
            "metadata":dict(interaction.metadata),
        })
        edges.append(DependencyEdge(
            f"minigame-has-interaction:{_token(model.feature_id,interaction.interaction_id)}",
            model.feature_id,node,"HAS_INTERACTION",
            evidence_id=(interaction.evidence_ids[0] if interaction.evidence_ids else None),
            confidence="INFERRED",status="DISCOVERED",
            discovered_by="minigame_framework",source_snapshot_id=source_snapshot_id,
        ))
        if interaction.subject:
            subject,scoped=_state_subject(model.feature_id,interaction.subject)
            entities.setdefault(subject,Entity(subject,"MINIGAME_SUBJECT",interaction.subject,{
                "scope":"feature" if scoped else "shared",
                **({"feature_id":model.feature_id} if scoped else {}),
                "raw_subject":interaction.subject,
            }))
            edges.append(DependencyEdge(
                f"minigame-interaction-subject:{_token(model.feature_id,interaction.interaction_id,subject)}",
                node,subject,"REFERENCES",
                evidence_id=(interaction.evidence_ids[0] if interaction.evidence_ids else None),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="minigame_framework",source_snapshot_id=source_snapshot_id,
            ))
        for timer_id in interaction.starts_timers:
            edges.append(DependencyEdge(
                f"minigame-starts-timer:{_token(model.feature_id,interaction.interaction_id,timer_id)}",
                node,timer_nodes[timer_id],"STARTS_TIMER",
                evidence_id=(interaction.evidence_ids[0] if interaction.evidence_ids else None),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="minigame_framework",source_snapshot_id=source_snapshot_id,
            ))
        for timer_id in interaction.cancels_timers:
            edges.append(DependencyEdge(
                f"minigame-cancels-timer:{_token(model.feature_id,interaction.interaction_id,timer_id)}",
                node,timer_nodes[timer_id],"CANCELS_TIMER",
                evidence_id=(interaction.evidence_ids[0] if interaction.evidence_ids else None),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="minigame_framework",source_snapshot_id=source_snapshot_id,
            ))
        if interaction.score_delta:
            score_node=f"minigame-subject:{model.feature_id}:score"
            entities.setdefault(score_node,Entity(score_node,"MINIGAME_SCORE","score",{
                "scope":"feature","feature_id":model.feature_id,
            }))
            edges.append(DependencyEdge(
                f"minigame-score:{_token(model.feature_id,interaction.interaction_id,interaction.score_delta)}",
                node,score_node,"AFFECTS",
                evidence_id=(interaction.evidence_ids[0] if interaction.evidence_ids else None),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="minigame_framework",
                notes=f"score_delta={interaction.score_delta}",
                source_snapshot_id=source_snapshot_id,
            ))
        for index,condition in enumerate(interaction.conditions):
            subject,scoped=_state_subject(model.feature_id,condition.subject)
            entities.setdefault(subject,Entity(subject,"MINIGAME_SUBJECT",condition.subject,{
                "scope":"feature" if scoped else "shared",
                **({"feature_id":model.feature_id} if scoped else {}),
                "raw_subject":condition.subject,
            }))
            edges.append(DependencyEdge(
                f"minigame-interaction-requires:{_token(model.feature_id,interaction.interaction_id,index,subject,condition.operator,condition.value)}",
                node,subject,"REQUIRES",
                evidence_id=(condition.evidence_ids[0] if condition.evidence_ids else (interaction.evidence_ids[0] if interaction.evidence_ids else None)),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="minigame_framework",
                notes=f"{condition.operator} {condition.value!r}",
                source_snapshot_id=source_snapshot_id,
            ))
        for index,effect in enumerate(interaction.effects):
            subject,scoped=_state_subject(model.feature_id,effect.subject)
            entities.setdefault(subject,Entity(subject,"MINIGAME_SUBJECT",effect.subject,{
                "scope":"feature" if scoped else "shared",
                **({"feature_id":model.feature_id} if scoped else {}),
                "raw_subject":effect.subject,
            }))
            edges.append(DependencyEdge(
                f"minigame-interaction-affects:{_token(model.feature_id,interaction.interaction_id,index,subject,effect.effect,effect.value)}",
                node,subject,"AFFECTS",
                evidence_id=(effect.evidence_ids[0] if effect.evidence_ids else (interaction.evidence_ids[0] if interaction.evidence_ids else None)),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="minigame_framework",
                notes=f"{effect.effect} {effect.value!r}",
                source_snapshot_id=source_snapshot_id,
            ))

    for reset in model.resets:
        node=f"minigame-reset:{model.feature_id}:{reset.reset_id}"
        entities[node]=Entity(node,"MINIGAME_RESET",reset.label,{
            "feature_id":model.feature_id,
            "reset_id":reset.reset_id,
            "trigger":reset.trigger,
            "clears_subjects":list(reset.clears_subjects),
            "cancels_timers":list(reset.cancels_timers),
            "reset_score":reset.reset_score,
            "metadata":dict(reset.metadata),
        })
        edges.append(DependencyEdge(
            f"minigame-has-reset:{_token(model.feature_id,reset.reset_id)}",
            model.feature_id,node,"HAS_RESET",
            evidence_id=(reset.evidence_ids[0] if reset.evidence_ids else None),
            confidence="INFERRED",status="DISCOVERED",
            discovered_by="minigame_framework",source_snapshot_id=source_snapshot_id,
        ))
        for timer_id in reset.cancels_timers:
            edges.append(DependencyEdge(
                f"minigame-reset-timer:{_token(model.feature_id,reset.reset_id,timer_id)}",
                node,timer_nodes[timer_id],"CANCELS_TIMER",
                evidence_id=(reset.evidence_ids[0] if reset.evidence_ids else None),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="minigame_framework",source_snapshot_id=source_snapshot_id,
            ))
        for subject_raw in reset.clears_subjects:
            subject,scoped=_state_subject(model.feature_id,subject_raw)
            entities.setdefault(subject,Entity(subject,"MINIGAME_SUBJECT",subject_raw,{
                "scope":"feature" if scoped else "shared",
                **({"feature_id":model.feature_id} if scoped else {}),
                "raw_subject":subject_raw,
            }))
            edges.append(DependencyEdge(
                f"minigame-reset-state:{_token(model.feature_id,reset.reset_id,subject)}",
                node,subject,"RESETS",
                evidence_id=(reset.evidence_ids[0] if reset.evidence_ids else None),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="minigame_framework",source_snapshot_id=source_snapshot_id,
            ))
        if reset.reset_score:
            score_node=f"minigame-subject:{model.feature_id}:score"
            entities.setdefault(score_node,Entity(score_node,"MINIGAME_SCORE","score",{
                "scope":"feature","feature_id":model.feature_id,
            }))
            edges.append(DependencyEdge(
                f"minigame-reset-score:{_token(model.feature_id,reset.reset_id)}",
                node,score_node,"RESETS",
                evidence_id=(reset.evidence_ids[0] if reset.evidence_ids else None),
                confidence="INFERRED",status="DISCOVERED",
                discovered_by="minigame_framework",source_snapshot_id=source_snapshot_id,
            ))

    return MinigameGraphProjection(feature,tuple(entities.values()),tuple(edges))


def persist_minigame_graph(
    con: sqlite3.Connection,
    projection: MinigameGraphProjection,
    *,
    commit: bool=True,
) -> None:
    if con.execute("SELECT 1 FROM features WHERE feature_id=?",(projection.feature.feature_id,)).fetchone() is None:
        graph_store.insert_record(con,projection.feature)
    for entity in projection.entities:
        if con.execute("SELECT 1 FROM entities WHERE entity_id=?",(entity.entity_id,)).fetchone() is None:
            graph_store.insert_record(con,entity)
    for edge in projection.edges:
        graph_store.insert_record(con,edge)
    if commit:
        con.commit()
