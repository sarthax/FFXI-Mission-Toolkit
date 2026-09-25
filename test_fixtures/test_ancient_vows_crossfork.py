#!/usr/bin/env python3
"""Pinned public-repository flagship E2E: CoP 2-5 Ancient Vows, LSB -> legacy DSP."""
from __future__ import annotations
import json,sys
from pathlib import Path
from dataclasses import asdict

from workbench.adapters.servers import DSPAdapter, LSBAdapter
from workbench.adapters.servers.logical import compare_records
from workbench.adapters.servers.sql_extract import extract_logical_records
from workbench.adapters.servers.entity_symbols import yaml_mob_template_spawns
from workbench.migrations.feature_surface import FeatureSurface, SurfaceArtifact, SurfaceCapability, compare_feature_surfaces
from workbench.migrations.package_plan import build_package_plan
from workbench.migrations.feature_surface_plan import plan_feature_surface, bind_surface_actions_to_artifacts
from workbench.migrations.package_manifest import build_package_manifest, attach_generated_outputs
from workbench.migrations.package_validation import build_validation_package
from workbench.migrations.package_assembly import assemble_migration_package
from workbench.migrations.package_cohesion import verify_package_cohesion
from workbench.migrations.package_apply_gate import assess_apply_readiness
from workbench.migrations.package_preflight import preflight_manifest_artifacts
from workbench.migrations.backend_probe import probe_lsb_to_dsp_lua
from workbench.migrations.backend_probe_plan import plan_lsb_dsp_lua_probe
from workbench.core import graph
from workbench.core.schema import Artifact, CapabilityRequirement, DependencyEdge, Feature, MigrationAction
from workbench.core.services.feature_surface_graph import persist_feature_surface
from workbench.core.services.feature_surface_validation import build_feature_surface_validation
from workbench.plugins.domain import PluginContext, default_registry, propose_dsp_battlefield_membership, propose_dsp_battlefield_policy, analyze_dsp_battlefield_callbacks, plan_dsp_battlefield_callback_adaptation, generated_outputs_for_dsp_battlefield, extract_lsb_battlefield_policy, extract_lsb_mission_level_cap, extract_lsb_battlefield_mob_groups, validate_dsp_battlefield_proposals, plan_dsp_battlefield_representation, battlefield_representation_finding, apply_plugin_reshape_findings, MissionRequirement, MissionRepresentation, plan_mission_representation, MissionPatchProposal, generated_mission_patch_proposals
from feature_checker import resolve_feature, check_feature
import tempfile
import backport_binding_audit as bba
import backport_lua_sanity_check as blsc

FEATURE_NAME="ancient_vows"
BATTLEFIELD_ID=960
ZONE_ID=31
MAMMET_TEMPLATE="Mammet-19_Epsilon"
EXPECTED_MAMMETS=set(range(16904193,16904202))
EXPECTED_MAMMET_GROUPS=(
    (16904193,16904194,16904195),
    (16904196,16904197,16904198),
    (16904199,16904200,16904201),
)

def one(records,pred):
    matches=[r for r in records if pred(r)]
    assert len(matches)==1,matches
    return matches[0]

def main():
    if len(sys.argv)!=3:
        raise SystemExit("usage: test_ancient_vows_crossfork.py <lsb-root> <dsp-root>")
    lsb_root=Path(sys.argv[1]).resolve()
    dsp_root=Path(sys.argv[2]).resolve()
    lsb=LSBAdapter(lsb_root); dsp=DSPAdapter(dsp_root)
    assert lsb.probe().compatible
    assert dsp.probe().compatible

    plugin_registry=default_registry()
    plugin_context=PluginContext(
        feature_id="feature:cop:ancient_vows",
        source_family="LSB",
        target_family="DSP",
        source_snapshot_id="lsb:3747feee0e38",
        target_snapshot_id="dsp:ee1f489efbde",
        metadata={"systems":["MISSION_BATTLEFIELD","MISSION"]},
    )
    active_plugins=[
        plugin.spec.plugin_id for plugin in plugin_registry.plugins()
        if plugin.identify(plugin_context)
    ]
    assert "framework.battlefield" in active_plugins,active_plugins
    assert "framework.quest_mission" in active_plugins,active_plugins
    assert "system.assault" not in active_plugins,active_plugins

    source_registry=one(
        extract_logical_records(lsb,"battlefields"),
        lambda r:r.fields["battlefield_id"]==BATTLEFIELD_ID,
    )
    target_registry=one(
        extract_logical_records(dsp,"battlefields"),
        lambda r:r.fields["battlefield_id"]==BATTLEFIELD_ID,
    )
    assert source_registry.fields["name"]==target_registry.fields["name"]==FEATURE_NAME
    assert source_registry.fields["zone_id"]==target_registry.fields["zone_id"]==ZONE_ID
    assert source_registry.identity==target_registry.identity

    registry_diff=compare_records(source_registry,target_registry)
    registry_fields={d.field:d.status for d in registry_diff.differences}
    # Expected representation drift: DSP stores battlefield policy in SQL while
    # LSB implements those fields in Lua/module policy.
    for field in ("time_limit","level_cap","party_size","loot_drop_id","rules","is_mission"):
        assert registry_fields.get(field)=="MISSING_FIELD_VALUE",(field,registry_diff)

    target_members=extract_logical_records(dsp,"battlefield_members")
    target_mammets={
        r.fields["entity_id"] for r in target_members
        if r.fields["battlefield_id"]==BATTLEFIELD_ID
    }
    assert target_mammets==EXPECTED_MAMMETS,target_mammets
    source_mammets=set(yaml_mob_template_spawns(
        lsb_root/"data"/"zones"/"monarch_linn"/"mobs.yaml",
        MAMMET_TEMPLATE,
    ))
    assert EXPECTED_MAMMETS <= source_mammets,source_mammets
    assert target_mammets <= source_mammets

    surfaces={
        "lsb_mission":lsb_root/"scripts"/"missions"/"cop"/"2_5_Ancient_Vows.lua",
        "lsb_battlefield":lsb_root/"scripts"/"battlefields"/"Monarch_Linn"/"ancient_vows.lua",
        "lsb_mammet":lsb_root/"scripts"/"zones"/"Monarch_Linn"/"mobs"/"Mammet-19_Epsilon.lua",
        "lsb_level_cap_policy":lsb_root/"modules"/"era"/"lua"/"battlefields"/"mission_level_caps.lua",
        "dsp_battlefield":dsp_root/"scripts"/"zones"/"Monarch_Linn"/"bcnms"/"ancient_vows.lua",
        "dsp_mammet":dsp_root/"scripts"/"zones"/"Monarch_Linn"/"mobs"/"Mammet-19_Epsilon.lua",
        "dsp_justinius":dsp_root/"scripts"/"zones"/"Tavnazian_Safehold"/"npcs"/"Justinius.lua",
        "dsp_misareaux_gate":dsp_root/"scripts"/"zones"/"Misareaux_Coast"/"npcs"/"_0p2.lua",
        "dsp_riverne_zone":dsp_root/"scripts"/"zones"/"Riverne-Site_A01"/"Zone.lua",
    }
    missing=[name for name,path in surfaces.items() if not path.exists()]
    assert not missing,missing

    source_mission=surfaces["lsb_mission"].read_text(encoding="utf-8",errors="ignore")
    source_battlefield=surfaces["lsb_battlefield"].read_text(encoding="utf-8",errors="ignore")
    source_group_surface=extract_lsb_battlefield_mob_groups(
        source_battlefield,
        {"monarchLinnID.mob.MAMMET_19_EPSILON":min(source_mammets)},
    )
    assert not source_group_surface.unresolved_expressions,source_group_surface
    assert source_group_surface.groups==EXPECTED_MAMMET_GROUPS,source_group_surface
    membership_proposal=propose_dsp_battlefield_membership(
        BATTLEFIELD_ID,
        source_group_surface.groups,
        target_members,
    )
    assert membership_proposal.status=="EQUIVALENT",membership_proposal
    assert not membership_proposal.insert_sql,membership_proposal
    lsb_lua_probes={
        "mission":probe_lsb_to_dsp_lua(source_mission),
        "battlefield":probe_lsb_to_dsp_lua(source_battlefield),
    }
    framework_methods={
        method
        for probe in lsb_lua_probes.values()
        if probe.method_surface is not None
        for method in probe.method_surface.framework_methods
    }
    binding_candidate_methods={
        method
        for probe in lsb_lua_probes.values()
        if probe.method_surface is not None
        for method in probe.method_surface.binding_candidate_methods
    }
    probe_actions={
        name:plan_lsb_dsp_lua_probe(
            probe,
            "migration:cop:ancient-vows:probe",
            artifact_id=f"artifact:ancient-vows:{name}",
            source_path=str(surfaces["lsb_mission" if name=="mission" else "lsb_battlefield"].relative_to(lsb_root)),
        )
        for name,probe in lsb_lua_probes.items()
    }
    assert all(action.metadata["adaptation_type"]=="STRUCTURAL_FRAMEWORK_ADAPTATION" for action in probe_actions.values()),probe_actions

    with tempfile.TemporaryDirectory() as probe_td:
        probe_root=Path(probe_td)
        for name,probe in lsb_lua_probes.items():
            (probe_root/f"{name}.lua").write_text(probe.converted_text,encoding="utf-8")
        binding_probe=bba.audit_package(
            probe_root,
            dsp_root,
            "old_dsp_reference",
            ignore_methods=framework_methods,
        )
        sanity_probe=blsc.check_package(probe_root)
    assert not binding_probe["missing"],binding_probe
    target_battlefield=surfaces["dsp_battlefield"].read_text(encoding="utf-8",errors="ignore")
    callback_profile=plugin_registry.get("framework.battlefield").spec.metadata["legacy_dsp_callback_surface"]
    callback_surface=analyze_dsp_battlefield_callbacks(target_battlefield,callback_profile)
    assert callback_surface.status=="COVERAGE_ALIGNED",callback_surface
    assert not callback_surface.missing_callbacks,callback_surface
    callback_plan=plan_dsp_battlefield_callback_adaptation(
        callback_surface,
        source_framework_methods=framework_methods,
    )
    assert callback_plan.status=="COVERAGE_ALIGNED",callback_plan
    assert not callback_plan.missing_callbacks,callback_plan
    assert not callback_plan.safe_to_generate,callback_plan
    source_mob=surfaces["lsb_mammet"].read_text(encoding="utf-8",errors="ignore")
    target_mob=surfaces["dsp_mammet"].read_text(encoding="utf-8",errors="ignore")
    source_level_cap=surfaces["lsb_level_cap_policy"].read_text(encoding="utf-8",errors="ignore")
    target_justinius=surfaces["dsp_justinius"].read_text(encoding="utf-8",errors="ignore")
    target_misareaux_gate=surfaces["dsp_misareaux_gate"].read_text(encoding="utf-8",errors="ignore")
    target_riverne_zone=surfaces["dsp_riverne_zone"].read_text(encoding="utf-8",errors="ignore")

    mission_requirements=(
        MissionRequirement(
            "justinius_128",
            "Ancient Vows exposes Justinius event 128 in Tavnazian Safehold.",
            (str(surfaces["lsb_mission"].relative_to(lsb_root)),),
        ),
        MissionRequirement(
            "misareaux_0_to_1",
            "Dilapidated Gate event 6 advances Promathia mission status 0 to 1.",
            (str(surfaces["lsb_mission"].relative_to(lsb_root)),),
        ),
        MissionRequirement(
            "riverne_1_to_2",
            "Entering Riverne Site #A01 at mission status 1 runs event 100 and advances status to 2.",
            (str(surfaces["lsb_mission"].relative_to(lsb_root)),),
        ),
        MissionRequirement(
            "monarch_completion",
            "Winning Ancient Vows at mission status 2 completes the mission and advances to The Call of the Wyrmking.",
            (str(surfaces["lsb_mission"].relative_to(lsb_root)),),
        ),
    )
    mission_representations=[]
    if (
        "ANCIENT_VOWS" in target_justinius
        and "startEvent(128)" in target_justinius
    ):
        mission_representations.append(MissionRepresentation(
            "justinius_128","VERIFIED",
            (str(surfaces["dsp_justinius"].relative_to(dsp_root)),),
        ))
    if (
        "ANCIENT_VOWS" in target_misareaux_gate
        and "startEvent(6)" in target_misareaux_gate
        and 'setCharVar("PromathiaStatus",1)' in target_misareaux_gate
    ):
        mission_representations.append(MissionRepresentation(
            "misareaux_0_to_1","VERIFIED",
            (str(surfaces["dsp_misareaux_gate"].relative_to(dsp_root)),),
        ))
    if (
        "ANCIENT_VOWS" in target_riverne_zone
        and "100" in target_riverne_zone
        and 'setCharVar("PromathiaStatus",2)' in target_riverne_zone
    ):
        mission_representations.append(MissionRepresentation(
            "riverne_1_to_2","VERIFIED",
            (str(surfaces["dsp_riverne_zone"].relative_to(dsp_root)),),
        ))
    if (
        "completeMission(COP, dsp.mission.id.cop.ANCIENT_VOWS)" in target_battlefield
        and "THE_CALL_OF_THE_WYRMKING" in target_battlefield
    ):
        mission_representations.append(MissionRepresentation(
            "monarch_completion","VERIFIED",
            (str(surfaces["dsp_battlefield"].relative_to(dsp_root)),),
        ))
    mission_representation_plan=plan_mission_representation(
        mission_requirements,
        mission_representations,
    )
    assert mission_representation_plan.status=="MANUAL_REQUIRED",mission_representation_plan
    assert set(mission_representation_plan.missing_requirement_ids)=={
        "justinius_128",
        "riverne_1_to_2",
    },mission_representation_plan

    mission_patch_outputs=generated_mission_patch_proposals(
        mission_representation_plan,
        (
            MissionPatchProposal(
                "justinius_128",
                "scripts/zones/Tavnazian_Safehold/npcs/Justinius.lua",
                """-- REVIEW PROPOSAL: add an Ancient Vows branch before the default Justinius event.
elseif (player:getCurrentMission(COP) == dsp.mission.id.cop.ANCIENT_VOWS) then
    player:startEvent(128);
""",
                "LSB Ancient Vows replaces Justinius' default interaction with event 128 while this mission is active.",
            ),
            MissionPatchProposal(
                "riverne_1_to_2",
                "scripts/zones/Riverne-Site_A01/Zone.lua",
                """-- REVIEW PROPOSAL: Riverne Ancient Vows progression.
-- Ensure scripts/globals/missions is required by the target zone script.
-- In onZoneIn(player, prevZone), set cs = 100 when:
--   player:getCurrentMission(COP) == dsp.mission.id.cop.ANCIENT_VOWS
--   and player:getCharVar("PromathiaStatus") == 1
-- In onEventFinish(player, csid, option), when csid == 100:
--   player:setCharVar("PromathiaStatus", 2)
""",
                "LSB advances Ancient Vows from mission status 1 to 2 on Riverne Site #A01 event 100; the pinned DSP zone script has no equivalent progression.",
            ),
        ),
    )
    assert len(mission_patch_outputs)==2,mission_patch_outputs
    assert all(output.metadata.get("proposal_only") is True for output in mission_patch_outputs),mission_patch_outputs
    source_policy=extract_lsb_battlefield_policy(source_battlefield)
    era_level_cap=extract_lsb_mission_level_cap(source_level_cap,"ANCIENT_VOWS")
    assert source_policy.resolved_fields["time_limit"]==1800,source_policy
    assert source_policy.resolved_fields["party_size"]==6,source_policy
    assert source_policy.resolved_fields["is_mission"] is True,source_policy
    assert source_policy.unresolved_fields.get("level_cap")=="xi.settings.main.MAX_LEVEL",source_policy
    assert era_level_cap==40,era_level_cap
    desired_policy=dict(source_policy.resolved_fields)
    desired_policy["level_cap"]=era_level_cap
    policy_proposal=propose_dsp_battlefield_policy(
        BATTLEFIELD_ID,
        desired_policy,
        target_registry,
    )
    assert policy_proposal.status=="EQUIVALENT",policy_proposal
    assert policy_proposal.update_sql is None,policy_proposal
    representation_plan=plan_dsp_battlefield_representation(
        membership_proposal,
        policy_proposal,
        callback_plan,
    )
    assert representation_plan.status=="READY",representation_plan
    assert representation_plan.callback_status=="NOT_REQUIRED",representation_plan
    assert not representation_plan.manual_surfaces,representation_plan
    reshape_finding=battlefield_representation_finding(
        "feature:cop:ancient_vows",
        representation_plan,
    )

    generated_dsp_outputs=generated_outputs_for_dsp_battlefield(
        membership_proposal,
        policy_proposal,
    )
    assert not generated_dsp_outputs,generated_dsp_outputs
    package_generated_outputs=generated_dsp_outputs+mission_patch_outputs
    generated_sql_validations=validate_dsp_battlefield_proposals(
        membership_proposal,
        policy_proposal,
    )
    assert generated_sql_validations,generated_sql_validations
    assert all(result.status=="NOT_REQUIRED" for result in generated_sql_validations),generated_sql_validations

    source_surface=FeatureSurface(
        feature_id="feature:cop:ancient_vows",
        family="LSB",
        artifacts=(
            SurfaceArtifact("registry_sql","sql/bcnm_info.sql","SQL"),
            SurfaceArtifact("mission_script",str(surfaces["lsb_mission"].relative_to(lsb_root)),"LUA"),
            SurfaceArtifact("battlefield_script",str(surfaces["lsb_battlefield"].relative_to(lsb_root)),"LUA"),
            SurfaceArtifact("mob_script",str(surfaces["lsb_mammet"].relative_to(lsb_root)),"LUA"),
            SurfaceArtifact("level_cap_policy",str(surfaces["lsb_level_cap_policy"].relative_to(lsb_root)),"LUA"),
            SurfaceArtifact("entity_registry","data/zones/monarch_linn/mobs.yaml","YAML"),
        ),
        entity_ids=tuple(sorted(EXPECTED_MAMMETS)),
        capabilities=(
            SurfaceCapability("mission_completion",evidence=(str(surfaces["lsb_mission"].relative_to(lsb_root)),)),
            SurfaceCapability("battlefield_entity_membership",evidence=(str(surfaces["lsb_battlefield"].relative_to(lsb_root)),"data/zones/monarch_linn/mobs.yaml")),
            SurfaceCapability("era_level_cap_40",evidence=(str(surfaces["lsb_level_cap_policy"].relative_to(lsb_root)),)),
            SurfaceCapability("xp_reward_1000",evidence=(str(surfaces["lsb_battlefield"].relative_to(lsb_root)),)),
            SurfaceCapability("title_tavnazian_traveler",evidence=(str(surfaces["lsb_battlefield"].relative_to(lsb_root)),)),
            SurfaceCapability("mammet_form_change",evidence=(str(surfaces["lsb_mammet"].relative_to(lsb_root)),)),
        ),
    )
    target_surface=FeatureSurface(
        feature_id="feature:cop:ancient_vows",
        family="DSP",
        artifacts=(
            SurfaceArtifact("registry_sql","sql/bcnm_info.sql","SQL"),
            SurfaceArtifact("battlefield_script",str(surfaces["dsp_battlefield"].relative_to(dsp_root)),"LUA"),
            SurfaceArtifact("mob_script",str(surfaces["dsp_mammet"].relative_to(dsp_root)),"LUA"),
            SurfaceArtifact("battlefield_membership","sql/bcnm_battlefield.sql","SQL"),
        ),
        entity_ids=tuple(sorted(target_mammets)),
        capabilities=(
            SurfaceCapability("mission_completion",evidence=(str(surfaces["dsp_battlefield"].relative_to(dsp_root)),)),
            SurfaceCapability("battlefield_entity_membership",evidence=("sql/bcnm_battlefield.sql",)),
            SurfaceCapability("era_level_cap_40",evidence=("sql/bcnm_info.sql",)),
            SurfaceCapability("xp_reward_1000",evidence=(str(surfaces["dsp_battlefield"].relative_to(dsp_root)),)),
            SurfaceCapability("title_tavnazian_traveler",evidence=(str(surfaces["dsp_battlefield"].relative_to(dsp_root)),)),
            SurfaceCapability("mammet_form_change",evidence=(str(surfaces["dsp_mammet"].relative_to(dsp_root)),)),
        ),
    )
    surface_comparison=compare_feature_surfaces(source_surface,target_surface)
    assert surface_comparison.status=="REPRESENTATION_DRIFT",surface_comparison

    semantic_actions=plan_feature_surface(source_surface,surface_comparison,"migration:cop:ancient-vows:semantic")
    semantic_by_role={action.metadata.get("source_role"):action for action in semantic_actions if action.metadata.get("source_role")}
    assert semantic_by_role["registry_sql"].action=="NOT_REQUIRED",semantic_actions
    assert semantic_by_role["mission_script"].action=="MANUAL_REVIEW",semantic_actions
    assert semantic_by_role["battlefield_script"].action=="NOT_REQUIRED",semantic_actions
    refined_actions=apply_plugin_reshape_findings(semantic_actions,(reshape_finding,))
    assert any(
        action.metadata.get("source_role")=="battlefield_script"
        and action.metadata.get("plugin_reshape_applied") is True
        for action in refined_actions
    ),refined_actions
    assert any(
        action.metadata.get("source_role")=="mission_script"
        and action.metadata.get("plugin_reshape_applied") is not True
        for action in refined_actions
    ),refined_actions
    migration_plugin_context=PluginContext(
        feature_id="feature:cop:ancient_vows",
        source_family="LSB",
        target_family="DSP",
        source_snapshot_id="lsb:3747feee0e38",
        target_snapshot_id="dsp:ee1f489efbde",
        metadata={
            "systems":["MISSION_BATTLEFIELD","MISSION"],
            "capability_coverage_status":surface_comparison.capability_coverage_status,
            "entity_coverage_aligned":not surface_comparison.source_only_entity_ids and not surface_comparison.target_only_entity_ids,
        },
    )
    migration_findings=plugin_registry.migration_findings(migration_plugin_context)
    battlefield_migration_findings=[f for f in migration_findings if f.plugin_id=="framework.battlefield"]
    assert battlefield_migration_findings,battlefield_migration_findings
    assert battlefield_migration_findings[0].metadata["proposed_action"]=="NOT_REQUIRED",battlefield_migration_findings

    package_artifacts=[
        Artifact("artifact:ancient-vows:registry","SQL",path="sql/bcnm_info.sql",feature_id="feature:cop:ancient_vows"),
        Artifact("artifact:ancient-vows:battlefield","LUA",path=str(surfaces["lsb_battlefield"].relative_to(lsb_root)),feature_id="feature:cop:ancient_vows"),
        Artifact("artifact:ancient-vows:mission","LUA",path=str(surfaces["lsb_mission"].relative_to(lsb_root)),feature_id="feature:cop:ancient_vows"),
    ]
    package_actions=bind_surface_actions_to_artifacts(
        refined_actions,
        {
            "registry_sql":"artifact:ancient-vows:registry",
            "battlefield_script":"artifact:ancient-vows:battlefield",
            "mission_script":"artifact:ancient-vows:mission",
        },
    )
    package_dependencies=[
        DependencyEdge("edge:ancient-vows:battlefield-registry","artifact:ancient-vows:battlefield","artifact:ancient-vows:registry","REQUIRES",confidence="VERIFIED"),
        DependencyEdge("edge:ancient-vows:mission-battlefield","artifact:ancient-vows:mission","artifact:ancient-vows:battlefield","REQUIRES",confidence="VERIFIED"),
    ]
    package_plan=build_package_plan(package_actions,package_dependencies)
    package_manifest=build_package_manifest(
        package_plan,
        package_artifacts,
        feature_id="feature:cop:ancient_vows",
        source_snapshot_id="lsb:3747feee0e38",
        target_snapshot_id="dsp:ee1f489efbde",
        source_family="LSB",
        target_family="DSP",
    )
    package_manifest=attach_generated_outputs(package_manifest,package_generated_outputs)
    lua_steps=[
        step for step in package_manifest["execution"]["steps"]
        if step["backend"]=="lua"
    ]
    sql_steps=[
        step for step in package_manifest["execution"]["steps"]
        if step["backend"]=="sql"
    ]
    assert len(lua_steps)==1,lua_steps
    assert lua_steps[0]["artifact_id"]=="artifact:ancient-vows:mission",lua_steps
    assert lua_steps[0]["conversion_status"]=="CONDITIONAL",package_manifest
    assert not sql_steps,package_manifest
    preflighted_manifest,preflight_results=preflight_manifest_artifacts(package_manifest,lsb_root)
    assert preflight_results,preflight_results
    lua_preflight=[result for result in preflight_results if result.path.endswith(".lua")]
    assert len(lua_preflight)==1,lua_preflight
    assert lua_preflight[0].status=="MANUAL_REQUIRED",lua_preflight
    assert all(
        step["conversion_status"]=="CONDITIONAL"
        for step in preflighted_manifest["execution"]["steps"]
        if step["backend"]=="lua"
    ),preflighted_manifest
    validation_package=build_validation_package(preflighted_manifest)
    with tempfile.TemporaryDirectory() as package_td:
        package_root=Path(package_td)/"ancient-vows-package"
        assembled=assemble_migration_package(
            package_manifest,
            lsb_root,
            package_root,
            generated_outputs=package_generated_outputs,
        )
        assert assembled.status=="MANUAL_REQUIRED",assembled
        assert len(assembled.source_result.copied)==1,assembled
        assert len(assembled.source_result.artifacts)==1,assembled
        assert len(assembled.generated_result.records)==2,assembled
        assert assembled.manifest_path.exists(),assembled
        assert assembled.validation_path.exists(),assembled
        assert assembled.source_journal_path.exists(),assembled
        assert assembled.generated_journal_path.exists(),assembled
        cohesion=verify_package_cohesion(package_root)
        assert cohesion.status=="COHERENT",cohesion
        apply_readiness=assess_apply_readiness(package_root)
        assert apply_readiness.status=="MANUAL_REQUIRED",apply_readiness
    assert package_plan.status=="MANUAL_REQUIRED",package_plan
    assert len(package_manifest["execution"]["steps"])==1,package_manifest
    assert package_manifest["execution"]["steps"][0]["artifact_id"]=="artifact:ancient-vows:mission",package_manifest
    assert validation_package["status"]=="MANUAL_REQUIRED",validation_package
    assert not any(check["validation_type"]=="CONVERTER_BACKEND_SUPPORT" for check in validation_package["checks"]),validation_package
    assert any(check["validation_type"]=="CONVERTER_PREFLIGHT_REQUIRED" for check in validation_package["checks"]),validation_package
    assert any(check["validation_type"]=="GENERATED_PROPOSAL_REVIEW" for check in validation_package["checks"]),validation_package
    assert not surface_comparison.source_only_entity_ids,surface_comparison
    assert not surface_comparison.target_only_entity_ids,surface_comparison
    assert surface_comparison.capability_coverage_status=="CAPABILITIES_ALIGNED",surface_comparison
    assert len(surface_comparison.shared_capabilities)==6,surface_comparison

    with tempfile.TemporaryDirectory() as td:
        con=graph.init_db(Path(td)/"ancient_vows.db")
        feature=Feature(
            feature_id="feature:cop:ancient_vows",
            name="Chains of Promathia 2-5: Ancient Vows",
            feature_type="MISSION_BATTLEFIELD",
            domain_id="domain:cop",
            source_snapshot_id="lsb:3747feee0e38",
            target_snapshot_id="dsp:ee1f489efbde",
            status="ANALYZED",
        )
        src_counts=persist_feature_surface(con,source_surface,feature,"lsb:3747feee0e38")
        dst_counts=persist_feature_surface(con,target_surface,feature,"dsp:ee1f489efbde")
        for capability in source_surface.capabilities:
            graph.insert_record(con,CapabilityRequirement(
                requirement_id=f"requirement:cop:ancient_vows:{capability.name}",
                feature_id=feature.feature_id,
                capability_id=f"capability:{feature.feature_id}:{capability.name}",
                required=True,
                status="DISCOVERED",
                notes=["Flagship E2E behavioral requirement; evaluated against the target snapshot observation."],
            ))
        implementation_count=con.execute(
            "SELECT COUNT(*) FROM implementations WHERE feature_id=?",
            (feature.feature_id,),
        ).fetchone()[0]
        uses_id_count=con.execute(
            "SELECT COUNT(*) FROM entity_relationships WHERE source_node=? AND relationship='USES_ID'",
            (feature.feature_id,),
        ).fetchone()[0]
        assert implementation_count==len(source_surface.artifacts)+len(target_surface.artifacts),(implementation_count,src_counts,dst_counts)
        assert uses_id_count==18,uses_id_count
        validation_run,validation_results=build_feature_surface_validation(
            surface_comparison,
            run_id="validation:cop:ancient_vows:surface",
            source_snapshot_id="lsb:3747feee0e38",
            target_snapshot_id="dsp:ee1f489efbde",
        )
        graph.insert_record(con,validation_run)
        for result in validation_results:
            graph.insert_record(con,result)
        validation_status=con.execute(
            "SELECT status FROM validation_results WHERE validation_id=?",
            (validation_results[0].validation_id,),
        ).fetchone()[0]
        assert validation_status=="VERIFIED",validation_status

        resolved_feature=resolve_feature(con,feature.feature_id)
        assert resolved_feature is not None
        checker=check_feature(con,resolved_feature)
        assert checker["dimensions"]["implementation"]=="IMPLEMENTATIONS_VERIFIED",checker
        assert checker["dimensions"]["validation"]=="VALIDATIONS_VERIFIED",checker
        assert checker["dimensions"]["requirements"]=="REQUIRED_CAPABILITIES_VERIFIED",checker
        assert len(checker["requirements"])==6,checker
        assert all(req["observation_selection"]=="TARGET_SNAPSHOT" for req in checker["requirements"]),checker
        assert all(req["observed_status"]=="VERIFIED" for req in checker["requirements"]),checker
        checker_dimensions=checker["dimensions"]
        con.close()

    assert "BattlefieldMission:new" in source_battlefield
    assert "content.groups" in source_battlefield
    assert "mission:complete(player)" in source_mission
    assert "ANCIENT_VOWS,                         40" in source_level_cap
    assert "grantXP = 1000" in source_battlefield
    assert "TAVNAZIAN_TRAVELER" in source_battlefield
    assert "onBattlefieldLeave" in target_battlefield
    assert "completeMission" in target_battlefield
    assert "addExp(1000)" in target_battlefield
    assert "TAVNAZIAN_TRAVELER" in target_battlefield
    assert target_registry.fields["level_cap"]==40,target_registry
    assert "setMagicCastingEnabled" in source_mob
    assert "setAnimationSub" in source_mob
    assert "SetMagicCastingEnabled" in target_mob
    assert "changeForm(mob)" in target_mob

    report={
        "feature":"Chains of Promathia 2-5: Ancient Vows",
        "source_family":"LSB",
        "target_family":"DSP",
        "battlefield_id":BATTLEFIELD_ID,
        "zone_id":ZONE_ID,
        "registry_identity":"EXACT",
        "registry_representation_drift":sorted(registry_fields),
        "mammet_membership":{
            "expected_count":len(EXPECTED_MAMMETS),
            "dsp_membership_reshape_status":membership_proposal.status,
            "source_group_count":len(source_group_surface.groups),
            "generated_insert_count":len(membership_proposal.insert_sql),
            "dsp_policy_reshape_status":policy_proposal.status,
            "source_policy_fields":dict(sorted(desired_policy.items())),
            "generated_policy_update":policy_proposal.update_sql is not None,
            "generated_target_sql_count":len(generated_dsp_outputs),
            "generated_mission_proposal_count":len(mission_patch_outputs),
            "generated_sql_validation_statuses":[result.status for result in generated_sql_validations],
            "dsp_callback_surface_status":callback_surface.status,
            "dsp_callback_adaptation_status":callback_plan.status,
            "missing_callback_count":len(callback_surface.missing_callbacks),
            "source_template_spawn_count":len(source_mammets),
            "target_battlefield_member_count":len(target_mammets),
            "shared_expected_ids":sorted(target_mammets & source_mammets),
        },
        "implementation_surfaces":{
            name:str(path.relative_to(lsb_root if name.startswith("lsb_") else dsp_root))
            for name,path in surfaces.items()
        },
        "feature_surface":{
            "status":surface_comparison.status,
            "shared_roles":list(surface_comparison.shared_roles),
            "source_only_roles":list(surface_comparison.source_only_roles),
            "target_only_roles":list(surface_comparison.target_only_roles),
            "path_drift":list(surface_comparison.role_path_drift),
            "shared_entity_count":len(surface_comparison.shared_entity_ids),
            "capability_coverage_status":surface_comparison.capability_coverage_status,
            "shared_capabilities":list(surface_comparison.shared_capabilities),
        },
        "canonical_graph":{
            "implementation_count":implementation_count,
            "uses_id_edge_count":uses_id_count,
            "snapshot_scoped_entity_refs":True,
            "entity_coverage_validation":validation_status,
            "feature_checker_dimensions":checker_dimensions,
        },
        "migration_package":{
            "plan_status":package_plan.status,
            "step_count":len(package_manifest["execution"]["steps"]),
            "validation_check_count":len(validation_package["checks"]),
            "materialized_artifact_count":1,
            "package_cohesion":"COHERENT",
            "apply_readiness":"MANUAL_REQUIRED",
            "lua_conversion_status":"CONDITIONAL",
            "lua_preflight_status":"MANUAL_REQUIRED",
            "sql_conversion_status":"NOT_QUEUED",
            "battlefield_representation_status":"READY",
            "plugin_reshape_refinement":"VERIFIED",
            "mission_representation_status":mission_representation_plan.status,
            "mission_missing_requirements":list(mission_representation_plan.missing_requirement_ids),
            "package_assembly_status":"MANUAL_REQUIRED",
            "semantic_action_count":len(semantic_actions),
            "semantic_migration_required":any(action.action!="NOT_REQUIRED" for action in semantic_actions),
            "plugin_migration_findings":len(migration_findings),
            "lsb_dsp_lua_probe":{
                "files":{
                    name:{
                        "status":probe.status,
                        "flagged_count":probe.flagged_count,
                        "leftover_count":probe.leftover_count,
                    }
                    for name,probe in lsb_lua_probes.items()
                },
                "framework_methods":sorted(framework_methods),
                "binding_candidate_methods":sorted(binding_candidate_methods),
                "binding_confirmed":len(binding_probe["confirmed"]),
                "binding_missing":len(binding_probe["missing"]),
                "missing_binding_names":[name for name,_reason,_files in binding_probe["missing"]],
                "sanity_syntax_errors":len(sanity_probe["syntax_errors"]),
                "sanity_undeclared_globals":len(sanity_probe["undeclared_globals"]),
                "probe_actions":{
                    name:{
                        "action":action.action,
                        "status":action.status,
                        "adaptation_type":action.metadata["adaptation_type"],
                    }
                    for name,action in probe_actions.items()
                },
            },
        },
        "domain_plugins":{
            "active":active_plugins,
            "archetypes":sorted({
                archetype
                for plugin in plugin_registry.plugins()
                if plugin.spec.plugin_id in active_plugins
                for archetype in plugin.classify_archetypes(plugin_context)
            }),
        },
        "e2e_status":"PUBLIC_CROSS_FORK_FEATURE_SURFACE_VERIFIED",
    }
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
