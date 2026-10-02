#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.devtools.battlefields import lsb as canonical
from workbench.plugins.domain import battlefield_lsb as legacy


def main() -> None:
    assert legacy is canonical

    lua = """
    return Battlefield:new({
        maxPlayers = 6,
        isMission = true,
        timeLimit = utils.minutes(30),
        levelCap = xi.settings.main.LEVEL_CAP,
        mobIds = {
            { mobs.BOSS, mobs.BOSS + 1 },
            { 17000001, unknown.symbol },
        },
    })
    """
    policy = canonical.extract_lsb_battlefield_policy(lua)
    assert policy.resolved_fields == {
        "party_size": 6,
        "is_mission": True,
        "time_limit": 1800,
    }, policy
    assert policy.unresolved_fields == {"level_cap": "xi.settings.main.LEVEL_CAP"}, policy

    groups = canonical.extract_lsb_battlefield_mob_groups(lua, {"mobs.BOSS": 16900000})
    assert groups.groups == ((16900000, 16900001), (17000001,)), groups
    assert groups.unresolved_expressions == ("unknown.symbol",), groups

    era = "{ xi.battlefield.id.ANCIENT_VOWS, 40 },"
    assert canonical.extract_lsb_mission_level_cap(era, "ANCIENT_VOWS") == 40

    with tempfile.TemporaryDirectory() as tmp:
        code = (
            "from workbench.devtools.battlefields import lsb as c; "
            "from workbench.plugins.domain import battlefield_lsb as l; "
            "assert l is c; "
            "assert c.extract_lsb_battlefield_policy('maxPlayers = 3,').resolved_fields['party_size']==3"
        )
        subprocess.run([sys.executable, "-c", code], cwd=Path(tmp), check=True)

    print("battlefield LSB package migration: PASS")


if __name__ == "__main__":
    main()
