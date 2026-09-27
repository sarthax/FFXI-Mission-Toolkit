#!/usr/bin/env python3
"""Focused regression for conditional same-stem/shared-system discovery."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.analyzers.server.related_variants import analyze_related_variants
from workbench.core import graph
from workbench.core.schema import MigrationAction
from workbench.migrations.package_scope import (
    DEPENDENCY_RELATIONSHIPS,
    build_dependency_scope,
)


ARRAPAGO = """local entity = {}
entity.onMobSpawn = function(mob)
    mob:setMobMod(xi.mobMod.NO_MOVE, 1)
end
return entity
"""

BESIEGED_VARIANT = """local entity = {}
entity.onMobInitialize = function(mob)
    xi.besieged.onMobInitialize(mob)
end
entity.onMobSpawn = function(mob)
    xi.besieged.onMobSpawn(mob)
end
entity.onMobDeath = function(mob, player, optParams)
    xi.besieged.onMobDeath(mob, player, optParams)
end
entity.onMobDespawn = function(mob)
    xi.besieged.onMobDespawn(mob)
end
return entity
"""


def main() -> int:
    with TemporaryDirectory() as td:
        root=Path(td)
        arrapago=root/"scripts/zones/Arrapago_Reef/mobs/Medusa.lua"
        al_zahbi=root/"scripts/zones/Al_Zahbi/mobs/Medusa.lua"
        bhaflau=root/"scripts/zones/Bhaflau_Thickets/mobs/Medusa.lua"
        besieged=root/"scripts/globals/besieged.lua"

        for path in (arrapago,al_zahbi,bhaflau,besieged):
            path.parent.mkdir(parents=True,exist_ok=True)

        arrapago.write_text(ARRAPAGO,encoding="utf-8")
        al_zahbi.write_text(BESIEGED_VARIANT,encoding="utf-8")
        bhaflau.write_text(BESIEGED_VARIANT,encoding="utf-8")
        besieged.write_text("xi = xi or {}\nxi.besieged = xi.besieged or {}\n",encoding="utf-8")

        payload=analyze_related_variants(
            root,
            arrapago,
            source_snapshot_id="lsb:test",
        )

        assert payload["summary"]=={
            "candidate_variants":2,
            "shared_systems":1,
            "related_variant_edges":2,
            "conditional_system_edges":1,
        },payload["summary"]

        artifacts={row["path"]:row for row in payload["artifacts"]}
        assert set(artifacts)=={
            "scripts/zones/Arrapago_Reef/mobs/Medusa.lua",
            "scripts/zones/Al_Zahbi/mobs/Medusa.lua",
            "scripts/zones/Bhaflau_Thickets/mobs/Medusa.lua",
            "scripts/globals/besieged.lua",
        },artifacts

        system_edges=[
            edge for edge in payload["edges"]
            if edge["relationship"]=="SYSTEM_COUPLED_CONDITIONAL_DEPENDENCY"
        ]
        variant_edges=[
            edge for edge in payload["edges"]
            if edge["relationship"]=="RELATED_VARIANT"
        ]
        assert len(system_edges)==1,system_edges
        assert len(variant_edges)==2,variant_edges
        assert system_edges[0]["status"]=="QUESTIONABLE",system_edges
        assert system_edges[0]["confidence"]=="HIGH",system_edges
        assert all(edge["status"]=="QUESTIONABLE" for edge in variant_edges),variant_edges
        assert all(edge["confidence"]=="HIGH" for edge in variant_edges),variant_edges

        # Import into the canonical graph.
        out=root/"analysis.json"
        out.write_text(json.dumps(payload,indent=2),encoding="utf-8")
        db=root/"workbench.db"
        graph.import_json(out,db)

        con=sqlite3.connect(db)
        try:
            source_id=artifacts["scripts/zones/Arrapago_Reef/mobs/Medusa.lua"]["artifact_id"]
            con.execute(
                "INSERT INTO migrations VALUES (?,?,?,?,?,?)",
                ("migration:medusa-besieged","feature:medusa","lsb:test","dsp:test","DISCOVERED","{}"),
            )
            graph.insert_record(
                con,
                MigrationAction(
                    "action:medusa-besieged",
                    "migration:medusa-besieged",
                    "CONVERT",
                    source_id,
                    "AUTO_MIGRATABLE",
                    "Arrapago Medusa root",
                ),
            )
            con.commit()

            # Default package closure must NOT auto-include conditional related variants.
            default_scope=build_dependency_scope(con,"migration:medusa-besieged")
            default_ids={item["node_id"] for item in default_scope["items"]}
            assert len(default_ids)==1,default_scope

            # Review tooling can opt in to show the conditional relationships.
            review_scope=build_dependency_scope(
                con,
                "migration:medusa-besieged",
                relationships=set(DEPENDENCY_RELATIONSHIPS) | {
                    "RELATED_VARIANT",
                    "SYSTEM_COUPLED_CONDITIONAL_DEPENDENCY",
                },
            )
            review_paths={
                item["artifact_path"]
                for item in review_scope["items"]
                if item["artifact_path"]
            }
            assert "scripts/globals/besieged.lua" in review_paths,review_scope
            assert "scripts/zones/Al_Zahbi/mobs/Medusa.lua" in review_paths,review_scope
            assert "scripts/zones/Bhaflau_Thickets/mobs/Medusa.lua" in review_paths,review_scope
        finally:
            con.close()

        # One same-stem variant is insufficient to prove a shared-system coupling.
        bhaflau.unlink()
        single=analyze_related_variants(
            root,
            arrapago,
            source_snapshot_id="lsb:test",
        )
        assert single["summary"]["candidate_variants"]==1,single
        assert single["summary"]["shared_systems"]==0,single
        assert single["summary"]["related_variant_edges"]==0,single
        assert single["summary"]["conditional_system_edges"]==0,single

    print("related variant system discovery self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
