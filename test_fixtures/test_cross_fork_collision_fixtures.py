#!/usr/bin/env python3
"""Cross-fork collision fixtures derived from public Darkstar/Topaz/LSB SQL shapes.

The Cesti item_weapon row (item 16385) is present with the same stable values in
public Darkstar, Topaz, and LSB item_weapon.sql snapshots. The spell fixture
models the audited legacy DSP spell_list shape, which lacks Topaz-era family.
"""
from pathlib import Path
import tempfile

from workbench.adapters.servers import DSPAdapter, LSBAdapter, TopazAdapter
from workbench.migrations.id_collision import analyze_collisions


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/"sql").mkdir()
        topaz=TopazAdapter(root)
        dsp=DSPAdapter(root)
        lsb=LSBAdapter(root)

        cesti={
            "itemId":16385,"name":"cesti","skill":1,"subskill":0,
            "ilvl_skill":0,"ilvl_parry":0,"ilvl_macc":0,
            "dmgType":4,"hit":1,"delay":528,"dmg":1,"unlock_points":0,
        }
        topaz_weapon=topaz.normalize_row("item_weapon",cesti)
        dsp_weapon=dsp.normalize_row("item_weapon",cesti)
        lsb_weapon=lsb.normalize_row("item_weapon",cesti)

        td_result=analyze_collisions(
            [topaz_weapon],[dsp_weapon],
            source_snapshot_id="public:topaz:item_weapon",
            target_snapshot_id="public:dsp:item_weapon",
        )
        assert td_result["summary"]=={"EXACT_IDENTITY_EQUIVALENT":1},td_result

        tl_result=analyze_collisions(
            [topaz_weapon],[lsb_weapon],
            source_snapshot_id="public:topaz:item_weapon",
            target_snapshot_id="public:lsb:item_weapon",
        )
        assert tl_result["summary"]=={"EXACT_IDENTITY_EQUIVALENT":1},tl_result

        common_spell={
            "spellid":1,"name":"cure","jobs":"fixture","group":6,
            "element":7,"zonemisc":0,"validTargets":95,"skill":33,
            "mpCost":8,"castTime":2000,"recastTime":5000,
            "message":230,"magicBurstMessage":0,"animation":1,
            "animationTime":2000,"AOE":0,"base":10,"multiplier":1.0,
            "CE":0,"VE":0,"requirements":0,"spell_range":12,
            "content_tag":None,
        }
        topaz_spell=topaz.normalize_row("spells",{**common_spell,"family":1})
        dsp_spell=dsp.normalize_row("spells",common_spell)
        spell_result=analyze_collisions(
            [topaz_spell],[dsp_spell],
            source_snapshot_id="public:topaz:spell_list",
            target_snapshot_id="public:dsp:spell_list",
        )
        assert spell_result["summary"]=={"ID_CONTENT_COLLISION":1},spell_result
        finding=spell_result["findings"][0]
        assert finding["logical_type"]=="spells",finding
        assert finding["source_identity"]==[["spell_id",1]],finding
        assert finding["target_identity"]==[["spell_id",1]],finding
        assert finding["confidence"]=="VERIFIED",finding

    print("real cross-fork collision fixture self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
