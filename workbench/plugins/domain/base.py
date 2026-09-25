"""Domain-plugin contracts for reusable FFXI content frameworks.

This package is intentionally outside workbench.core. The universal graph/schema
must not gain BCNM/Assault/Nyzul/etc. fields just because a plugin understands
those systems.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from workbench.migrations.feature_surface import SurfaceArtifact


@dataclass(frozen=True)
class ContentArchetype:
    archetype_id: str
    name: str
    description: str
    semantic_roles: tuple[str, ...] = ()
    validation_dimensions: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainPluginSpec:
    plugin_id: str
    name: str
    version: str
    archetypes: tuple[str, ...]
    systems: tuple[str, ...] = ()
    framework_dependencies: tuple[str, ...] = ()
    semantic_roles: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginContext:
    feature_id: str
    source_family: str | None = None
    target_family: str | None = None
    source_snapshot_id: str | None = None
    target_snapshot_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginFinding:
    plugin_id: str
    subject_id: str
    finding_type: str
    status: str
    message: str
    evidence_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


class DomainPlugin:
    """Base class for optional archetype/system-specific analysis."""

    spec: DomainPluginSpec

    def identify(self, context: PluginContext) -> bool:
        return False

    def classify_archetypes(self, context: PluginContext) -> tuple[str, ...]:
        return self.spec.archetypes if self.identify(context) else ()

    def discover_surfaces(self, context: PluginContext) -> tuple[SurfaceArtifact, ...]:
        return ()

    def discover_dependencies(self, context: PluginContext) -> tuple[PluginFinding, ...]:
        return ()

    def compare(self, context: PluginContext) -> tuple[PluginFinding, ...]:
        return ()

    def generate_migration_rules(self, context: PluginContext) -> tuple[PluginFinding, ...]:
        return ()

    def validate(self, context: PluginContext) -> tuple[PluginFinding, ...]:
        return ()

    def report(self, context: PluginContext) -> Mapping[str, Any]:
        return {
            "plugin_id": self.spec.plugin_id,
            "feature_id": context.feature_id,
            "archetypes": list(self.classify_archetypes(context)),
        }
