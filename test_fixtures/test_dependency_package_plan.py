#!/usr/bin/env python3
"""Regression checks for dependency-aware migration package planning."""
from workbench.core.schema import DependencyEdge, MigrationAction
from workbench.migrations.package_plan import build_package_plan


def action(action_id, artifact_id, status="AUTO_MIGRATABLE", action_name="IMPLEMENT"):
    return MigrationAction(
        action_id=action_id,
        migration_id="migration:test",
        action=action_name,
        artifact_id=artifact_id,
        status=status,
    )


def edge(edge_id, source, target):
    return DependencyEdge(
        edge_id=edge_id,
        source_node=source,
        target_node=target,
        relationship="REQUIRES",
        confidence="VERIFIED",
    )


def main():
    actions = [
        action("a:mission", "artifact:mission"),
        action("a:registry", "artifact:registry"),
        action("a:battlefield", "artifact:battlefield"),
        action("a:noop", "artifact:noop", action_name="NOT_REQUIRED"),
    ]
    deps = [
        edge("e1", "artifact:mission", "artifact:battlefield"),
        edge("e2", "artifact:battlefield", "artifact:registry"),
    ]
    plan = build_package_plan(actions, deps)
    assert [a.action_id for a in plan.ordered_actions] == [
        "a:registry", "a:battlefield", "a:mission"
    ], plan
    assert [a.action_id for a in plan.excluded_actions] == ["a:noop"], plan
    assert plan.status == "READY", plan

    manual = build_package_plan([
        action("a:review", "artifact:review", status="MANUAL_REQUIRED"),
    ])
    assert manual.status == "MANUAL_REQUIRED", manual

    cycle = build_package_plan(
        [action("a:one", "artifact:one"), action("a:two", "artifact:two")],
        [
            edge("c1", "artifact:one", "artifact:two"),
            edge("c2", "artifact:two", "artifact:one"),
        ],
    )
    assert cycle.status == "BLOCKED", cycle
    assert cycle.cycle_action_ids == ("a:one", "a:two"), cycle

    print("dependency-aware package plan self-test: PASS")


if __name__ == "__main__":
    main()
