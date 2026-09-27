"""Built-in reusable framework and system-package plugin metadata.

These are contracts/capabilities, not claims that the analyzers are complete.
"""
from __future__ import annotations

from .base import ContentArchetype, DomainPlugin, DomainPluginSpec, PluginContext, PluginFinding
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
    def generate_migration_rules(self, context: PluginContext) -> tuple[PluginFinding, ...]:
        if not self.identify(context):
            return ()
        capability_status=context.metadata.get("capability_coverage_status")
        entity_aligned=context.metadata.get("entity_coverage_aligned")
        if capability_status=="CAPABILITIES_ALIGNED" and entity_aligned is True:
            return (PluginFinding(
                plugin_id=self.spec.plugin_id,
                subject_id=context.feature_id,
                finding_type="MIGRATION_RULE",
                status="COMPATIBLE",
                message="Battlefield behavior and entity coverage are aligned; representation drift alone does not require migration.",
                metadata={"proposed_action":"NOT_REQUIRED","safe_auto":True},
            ),)
        findings=[PluginFinding(
            plugin_id=self.spec.plugin_id,
            subject_id=context.feature_id,
            finding_type="MIGRATION_RULE",
            status="MANUAL_REQUIRED",
            message="Battlefield semantic coverage is not fully aligned; keep migration decisions under manual review until a verified rule resolves the gap.",
            metadata={"proposed_action":"MANUAL_REVIEW","safe_auto":False},
        )]
        if (context.source_family or "").upper()=="LSB" and (context.target_family or "").upper()=="DSP":
            findings.extend((
                PluginFinding(
                    plugin_id=self.spec.plugin_id,
                    subject_id=context.feature_id,
                    finding_type="MIGRATION_RESHAPE",
                    status="MANUAL_REQUIRED",
                    message="Map modern battlefield policy fields into the legacy DSP registry representation.",
                    metadata={
                        "proposed_action":"RESHAPE",
                        "source_roles":["battlefield_script","level_cap_policy"],
                        "target_roles":["registry_sql"],
                        "reshape":"BATTLEFIELD_POLICY_TO_REGISTRY_SQL",
                        "safe_auto":False,
                    },
                ),
                PluginFinding(
                    plugin_id=self.spec.plugin_id,
                    subject_id=context.feature_id,
                    finding_type="MIGRATION_RESHAPE",
                    status="MANUAL_REQUIRED",
                    message="Map modern group/entity registry membership into legacy DSP battlefield membership rows.",
                    metadata={
                        "proposed_action":"RESHAPE",
                        "source_roles":["battlefield_script","entity_registry"],
                        "target_roles":["battlefield_membership"],
                        "reshape":"BATTLEFIELD_GROUPS_TO_MEMBERSHIP_SQL",
                        "safe_auto":False,
                    },
                ),
                PluginFinding(
                    plugin_id=self.spec.plugin_id,
                    subject_id=context.feature_id,
                    finding_type="MIGRATION_RESHAPE",
                    status="MANUAL_REQUIRED",
                    message="Translate modern mission/battlefield framework orchestration into legacy DSP callback Lua.",
                    metadata={
                        "proposed_action":"RESHAPE",
                        "source_roles":["mission_script","battlefield_script"],
                        "target_roles":["battlefield_script"],
                        "reshape":"FRAMEWORK_ORCHESTRATION_TO_DSP_CALLBACKS",
                        "safe_auto":False,
                    },
                ),
            ))
        return tuple(findings)

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
            "legacy_dsp_callback_surface":(
                "onBattlefieldTick",
                "onBattlefieldRegister",
                "onBattlefieldEnter",
                "onBattlefieldLeave",
                "onEventUpdate",
                "onEventFinish",
            ),
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
