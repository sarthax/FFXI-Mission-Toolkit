#!/usr/bin/env python3
"""Regression checks for generic instance feature slicing."""
from pathlib import Path
import tempfile
from workbench.adapters.servers import TopazAdapter
from workbench.migrations.instance_feature_slice import extract_instance_feature_slice

def write(path,text):
    path.write_text(text+"\n",encoding="utf-8")

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/"sql").mkdir()

        write(root/"sql"/"instance_list.sql",
              "INSERT INTO `instance_list` VALUES (6300,'Excavation Duty',63,55,30,1,2,3,0,0,0,0,0);")
        write(root/"sql"/"instance_entities.sql",
              "INSERT INTO `instance_entities` VALUES (6300,17035265);\n"
              "INSERT INTO `instance_entities` VALUES (6300,17035270);")
        write(root/"sql"/"npc_list.sql",
              "INSERT INTO `npc_list` VALUES (17035270,'Rune_of_Release','Rune of Release',0,0,0,0,0,0,0,0,0,0,0,3,'0',0,0,1);")
        write(root/"sql"/"mob_spawn_points.sql",
              "INSERT INTO `mob_spawn_points` VALUES (17035265,'Brittle_Rock','Brittle Rock',100,0,0,0,0);")
        write(root/"sql"/"mob_groups.sql",
              "INSERT INTO `mob_groups` VALUES (100,200,63,'Brittle_Rock',0,0,300,100,0,50,50,0);")
        write(root/"sql"/"mob_pools.sql",
              "INSERT INTO `mob_pools` VALUES (200,'Brittle_Rock','Brittle Rock',10,'0x01',1,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);")
        write(root/"sql"/"mob_droplist.sql",
              "INSERT INTO `mob_droplist` VALUES (300,0,1,1000,123,250);")

        result=extract_instance_feature_slice(TopazAdapter(root),6300)
        assert result.instance is not None,result
        assert result.instance.fields["name"]=="Excavation Duty",result.instance
        assert result.counts()=={
            "instance":1,"instance_entities":2,"npcs":1,"mob_spawns":1,
            "mob_groups":1,"mob_pools":1,"mob_drops":1,
        },result.counts()
    print("instance feature slice self-test: PASS")

if __name__=="__main__":
    main()
