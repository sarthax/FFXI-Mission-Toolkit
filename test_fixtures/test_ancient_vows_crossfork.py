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
from workbench.migrations.feature_surface_plan import plan_feature_surface
from workbench.migrations.package_manifest import build_package_manifest
from workbench.migrations.package_validation import build_validation_package
from workbench.migrations.package_materialize import materialize_package, write_materialization_journal
from workbench.migrations.backend_probe import probe_lsb_to_dsp_lua
from workbench.migrations.backend_probe_plan import plan_lsb_dsp_lua_probe
from workbench.core import graph
from workbench.core.schema import Artifact, CapabilityRequirement, DependencyEdge, Feature, MigrationAction
from workbench.core.services.feature_surface_graph import persist_feature_surface
from workbench.core.services.feature_surface_validation import build_feature_surface_validation
from workbench.plugins.domain import PluginContext, default_registry, propose_dsp_battlefield_membership, propose_dsp_battlefield_policy
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
    membership_proposal=propose_dsp_battlefield_membership(
        BATTLEFIELD_ID,
        EXPECTED_MAMMET_GROUPS,
        target_members,
    )
    assert membership_proposal.status=="EQUIVALENT",membership_proposal
    assert not membership_proposal.insert_sql,membership_proposal

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
    }
    missing=[name for name,path in surfaces.items() if not path.exists()]
    assert not missing,missing

    source_mission=surfaces["lsb_mission"].read_text(encoding="utf-8",errors="ignore")
    source_battlefield=surfaces["lsb_battlefield"].read_text(encoding="utf-8",errors="ignore")
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
    source_mob=surfaces["lsb_mammet"].read_text(encoding="utf-8",errors="ignore")
    target_mob=surfaces["dsp_mammet"].read_text(encoding="utf-8",errors="ignore")
    source_level_cap=surfaces["lsb_level_cap_policy"].read_text(encoding="utf-8",errors="ignore")
    assert "timeLimit     = utils.minutes(30)" in source_battlefield
    assert "maxPlayers    = 6" in source_battlefield
    assert "isMission     = true" in source_battlefield
    assert "ANCIENT_VOWS,                         40" in source_level_cap
    policy_proposal=propose_dsp_battlefield_policy(
        BATTLEFIELD_ID,
        {
            "time_limit":1800,
            "level_cap":40,
            "party_size":6,
            "is_mission":True,
        },
        target_registry,
    )
    assert policy_proposal.status=="EQUIVALENT",policy_proposal
    assert policy_proposal.update_sql is None,policy_proposal

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
    assert semantic_actions and all(action.action=="NOT_REQUIRED" for action in semantic_actions),semantic_actions
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
    package_actions=[
        MigrationAction("action:ancient-vows:registry","migration:cop:ancient-vows","CONVERT","artifact:ancient-vows:registry","AUTO_MIGRATABLE"),
        MigrationAction("action:ancient-vows:battlefield","migration:cop:ancient-vows","CONVERT","artifact:ancient-vows:battlefield","AUTO_MIGRATABLE"),
        MigrationAction("action:ancient-vows:mission","migration:cop:ancient-vows","CONVERT","artifact:ancient-vows:mission","AUTO_MIGRATABLE"),
    ]
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
    assert all(
        step["conversion_status"]=="UNSUPPORTED"
        for step in package_manifest["execution"]["steps"]
        if step["backend"] in {"lua","sql"}
    ),package_manifest
    validation_package=build_validation_package(package_manifest)
    with tempfile.TemporaryDirectory() as package_td:
        package_root=Path(package_td)/"ancient-vows-package"
        materialized=materialize_package(package_manifest,lsb_root,package_root)
        assert materialized.status=="MATERIALIZED",materialized
        assert len(materialized.copied)==3,materialized
        assert len(materialized.artifacts)==3,materialized
        journal_path=write_materialization_journal(package_root,package_manifest,materialized)
        assert journal_path.exists(),journal_path
    assert package_plan.status=="READY",package_plan
    assert [step["action_id"] for step in package_manifest["execution"]["steps"]]==[
        "action:ancient-vows:registry",
        "action:ancient-vows:battlefield",
        "action:ancient-vows:mission",
    ],package_manifest
    assert validation_package["status"]=="MANUAL_REQUIRED",validation_package
    assert any(check["validation_type"]=="CONVERTER_BACKEND_SUPPORT" for check in validation_package["checks"]),validation_package
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
            "generated_insert_count":len(membership_proposal.insert_sql),
            "dsp_policy_reshape_status":policy_proposal.status,
            "generated_policy_update":policy_proposal.update_sql is not None,
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
            "materialized_artifact_count":3,
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
