"""Generic conditional dependency projection.

Conditional dependencies are explicit graph structure, not ordinary REQUIRES edges with hidden
prose. A gate node preserves why the dependency is conditional while Package Scope can traverse
the relationship and require a human disposition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha1
from typing import Any, Mapping

from workbench.core import graph
from workbench.core.schema import DependencyEdge, Entity, Evidence


@dataclass(frozen=True)
class ConditionalDependency:
    source_node: str
    target_node: str
    label: str
    conditions: tuple[Mapping[str, Any], ...] = ()
    rationale: str | None = None
    evidence_id: str | None = None
    confidence: str = "INFERRED"
    status: str = "DISCOVERED"
    source_snapshot_id: str | None = None
    source_location: str | None = None
    gate_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConditionalDependencyProjection:
    gate: Entity
    edges: tuple[DependencyEdge, ...]


def _token(*parts: object) -> str:
    raw="|".join("" if p is None else str(p) for p in parts)
    return sha1(raw.encode("utf-8")).hexdigest()[:16]


def project_conditional_dependency(spec: ConditionalDependency) -> ConditionalDependencyProjection:
    gate_id=spec.gate_id or f"conditional-dependency:{_token(spec.source_node,spec.target_node,spec.label,spec.conditions)}"
    gate=Entity(
        gate_id,
        "CONDITIONAL_DEPENDENCY",
        spec.label,
        {
            "source_node":spec.source_node,
            "target_node":spec.target_node,
            "conditions":[dict(row) for row in spec.conditions],
            "rationale":spec.rationale,
            "review_default":"QUESTIONABLE",
            **dict(spec.metadata),
        },
    )
    notes=spec.rationale or "Conditional dependency requires explicit scope review."
    edges=(
        DependencyEdge(
            f"has-conditional:{_token(spec.source_node,gate_id)}",
            spec.source_node,gate_id,"HAS_CONDITIONAL_DEPENDENCY",
            spec.evidence_id,spec.confidence,spec.status,
            discovered_by="conditional_dependency_projection",
            source_location=spec.source_location,
            notes=notes,
            source_snapshot_id=spec.source_snapshot_id,
        ),
        DependencyEdge(
            f"conditionally-requires:{_token(gate_id,spec.target_node)}",
            gate_id,spec.target_node,"CONDITIONALLY_REQUIRES",
            spec.evidence_id,spec.confidence,spec.status,
            discovered_by="conditional_dependency_projection",
            source_location=spec.source_location,
            notes=notes,
            source_snapshot_id=spec.source_snapshot_id,
        ),
    )
    return ConditionalDependencyProjection(gate,edges)


def persist_conditional_dependency(con, projection: ConditionalDependencyProjection, *, commit: bool=True) -> None:
    graph.insert_record(con,projection.gate)
    for edge in projection.edges:
        graph.insert_record(con,edge)
    if commit:
        con.commit()
