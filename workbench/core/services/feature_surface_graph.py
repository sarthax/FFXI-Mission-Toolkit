"""Persist generic FeatureSurface evidence into the canonical Workbench graph."""
from __future__ import annotations
import hashlib

from workbench.core import graph
from workbench.core.schema import Artifact, DependencyEdge, Evidence, Feature, Implementation
from workbench.migrations.feature_surface import FeatureSurface


def _slug(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def persist_feature_surface(
    con,
    surface: FeatureSurface,
    feature: Feature,
    snapshot_id: str,
) -> dict[str, int]:
    """Persist one snapshot's feature surface without conflating numeric entity IDs across snapshots."""
    graph.insert_record(con, feature)
    counts={"artifacts":0,"implementations":0,"entity_refs":0,"edges":0,"evidence":0}

    for artifact in surface.artifacts:
        suffix=_slug(f"{artifact.role}:{artifact.path}")
        evidence_id=f"evidence:surface:{snapshot_id}:{suffix}"
        artifact_id=f"artifact:{snapshot_id}:{suffix}"
        implementation_id=f"implementation:{feature.feature_id}:{snapshot_id}:{suffix}"

        graph.insert_record(con,Evidence(
            evidence_id=evidence_id,
            evidence_type="SOURCE",
            source=surface.family,
            location=artifact.path,
            snapshot=snapshot_id,
            notes=f"Feature surface artifact role: {artifact.role}",
        ))
        graph.insert_record(con,Artifact(
            artifact_id=artifact_id,
            artifact_type=artifact.artifact_type,
            path=artifact.path,
            source_snapshot_id=snapshot_id,
            feature_id=feature.feature_id,
            metadata={
                "role":artifact.role,
                "family":surface.family,
                "surface_status":artifact.status,
                **artifact.metadata,
            },
        ))
        graph.insert_record(con,Implementation(
            implementation_id=implementation_id,
            feature_id=feature.feature_id,
            source_snapshot_id=snapshot_id,
            target_snapshot_id=None,
            artifact_id=artifact_id,
            artifact_type=artifact.artifact_type,
            status="VERIFIED" if artifact.status=="PRESENT" else artifact.status,
            language=artifact.artifact_type if artifact.artifact_type in {"LUA","SQL","CPP","YAML"} else None,
            path=artifact.path,
            evidence_id=evidence_id,
            notes=[f"Semantic feature-surface role: {artifact.role}",f"Server family: {surface.family}"],
        ))
        counts["evidence"]+=1
        counts["artifacts"]+=1
        counts["implementations"]+=1
        counts["edges"]+=1

    for entity_id in sorted(set(surface.entity_ids)):
        node=f"entity-ref:{snapshot_id}:{entity_id}"
        evidence_id=f"evidence:surface-entity:{snapshot_id}:{entity_id}"
        con.execute(
            "INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
            (node,"ENTITY_REF",str(entity_id),graph._json({
                "numeric_id":entity_id,
                "snapshot_id":snapshot_id,
                "family":surface.family,
            })),
        )
        graph.insert_record(con,Evidence(
            evidence_id=evidence_id,
            evidence_type="SOURCE",
            source=surface.family,
            location=f"feature-surface:{surface.feature_id}",
            snapshot=snapshot_id,
            notes="Snapshot-scoped numeric entity membership reference.",
        ))
        graph.insert_record(con,DependencyEdge(
            edge_id=f"surface-uses-id:{feature.feature_id}:{snapshot_id}:{entity_id}",
            source_node=feature.feature_id,
            target_node=node,
            relationship="USES_ID",
            evidence_id=evidence_id,
            confidence="VERIFIED",
            status="DISCOVERED",
            discovered_by="feature_surface_graph",
            source_location=f"feature-surface:{surface.feature_id}",
            notes="Numeric entity ID is snapshot-scoped; semantic cross-snapshot identity requires separate evidence.",
            source_snapshot_id=snapshot_id,
        ))
        counts["entity_refs"]+=1
        counts["evidence"]+=1
        counts["edges"]+=1

    con.commit()
    return counts
