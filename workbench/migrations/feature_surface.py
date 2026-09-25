"""Generic semantic feature-surface comparison.

A feature surface describes which artifact roles and entity identities participate in
an implementation without assuming a game system such as Assault, BCNM, Limbus, etc.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class SurfaceArtifact:
    role: str
    path: str
    artifact_type: str
    status: str = "PRESENT"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureSurface:
    feature_id: str
    family: str
    artifacts: tuple[SurfaceArtifact, ...] = ()
    entity_ids: tuple[int, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeatureSurfaceComparison:
    feature_id: str
    source_family: str
    target_family: str
    shared_roles: tuple[str, ...]
    source_only_roles: tuple[str, ...]
    target_only_roles: tuple[str, ...]
    role_path_drift: tuple[dict[str, Any], ...]
    shared_entity_ids: tuple[int, ...]
    source_only_entity_ids: tuple[int, ...]
    target_only_entity_ids: tuple[int, ...]
    status: str


def _by_role(artifacts: Iterable[SurfaceArtifact]) -> dict[str, list[SurfaceArtifact]]:
    out: dict[str, list[SurfaceArtifact]] = {}
    for artifact in artifacts:
        out.setdefault(artifact.role, []).append(artifact)
    return out


def compare_feature_surfaces(source: FeatureSurface, target: FeatureSurface) -> FeatureSurfaceComparison:
    if source.feature_id != target.feature_id:
        raise ValueError("Feature surface IDs differ")

    src_roles=_by_role(source.artifacts)
    dst_roles=_by_role(target.artifacts)
    shared=sorted(set(src_roles) & set(dst_roles))
    src_only=sorted(set(src_roles) - set(dst_roles))
    dst_only=sorted(set(dst_roles) - set(src_roles))

    path_drift=[]
    for role in shared:
        src_paths=sorted(a.path for a in src_roles[role])
        dst_paths=sorted(a.path for a in dst_roles[role])
        if src_paths != dst_paths:
            path_drift.append({
                "role":role,
                "source_paths":src_paths,
                "target_paths":dst_paths,
                "classification":"PATH_DRIFT",
            })

    src_entities=set(source.entity_ids)
    dst_entities=set(target.entity_ids)
    source_only_entities=tuple(sorted(src_entities-dst_entities))
    target_only_entities=tuple(sorted(dst_entities-src_entities))

    if not src_only and not dst_only and not source_only_entities and not target_only_entities:
        status="ROLE_AND_ENTITY_COVERAGE_ALIGNED"
    elif source_only_entities or target_only_entities:
        status="ENTITY_COVERAGE_DRIFT"
    else:
        status="REPRESENTATION_DRIFT"

    return FeatureSurfaceComparison(
        feature_id=source.feature_id,
        source_family=source.family,
        target_family=target.family,
        shared_roles=tuple(shared),
        source_only_roles=tuple(src_only),
        target_only_roles=tuple(dst_only),
        role_path_drift=tuple(path_drift),
        shared_entity_ids=tuple(sorted(src_entities & dst_entities)),
        source_only_entity_ids=source_only_entities,
        target_only_entity_ids=target_only_entities,
        status=status,
    )
