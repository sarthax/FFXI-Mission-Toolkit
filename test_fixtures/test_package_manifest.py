#!/usr/bin/env python3
"""Regression checks for migration package manifest generation."""
from workbench.core.schema import Artifact, DependencyEdge, MigrationAction
from workbench.migrations.package_manifest import build_package_manifest, converter_scope
from workbench.migrations.package_plan import build_package_plan


def main():
    artifacts=[
        Artifact("artifact:registry","SQL",path="sql/bcnm_info.sql"),
        Artifact("artifact:battlefield","LUA",path="lua/scripts/battlefields/ancient_vows.lua"),
        Artifact("artifact:notes","REPORT",path="notes.md"),
    ]
    actions=[
        MigrationAction("a:battlefield","migration:av","CONVERT","artifact:battlefield","AUTO_MIGRATABLE"),
        MigrationAction("a:registry","migration:av","CONVERT","artifact:registry","AUTO_MIGRATABLE"),
        MigrationAction("a:notes","migration:av","MANUAL_REVIEW","artifact:notes","MANUAL_REQUIRED"),
    ]
    deps=[DependencyEdge("e1","artifact:battlefield","artifact:registry","REQUIRES")]
    plan=build_package_plan(actions,deps)
    manifest=build_package_manifest(
        plan,
        artifacts,
        feature_id="feature:cop:ancient_vows",
        source_snapshot_id="lsb:test",
        target_snapshot_id="dsp:test",
    )
    assert manifest["schema"]==2,manifest
    assert [s["action_id"] for s in manifest["execution"]["steps"]]==[
        "a:notes","a:registry","a:battlefield"
    ],manifest
    assert converter_scope(manifest,"sql")==("sql/bcnm_info.sql",),manifest
    assert converter_scope(manifest,"lua")==("lua/scripts/battlefields/ancient_vows.lua",),manifest
    assert manifest["migration"]["status"]=="MANUAL_REQUIRED",manifest
    print("migration package manifest self-test: PASS")


if __name__=="__main__":
    main()
