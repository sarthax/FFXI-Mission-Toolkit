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

        tim=topaz.normalize_row("item_modifiers",{"itemId":10250,"modId":1,"value":1})
        dim=dsp.normalize_row("item_modifiers",{"itemId":10250,"modId":1,"value":1})
        lim=lsb.normalize_row("item_modifiers",{"itemId":10250,"modId":1,"value":1})
        assert compare_records(tim,dim).status=="EQUIVALENT"
        assert compare_records(tim,lim).status=="EQUIVALENT"
        assert tim.identity==(("item_id",10250),("modifier_id",1)),tim

        tpm=topaz.normalize_row("item_pet_modifiers",{"itemId":10296,"modId":25,"value":3,"petType":3})
        dpm=dsp.normalize_row("item_pet_modifiers",{"itemId":10296,"modId":25,"value":3,"petType":3})
        lpm=lsb.normalize_row("item_pet_modifiers",{"itemId":10296,"modId":25,"value":3,"petType":3})
        assert compare_records(tpm,dpm).status=="EQUIVALENT"
        assert compare_records(tpm,lpm).status=="EQUIVALENT"
        assert tpm.identity==(("item_id",10296),("modifier_id",25),("pet_type",3)),tpm

        til=topaz.normalize_row("item_latents",{
            "itemId":10293,"modId":25,"value":50,"latentId":50,"latentParam":31,
        })
        dil=dsp.normalize_row("item_latents",{
            "itemId":10293,"modId":25,"value":50,"latentId":50,"latentParam":31,
        })
        lil=lsb.normalize_row("item_latents",{
            "itemId":10293,"modId":25,"value":50,"latentId":50,"latentParam":31,
        })
        assert compare_records(til,dil).status=="EQUIVALENT"
        assert compare_records(til,lil).status=="EQUIVALENT"
        assert til.identity==(
            ("item_id",10293),("modifier_id",25),("value",50),
            ("latent_id",50),("latent_parameter",31),
        ),til

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

        tpmod=topaz.normalize_row("mob_pool_modifiers",{
            "poolid":70,"modid":48,"value":434,"is_mob_mod":1,
        })
        dpmod=dsp.normalize_row("mob_pool_modifiers",{
            "poolid":70,"modid":48,"value":434,"is_mob_mod":1,
        })
        lpmod=lsb.normalize_row("mob_pool_modifiers",{
            "poolid":70,"modid":48,"value":434,"is_mob_mod":1,
        })
        assert compare_records(tpmod,dpmod).status=="EQUIVALENT"
        assert compare_records(tpmod,lpmod).status=="EQUIVALENT"
        assert tpmod.identity==(("pool_id",70),("modifier_id",48)),tpmod

        tmsl=topaz.normalize_row("mob_spell_lists",{
            "spell_list_name":"Beastmen_WHM","spell_list_id":1,"spell_id":1,
            "min_level":1,"max_level":10,
        })
        dmsl=dsp.normalize_row("mob_spell_lists",{
            "spell_list_name":"Beastmen_WHM","spell_list_id":1,"spell_id":1,
            "min_level":1,"max_level":10,
        })
        lmsl=lsb.normalize_row("mob_spell_lists",{
            "spell_list_name":"Beastmen_WHM","spell_list_id":1,"spell_id":1,
            "min_level":1,"max_level":10,
        })
        assert compare_records(tmsl,dmsl).status=="EQUIVALENT"
        assert compare_records(tmsl,lmsl).status=="EQUIVALENT"

        cap_row={"level":1,**{f"r{i}":v for i,v in enumerate((0,6,6,5,5,5,5,5,5,4,4,4,3,4))}}
        tcap=topaz.normalize_row("skill_caps",cap_row)
        dcap=dsp.normalize_row("skill_caps",cap_row)
        lcap=lsb.normalize_row("skill_caps",cap_row)
        assert compare_records(tcap,dcap).status=="EQUIVALENT"
        assert compare_records(tcap,lcap).status=="EQUIVALENT"
        assert tcap.identity==(("level",1),),tcap
        assert tcap.fields["rank_13"]==4,tcap

        rank_row={
            "skillid":1,"name":"hand2hand","war":9,"mnk":1,"whm":0,"blm":0,
            "rdm":0,"thf":10,"pld":0,"drk":0,"bst":0,"brd":0,"rng":0,
            "sam":0,"nin":10,"drg":0,"smn":0,"blu":0,"cor":0,"pup":1,
            "dnc":9,"sch":0,"geo":0,"run":0,
        }
        trank=topaz.normalize_row("skill_ranks",rank_row)
        drank=dsp.normalize_row("skill_ranks",rank_row)
        lrank=lsb.normalize_row("skill_ranks",rank_row)
        assert compare_records(trank,drank).status=="EQUIVALENT"
        assert compare_records(trank,lrank).status=="EQUIVALENT"
        assert trank.identity==(("skill_id",1),),trank
        assert trank.fields["thf_rank"]==10,trank

        ta=topaz.normalize_row("abilities",{
            "abilityId":5,"name":"provoke","job":1,"level":5,"validTarget":4,
            "recastTime":30,"recastId":5,"message1":100,"message2":101,
            "animation":10,"animationTime":1000,"castTime":0,"actionType":6,
            "range":15.0,"isAOE":0,"CE":1800,"VE":1800,"meritModID":0,
            "addType":0,"content_tag":None,
        })
        da=dsp.normalize_row("abilities",{
            "abilityId":5,"name":"provoke","job":1,"level":5,"validTarget":4,
            "recastTime":30,"recastId":5,"message1":100,"message2":101,
            "animation":10,"animationTime":1000,"castTime":0,"actionType":6,
            "range":15.0,"isAOE":0,"CE":1800,"VE":1800,"meritModID":0,
            "addType":0,"content_tag":None,
        })
        assert compare_records(ta,da).status=="EQUIVALENT"
        la=lsb.normalize_row("abilities",{
            "abilityId":5,"name":"provoke","job":1,"level":5,"validTarget":4,
            "recastTime":30,"recastId":5,"message1":100,"message2":101,
            "animation":10,"animationTime":1000,"castTime":0,"actionType":6,
            "range":15.0,"isAOE":0,"radius":10,"CE":1800,"VE":1800,"meritModID":0,
            "addType":0,"content_tag":None,
        })
        adiff=compare_records(ta,la)
        assert any(d.field=="radius" and d.status=="MISSING_FIELD_VALUE" for d in adiff.differences),adiff

        tws=topaz.normalize_row("weapon_skills",{
            "weaponskillid":1,"name":"fast_blade","jobs":"fixture","type":3,
            "skilllevel":10,"element":0,"animation":1,"animationTime":2000,
            "range":5,"aoe":0,"primary_sc":1,"secondary_sc":0,"tertiary_sc":0,
            "main_only":0,"unlock_id":0,
        })
        dws=dsp.normalize_row("weapon_skills",{
            "weaponskillid":1,"name":"fast_blade","jobs":"fixture","type":3,
            "skilllevel":10,"element":0,"animation":1,"animationTime":2000,
            "range":5,"aoe":0,"primary_sc":1,"secondary_sc":0,"tertiary_sc":0,
            "main_only":0,"unlock_id":0,
        })
        assert compare_records(tws,dws).status=="EQUIVALENT"
        lws=lsb.normalize_row("weapon_skills",{
            "weaponskillid":1,"name":"fast_blade","jobs":"fixture","type":3,
            "skilllevel":10,"element":0,"animation":1,"animationTime":2000,
            "range":5,"aoe":0,"radius":3,"primary_sc":1,"secondary_sc":0,
            "tertiary_sc":0,"main_only":0,"unlock_id":0,
        })
        wdiff=compare_records(tws,lws)
        assert any(d.field=="radius" and d.status=="MISSING_FIELD_VALUE" for d in wdiff.differences),wdiff

        tms=topaz.normalize_row("mob_skills",{
            "mob_skill_id":100,"mob_anim_id":55,"mob_skill_name":"test_roar",
            "mob_skill_aoe":1,"mob_skill_distance":8.0,"mob_anim_time":2000,
            "mob_prepare_time":1000,"mob_valid_targets":4,"mob_skill_flag":0,
            "mob_skill_param":0,"knockback":0,"primary_sc":0,"secondary_sc":0,
            "tertiary_sc":0,
        })
        dms=dsp.normalize_row("mob_skills",{
            "mob_skill_id":100,"mob_anim_id":55,"mob_skill_name":"test_roar",
            "mob_skill_aoe":1,"mob_skill_distance":8.0,"mob_anim_time":2000,
            "mob_prepare_time":1000,"mob_valid_targets":4,"mob_skill_flag":0,
            "mob_skill_param":0,"knockback":0,"primary_sc":0,"secondary_sc":0,
            "tertiary_sc":0,
        })
        assert compare_records(tms,dms).status=="EQUIVALENT"
        lms=lsb.normalize_row("mob_skills",{
            "mob_skill_id":100,"mob_anim_id":55,"mob_skill_name":"test_roar",
            "mob_skill_aoe":1,"mob_skill_aoe_radius":10.0,"mob_skill_distance":8.0,
            "mob_anim_time":2000,"mob_prepare_time":1000,"mob_valid_targets":4,
            "mob_skill_flag":0,"mob_skill_param":0,"knockback":0,"primary_sc":0,
            "secondary_sc":0,"tertiary_sc":0,
        })
        mdiff=compare_records(tms,lms)
        assert any(d.field=="aoe_radius" and d.status=="MISSING_FIELD_VALUE" for d in mdiff.differences),mdiff

        membership=topaz.normalize_row("mob_skill_lists",{
            "skill_list_name":"test_list","skill_list_id":42,"mob_skill_id":100,
        })
        assert membership.identity==(("skill_list_id",42),("mob_skill_id",100)),membership

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
