"""Relationship-generator registry for scenario-driven Feature Trace.

Generators are adapters over evidence that already exists elsewhere in the toolkit.  This module
only defines ownership, supported roots/modes and confidence policy; generators must return
provenanced relationship candidates and never silently write graph edges.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class RelationshipCandidate:
    source_node: str
    target_node: str
    relationship: str
    confidence: str
    generator: str
    evidence: tuple[dict, ...] = ()
    metadata: dict | None = None

    def as_dict(self) -> dict:
        return {
            "source_node": self.source_node,
            "target_node": self.target_node,
            "relationship": self.relationship,
            "confidence": self.confidence,
            "generator": self.generator,
            "evidence": list(self.evidence),
            "metadata": dict(self.metadata or {}),
            "generated": True,
        }


@dataclass(frozen=True)
class GeneratorSpec:
    generator_id: str
    label: str
    root_kinds: tuple[str, ...]
    modes: tuple[str, ...]
    evidence_domains: tuple[str, ...]
    phase: int


GENERATORS = (
    GeneratorSpec("mission-state", "Mission/quest state machine", ("mission",),
                  ("mission", "triggers", "effects", "diagnose", "implementation"), ("server-lua", "character-state"), 2),
    GeneratorSpec("lua-sql", "Lua / SQL implementation wiring", ("entity", "mission", "instance", "item", "feature"),
                  ("implementation", "triggers", "effects", "dependencies", "diagnose"), ("server-lua", "server-sql"), 3),
    GeneratorSpec("identity", "Client/server/runtime identity", ("entity", "runtime"),
                  ("identity", "implementation", "runtime", "diagnose"), ("server-sql", "client", "capture"), 1),
    GeneratorSpec("event-csid", "Event / CSID wiring", ("entity", "mission", "feature"),
                  ("mission", "triggers", "effects", "runtime", "diagnose"), ("server-lua", "client-events", "capture"), 3),
    GeneratorSpec("binding", "Lua API / C++ binding", ("implementation", "entity", "mission", "feature", "ability"),
                  ("implementation", "diagnose"), ("behavior", "bindings", "cpp"), 7),
    GeneratorSpec("runtime", "Runtime capture correlation", ("entity", "runtime", "mission", "instance", "feature"),
                  ("runtime", "identity", "diagnose", "implementation"), ("capture", "packets", "chat"), 7),
    GeneratorSpec("reference", "Wiki/research supporting evidence", ("entity", "mission", "item", "instance", "feature"),
                  ("diagnose", "dependencies", "mission", "implementation"), ("wiki", "research"), 7),
)

GENERATOR_BY_ID = {spec.generator_id: spec for spec in GENERATORS}


def generators_for(root_kind: str, mode: str) -> list[GeneratorSpec]:
    return [
        spec for spec in GENERATORS
        if root_kind in spec.root_kinds and mode in spec.modes
    ]


def confidence_rank(value: str | None) -> int:
    return {"VERIFIED": 4, "EXACT": 4, "STRONG": 3, "INFERRED": 2, "REFERENCE": 1}.get(str(value or "").upper(), 0)


def rank_candidates(candidates: Iterable[RelationshipCandidate]) -> list[RelationshipCandidate]:
    return sorted(candidates, key=lambda row: (-confidence_rank(row.confidence), row.relationship, row.target_node, row.generator))


def dedupe_candidates(candidates: Iterable[RelationshipCandidate]) -> list[RelationshipCandidate]:
    best: dict[tuple[str, str, str], RelationshipCandidate] = {}
    for row in candidates:
        key = (row.source_node, row.target_node, row.relationship)
        current = best.get(key)
        if current is None or confidence_rank(row.confidence) > confidence_rank(current.confidence):
            best[key] = row
    return rank_candidates(best.values())
