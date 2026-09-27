#!/usr/bin/env python3
"""End-to-end Medusa-style closure through LSB zone YAML plus normalized SQL registries."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.analyzers.server.lua_dependencies import analyze_script
from workbench.analyzers.server.zone_yaml_dependencies import analyze_zone
from workbench.core import graph
from workbench.core.schema import MigrationAction
from workbench.migrations.package_scope import build_dependency_scope


MEDUSA_LUA = """local ID = zones[xi.zone.ARRAPAGO_REEF]
mixins = { require('scripts/mixins/job_special') }
local entity = {}
entity.onMobEngage = function(mob, target)
    for i = ID.mob.MEDUSA + 1, ID.mob.MEDUSA + 4 do
        SpawnMob(i):updateEnmity(target)
    end
end
return entity
"""

IDS_LUA = """zones = zones or {}
zones[xi.zone.ARRAPAGO_REEF] =
{
    mob =
    {
        MEDUSA = GetFirstID('Medusa'),
    },
}
return zones[xi.zone.ARRAPAGO_REEF]
"""

MOBS_YAML = """templates:
  Medusa:
    id: 2606
    species: medusa
    skill_list_id: 725
    loot:
      drops:
        - chance: very_common
          item: medusas_armlet
        - chance: common
          item: mercenarys_dastanas
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


def mob_skill_row(skill_id: int, name: str) -> str:
    vals=[
        skill_id,skill_id,name,0,0,5,1000,1000,4,0,0,0,0,0,0,
    ]
    rendered=",".join(f"'{v}'" if isinstance(v,str) else str(v) for v in vals)
    return f"INSERT INTO `mob_skills` VALUES ({rendered});\n"


def spell_row(spell_id: int, name: str) -> str:
    # LSB spell_list parse order has 27 columns.
    vals=[
        spell_id,name,"0","0","0",0,0,4,0,10,1000,1000,0,0,0,1000,0,0,1,0,0,0,12,10,None,None,None,
    ]
    rendered=[]
    for value in vals:
        if value is None:
            rendered.append("NULL")
        elif isinstance(value,str):
            rendered.append(f"'{value}'")
        else:
            rendered.append(str(value))
    return f"INSERT INTO `spell_list` VALUES ({','.join(rendered)});\n"


def main() -> int:
    with TemporaryDirectory() as td:
        root=Path(td)
        script=root/"scripts/zones/Arrapago_Reef/mobs/Medusa.lua"
        ids=root/"scripts/zones/Arrapago_Reef/IDs.lua"
        mobs=root/"data/zones/arrapago_reef/mobs.yaml"
        mixin=root/"scripts/mixins/job_special.lua"
        sql=root/"sql"
        sql.mkdir(parents=True)
        for path in (script,ids,mobs,mixin):
            path.parent.mkdir(parents=True,exist_ok=True)
        script.write_text(MEDUSA_LUA,encoding="utf-8")
        ids.write_text(IDS_LUA,encoding="utf-8")
        mobs.write_text(MOBS_YAML,encoding="utf-8")
        mixin.write_text("return {}\n",encoding="utf-8")

        # Medusa list 725 plus Lamia Exon list 171.
        (sql/"mob_skill_lists.sql").write_text(
            "".join(
                f"INSERT INTO `mob_skill_lists` VALUES ('{name}',{list_id},{skill_id});\n"
                for list_id,name,skill_id in [
                    (725,"medusa",1808),(725,"medusa",1809),(725,"medusa",1810),
                    (725,"medusa",1812),(725,"medusa",1813),(725,"medusa",1814),
                    (171,"lamia_exon",1500),
                ]
            ),
            encoding="utf-8",
        )
        skill_names={
            1808:"petrifaction",
            1809:"shadow_thrust",
            1810:"tail_slap",
            1812:"pinning_shot",
            1813:"calcifying_deluge",
            1814:"gorgon_dance",
            1500:"helper_strike",
        }
        (sql/"mob_skills.sql").write_text(
            "".join(mob_skill_row(skill_id,name) for skill_id,name in skill_names.items()),
            encoding="utf-8",
        )
        (sql/"mob_spell_lists.sql").write_text(
            "INSERT INTO `mob_spell_lists` VALUES ('lamia_exon',28,5,1,99);\n",
            encoding="utf-8",
        )
        (sql/"spell_list.sql").write_text(spell_row(5,"stone"),encoding="utf-8")
        (sql/"item_basic.sql").write_text(
            "INSERT INTO `item_basic` VALUES (15000,0,'medusas_armlet','medusas_armlet','',4,1,0,0,1000);\n"
            "INSERT INTO `item_basic` VALUES (15001,0,'mercenarys_dastanas','mercenarys_dastanas','',4,1,0,0,1000);\n",
            encoding="utf-8",
        )

        for name in ("shadow_thrust","pinning_shot","calcifying_deluge","gorgon_dance","helper_strike"):
            path=root/f"scripts/actions/mobskills/{name}.lua"
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text("return {}\n",encoding="utf-8")

        lua_payload=analyze_script(
            root,script,source_snapshot_id="lsb:test",zone_id=54,ids_lua=ids,mobs_yaml=mobs
        )
        zone_payload=analyze_zone(
            root,mobs,source_snapshot_id="lsb:test",zone_id=54,
            root_entity_ids=[16998862,16998863,16998864,16998865,16998866],
        )

        assert zone_payload["summary"]["root_entities"]==5,zone_payload["summary"]

        by_type={}
        for row in zone_payload["entities"]:
            by_type.setdefault(row["entity_type"],[]).append(row)
        assert len(by_type["MOB_TEMPLATE"])==2,by_type
        assert {row["display_name"] for row in by_type["SPECIES"]}=={"medusa","lamiae"},by_type
        assert {row["metadata"]["skill_list_id"] for row in by_type["MOB_SKILL_LIST"]}=={725,171},by_type
        assert {row["metadata"]["spell_list_id"] for row in by_type["MOB_SPELL_LIST"]}=={28},by_type

        mob_skills={row["metadata"]["mob_skill_id"]:row for row in by_type["MOB_SKILL"]}
        assert set(mob_skills)=={1500,1808,1809,1810,1812,1813,1814},mob_skills
        spells={row["metadata"]["spell_id"]:row for row in by_type["SPELL"]}
        assert set(spells)=={5},spells
        items={row["display_name"]:row for row in by_type["ITEM"]}
        assert set(items)=={"medusas_armlet","mercenarys_dastanas"},items
        assert items["medusas_armlet"]["metadata"]["item_id"]==15000,items
        assert items["medusas_armlet"]["metadata"]["loot_chance"]=="very_common",items
        assert items["mercenarys_dastanas"]["metadata"]["item_id"]==15001,items
        assert items["mercenarys_dastanas"]["metadata"]["loot_chance"]=="common",items
        assert items["medusas_armlet"]["metadata"]["item_basic"]["name"]=="medusas_armlet",items

        artifact_paths={row["path"] for row in zone_payload["artifacts"]}
        for required in (
            "scripts/actions/mobskills/shadow_thrust.lua",
            "scripts/actions/mobskills/pinning_shot.lua",
            "scripts/actions/mobskills/calcifying_deluge.lua",
            "scripts/actions/mobskills/gorgon_dance.lua",
            "scripts/actions/mobskills/helper_strike.lua",
        ):
            assert required in artifact_paths,artifact_paths

        # Petrifaction/tail_slap have no fixture scripts: omission must stay explicit.
        findings={row["value"] for row in zone_payload["findings"] if row["field"]=="lua_implementation"}
        assert "scripts/actions/mobskills/petrifaction.lua" in findings,findings
        assert "scripts/actions/mobskills/tail_slap.lua" in findings,findings

        combined=root/"combined.json"
        payload={
            "schema":1,
            "entities":lua_payload["entities"]+zone_payload["entities"],
            "artifacts":lua_payload["artifacts"]+zone_payload["artifacts"],
            "evidence":lua_payload["evidence"]+zone_payload["evidence"],
            "findings":lua_payload["findings"]+zone_payload["findings"],
            "edges":lua_payload["edges"]+zone_payload["edges"],
        }
        combined.write_text(json.dumps(payload,indent=2),encoding="utf-8")

        db=root/"workbench.db"
        graph.import_json(combined,db)
        con=sqlite3.connect(db)
        try:
            source_artifact=next(
                row["artifact_id"] for row in lua_payload["artifacts"]
                if row["path"]=="scripts/zones/Arrapago_Reef/mobs/Medusa.lua"
            )
            con.execute(
                "INSERT INTO migrations VALUES (?,?,?,?,?,?)",
                ("migration:medusa","feature:medusa","lsb:test","dsp:test","DISCOVERED","{}"),
            )
            graph.insert_record(
                con,
                MigrationAction(
                    "action:medusa","migration:medusa","CONVERT",source_artifact,
                    "AUTO_MIGRATABLE","Medusa root",
                ),
            )
            con.commit()

            scope=build_dependency_scope(con,"migration:medusa")
            paths={item["artifact_path"] for item in scope["items"] if item["artifact_path"]}
            assert "scripts/mixins/job_special.lua" in paths,scope
            assert "scripts/actions/mobskills/shadow_thrust.lua" in paths,scope
            assert "scripts/actions/mobskills/gorgon_dance.lua" in paths,scope

            labels={item["display_name"] for item in scope["items"] if item["display_name"]}
            assert "Lamia_Exon" in labels,labels
            assert "lamiae" in labels,labels
            assert "Mob skill list 171" in labels,labels
            assert "Mob spell list 28" in labels,labels
            assert "stone" in labels,labels
            assert "medusas_armlet" in labels,labels
            assert "mercenarys_dastanas" in labels,labels
        finally:
            con.close()

    print("zone YAML dependency closure self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
