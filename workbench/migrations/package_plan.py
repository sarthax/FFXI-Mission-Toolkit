"""Dependency-aware migration package planning.

This module orders existing generic MigrationAction records using explicit canonical
dependency edges. It plans only; it never writes source trees, SQL, DATs, or packages.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from workbench.core.schema import DependencyEdge, MigrationAction

DEPENDENCY_RELATIONSHIPS = {
    "REQUIRES",
    "IMPORTS",
    "REFERENCES",
    "USES_ID",
    "USES_PACKET",
    "USES_ENUM",
    "USES_CLIENT_CAPABILITY",
    "BINDS",
    "BUILDS_INTO",
}


@dataclass(frozen=True)
class PackagePlan:
    migration_id: str
    ordered_actions: tuple[MigrationAction, ...]
    excluded_actions: tuple[MigrationAction, ...]
    dependency_links: tuple[tuple[str, str], ...]
    cycle_action_ids: tuple[str, ...] = ()
    status: str = "READY"


def build_package_plan(
    actions: Iterable[MigrationAction],
    dependencies: Iterable[DependencyEdge] = (),
) -> PackagePlan:
    action_list = list(actions)
    migration_ids = {a.migration_id for a in action_list}
    if len(migration_ids) > 1:
        raise ValueError("Package plan actions must belong to one migration")
    migration_id = next(iter(migration_ids), "migration:empty")

    excluded = tuple(sorted(
        (a for a in action_list if a.action == "NOT_REQUIRED"),
        key=lambda a: a.action_id,
    ))
    actionable = [a for a in action_list if a.action != "NOT_REQUIRED"]
    by_id = {a.action_id: a for a in actionable}
    by_artifact = {
        a.artifact_id: a.action_id
        for a in actionable
        if a.artifact_id
    }

    prereqs = {a.action_id: set() for a in actionable}
    links: set[tuple[str, str]] = set()

    for edge in dependencies:
        if edge.relationship not in DEPENDENCY_RELATIONSHIPS:
            continue
        dependent = by_artifact.get(edge.source_node)
        prerequisite = by_artifact.get(edge.target_node)
        if dependent and prerequisite and dependent != prerequisite:
            prereqs[dependent].add(prerequisite)
            links.add((dependent, prerequisite))

    for action in actionable:
        explicit = action.metadata.get("depends_on_action_ids", [])
        if isinstance(explicit, str):
            explicit = [explicit]
        for prerequisite in explicit:
            if prerequisite in by_id and prerequisite != action.action_id:
                prereqs[action.action_id].add(prerequisite)
                links.add((action.action_id, prerequisite))

    ordered_ids: list[str] = []
    remaining = {k: set(v) for k, v in prereqs.items()}
    while remaining:
        ready = sorted(k for k, v in remaining.items() if not v)
        if not ready:
            break
        for action_id in ready:
            ordered_ids.append(action_id)
            remaining.pop(action_id)
        for requirements in remaining.values():
            requirements.difference_update(ready)

    cycle_ids = tuple(sorted(remaining))
    ordered = tuple(by_id[action_id] for action_id in ordered_ids)
    if cycle_ids:
        status = "BLOCKED"
    elif any(a.status in {"BLOCKED", "FAILED"} for a in ordered):
        status = "BLOCKED"
    elif any(a.status in {"MANUAL_REQUIRED", "UNKNOWN"} for a in ordered):
        status = "MANUAL_REQUIRED"
    else:
        status = "READY"

    return PackagePlan(
        migration_id=migration_id,
        ordered_actions=ordered,
        excluded_actions=excluded,
        dependency_links=tuple(sorted(links)),
        cycle_action_ids=cycle_ids,
        status=status,
    )
