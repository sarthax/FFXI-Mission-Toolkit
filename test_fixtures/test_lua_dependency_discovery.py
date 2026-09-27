#!/usr/bin/env python3
"""Regression for conservative Lua dependency discovery using a Medusa-style fixture."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.analyzers.server.lua_dependencies import analyze_script
from workbench.core import graph
from workbench.core.schema import MigrationAction
from workbench.migrations.package_scope import build_dependency_scope


MEDUSA = """local ID = zones[xi.zone.ARRAPAGO_REEF]
mixins = { require('scripts/mixins/job_special') }

local entity = {}

entity.onMobEngage = function(mob, target)
    for i = ID.mob.MEDUSA + 1, ID.mob.MEDUSA + 4 do
        SpawnMob(i):updateEnmity(target)
    end
end

return entity
"""

IDS = """zones = zones or {}
zones[xi.zone.ARRAPAGO_REEF] =
{
    mob =
    {
        MEDUSA = GetFirstID('Medusa'),
    },
}
return zones[xi.zone.ARRAPAGO_REEF]
"""

MOBS = """templates:
  Medusa:
    id: 2606
    species: medusa
    skill_list_id: 725
  Lamia_Exon:
    id: 2331
    species: lamiae
    spell_list_id: 28
    skill_list_id: 171
entities:
  16998862:
    template: Medusa
    level: [85, 85]
  16998863:
    template: Lamia_Exon
    level: [76, 76]
  16998864:
    template: Lamia_Exon
    level: [76, 76]
  16998865:
    template: Lamia_Exon
    level: [76, 76]
  16998866:
    template: Lamia_Exon
    level: [76, 76]
"""


def main() -> int:
    with TemporaryDirectory() as td:
        root=Path(td)
        script=root/"scripts/zones/Arrapago_Reef/mobs/Medusa.lua"
        ids=root/"scripts/zones/Arrapago_Reef/IDs.lua"
        mobs=root/"data/zones/arrapago_reef/mobs.yaml"
        mixin=root/"scripts/mixins/job_special.lua"
        for path in (script,ids,mobs,mixin):
            path.parent.mkdir(parents=True,exist_ok=True)
        script.write_text(MEDUSA,encoding="utf-8")
        ids.write_text(IDS,encoding="utf-8")
        mobs.write_text(MOBS,encoding="utf-8")
        mixin.write_text("return {}\n",encoding="utf-8")

        payload=analyze_script(
            root,
            script,
            source_snapshot_id="lsb:test",
            zone_id=54,
            ids_lua=ids,
            mobs_yaml=mobs,
        )

        assert payload["summary"]=={
            "require_dependencies":1,
            "entity_dependencies":4,
            "unresolved_findings":0,
        },payload["summary"]

        artifacts={row["path"]:row for row in payload["artifacts"]}
        assert "scripts/zones/Arrapago_Reef/mobs/Medusa.lua" in artifacts,artifacts
        assert "scripts/mixins/job_special.lua" in artifacts,artifacts
        assert artifacts["scripts/mixins/job_special.lua"]["metadata"]["exists_in_source"] is True,artifacts

        entities=sorted(
            row["metadata"]["numeric_id"]
            for row in payload["entities"]
        )
        assert entities==[16998863,16998864,16998865,16998866],entities
        for row in payload["entities"]:
            assert row["display_name"]=="Lamia_Exon",row
            assert row["metadata"]["template_id"]==2331,row
            assert row["metadata"]["species"]=="lamiae",row
            assert row["metadata"]["spell_list_id"]==28,row
            assert row["metadata"]["skill_list_id"]==171,row

        require_edges=[e for e in payload["edges"] if e["edge_id"].startswith("lua-require:")]
        entity_edges=[e for e in payload["edges"] if e["edge_id"].startswith("lua-entity:")]
        assert len(require_edges)==1,require_edges
        assert len(entity_edges)==4,entity_edges
        assert all(e["relationship"]=="REQUIRES" for e in payload["edges"]),payload["edges"]
        assert all(e["confidence"]=="VERIFIED" for e in payload["edges"]),payload["edges"]

        out=root/"analysis.json"
        out.write_text(json.dumps(payload,indent=2),encoding="utf-8")
        db=root/"workbench.db"
        graph.import_json(out,db)

        con=sqlite3.connect(db)
        try:
            assert con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]==4
            assert con.execute(
                "SELECT COUNT(*) FROM entity_relationships WHERE relationship='REQUIRES'"
            ).fetchone()[0]==5

            source_artifact=artifacts["scripts/zones/Arrapago_Reef/mobs/Medusa.lua"]["artifact_id"]
            con.execute(
                "INSERT INTO migrations VALUES (?,?,?,?,?,?)",
                ("migration:medusa","feature:medusa","lsb:test","dsp:test","DISCOVERED","{}"),
            )
            graph.insert_record(
                con,
                MigrationAction(
                    "action:medusa",
                    "migration:medusa",
                    "CONVERT",
                    source_artifact,
                    "AUTO_MIGRATABLE",
                    "Medusa source script root",
                ),
            )
            con.commit()

            scope=build_dependency_scope(con,"migration:medusa")
            ids_in_scope={item["node_id"] for item in scope["items"]}
            require_target=require_edges[0]["target_node"]
            assert require_target in ids_in_scope,scope
            for edge in entity_edges:
                assert edge["target_node"] in ids_in_scope,scope
            helper_items=[
                item for item in scope["items"]
                if item["node_id"] in {edge["target_node"] for edge in entity_edges}
            ]
            assert len(helper_items)==4,helper_items
            assert all(item["node_kind"]=="ENTITY" for item in helper_items),helper_items
            assert all(item["display_name"]=="Lamia_Exon" for item in helper_items),helper_items
        finally:
            con.close()

        # Missing identity evidence must remain explicit rather than silently omitted.
        unresolved=analyze_script(
            root,
            script,
            source_snapshot_id="lsb:test",
            zone_id=54,
        )
        assert unresolved["summary"]["entity_dependencies"]==0,unresolved
        assert unresolved["summary"]["unresolved_findings"]>=4,unresolved

    print("lua dependency discovery self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
