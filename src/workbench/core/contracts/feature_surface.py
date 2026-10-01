"""Neutral feature-surface observation contracts shared across product components."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SurfaceArtifact:
    role: str
    path: str
    artifact_type: str
    status: str = "PRESENT"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SurfaceCapability:
    name: str
    status: str = "VERIFIED"
    evidence: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureSurface:
    feature_id: str
    family: str
    artifacts: tuple[SurfaceArtifact, ...] = ()
    entity_ids: tuple[int, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    capabilities: tuple[SurfaceCapability, ...] = ()
