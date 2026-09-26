#!/usr/bin/env python3
from workbench.migrations.feature_surface import FeatureSurface, SurfaceArtifact, SurfaceCapability, compare_feature_surfaces
from workbench.migrations.feature_surface_plan import plan_feature_surface, bind_surface_actions_to_artifacts


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
    by_role={a.metadata["source_role"]:a for a in actions}
    assert by_role["registry_sql"].action=="NOT_REQUIRED",actions
    assert by_role["registry_sql"].status=="COMPATIBLE",actions
    assert by_role["mission_script"].action=="MANUAL_REVIEW",actions
    assert by_role["mission_script"].status=="MANUAL_REQUIRED",actions
    bound=bind_surface_actions_to_artifacts(
        actions,
        {"mission_script":"artifact:mission","registry_sql":"artifact:registry"},
    )
    assert {a.artifact_id for a in bound}=={"artifact:mission","artifact:registry"},bound

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
    assert any(a.metadata.get("gap_type")=="ENTITY_COVERAGE_DRIFT" for a in gap_actions),gap_actions

    path_target=FeatureSurface(
        feature_id="feature:test",
        family="DSP",
        artifacts=(
            SurfaceArtifact("mission_script","scripts/legacy_mission.lua","LUA"),
            SurfaceArtifact("registry_sql","sql/registry.sql","SQL"),
        ),
        entity_ids=(1,2),
        capabilities=(
            SurfaceCapability("completion",status="INFERRED"),
            SurfaceCapability("membership"),
        ),
    )
    path_comparison=compare_feature_surfaces(source,path_target)
    path_actions=plan_feature_surface(source,path_comparison,"migration:test-path")
    assert any(a.metadata.get("gap_type")=="ROLE_PATH_DRIFT" for a in path_actions),path_actions
    assert any(a.metadata.get("gap_type")=="CAPABILITY_STATUS_DRIFT" for a in path_actions),path_actions
    print("feature surface migration planning self-test: PASS")


if __name__=="__main__":
    main()
