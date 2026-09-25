#!/usr/bin/env python3
from workbench.plugins.domain import PluginContext, default_registry
from workbench.plugins.domain.planning import plugin_findings_to_actions


def main():
    registry=default_registry()
    context=PluginContext(
        feature_id="feature:test",
        source_family="LSB",
        target_family="DSP",
        metadata={
            "systems":["MISSION_BATTLEFIELD"],
            "capability_coverage_status":"CAPABILITY_COVERAGE_DRIFT",
            "entity_coverage_aligned":False,
        },
    )
    findings=registry.migration_findings(context)
    actions=plugin_findings_to_actions(findings,"migration:test")
    reshape={a.metadata.get("reshape") for a in actions if a.action=="RESHAPE"}
    assert {
        "BATTLEFIELD_POLICY_TO_REGISTRY_SQL",
        "BATTLEFIELD_GROUPS_TO_MEMBERSHIP_SQL",
        "FRAMEWORK_ORCHESTRATION_TO_DSP_CALLBACKS",
    } <= reshape,actions
    assert all(a.status=="MANUAL_REQUIRED" for a in actions),actions
    print("domain plugin migration action self-test: PASS")


if __name__=="__main__":
    main()
