"""Generic mission/quest state-machine model.

The model describes behavior, not a specific FFXI mission or server layout.  Source
adapters may populate it from Lua, references, captures, or other evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


VALID_GATE_LOGIC={"ALL","ANY"}
VALID_EFFECTS={"SET_STATE","SET_VAR","GRANT","REQUIRE","CONSUME","REMOVE","REISSUE","COMPLETE","START","ENTER","EXIT"}
VALID_CONFIDENCE={"UNKNOWN","EXPECTED","INFERRED","VERIFIED"}


@dataclass(frozen=True)
class EventIdentity:
    zone: str
    event_id: int
    actor: str | None = None

    @property
    def key(self) -> str:
        actor=self.actor or "*"
        return f"event:{self.zone}:{actor}:{self.event_id}"


@dataclass(frozen=True)
class StateCondition:
    subject: str
    operator: str
    value: Any = None
    evidence_ids: tuple[str,...] = ()


@dataclass(frozen=True)
class DependencyGate:
    gate_id: str
    logic: str
    conditions: tuple[StateCondition,...]
    evidence_ids: tuple[str,...] = ()

    def __post_init__(self) -> None:
        if self.logic not in VALID_GATE_LOGIC:
            raise ValueError(f"Unsupported gate logic: {self.logic}")
        if not self.conditions:
            raise ValueError("DependencyGate requires at least one condition")


@dataclass(frozen=True)
class TransitionEffect:
    effect: str
    subject: str
    value: Any = None
    evidence_ids: tuple[str,...] = ()

    def __post_init__(self) -> None:
        if self.effect not in VALID_EFFECTS:
            raise ValueError(f"Unsupported transition effect: {self.effect}")


@dataclass(frozen=True)
class MissionState:
    state_id: str
    label: str
    terminal: bool = False
    metadata: Mapping[str,Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MissionTransition:
    transition_id: str
    from_state: str
    to_state: str
    trigger: str
    gate: DependencyGate | None = None
    event: EventIdentity | None = None
    effects: tuple[TransitionEffect,...] = ()
    confidence: str = "UNKNOWN"
    evidence_ids: tuple[str,...] = ()
    implementation_status: str = "PRESENT"
    metadata: Mapping[str,Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.confidence not in VALID_CONFIDENCE:
            raise ValueError(f"Unsupported confidence: {self.confidence}")


@dataclass(frozen=True)
class MissionStateMachine:
    machine_id: str
    feature_id: str
    states: tuple[MissionState,...]
    transitions: tuple[MissionTransition,...]
    entry_state_ids: tuple[str,...] = ()
    metadata: Mapping[str,Any] = field(default_factory=dict)

    def validate(self) -> tuple[str,...]:
        errors=[]
        state_ids=[s.state_id for s in self.states]
        if len(state_ids)!=len(set(state_ids)):
            errors.append("duplicate state_id")
        known=set(state_ids)
        transition_ids=[t.transition_id for t in self.transitions]
        if len(transition_ids)!=len(set(transition_ids)):
            errors.append("duplicate transition_id")
        for entry in self.entry_state_ids:
            if entry not in known:
                errors.append(f"unknown entry state: {entry}")
        for t in self.transitions:
            if t.from_state not in known:
                errors.append(f"{t.transition_id}: unknown from_state {t.from_state}")
            if t.to_state not in known:
                errors.append(f"{t.transition_id}: unknown to_state {t.to_state}")
        return tuple(errors)

    def outgoing(self,state_id: str) -> tuple[MissionTransition,...]:
        return tuple(t for t in self.transitions if t.from_state==state_id)


@dataclass(frozen=True)
class BranchReadiness:
    entry_state_id: str
    reachable_state_ids: tuple[str,...]
    terminal_state_ids: tuple[str,...]
    visible_gap_transition_ids: tuple[str,...]
    status: str


@dataclass(frozen=True)
class MissionMachineAnalysis:
    status: str
    branch_readiness: tuple[BranchReadiness,...]
    event_keys: tuple[str,...]
    lifecycle_subjects: Mapping[str,tuple[str,...]]
    gap_transition_ids: tuple[str,...]


def analyze_state_machine(machine: MissionStateMachine) -> MissionMachineAnalysis:
    errors=machine.validate()
    if errors:
        raise ValueError("; ".join(errors))

    gaps=tuple(sorted(t.transition_id for t in machine.transitions if t.implementation_status not in {"PRESENT","IMPLEMENTED","VERIFIED"}))
    event_keys=tuple(sorted({t.event.key for t in machine.transitions if t.event}))
    lifecycle: dict[str,set[str]]={}
    for t in machine.transitions:
        for e in t.effects:
            if e.effect in {"GRANT","REQUIRE","CONSUME","REMOVE","REISSUE"}:
                lifecycle.setdefault(e.subject,set()).add(e.effect)

    branches=[]
    terminal={s.state_id for s in machine.states if s.terminal}
    for entry in machine.entry_state_ids:
        seen={entry}
        stack=[entry]
        branch_gaps=set()
        while stack:
            current=stack.pop()
            for t in machine.outgoing(current):
                if t.implementation_status not in {"PRESENT","IMPLEMENTED","VERIFIED"}:
                    branch_gaps.add(t.transition_id)
                if t.to_state not in seen:
                    seen.add(t.to_state)
                    stack.append(t.to_state)
        reached_terminal=terminal & seen
        status="COMPLETE" if reached_terminal and not branch_gaps else ("VIABLE_WITH_GAPS" if reached_terminal else "INCOMPLETE")
        branches.append(BranchReadiness(entry,tuple(sorted(seen)),tuple(sorted(reached_terminal)),tuple(sorted(branch_gaps)),status))

    overall="COMPLETE" if branches and all(b.status=="COMPLETE" for b in branches) else ("PARTIAL" if any(b.terminal_state_ids for b in branches) else "INCOMPLETE")
    return MissionMachineAnalysis(
        overall,
        tuple(branches),
        event_keys,
        {k:tuple(sorted(v)) for k,v in sorted(lifecycle.items())},
        gaps,
    )


def conditions_for_alternatives(subjects: Iterable[str], *, gate_id: str) -> DependencyGate:
    return DependencyGate(gate_id,"ANY",tuple(StateCondition(s,"COMPLETE",True) for s in subjects))
