#!/usr/bin/env python3
"""Regression checks for entity/spawn/drop logical normalization across server families."""
from pathlib import Path
import tempfile
from workbench.adapters.servers import DSPAdapter, LSBAdapter, TopazAdapter
from workbench.adapters.servers.logical import compare_records

def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/"sql").mkdir()
        topaz=TopazAdapter(root); dsp=DSPAdapter(root); lsb=LSBAdapter(root)

        npc_t=topaz.normalize_row("npc",{
            "npcid":17000001,"name":"Example_NPC","pos_x":1,"pos_y":2,"pos_z":3,
            "pos_rot":64,"entityFlags":3,"widescan":1,
        })
        npc_d=dsp.normalize_row("npc",{
            "npcid":17000001,"name":"Example_NPC","pos_x":1,"pos_y":2,"pos_z":3,
            "pos_rot":64,"entityFlags":3,"widescan":1,
        })
        assert compare_records(npc_t,npc_d).status=="EQUIVALENT"

        spawn_l=lsb.normalize_row("mob_spawns",{
            "mobid":17001000,"spawnslotid":4,"mobname":"Example_Mob","groupid":12,
            "minLevel":50,"maxLevel":52,"pos_x":10,"pos_y":11,"pos_z":12,"pos_rot":90,
        })
        spawn_t=topaz.normalize_row("mob_spawns",{
            "mobid":17001000,"mobname":"Example_Mob","groupid":12,
            "pos_x":10,"pos_y":11,"pos_z":12,"pos_rot":90,
        })
        diff=compare_records(spawn_l,spawn_t)
        fields={d.field:d.status for d in diff.differences}
        assert fields["spawn_slot_id"]=="MISSING_FIELD_VALUE",diff
        assert fields["min_level"]=="MISSING_FIELD_VALUE",diff
        assert fields["max_level"]=="MISSING_FIELD_VALUE",diff

        drop_t=topaz.normalize_row("mob_drops",{
            "dropId":8,"dropType":0,"groupId":1,"groupRate":1000,"itemId":123,"itemRate":250,
        })
        drop_d=dsp.normalize_row("mob_drops",{
            "dropid":8,"droptype":0,"groupid":1,"grouprate":1000,"itemid":123,"itemrate":250,
        })
        assert compare_records(drop_t,drop_d).status=="EQUIVALENT"

        pool_t=topaz.normalize_row("mob_pools",{"poolid":5,"name":"Mob","familyid":10,"modelid":"0x01"})
        pool_l=lsb.normalize_row("mob_pools",{"poolid":5,"name":"Mob","speciesid":10,"modelid":"0x01"})
        pdiff=compare_records(pool_t,pool_l)
        assert {d.field for d in pdiff.differences}=={"family_id","species_id"},pdiff

        group_d=dsp.normalize_row("mob_groups",{
            "groupid":2,"poolid":5,"zoneid":55,"respawntime":300,"dropid":8,
        })
        assert group_d.fields["name"] is None
        assert any("mob_pools join" in note for note in group_d.notes),group_d.notes

        ie_t=topaz.normalize_row("instance_entities",{"instanceid":7,"id":17001000})
        ie_l=lsb.normalize_row("instance_entities",{"instanceId":7,"entity_id":17001000})
        assert compare_records(ie_t,ie_l).status=="EQUIVALENT"

    print("server entity logical mapping self-test: PASS")

if __name__=="__main__":
    main()
