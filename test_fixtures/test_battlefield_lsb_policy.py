#!/usr/bin/env python3
from workbench.plugins.domain.battlefield_lsb import (
    extract_lsb_battlefield_policy,
    extract_lsb_mission_level_cap,
    extract_lsb_battlefield_mob_groups,
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

    groups=extract_lsb_battlefield_mob_groups(
        """
mobIds =
{
    {
        zone.mob.BASE,
        zone.mob.BASE + 1,
        zone.mob.BASE + 2,
    },
    {
        zone.mob.BASE + 3,
        999,
    },
}
""",
        {"zone.mob.BASE":100},
    )
    assert groups.groups==((100,101,102),(103,999)),groups
    assert not groups.unresolved_expressions,groups

    unresolved=extract_lsb_battlefield_mob_groups(
        "mobIds = { { zone.mob.UNKNOWN + 1, helper() } }",
        {},
    )
    assert not unresolved.groups,unresolved
    assert set(unresolved.unresolved_expressions)=={"zone.mob.UNKNOWN + 1","helper()"},unresolved

    print("LSB battlefield policy/group extraction self-test: PASS")


if __name__=="__main__":
    main()
