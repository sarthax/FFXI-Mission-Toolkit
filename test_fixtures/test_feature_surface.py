#!/usr/bin/env python3
"""Regression checks for generic feature-surface comparison."""
from workbench.migrations.feature_surface import FeatureSurface, SurfaceArtifact, compare_feature_surfaces

def main():
    src=FeatureSurface(
        feature_id="feature:test",
        family="SOURCE",
        artifacts=(
            SurfaceArtifact("battlefield_script","scripts/new.lua","LUA"),
            SurfaceArtifact("mission_script","scripts/mission.lua","LUA"),
        ),
        entity_ids=(1,2,3),
    )
    dst=FeatureSurface(
        feature_id="feature:test",
        family="TARGET",
        artifacts=(
            SurfaceArtifact("battlefield_script","scripts/old.lua","LUA"),
            SurfaceArtifact("membership_sql","sql/members.sql","SQL"),
        ),
        entity_ids=(1,2,3),
    )
    result=compare_feature_surfaces(src,dst)
    assert result.status=="REPRESENTATION_DRIFT",result
    assert result.shared_roles==("battlefield_script",),result
    assert result.source_only_roles==("mission_script",),result
    assert result.target_only_roles==("membership_sql",),result
    assert result.role_path_drift[0]["role"]=="battlefield_script",result
    assert result.shared_entity_ids==(1,2,3),result
    print("feature surface self-test: PASS")

if __name__=="__main__":
    main()
