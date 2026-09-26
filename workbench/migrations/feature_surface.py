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
    shared_capabilities: tuple[str, ...] = ()
    source_only_capabilities: tuple[str, ...] = ()
    target_only_capabilities: tuple[str, ...] = ()
    capability_status_drift: tuple[dict[str, Any], ...] = ()
    capability_coverage_status: str = "NO_CAPABILITIES_DECLARED"


def _by_role(artifacts: Iterable[SurfaceArtifact]) -> dict[str, list[SurfaceArtifact]]:
    out: dict[str, list[SurfaceArtifact]] = {}
    for artifact in artifacts:
        out.setdefault(artifact.role, []).append(artifact)
    return out


def _capabilities_by_name(capabilities: Iterable[SurfaceCapability]) -> dict[str, SurfaceCapability]:
    result={}
    for capability in capabilities:
        if capability.name in result:
            raise ValueError(f"Duplicate surface capability: {capability.name}")
        result[capability.name]=capability
    return result


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

    src_caps=_capabilities_by_name(source.capabilities)
    dst_caps=_capabilities_by_name(target.capabilities)
    shared_caps=sorted(set(src_caps) & set(dst_caps))
    source_only_caps=sorted(set(src_caps)-set(dst_caps))
    target_only_caps=sorted(set(dst_caps)-set(src_caps))
    cap_status_drift=[
        {
            "capability":name,
            "source_status":src_caps[name].status,
            "target_status":dst_caps[name].status,
        }
        for name in shared_caps
        if src_caps[name].status != dst_caps[name].status
    ]
    if not src_caps and not dst_caps:
        capability_coverage_status="NO_CAPABILITIES_DECLARED"
    elif source_only_caps or target_only_caps:
        capability_coverage_status="CAPABILITY_COVERAGE_DRIFT"
    elif cap_status_drift:
        capability_coverage_status="CAPABILITY_STATUS_DRIFT"
    else:
        capability_coverage_status="CAPABILITIES_ALIGNED"

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
        shared_capabilities=tuple(shared_caps),
        source_only_capabilities=tuple(source_only_caps),
        target_only_capabilities=tuple(target_only_caps),
        capability_status_drift=tuple(cap_status_drift),
        capability_coverage_status=capability_coverage_status,
    )
