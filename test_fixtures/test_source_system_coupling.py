#!/usr/bin/env python3
"""Regression for conservative source-discovered cross-zone lifecycle coupling."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from workbench.analyzers.server.system_coupling import analyze_cross_zone_system_coupling
from workbench.core import graph
from workbench.core.schema import MigrationAction
from workbench.migrations.package_scope import build_dependency_scope


ROOT_SCRIPT="""return {
    onMobEngage = function(mob, target)
        mob:updateEnmity(target)
    end,
}
"""

VARIANT="""return {
    onMobInitialize = function(mob)
        xi.besieged.onMobInitialize(mob)
    end,
    onMobSpawn = function(mob)
        xi.besieged.onMobSpawn(mob)
    end,
    onMobDeath = function(mob)
        xi.besieged.onMobDeath(mob)
    end,
    onMobDespawn = function(mob)
        xi.besieged.onMobDespawn(mob)
    end,
}
"""

NOISE="""return {
    onMobSpawn = function(mob)
        xi.other.onMobSpawn(mob)
    end,
}
"""


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        arr=root/"scripts/zones/Arrapago_Reef/mobs/Medusa.lua"
        alz=root/"scripts/zones/Al_Zahbi/mobs/Medusa.lua"
        bha=root/"scripts/zones/Bhaflau_Thickets/mobs/Medusa.lua"
        noise=root/"scripts/zones/Test_Zone/mobs/Medusa.lua"
        bes=root/"scripts/globals/besieged.lua"
        other=root/"scripts/globals/other.lua"
        for path in (arr,alz,bha,noise,bes,other):
            path.parent.mkdir(parents=True,exist_ok=True)
        arr.write_text(ROOT_SCRIPT,encoding="utf-8")
        alz.write_text(VARIANT,encoding="utf-8")
        bha.write_text(VARIANT,encoding="utf-8")
        noise.write_text(NOISE,encoding="utf-8")
        bes.write_text("return {}\n",encoding="utf-8")
        other.write_text("return {}\n",encoding="utf-8")

        payload=analyze_cross_zone_system_coupling(
            root,arr,source_snapshot_id="lsb:test"
        )
        summary=payload["summary"]
        assert summary["candidate_variant_files"]==3,summary
        assert summary["qualified_systems"]==1,summary
        assert summary["conditional_gate_nodes"]==3,summary
        assert summary["conditional_edges"]==6,summary

        paths={row["path"] for row in payload["artifacts"]}
        assert "scripts/globals/besieged.lua" in paths,paths
        assert "scripts/zones/Al_Zahbi/mobs/Medusa.lua" in paths,paths
        assert "scripts/zones/Bhaflau_Thickets/mobs/Medusa.lua" in paths,paths
        assert "scripts/zones/Test_Zone/mobs/Medusa.lua" not in paths,paths

        root_artifact=next(
            row["artifact_id"] for row in payload["artifacts"]
            if row["path"]=="scripts/zones/Arrapago_Reef/mobs/Medusa.lua"
        )
        system_artifact=next(
            row["artifact_id"] for row in payload["artifacts"]
            if row["path"]=="scripts/globals/besieged.lua"
        )
        assert any(
            row["source_node"]==root_artifact
            and row["target_node"]!=system_artifact
            and row["relationship"]=="HAS_CONDITIONAL_DEPENDENCY"
            for row in payload["edges"]
        ),payload["edges"]
        assert any(
            row["target_node"]==system_artifact
            and row["relationship"]=="CONDITIONALLY_REQUIRES"
            for row in payload["edges"]
        ),payload["edges"]

        out=root/"coupling.json"
        out.write_text(json.dumps(payload),encoding="utf-8")
        db=root/"workbench.db"
        graph.import_json(out,db)
        con=sqlite3.connect(db)
        con.execute(
            "INSERT INTO migrations VALUES (?,?,?,?,?,?)",
            ("migration:medusa","feature:medusa","lsb:test","dsp:test","DISCOVERED","{}"),
        )
        graph.insert_record(con,MigrationAction(
            "action:medusa","migration:medusa","CONVERT",root_artifact,
            "AUTO_MIGRATABLE","Medusa root",
        ))
        con.commit()
        scope=build_dependency_scope(con,"migration:medusa",max_depth=6)
        by_id={item["node_id"]:item for item in scope["items"]}
        assert system_artifact in by_id,scope
        assert by_id[system_artifact]["effective_decision"]=="QUESTIONABLE",scope
        variants=[
            row["artifact_id"] for row in payload["artifacts"]
            if row["metadata"].get("analysis_role")=="CROSS_ZONE_SYSTEM_VARIANT"
        ]
        assert len(variants)==2,variants
        assert all(variant in by_id for variant in variants),scope
        assert all(by_id[variant]["effective_decision"]=="QUESTIONABLE" for variant in variants),scope
        assert any(
            item["node_kind"]=="CONDITIONAL_DEPENDENCY"
            and item["condition_summary"]
            for item in scope["items"]
        ),scope
        con.close()

    print("source-discovered system coupling regression: PASS")


if __name__=="__main__":
    main()
