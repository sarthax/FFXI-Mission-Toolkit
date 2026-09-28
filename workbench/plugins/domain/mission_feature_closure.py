"""Cross-feature closure for mission/quest state-machine requirements.

This domain-level adapter follows explicit feature prerequisites without changing the
canonical graph schema. It preserves ALL/ANY gate semantics, supports selecting one
alternative for a bounded branch analysis, and keeps unresolved feature symbols visible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .mission_state_machine import DependencyGate, MissionStateMachine, StateCondition


@dataclass(frozen=True)
class FeatureDependency:
    source_feature_id: str
    subject: str
    operator: str
    value: object
    logic: str
    group_id: str
    resolved_feature_id: str | None = None
    status: str = "UNRESOLVED"
    selected: bool = True


@dataclass(frozen=True)
class FeatureClosure:
    root_feature_id: str
    feature_ids: tuple[str,...]
    dependencies: tuple[FeatureDependency,...]
    unresolved_subjects: tuple[str,...]
    skipped_alternatives: tuple[str,...]
    cycles: tuple[tuple[str,str],...]


def feature_symbol_index(
    machines: Iterable[MissionStateMachine],
) -> dict[str,MissionStateMachine]:
    """Index structural machines by explicit domain symbol and feature id."""
    out={}
    for machine in machines:
        out[machine.feature_id]=machine
        quest_symbol=machine.metadata.get("quest_symbol")
        if quest_symbol:
            out[f"quest:{quest_symbol}"]=machine
        mission_symbol=machine.metadata.get("mission_symbol")
        if mission_symbol:
            out[f"mission:{mission_symbol}"]=machine
    return out


def _feature_requirements(machine: MissionStateMachine) -> tuple[StateCondition,...]:
    """Return de-duplicated feature-level prerequisites proven by source eligibility."""
    out=[]
    for transition in machine.transitions:
        for row in transition.metadata.get("section_eligibility_conditions",()):
            subject=str(row.get("subject") or "")
            operator=str(row.get("operator") or "")
            if not (
                (subject.startswith("quest:") and operator=="COMPLETE")
                or subject.startswith("mission:")
            ):
                continue
            condition=StateCondition(subject,operator,row.get("value"))
            if condition not in out:
                out.append(condition)
    return tuple(out)


def _selected(
    condition: StateCondition,
    gate: DependencyGate,
    selected_any_subjects: frozenset[str],
) -> bool:
    if gate.logic!="ANY":
        return True
    if not selected_any_subjects:
        return True
    return condition.subject in selected_any_subjects


def build_feature_requirement_closure(
    root: MissionStateMachine,
    *,
    machines: Iterable[MissionStateMachine]=(),
    entry_gates: Iterable[DependencyGate]=(),
    selected_any_subjects: Iterable[str]=(),
) -> FeatureClosure:
    """Recursively follow explicit quest/mission feature requirements.

    entry_gates represents requirements discovered outside the root source artifact
    (for example a next-mission helper gate). ANY alternatives remain explicit. When
    selected_any_subjects is supplied, non-selected ANY alternatives are recorded but
    are not recursively expanded.
    """
    all_machines=(root,*tuple(machines))
    index=feature_symbol_index(all_machines)
    selected=frozenset(selected_any_subjects)
    dependencies=[]
    unresolved=set()
    skipped=set()
    cycles=[]
    visited={root.feature_id}
    queue=[]

    def add_gate(source: str, gate: DependencyGate) -> None:
        for condition in gate.conditions:
            follow=_selected(condition,gate,selected)
            target=index.get(condition.subject)
            status="RESOLVED" if target else "UNRESOLVED"
            dependencies.append(FeatureDependency(
                source,
                condition.subject,
                condition.operator,
                condition.value,
                gate.logic,
                gate.gate_id,
                target.feature_id if target else None,
                status,
                follow,
            ))
            if not follow:
                skipped.add(condition.subject)
                continue
            if target is None:
                unresolved.add(condition.subject)
                continue
            if target.feature_id in visited:
                cycles.append((source,target.feature_id))
                continue
            visited.add(target.feature_id)
            queue.append(target)

    for gate in entry_gates:
        add_gate(root.feature_id,gate)

    while queue:
        machine=queue.pop(0)
        requirements=_feature_requirements(machine)
        if requirements:
            add_gate(
                machine.feature_id,
                DependencyGate(
                    f"feature-prerequisites:{machine.feature_id}",
                    "ALL",
                    requirements,
                ),
            )

    return FeatureClosure(
        root.feature_id,
        tuple(sorted(visited)),
        tuple(dependencies),
        tuple(sorted(unresolved)),
        tuple(sorted(skipped)),
        tuple(sorted(set(cycles))),
    )


def dependency_summary(closure: FeatureClosure) -> dict:
    """Presentation-neutral closure metrics for tests/UI adapters."""
    return {
        "root_feature_id":closure.root_feature_id,
        "feature_count":len(closure.feature_ids),
        "dependency_count":len(closure.dependencies),
        "resolved_dependency_count":sum(
            1 for dependency in closure.dependencies
            if dependency.status=="RESOLVED" and dependency.selected
        ),
        "unresolved_dependency_count":len(closure.unresolved_subjects),
        "skipped_alternative_count":len(closure.skipped_alternatives),
        "cycle_count":len(closure.cycles),
    }