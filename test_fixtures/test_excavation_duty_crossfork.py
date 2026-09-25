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
from workbench.migrations.entity_identity import compare_symbol_maps, semantic_membership
from workbench.adapters.servers.entity_symbols import lua_numeric_symbols, yaml_npc_script_symbols

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

    source_symbols=yaml_npc_script_symbols(lsb_root/"data"/"zones"/"lebros_cavern"/"npcs.yaml")
    target_symbols=lua_numeric_symbols(dsp_root/"scripts"/"zones"/"Lebros_Cavern"/"IDs.lua")
    interesting={name for name in target_symbols if name.startswith("_1r") or name.startswith("_jr")}
    source_symbols={k:v for k,v in source_symbols.items() if k in interesting}
    target_symbols={k:v for k,v in target_symbols.items() if k in interesting}
    symbol_diff=compare_symbol_maps(source_symbols,target_symbols)
    renumbered={d.symbol:(d.source_id,d.target_id) for d in symbol_diff["renumbered"]}
    assert renumbered.get("_jr1")== (17035542,17035541),renumbered
    assert renumbered.get("_1rx")== (17035538,17035537),renumbered

    source_membership_ids=set(membership["shared"]) | set(membership["source_only"])
    target_membership_ids=set(membership["shared"]) | set(membership["target_only"])
    source_semantic=semantic_membership(source_membership_ids,source_symbols)
    target_semantic=semantic_membership(target_membership_ids,target_symbols)

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
        "symbol_identity":{
            "renumbered":[asdict(d) for d in symbol_diff["renumbered"]],
            "stable":symbol_diff["stable"],
            "source_only_symbols":symbol_diff["source_only_symbols"],
            "target_only_symbols":symbol_diff["target_only_symbols"],
            "source_membership_symbols":source_semantic["symbols"],
            "target_membership_symbols":target_semantic["symbols"],
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
