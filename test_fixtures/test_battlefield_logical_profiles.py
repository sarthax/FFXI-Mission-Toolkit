#!/usr/bin/env python3
"""Regression checks for cross-fork battlefield registry normalization."""
from pathlib import Path
import tempfile
from workbench.adapters.servers import DSPAdapter, LSBAdapter
from workbench.adapters.servers.logical import compare_records
from workbench.adapters.servers.sql_extract import extract_logical_records

def write(path,text):
    path.write_text(text+"\n",encoding="utf-8")

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); lsb=root/"lsb"; dsp=root/"dsp"
        (lsb/"sql").mkdir(parents=True); (dsp/"sql").mkdir(parents=True)
        write(lsb/"sql"/"bcnm_info.sql",
              "INSERT INTO `bcnm_records` VALUES (960,31,'ancient_vows','nobody',0,1800);")
        write(dsp/"sql"/"bcnm_info.sql",
              "INSERT INTO `bcnm_info` VALUES (960,31,'ancient_vows','nobody',0,1800,1800,40,6,0,5,1);")
        write(dsp/"sql"/"bcnm_battlefield.sql",
              "INSERT INTO `bcnm_battlefield` VALUES (960,1,16904193,3);")

        sr=extract_logical_records(LSBAdapter(lsb),"battlefields")[0]
        tr=extract_logical_records(DSPAdapter(dsp),"battlefields")[0]
        assert sr.identity==tr.identity==(("battlefield_id",960),)
        assert sr.fields["zone_id"]==tr.fields["zone_id"]==31
        assert sr.fields["name"]==tr.fields["name"]=="ancient_vows"
        diff=compare_records(sr,tr)
        differing={d.field for d in diff.differences}
        assert {"time_limit","level_cap","party_size","loot_drop_id","rules","is_mission"} <= differing,diff

        members=extract_logical_records(DSPAdapter(dsp),"battlefield_members")
        assert members[0].fields["entity_id"]==16904193,members
        assert members[0].fields["battlefield_number"]==1,members
    print("battlefield logical profile self-test: PASS")

if __name__=="__main__":
    main()
