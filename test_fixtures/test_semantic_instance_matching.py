#!/usr/bin/env python3
"""Regression checks for semantic instance matching and renumber planning."""
from pathlib import Path
import tempfile
from workbench.adapters.servers import DSPAdapter, LSBAdapter
from workbench.migrations.record_match import match_records, compare_instance_membership
from workbench.migrations.logical_planner import plan_record_match

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/"sql").mkdir()
        lsb=LSBAdapter(root); dsp=DSPAdapter(root)

        s=lsb.normalize_row("instances",{"instanceid":6300,"instance_name":"excavation_duty","instance_zone":63,"entrance_zone":61})
        t=dsp.normalize_row("instances",{"instanceid":21,"instance_name":"excavation_duty","entrance_zone":61})
        matches=match_records([s],[t])
        assert len(matches)==1,matches
        m=matches[0]
        assert m.match_basis=="UNIQUE_NORMALIZED_NAME",m
        assert m.identity_changes==(("instance_id",6300,21),),m

        actions=plan_record_match(m,"migration:excavation")
        assert len(actions)==1,actions
        assert actions[0].action=="RENUMBER",actions
        assert actions[0].status=="AUTO_MIGRATABLE",actions

        se=[
            lsb.normalize_row("instance_entities",{"instanceid":6300,"id":100}),
            lsb.normalize_row("instance_entities",{"instanceid":6300,"id":101}),
        ]
        te=[
            dsp.normalize_row("instance_entities",{"instanceid":21,"id":100}),
            dsp.normalize_row("instance_entities",{"instanceid":21,"id":102}),
        ]
        membership=compare_instance_membership(se,te,6300,21)
        assert membership["shared"]==[100],membership
        assert membership["source_only"]==[101],membership
        assert membership["target_only"]==[102],membership
    print("semantic instance match self-test: PASS")

if __name__=="__main__":
    main()
