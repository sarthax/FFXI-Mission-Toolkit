#!/usr/bin/env python3
from workbench.plugins.domain.mission_lsb_extract import (
    channels_from_findings,
    correlate_lsb_handlers,
    extract_lsb_mission_findings,
)

SAMPLE=r"""
[xi.zone.ATTOHWA_CHASM] =
{
    ['Loose_Sand'] =
    {
        onTrigger = function(player, npc)
            SpawnMob(attohwaChasmID.mob.LIOUMERE):updateClaim(player)
            return mission:progressEvent(2)
        end,
    },
    onEventFinish =
    {
        [2] = function(player, csid, option, npc)
            mission:setVar(player, 'Status', 1)
            mission:setLocalVar(player, 'Timer', GetSystemTime() + 30 * 60)
            npcUtil.giveKeyItem(player, xi.keyItem.MIMEO_JEWEL)
            player:addKeyItem(xi.keyItem.DIRECT_GRANT_FIXTURE)
            player:delKeyItem(xi.keyItem.CRACKED_MIMEO_MIRROR)
            player:addTitle(xi.title.TEST_TITLE)
        end,
        [32001] = function(player)
            if player:getLocalVar('battlefieldWin') == xi.battlefield.id.ANCIENT_VOWS then
                mission:complete(player)
            end
        end,
    },
}
"""

def main():
    fs=extract_lsb_mission_findings(SAMPLE)
    kinds={f.kind for f in fs}
    assert {"event","spawn_entity","var_set","local_set","key_item_grant","key_item_remove","title_grant","battlefield_win","mission_complete"} <= kinds,kinds
    event=next(f for f in fs if f.kind=="event")
    assert (event.zone,event.actor,event.event_id)==("ATTOHWA_CHASM","Loose_Sand",2),event
    grants={f.value for f in fs if f.kind=="key_item_grant"}
    assert grants=={"MIMEO_JEWEL","DIRECT_GRANT_FIXTURE"},grants
    channels=channels_from_findings(fs)
    scopes={c.channel_id:c.scope for c in channels}
    assert scopes["mission_var:Status"]=="PERSISTENT",scopes
    assert scopes["local_var:Timer"]=="LOCAL",scopes

    machine=correlate_lsb_handlers(SAMPLE,feature_id="mission:test:keyitem-grants")
    finish=next(t for t in machine.transitions if t.event and t.event.event_id==2 and t.trigger=="EVENT_FINISH")
    effect_grants={
        effect.subject for effect in finish.effects if effect.effect=="GRANT"
    }
    assert effect_grants=={
        "key_item:MIMEO_JEWEL",
        "key_item:DIRECT_GRANT_FIXTURE",
    },effect_grants
    print("LSB mission static extractor self-test: PASS")

if __name__=="__main__":
    main()
