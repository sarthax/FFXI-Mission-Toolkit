"""Quest/mission ID lookup is scoped to the chosen log and parsed from the server's own Lua."""
import tempfile
from pathlib import Path

from workbench.server_admin.gm_commands.lookup import lookup
from workbench.server_admin.gm_commands.catalog import _lookup_kind

QUESTS = """QUEST_AVAILABLE = 0;
--
--  San d'Oria - 0
--
A_SENTRY_S_PERIL = 0;  -- x
THE_PICKPOCKET   = 3;
--
--  Bastok - 1
--
THE_SIREN_S_TEAR = 0;
"""
MISSIONS = """--  Nation IDs
NATION_SANDORIA = 0;
--  San d'Oria (0)
SMASH_THE_ORCISH_SCOUTS = 0;
BAT_HUNT = 1;
function foo()
    X = 9;
"""


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        g = Path(td) / "scripts" / "globals"
        g.mkdir(parents=True)
        (g / "quests.lua").write_text(QUESTS, encoding="utf-8")
        (g / "missions.lua").write_text(MISSIONS, encoding="utf-8")
        assert [r["id"] for r in lookup(td, "quest", "", 10, 0)] == [0, 3]
        assert [r["name"] for r in lookup(td, "quest", "", 10, 1)] == ["The Siren S Tear"]
        assert lookup(td, "quest", "", 10) == []  # log required
        assert lookup(td, "quest", "pickpocket", 10, 0)[0]["id"] == 3
        assert [r["id"] for r in lookup(td, "mission", "", 10, 0)] == [0, 1]
        assert lookup(td, "mission", "", 10, 9) == []
    assert _lookup_kind("questID", "addquest") == "quest"
    assert _lookup_kind("missionID", "addmission") == "mission"
    assert _lookup_kind("logID", "addquest") == "questlog"
    print("gm quest/mission lookup self-test: PASS")


if __name__ == "__main__":
    main()
