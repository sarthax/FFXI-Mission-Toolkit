"""Built-in reusable framework and system-package plugin metadata.

These are contracts/capabilities, not claims that the analyzers are complete.
"""
from __future__ import annotations

from .base import ContentArchetype, DomainPlugin, DomainPluginSpec, PluginContext
from .registry import DomainPluginRegistry


ARCHETYPES=(
    ContentArchetype(
        "simple_turnin","Simple NPC / Turn-in",
        "Small-scope NPC/event/item/key-item/reward content.",
        ("npc_script","dialog_event","item_gate","reward_logic"),
        ("event_flow","reward","state"),
    ),
    ContentArchetype(
        "multizone_progression","Multi-zone Hunt / Progression",
        "Staged progression across zones, NPC gates, kills, variables and key items.",
        ("mission_script","zone_script","npc_script","mob_script","state_logic"),
        ("stage_flow","zone_coverage","kill_conditions","state"),
    ),
    ContentArchetype(
        "battlefield_instance","Battlefield Instance",
        "Arena/battlefield content with registry, entry/exit policy, groups, mobs and rewards.",
        ("registry","entry_policy","battlefield_script","membership","mob_script","reward_logic","mission_hook","exit_policy"),
        ("registry_identity","entity_coverage","entry","win_loss","reward","policy"),
    ),
    ContentArchetype(
        "multistage_mission","Multi-stage Mission / Quest",
        "State-machine content spanning multiple stages and optional embedded sub-frameworks.",
        ("mission_script","stage_logic","npc_script","zone_script","reward_logic"),
        ("stage_flow","state","zone_coverage","completion"),
    ),
    ContentArchetype(
        "minigame","Minigame / Puzzle",
        "Temporary state, timers, interactables, scoring and win/loss logic.",
        ("minigame_script","timer_logic","interaction_logic","score_logic"),
        ("timer","interaction","win_loss","reset"),
    ),
    ContentArchetype(
        "system_container","Repeatable / System Container",
        "Reusable progression system with entry resources, rank/points/currency/rewards and child features.",
        ("system_global","entry_resource","progression_logic","reward_table","child_feature"),
        ("entry","progression","currency","reward","child_coverage"),
    ),
)


class MetadataPlugin(DomainPlugin):
    """Declarative plugin used until a framework gains dedicated analyzers."""

    def identify(self, context: PluginContext) -> bool:
        requested=context.metadata.get("plugin_ids",())
        systems={str(x).lower() for x in context.metadata.get("systems",())}
        return self.spec.plugin_id in requested or any(s.lower() in systems for s in self.spec.systems)


class BattlefieldFamilyPlugin(MetadataPlugin):
    spec=DomainPluginSpec(
        plugin_id="framework.battlefield",
        name="Reusable Battlefield Family",
        version="0.1",
        archetypes=("battlefield_instance",),
        systems=("BCNM","KSNM","ISNM","ENM","MISSION_BATTLEFIELD"),
        semantic_roles=(
            "registry","entry_policy","battlefield_script","membership",
            "mob_script","reward_logic","mission_hook","exit_policy",
        ),
        capabilities=("registry_identity","entity_coverage","policy_mapping","win_loss","reward"),
        metadata={
            "representation_profiles":("legacy_sql_plus_zone_lua","modular_lua_plus_data_registry"),
            "intended_reuse":("BCNM","KSNM","ISNM","ENM","mission battlefields"),
        },
    )


class QuestMissionPlugin(MetadataPlugin):
    spec=DomainPluginSpec(
        plugin_id="framework.quest_mission",
        name="Quest / Mission State Machine",
        version="0.1",
        archetypes=("simple_turnin","multistage_mission"),
        systems=("QUEST","MISSION"),
        capabilities=("state_machine","event_flow","completion","reward"),
    )


class MultiZoneProgressionPlugin(MetadataPlugin):
    spec=DomainPluginSpec(
        plugin_id="framework.multizone_progression",
        name="Multi-zone Progression / Hunt",
        version="0.1",
        archetypes=("multizone_progression",),
        capabilities=("zone_coverage","npc_gates","kill_conditions","state_machine"),
    )


class MinigamePlugin(MetadataPlugin):
    spec=DomainPluginSpec(
        plugin_id="framework.minigame",
        name="Minigame / Puzzle",
        version="0.1",
        archetypes=("minigame",),
        capabilities=("timers","interactions","scoring","win_loss","reset"),
    )


class AssaultPlugin(MetadataPlugin):
    spec=DomainPluginSpec(
        plugin_id="system.assault",
        name="Assault System Package",
        version="0.1",
        archetypes=("system_container","battlefield_instance","multistage_mission"),
        systems=("ASSAULT",),
        framework_dependencies=("framework.battlefield","framework.quest_mission"),
        semantic_roles=("assault_mission","assault_rank","assault_points","tags","appraisal","lockbox"),
        capabilities=("entry_tags","rank_progression","ap_rewards","appraisal","mission_objectives"),
        metadata={"scope":"bounded 50+ Assault mission family"},
    )


def default_registry() -> DomainPluginRegistry:
    registry=DomainPluginRegistry()
    for archetype in ARCHETYPES:
        registry.register_archetype(archetype)
    for plugin in (
        BattlefieldFamilyPlugin(),
        QuestMissionPlugin(),
        MultiZoneProgressionPlugin(),
        MinigamePlugin(),
        AssaultPlugin(),
    ):
        registry.register(plugin)
    registry.validate_composition()
    return registry
