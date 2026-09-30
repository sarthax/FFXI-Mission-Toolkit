#!/usr/bin/env python3
"""Regression for unified acquisition catalog over audited producer families."""
from __future__ import annotations

from workbench.adapters.servers.base import LogicalRecord
from workbench.core.services.acquisition_catalog import (
    build_acquisition_catalog,
    verified_external_item_ids,
)
from workbench.migrations.crafting_closure import build_crafting_closure
from workbench.plugins.domain.scripted_behavior import (
    BehaviorEffect,
    BehaviorRule,
    ScriptedBehaviorMap,
    project_scripted_behavior,
)


def rec(logical_type, identity, fields, source_table=None):
    return LogicalRecord(
        logical_type=logical_type,
        identity=tuple(identity),
        fields=dict(fields),
        source_family="LSB",
        source_table=source_table or logical_type,
    )


def main():
    drop = rec(
        "mob_drops",
        (("drop_id", 77), ("drop_type", 0), ("group_id", 1), ("item_id", 936)),
        {
            "drop_id": 77,
            "drop_type": 0,
            "group_id": 1,
            "group_rate": 1000,
            "item_id": 936,
            "item_rate": 250,
        },
        "mob_droplist",
    )
    craft = rec(
        "synth_recipes",
        (("recipe_id", 62531),),
        {
            "recipe_id": 62531,
            "alchemy": 56,
            "crystal_item_id": 4096,
            "ingredient_1": 936,
            "ingredient_2": 1888,
            "result_item_id": 1887,
            "result_qty": 1,
            "result_name": "Glass Sheet",
        },
        "synth_recipes",
    )
    synergy = rec(
        "synergy_recipes",
        (("recipe_id", 99),),
        {
            "recipe_id": 99,
            "primary_skill": 0,
            "primary_rank": 4,
            "ingredient_1": 1887,
            "result_item_id": 9999,
            "result_qty": 1,
            "result_name": "Synergy Test",
        },
        "synergy_recipes",
    )

    behavior = ScriptedBehaviorMap(
        map_id="behavior-map:reward-catalog",
        feature_id="feature:reward-catalog",
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
                    BehaviorEffect("GRANT_ITEM", "player", "1888"),
                    BehaviorEffect("GRANT_KEY_ITEM", "player", "TEST_SEAL"),
                ),
                confidence="VERIFIED",
                implementation_status="PRESENT",
                metadata={"source_path": "scripts/zones/Test/npcs/Reward_NPC.lua"},
            ),
        ),
    )
    projection = project_scripted_behavior(
        behavior,
        evidence_source="LSB_LUA",
        evidence_location="scripts/zones/Test/npcs/Reward_NPC.lua",
    )

    catalog = build_acquisition_catalog(
        logical_records=(drop, craft, synergy),
        scripted_projections=(projection,),
    )
    assert catalog["schema_version"] == "acquisition-catalog/v1", catalog
    assert catalog["unsupported_until_profiled"] == ["SHOP"], catalog
    assert catalog["counts"] == {
        "DROP_POOL": 1,
        "SCRIPTED_REWARD": 2,
        "SYNERGY": 1,
        "SYNTHESIS": 1,
    }, catalog

    by_subject = {
        (row["subject_kind"], row["subject_id"]): row
        for row in catalog["subjects"]
    }
    assert by_subject[("ITEM", "936")]["acquisition_types"] == ["DROP_POOL"]
    assert set(by_subject[("ITEM", "1888")]["acquisition_types"]) == {"SCRIPTED_REWARD"}
    assert by_subject[("KEY_ITEM", "TEST_SEAL")]["acquisition_types"] == ["SCRIPTED_REWARD"]
    assert by_subject[("ITEM", "1887")]["acquisition_types"] == ["SYNTHESIS"]
    assert by_subject[("ITEM", "9999")]["acquisition_types"] == ["SYNERGY"]

    drop_path = by_subject[("ITEM", "936")]["paths"][0]
    assert drop_path["metadata"]["item_rate"] == 250
    assert drop_path["metadata"]["drop_id"] == 77

    craft_path = by_subject[("ITEM", "1887")]["paths"][0]
    assert craft_path["metadata"]["ingredient_item_ids"] == ["936", "1888"]
    assert craft_path["metadata"]["craft_levels"]["alchemy"] == 56

    reward_path = by_subject[("ITEM", "1888")]["paths"][0]
    assert reward_path["confidence"] == "VERIFIED"
    assert reward_path["metadata"]["source_effect"] == "GRANT_ITEM"
    assert reward_path["evidence_ids"], reward_path

    external = verified_external_item_ids(catalog)
    assert external == {936, 1888}, external

    closure = build_crafting_closure(
        (craft,),
        1887,
        known_obtainable_items={4096, *external},
    )
    assert closure["status"] == "OBTAINABLE", closure
    assert closure["root"]["satisfied_by"] == "CRAFTING", closure

    print("acquisition catalog self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
