#!/usr/bin/env python3
"""Package migration smoke for quest extraction and mission source catalog."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.devtools.missions import mission_source_catalog as canonical_catalog
from workbench.devtools.missions import quest_lsb_extract as canonical_quest
from workbench.plugins.domain import mission_source_catalog as legacy_catalog
from workbench.plugins.domain import quest_lsb_extract as legacy_quest


def main() -> None:
    assert legacy_quest is canonical_quest
    assert legacy_catalog is canonical_catalog

    helper_lua = """
xi.testPrereq = function(player)
    return player:hasCompletedQuest(xi.questLog.BASTOK, xi.quest.id.bastok.QUEST_A)
        or player:hasCompletedMission(xi.mission.log_id.WOTG, xi.mission.id.wotg.MISSION_B)
end
"""
    gates = canonical_quest.extract_feature_requirement_helpers(helper_lua)
    assert "xi.testPrereq" in gates
    gate = gates["xi.testPrereq"]
    assert gate.logic == "ANY"
    assert {condition.subject for condition in gate.conditions} == {"quest:QUEST_A", "mission:MISSION_B"}

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "sample_quest.lua").write_text(
            "return Quest:new(xi.questLog.BASTOK, xi.quest.id.bastok.TEST_QUEST)\n",
            encoding="utf-8",
        )
        (root / "sample_mission.lua").write_text(
            "return Mission:new(xi.mission.log_id.COP, xi.mission.id.cop.TEST_MISSION)\n",
            encoding="utf-8",
        )
        catalog = canonical_catalog.LsbFeatureSourceCatalog(root)
        assert catalog.source_for("quest:TEST_QUEST").feature_id == "quest:bastok:test_quest"
        assert catalog.source_for("mission:TEST_MISSION").feature_id == "mission:cop:test_mission"

    code = (
        "from workbench.devtools.missions import quest_lsb_extract, mission_source_catalog; "
        "assert callable(quest_lsb_extract.extract_feature_requirement_helpers); "
        "assert hasattr(mission_source_catalog, 'LsbFeatureSourceCatalog')"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)
    print("quest/source catalog package migration self-test: PASS")


if __name__ == "__main__":
    main()
