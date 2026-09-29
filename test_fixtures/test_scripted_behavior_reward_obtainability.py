#!/usr/bin/env python3
"""Regression for scripted reward -> obtainability graph projection."""
from __future__ import annotations

from pathlib import Path
import tempfile

from workbench.core import graph
from workbench.core.services.obtainability_closure import build_obtainability_closure
from workbench.plugins.domain.scripted_behavior import (
    BehaviorEffect,
    BehaviorRule,
    ScriptedBehaviorMap,
    persist_scripted_behavior,
    project_scripted_behavior,
)


def main():
    behavior=ScriptedBehaviorMap(
        map_id="behavior-map:reward-fixture",
        feature_id="feature:reward-fixture",
        subject="Reward NPC",
        zone="TEST",
        hooks=("onEventFinish",),
        rules=(
            BehaviorRule(
                "reward-rule",
                "player_progression",
                "Reward NPC",
                trigger="ONEVENTFINISH",
                effects=(
                    BehaviorEffect("GRANT_KEY_ITEM","player","TEST_SEAL"),
                    BehaviorEffect("GRANT_ITEM","player","12345"),
                    BehaviorEffect("ADD_GIL","player","500"),
                ),
                confidence="VERIFIED",
                implementation_status="PRESENT",
                metadata={
                    "source_path":"scripts/zones/Test/npcs/Reward_NPC.lua",
                    "source_lines":(10,20),
                },
            ),
        ),
    )

    projection=project_scripted_behavior(
        behavior,
        evidence_source="LSB_LUA",
        evidence_location="scripts/zones/Test/npcs/Reward_NPC.lua",
    )

    reward_edges=[
        edge for edge in projection.edges
        if edge.relationship=="REWARDED_BY"
    ]
    assert len(reward_edges)==2,reward_edges

    obtainable={
        entity.entity_id:entity
        for entity in projection.entities
        if entity.entity_type=="OBTAINABLE_OBJECT"
    }
    assert len(obtainable)==2,obtainable
    assert {entity.display_name for entity in obtainable.values()}=={"TEST_SEAL","12345"},obtainable
    assert all(
        entity.metadata["identity_status"]=="SOURCE_LITERAL"
        for entity in obtainable.values()
    ),obtainable
    assert not any(
        entity.display_name=="500"
        for entity in obtainable.values()
    ),obtainable

    with tempfile.TemporaryDirectory() as td:
        con=graph.init_db(Path(td)/"reward-obtainability.db")
        persist_scripted_behavior(con,projection)

        for edge in reward_edges:
            closure=build_obtainability_closure(
                con,
                edge.source_node,
                relationships={"REWARDED_BY"},
            )
            assert len(closure["edges"])==1,closure
            row=closure["edges"][0]
            assert row["relationship"]=="REWARDED_BY",row
            assert row["target_node"]==edge.target_node,row
            assert row["requirement_group"]["operator"]=="OR",row
        con.close()

    print("scripted reward obtainability bridge regression: PASS")


if __name__=="__main__":
    main()
