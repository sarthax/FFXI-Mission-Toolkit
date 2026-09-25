#!/usr/bin/env python3
"""Pinned public-repository E2E smoke for Excavation Duty: LSB -> legacy DSP."""
from __future__ import annotations
import json,sys
from pathlib import Path
from dataclasses import asdict
from workbench.adapters.servers import DSPAdapter, LSBAdapter
from workbench.adapters.servers.sql_extract import extract_logical_records
from workbench.migrations.record_match import match_records, compare_instance_membership
from workbench.migrations.logical_planner import plan_record_match

MISSION_NAME="excavation_duty"

def by_name(records,name):
    return [r for r in records if str(r.fields.get("name") or "").lower()==name.lower()]

def main():
    if len(sys.argv)!=3:
        raise SystemExit("usage: test_excavation_duty_crossfork.py <lsb-root> <dsp-root>")
    lsb_root=Path(sys.argv[1]).resolve()
    dsp_root=Path(sys.argv[2]).resolve()
    lsb=LSBAdapter(lsb_root); dsp=DSPAdapter(dsp_root)
    assert lsb.probe().compatible
    assert dsp.probe().compatible

    source_instances=by_name(extract_logical_records(lsb,"instances"),MISSION_NAME)
    target_instances=by_name(extract_logical_records(dsp,"instances"),MISSION_NAME)
    assert len(source_instances)==1,source_instances
    assert len(target_instances)==1,target_instances

    matches=match_records(source_instances,target_instances)
    assert len(matches)==1,matches
    match=matches[0]
    assert match.source.fields["instance_id"]==6300,match
    assert match.target.fields["instance_id"]==21,match
    actions=plan_record_match(match,"migration:assault:excavation_duty")
    assert any(a.action=="RENUMBER" for a in actions),actions

    source_entities=extract_logical_records(lsb,"instance_entities")
    target_entities=extract_logical_records(dsp,"instance_entities")
    membership=compare_instance_membership(source_entities,target_entities,6300,21)
    assert membership["shared"],membership

    source_script=lsb_root/"scripts"/"assaults"/"Lebros_Cavern"/"excavation_duty.lua"
    target_script=dsp_root/"scripts"/"zones"/"Lebros_Cavern"/"instances"/"excavation_duty.lua"
    assert source_script.exists(),source_script
    assert target_script.exists(),target_script

    report={
        "feature":"Assault: Excavation Duty",
        "source_family":"LSB",
        "target_family":"DSP",
        "source_instance_id":6300,
        "target_instance_id":21,
        "match_basis":match.match_basis,
        "migration_actions":[asdict(a) for a in actions],
        "instance_membership":{
            "shared_count":len(membership["shared"]),
            "source_only_count":len(membership["source_only"]),
            "target_only_count":len(membership["target_only"]),
            "shared_sample":membership["shared"][:10],
            "source_only_sample":membership["source_only"][:10],
            "target_only_sample":membership["target_only"][:10],
        },
        "script_layout":{
            "source":str(source_script.relative_to(lsb_root)),
            "target":str(target_script.relative_to(dsp_root)),
            "status":"PATH_DRIFT",
        },
    }
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
