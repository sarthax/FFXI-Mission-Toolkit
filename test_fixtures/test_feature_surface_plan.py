#!/usr/bin/env python3
from workbench.migrations.feature_surface import FeatureSurface, SurfaceArtifact, SurfaceCapability, compare_feature_surfaces
from workbench.migrations.feature_surface_plan import plan_feature_surface


def main():
    source=FeatureSurface(
        feature_id="feature:test",
        family="LSB",
        artifacts=(
            SurfaceArtifact("mission_script","scripts/mission.lua","LUA"),
            SurfaceArtifact("registry_sql","sql/registry.sql","SQL"),
        ),
        entity_ids=(1,2),
        capabilities=(SurfaceCapability("completion"),SurfaceCapability("membership")),
    )
    target=FeatureSurface(
        feature_id="feature:test",
        family="DSP",
        artifacts=(
            SurfaceArtifact("battlefield_script","scripts/battlefield.lua","LUA"),
            SurfaceArtifact("registry_sql","sql/registry.sql","SQL"),
        ),
        entity_ids=(1,2),
        capabilities=(SurfaceCapability("completion"),SurfaceCapability("membership")),
    )
    comparison=compare_feature_surfaces(source,target)
    actions=plan_feature_surface(source,comparison,"migration:test")
    assert actions and all(a.action=="NOT_REQUIRED" for a in actions),actions
    assert all(a.status=="COMPATIBLE" for a in actions),actions

    target_gap=FeatureSurface(
        feature_id="feature:test",
        family="DSP",
        artifacts=(SurfaceArtifact("registry_sql","sql/registry.sql","SQL"),),
        entity_ids=(1,),
        capabilities=(SurfaceCapability("membership"),),
    )
    gap_comparison=compare_feature_surfaces(source,target_gap)
    gap_actions=plan_feature_surface(source,gap_comparison,"migration:test-gap")
    assert any(a.action=="MANUAL_REVIEW" for a in gap_actions),gap_actions
    assert any(a.metadata.get("gap_type")=="SOURCE_ONLY_CAPABILITY" for a in gap_actions),gap_actions
    print("feature surface migration planning self-test: PASS")


if __name__=="__main__":
    main()
