#!/usr/bin/env python3
from workbench.plugins.domain.mission_lsb_extract import extract_lsb_mission_findings, channels_from_findings

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
    channels=channels_from_findings(fs)
    scopes={c.channel_id:c.scope for c in channels}
    assert scopes["mission_var:Status"]=="PERSISTENT",scopes
    assert scopes["local_var:Timer"]=="LOCAL",scopes
    print("LSB mission static extractor self-test: PASS")

if __name__=="__main__":
    main()
