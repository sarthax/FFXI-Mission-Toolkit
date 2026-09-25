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
class Finding:
    finding_id: str
    analysis_id: str | None
    subject_id: str
    field: str | None
    value: Any = None
    status: str = "UNKNOWN"
    confidence: str = "UNKNOWN"
    evidence_id: str | None = None
    source_snapshot_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    notes: list[str] = field(default_factory=list)

@dataclass
class AnalysisResult:
    analysis_id: str
    analysis_type: str
    source: str
    target: str | None = None
    feature_id: str | None = None
    status: str = "UNKNOWN"
    created_at: str | None = None
    tool_version: str | None = None
    findings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

@dataclass
class FunctionSignature:
    return_type: str | None = None
    parameters: list[str] = field(default_factory=list)
    const: bool = False
    static: bool = False
    noexcept: bool = False
    raw: str | None = None

@dataclass
class Function:
    function_id: str
    qualified_name: str
    name: str
    namespace: str | None = None
    class_name: str | None = None
    source_snapshot_id: str | None = None
    path: str | None = None
    line: int | None = None
    kind: str = "FUNCTION"
    declaration: bool = False
    definition: bool = False
    signature: FunctionSignature = field(default_factory=FunctionSignature)
    evidence_id: str | None = None
    notes: list[str] = field(default_factory=list)

@dataclass
class Binding:
    binding_id: str
    lua_name: str
    binding_system: str
    cpp_symbol: str | None = None
    class_name: str | None = None
    function_id: str | None = None
    source_snapshot_id: str | None = None
    path: str | None = None
    line: int | None = None
    evidence_id: str | None = None
    status: str = "UNKNOWN"
    notes: list[str] = field(default_factory=list)

@dataclass
class EnumDefinition:
    enum_id: str
    enum_name: str
    source_snapshot_id: str | None
    path: str | None
    line: int | None
    format: str
    value: str
    symbol: str
    evidence_id: str | None = None
    notes: list[str] = field(default_factory=list)

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
