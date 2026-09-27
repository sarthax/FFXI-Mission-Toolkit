#!/usr/bin/env python3
"""Regression coverage for broader item/spell/trait logical mappings."""
from pathlib import Path
import tempfile

from workbench.adapters.servers import DSPAdapter, LSBAdapter, TopazAdapter
from workbench.adapters.servers.logical import compare_records


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/"sql").mkdir()
        topaz=TopazAdapter(root); dsp=DSPAdapter(root); lsb=LSBAdapter(root)

        tw=topaz.normalize_row("item_weapon",{
            "itemId":16555,"name":"test_sword","skill":3,"subskill":0,
            "ilvl_skill":0,"ilvl_parry":0,"ilvl_macc":0,"dmgType":2,
            "hit":1,"delay":240,"dmg":20,"unlock_points":0,
        })
        dw=dsp.normalize_row("item_weapon",{
            "itemId":16555,"name":"test_sword","skill":3,"subskill":0,
            "ilvl_skill":0,"ilvl_parry":0,"ilvl_macc":0,"dmgType":2,
            "hit":1,"delay":240,"dmg":20,"unlock_points":0,
        })
        assert compare_records(tw,dw).status=="EQUIVALENT"

        tu=topaz.normalize_row("item_usable",{
            "itemid":4096,"name":"fire_crystal","validTargets":1,"activation":0,
            "animation":0,"animationTime":0,"maxCharges":0,"useDelay":0,
            "reuseDelay":0,"aoe":0,
        })
        du=dsp.normalize_row("item_usable",{
            "itemid":4096,"name":"fire_crystal","validTargets":1,"activation":0,
            "animation":0,"animationTime":0,"maxCharges":0,"useDelay":0,
            "reuseDelay":0,"aoe":0,
        })
        assert compare_records(tu,du).status=="EQUIVALENT"

        ts=topaz.normalize_row("spells",{
            "spellid":1,"name":"cure","jobs":"fixture","group":6,"family":1,
            "element":7,"zonemisc":0,"validTargets":95,"skill":33,"mpCost":8,
            "castTime":2000,"recastTime":5000,"message":230,"magicBurstMessage":0,
            "animation":1,"animationTime":2000,"AOE":0,"base":10,"multiplier":1.0,
            "CE":0,"VE":0,"requirements":0,"spell_range":12,"content_tag":None,
        })
        ds=dsp.normalize_row("spells",{
            "spellid":1,"name":"cure","jobs":"fixture","group":6,
            "element":7,"zonemisc":0,"validTargets":95,"skill":33,"mpCost":8,
            "castTime":2000,"recastTime":5000,"message":230,"magicBurstMessage":0,
            "animation":1,"animationTime":2000,"AOE":0,"base":10,"multiplier":1.0,
            "CE":0,"VE":0,"requirements":0,"spell_range":12,"content_tag":None,
        })
        diff=compare_records(ts,ds)
        assert diff.status=="DIFFERENT",diff
        assert any(d.field=="family" and d.status=="MISSING_FIELD_VALUE" for d in diff.differences),diff

        ls=lsb.normalize_row("spells",{
            "spellid":1,"name":"cure","jobs":"fixture","group":6,"family":1,
            "element":7,"zonemisc":0,"validTargets":95,"skill":33,"mpCost":8,
            "castTime":2000,"recastTime":5000,"message":230,"magicBurstMessage":0,
            "animation":1,"animationTime":2000,"AOE":0,"base":10,"multiplier":1.0,
            "CE":0,"VE":0,"requirements":0,"spell_range":12,"radius":10,
            "content_tag":None,"status_effect":33,"status_effect_tier":1,
        })
        assert ls.fields["radius"]==10
        assert ls.fields["status_effect"]==33

        tt=topaz.normalize_row("traits",{
            "traitid":1,"name":"accuracy bonus","job":11,"level":10,"rank":1,
            "modifier":25,"value":10,"content_tag":None,"meritid":0,
        })
        dt=dsp.normalize_row("traits",{
            "traitid":1,"name":"accuracy bonus","job":11,"level":10,"rank":1,
            "modifier":25,"value":10,"content_tag":None,
        })
        tdiff=compare_records(tt,dt)
        assert any(d.field=="merit_id" for d in tdiff.differences),tdiff

    print("broader logical schema mapping self-test: PASS")

if __name__=="__main__":
    raise SystemExit(main())
