"""Cross-feature closure for mission/quest state-machine requirements.

This domain-level adapter follows explicit feature prerequisites without changing the
canonical graph schema. It preserves ALL/ANY gate semantics, supports selecting one
alternative for a bounded branch analysis, and keeps unresolved feature symbols visible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

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


def _metadata_feature_requirement_gates(
    machine: MissionStateMachine,
) -> tuple[DependencyGate,...]:
    """Recover de-duplicated feature prerequisite gates preserved by source adapters."""
    out=[]
    seen=set()
    row_sets=[
        machine.metadata.get("catalog_feature_requirement_gates",()),
        *(
            transition.metadata.get("section_feature_requirement_gates",())
            for transition in machine.transitions
        ),
    ]
    for rows in row_sets:
        for row in rows:
            conditions=tuple(
                StateCondition(
                    str(condition.get("subject") or ""),
                    str(condition.get("operator") or ""),
                    condition.get("value"),
                )
                for condition in row.get("conditions",())
                if condition.get("subject") and condition.get("operator")
            )
            if not conditions:
                continue
            key=(
                str(row.get("gate_id") or ""),
                str(row.get("logic") or "ALL"),
                tuple((c.subject,c.operator,repr(c.value)) for c in conditions),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(DependencyGate(
                str(row.get("gate_id") or f"feature-helper:{machine.feature_id}:{len(out)+1}"),
                str(row.get("logic") or "ALL"),
                conditions,
            ))
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
    gate_subjects={candidate.subject for candidate in gate.conditions}
    if not (gate_subjects & selected_any_subjects):
        return True
    return condition.subject in selected_any_subjects


def _actual_dependency_cycles(
    dependencies: Iterable[FeatureDependency],
) -> tuple[tuple[str,str],...]:
    """Return only graph back-edges; repeated convergence is not a cycle."""
    adjacency={}
    for dependency in dependencies:
        if not dependency.selected or not dependency.resolved_feature_id:
            continue
        adjacency.setdefault(dependency.source_feature_id,set()).add(
            dependency.resolved_feature_id
        )

    visited=set()
    active=set()
    cycles=set()

    def visit(node: str) -> None:
        if node in visited:
            return
        visited.add(node)
        active.add(node)
        for target in adjacency.get(node,()):
            if target in active:
                cycles.add((node,target))
            elif target not in visited:
                visit(target)
        active.remove(node)

    for node in tuple(adjacency):
        visit(node)
    return tuple(sorted(cycles))


def build_feature_requirement_closure(
    root: MissionStateMachine,
    *,
    machines: Iterable[MissionStateMachine]=(),
    entry_gates: Iterable[DependencyGate]=(),
    selected_any_subjects: Iterable[str]=(),
    resolver: Callable[[str], MissionStateMachine | None] | None=None,
) -> FeatureClosure:
    """Recursively follow explicit quest/mission feature requirements.

    entry_gates represents requirements discovered outside the root source artifact
    (for example a next-mission helper gate). ANY alternatives remain explicit. When
    selected_any_subjects is supplied, non-selected ANY alternatives are recorded but
    are not recursively expanded. resolver may load a missing feature on demand from a
    source catalog; only selected/resolved dependencies are requested from it.
    """
    all_machines=(root,*tuple(machines))
    index=feature_symbol_index(all_machines)
    selected=frozenset(selected_any_subjects)
    dependencies=[]
    unresolved=set()
    skipped=set()
    visited={root.feature_id}
    queue=[]

    def add_gate(source: str, gate: DependencyGate) -> None:
        for condition in gate.conditions:
            follow=_selected(condition,gate,selected)
            if condition.subject.startswith("mission:") and condition.subject.endswith(":current"):
                dependencies.append(FeatureDependency(
                    source,
                    condition.subject,
                    condition.operator,
                    condition.value,
                    gate.logic,
                    gate.gate_id,
                    None,
                    "CONTEXT",
                    follow,
                ))
                continue
            target=index.get(condition.subject)
            if target is None and follow and resolver is not None:
                target=resolver(condition.subject)
                if target is not None:
                    index.update(feature_symbol_index((target,)))
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
        for helper_gate in _metadata_feature_requirement_gates(machine):
            add_gate(machine.feature_id,helper_gate)

        for index_row,row in enumerate(
            machine.metadata.get("documented_feature_requirements",()),
            1,
        ):
            subject=str(row.get("subject") or "")
            if not subject:
                continue
            target=index.get(subject)
            if target is None and resolver is not None:
                target=resolver(subject)
                if target is not None:
                    index.update(feature_symbol_index((target,)))
            dependencies.append(FeatureDependency(
                machine.feature_id,
                subject,
                str(row.get("relation") or "DOCUMENTED"),
                row.get("note"),
                "ALL",
                f"documented-prerequisite:{machine.feature_id}:{index_row}",
                target.feature_id if target else None,
                "DOCUMENTED_UNENFORCED" if target else "DOCUMENTED_UNRESOLVED",
                True,
            ))
            if target is None:
                unresolved.add(subject)
                continue
            if target.feature_id in visited:
                continue
            visited.add(target.feature_id)
            queue.append(target)

    return FeatureClosure(
        root.feature_id,
        tuple(sorted(visited)),
        tuple(dependencies),
        tuple(sorted(unresolved)),
        tuple(sorted(skipped)),
        _actual_dependency_cycles(dependencies),
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