#!/usr/bin/env python3
"""Regression checks for generic source/target instance slice comparison."""
from pathlib import Path
import tempfile
from workbench.adapters.servers import DSPAdapter, TopazAdapter
from workbench.migrations.instance_feature_slice import extract_instance_feature_slice
from workbench.migrations.instance_slice_compare import compare_instance_slices

def write(path,text):
    path.write_text(text+"\n",encoding="utf-8")

def main():
    with tempfile.TemporaryDirectory() as td:
        base=Path(td); src=base/"src"; dst=base/"dst"
        (src/"sql").mkdir(parents=True); (dst/"sql").mkdir(parents=True)

        write(src/"sql"/"instance_list.sql",
              "INSERT INTO `instance_list` VALUES (6300,'excavation_duty',63,61,30,1,2,3,0,0,0,0,0);")
        write(src/"sql"/"instance_entities.sql",
              "INSERT INTO `instance_entities` VALUES (6300,17035265);")
        write(src/"sql"/"npc_list.sql","")
        write(src/"sql"/"mob_spawn_points.sql",
              "INSERT INTO `mob_spawn_points` VALUES (17035265,'Brittle_Rock','Brittle Rock',100,0,0,0,0);")
        write(src/"sql"/"mob_groups.sql",
              "INSERT INTO `mob_groups` VALUES (100,200,63,'Brittle_Rock',0,0,0,100,0,50,50,0);")
        write(src/"sql"/"mob_pools.sql",
              "INSERT INTO `mob_pools` VALUES (200,'Brittle_Rock','Brittle Rock',10,'0x01',1,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);")
        write(src/"sql"/"mob_droplist.sql","")

        for name in ("instance_list.sql","instance_entities.sql","npc_list.sql","mob_spawn_points.sql","mob_groups.sql","mob_pools.sql","mob_droplist.sql"):
            write(dst/"sql"/name,"")

        source=extract_instance_feature_slice(TopazAdapter(src),6300)
        target=extract_instance_feature_slice(DSPAdapter(dst),6300)
        result=compare_instance_slices(source,target,"m:test")
        assert result.actions,result
        assert all(a.action=="IMPLEMENT" for a in result.actions),result.actions
        assert all(a.status=="MANUAL_REQUIRED" for a in result.actions),result.actions
        assert len({a.action_id for a in result.actions})==len(result.actions),result.actions
    print("instance slice comparison self-test: PASS")

if __name__=="__main__":
    main()
