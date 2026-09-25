#!/usr/bin/env python3
"""Pinned public-repository flagship E2E: CoP 2-5 Ancient Vows, LSB -> legacy DSP."""
from __future__ import annotations
import json,sys
from pathlib import Path
from dataclasses import asdict

from workbench.adapters.servers import DSPAdapter, LSBAdapter
from workbench.adapters.servers.logical import compare_records
from workbench.adapters.servers.sql_extract import extract_logical_records
from workbench.adapters.servers.entity_symbols import yaml_mob_template_spawns

FEATURE_NAME="ancient_vows"
BATTLEFIELD_ID=960
ZONE_ID=31
MAMMET_TEMPLATE="Mammet-19_Epsilon"
EXPECTED_MAMMETS=set(range(16904193,16904202))

def one(records,pred):
    matches=[r for r in records if pred(r)]
    assert len(matches)==1,matches
    return matches[0]

def main():
    if len(sys.argv)!=3:
        raise SystemExit("usage: test_ancient_vows_crossfork.py <lsb-root> <dsp-root>")
    lsb_root=Path(sys.argv[1]).resolve()
    dsp_root=Path(sys.argv[2]).resolve()
    lsb=LSBAdapter(lsb_root); dsp=DSPAdapter(dsp_root)
    assert lsb.probe().compatible
    assert dsp.probe().compatible

    source_registry=one(
        extract_logical_records(lsb,"battlefields"),
        lambda r:r.fields["battlefield_id"]==BATTLEFIELD_ID,
    )
    target_registry=one(
        extract_logical_records(dsp,"battlefields"),
        lambda r:r.fields["battlefield_id"]==BATTLEFIELD_ID,
    )
    assert source_registry.fields["name"]==target_registry.fields["name"]==FEATURE_NAME
    assert source_registry.fields["zone_id"]==target_registry.fields["zone_id"]==ZONE_ID
    assert source_registry.identity==target_registry.identity

    registry_diff=compare_records(source_registry,target_registry)
    registry_fields={d.field:d.status for d in registry_diff.differences}
    # Expected representation drift: DSP stores battlefield policy in SQL while
    # LSB implements those fields in Lua/module policy.
    for field in ("time_limit","level_cap","party_size","loot_drop_id","rules","is_mission"):
        assert registry_fields.get(field)=="MISSING_FIELD_VALUE",(field,registry_diff)

    target_members=extract_logical_records(dsp,"battlefield_members")
    target_mammets={
        r.fields["entity_id"] for r in target_members
        if r.fields["battlefield_id"]==BATTLEFIELD_ID
    }
    assert target_mammets==EXPECTED_MAMMETS,target_mammets

    source_mammets=set(yaml_mob_template_spawns(
        lsb_root/"data"/"zones"/"monarch_linn"/"mobs.yaml",
        MAMMET_TEMPLATE,
    ))
    assert EXPECTED_MAMMETS <= source_mammets,source_mammets
    assert target_mammets <= source_mammets

    surfaces={
        "lsb_mission":lsb_root/"scripts"/"missions"/"cop"/"2_5_Ancient_Vows.lua",
        "lsb_battlefield":lsb_root/"scripts"/"battlefields"/"Monarch_Linn"/"ancient_vows.lua",
        "lsb_mammet":lsb_root/"scripts"/"zones"/"Monarch_Linn"/"mobs"/"Mammet-19_Epsilon.lua",
        "lsb_level_cap_policy":lsb_root/"modules"/"era"/"lua"/"battlefields"/"mission_level_caps.lua",
        "dsp_battlefield":dsp_root/"scripts"/"zones"/"Monarch_Linn"/"bcnms"/"ancient_vows.lua",
        "dsp_mammet":dsp_root/"scripts"/"zones"/"Monarch_Linn"/"mobs"/"Mammet-19_Epsilon.lua",
    }
    missing=[name for name,path in surfaces.items() if not path.exists()]
    assert not missing,missing

    source_battlefield=surfaces["lsb_battlefield"].read_text(encoding="utf-8",errors="ignore")
    target_battlefield=surfaces["dsp_battlefield"].read_text(encoding="utf-8",errors="ignore")
    source_mob=surfaces["lsb_mammet"].read_text(encoding="utf-8",errors="ignore")
    target_mob=surfaces["dsp_mammet"].read_text(encoding="utf-8",errors="ignore")

    assert "BattlefieldMission:new" in source_battlefield
    assert "content.groups" in source_battlefield
    assert "onBattlefieldLeave" in target_battlefield
    assert "completeMission" in target_battlefield
    assert "setMagicCastingEnabled" in source_mob
    assert "SetMagicCastingEnabled" in target_mob

    report={
        "feature":"Chains of Promathia 2-5: Ancient Vows",
        "source_family":"LSB",
        "target_family":"DSP",
        "battlefield_id":BATTLEFIELD_ID,
        "zone_id":ZONE_ID,
        "registry_identity":"EXACT",
        "registry_representation_drift":sorted(registry_fields),
        "mammet_membership":{
            "expected_count":len(EXPECTED_MAMMETS),
            "source_template_spawn_count":len(source_mammets),
            "target_battlefield_member_count":len(target_mammets),
            "shared_expected_ids":sorted(target_mammets & source_mammets),
        },
        "implementation_surfaces":{
            name:str(path.relative_to(lsb_root if name.startswith("lsb_") else dsp_root))
            for name,path in surfaces.items()
        },
        "e2e_status":"PUBLIC_CROSS_FORK_FEATURE_SURFACE_VERIFIED",
    }
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    main()
