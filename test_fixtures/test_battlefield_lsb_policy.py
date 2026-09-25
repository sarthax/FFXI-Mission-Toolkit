#!/usr/bin/env python3
from workbench.plugins.domain.battlefield_lsb import (
    extract_lsb_battlefield_policy,
    extract_lsb_mission_level_cap,
)


def main():
    lua="""
local content = BattlefieldMission:new({
    isMission  = true,
    maxPlayers = 6,
    levelCap   = xi.settings.main.MAX_LEVEL,
    timeLimit  = utils.minutes(30),
})
"""
    surface=extract_lsb_battlefield_policy(lua)
    assert surface.resolved_fields["is_mission"] is True,surface
    assert surface.resolved_fields["party_size"]==6,surface
    assert surface.resolved_fields["time_limit"]==1800,surface
    assert surface.unresolved_fields["level_cap"]=="xi.settings.main.MAX_LEVEL",surface

    era="ANCIENT_VOWS,                         40\n"
    assert extract_lsb_mission_level_cap(era,"ANCIENT_VOWS")==40
    assert extract_lsb_mission_level_cap(era,"OTHER_BATTLEFIELD") is None

    literal=extract_lsb_battlefield_policy("levelCap = 50,\n")
    assert literal.resolved_fields["level_cap"]==50,literal

    print("LSB battlefield policy extraction self-test: PASS")


if __name__=="__main__":
    main()
