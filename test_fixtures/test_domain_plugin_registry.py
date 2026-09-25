#!/usr/bin/env python3
"""Regression checks for reusable domain framework/plugin composition."""
from workbench.plugins.domain import PluginContext, default_registry

def main():
    registry=default_registry()
    ids={p.spec.plugin_id for p in registry.plugins()}
    assert {
        "framework.battlefield",
        "framework.quest_mission",
        "framework.multizone_progression",
        "framework.minigame",
        "system.assault",
    } <= ids,ids

    battlefield=registry.get("framework.battlefield")
    assert {"BCNM","KSNM","ISNM","ENM","MISSION_BATTLEFIELD"} <= set(battlefield.spec.systems)
    assert "battlefield_instance" in battlefield.spec.archetypes

    assault=registry.get("system.assault")
    assert "framework.battlefield" in assault.spec.framework_dependencies
    assert "framework.quest_mission" in assault.spec.framework_dependencies
    assert {"system_container","battlefield_instance","multistage_mission"} <= set(assault.spec.archetypes)

    ancient=PluginContext(
        feature_id="feature:cop:ancient_vows",
        metadata={"systems":["MISSION_BATTLEFIELD","MISSION"]},
    )
    assert battlefield.identify(ancient)
    assert registry.get("framework.quest_mission").identify(ancient)

    aligned=PluginContext(
        feature_id="feature:cop:ancient_vows",
        metadata={
            "systems":["MISSION_BATTLEFIELD","MISSION"],
            "capability_coverage_status":"CAPABILITIES_ALIGNED",
            "entity_coverage_aligned":True,
        },
    )
    findings=registry.migration_findings(aligned)
    battlefield_rules=[f for f in findings if f.plugin_id=="framework.battlefield"]
    assert battlefield_rules,battlefield_rules
    assert battlefield_rules[0].metadata["proposed_action"]=="NOT_REQUIRED",battlefield_rules

    assault_ctx=PluginContext(
        feature_id="feature:assault:excavation_duty",
        metadata={"systems":["ASSAULT"]},
    )
    assert assault.identify(assault_ctx)
    assert set(assault.classify_archetypes(assault_ctx)) >= {"system_container","battlefield_instance"}

    print("domain plugin registry self-test: PASS")

if __name__=="__main__":
    main()
