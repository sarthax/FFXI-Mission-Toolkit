#!/usr/bin/env python3
"""Regression checks for real SQL dump -> logical record extraction."""
from pathlib import Path
import tempfile
from workbench.adapters.servers import DSPAdapter, LSBAdapter, TopazAdapter
from workbench.adapters.servers.sql_extract import extract_logical_records

def write(path,text):
    path.write_text(text+"\n",encoding="utf-8")

def main():
    with tempfile.TemporaryDirectory() as td:
        base=Path(td)
        topaz=base/"topaz"; dsp=base/"dsp"; lsb=base/"lsb"
        for root in (topaz,dsp,lsb): (root/"sql").mkdir(parents=True)

        write(topaz/"sql"/"instance_list.sql",
              "INSERT INTO `instance_list` VALUES (7,'Demo',56,55,30,1,2,3,0,0,0,0,0);")
        write(dsp/"sql"/"instance_list.sql",
              "INSERT INTO `instance_list` VALUES (7,'Demo',55,30,1,2,3,0,0,0,0,0);")
        write(lsb/"sql"/"instance_list.sql",
              "INSERT INTO `instance_list` VALUES (7,'Demo',56,55,0,30,1,2,3,0,0,0,0,0);")

        ti=extract_logical_records(TopazAdapter(topaz),"instances")[0]
        di=extract_logical_records(DSPAdapter(dsp),"instances")[0]
        li=extract_logical_records(LSBAdapter(lsb),"instances")[0]
        assert ti.fields["instance_zone"]==56,ti
        assert li.fields["instance_zone"]==56,li
        assert di.fields["instance_zone"] is None,di
        assert ti.fields["entrance_zone"]==di.fields["entrance_zone"]==li.fields["entrance_zone"]==55

        write(dsp/"sql"/"mob_pools.sql",
              "INSERT INTO `mob_pools` VALUES (5,'Demo_Mob','Demo Mob',10,'0x01',1,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);")
        write(dsp/"sql"/"mob_groups.sql",
              "INSERT INTO `mob_groups` VALUES (2,5,55,300,0,8,100,0,50,52,0);")
        groups=extract_logical_records(DSPAdapter(dsp),"mob_groups")
        assert groups[0].fields["name"]=="Demo_Mob",groups
        assert any("Derived logical mob-group name" in note for note in groups[0].notes),groups[0].notes

        write(lsb/"sql"/"mob_droplist.sql",
              "SET @RATE = 250;\nINSERT INTO `mob_droplist` VALUES (8,0,1,1000,123,@RATE);")
        drops=extract_logical_records(LSBAdapter(lsb),"mob_drops")
        assert drops[0].fields["item_rate"]==250,drops
    print("server SQL logical extraction self-test: PASS")

if __name__=="__main__":
    main()
