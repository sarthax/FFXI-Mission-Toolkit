"""Minimal generic Workbench records.

These records deliberately contain no Assault/Nyzul/Salvage-specific fields. Domain-specific
plugins may attach extension metadata outside these core records.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any

@dataclass
class Evidence:
    evidence_id: str
    evidence_type: str
    source: str
    location: str | None = None
    snapshot: str | None = None
    notes: str | None = None

@dataclass
class DependencyEdge:
    edge_id: str
    source_node: str
    target_node: str
    relationship: str
    evidence_id: str | None = None
    confidence: str = "UNKNOWN"
    status: str = "DISCOVERED"
    discovered_by: str | None = None
    source_location: str | None = None
    notes: str | None = None

@dataclass
class Implementation:
    implementation_id: str
    feature_id: str | None
    source_snapshot_id: str | None
    target_snapshot_id: str | None
    artifact_id: str
    artifact_type: str
    status: str
    language: str | None = None
    path: str | None = None
    symbol: str | None = None
    change_type: str | None = None
    scope: str | None = None
    requires_build: bool = False
    build_target: str | None = None
    evidence_id: str | None = None
    notes: list[str] = field(default_factory=list)

def record_dict(record: Any) -> dict[str, Any]:
    return asdict(record)
