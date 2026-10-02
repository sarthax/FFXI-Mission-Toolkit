#!/usr/bin/env python3
"""Focused regression for checkout-local Character Editor quest labels."""
from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.quest_catalog import quest_catalog


TOPAZ_SAMPLE = """
tpz = tpz or {}
tpz.quest = tpz.quest or {}
tpz.quest.id =
{
    [tpz.quest.area[tpz.quest.log_id.SANDORIA]] =
    {
        A_SENTRY_S_PERIL = 0,
        OLD_WOUNDS = 102,
    },
    [tpz.quest.area[tpz.quest.log_id.COALITION]] =
    {
        SCOUTING_THE_FRONTIER = 7,
        OUT_OF_RANGE = 999,
    },
}
"""

LSB_SAMPLE = """
xi = xi or {}
xi.quest = xi.quest or {}
xi.quest.id =
{
    [xi.quest.area[xi.questLog.SANDORIA]] =
    {
        A_SENTRYS_PERIL = 0,
        OLD_WOUNDS = 102,
    },
    [xi.quest.area[xi.questLog.ADOULIN]] =
    {
        CHILDREN_OF_THE_RUNE = 12,
    },
}
"""


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        path = root / "scripts" / "globals" / "quests.lua"
        path.parent.mkdir(parents=True)

        path.write_text(TOPAZ_SAMPLE, encoding="utf-8")
        topaz = quest_catalog(root)
        assert topaz["source"]["available"] is True
        assert topaz["source"]["kind"] == "quests.lua"
        assert topaz["areas"]["0"][0]["symbol"] == "A_SENTRY_S_PERIL"
        assert topaz["areas"]["0"][102]["label"] == "Old Wounds"
        assert topaz["areas"]["10"][7]["label"] == "Scouting The Frontier"
        assert 999 not in topaz["areas"]["10"]

        path.write_text(LSB_SAMPLE, encoding="utf-8")
        lsb = quest_catalog(root)
        assert lsb["areas"]["0"][0]["symbol"] == "A_SENTRYS_PERIL"
        assert lsb["areas"]["9"][12]["label"] == "Children Of The Rune"

    missing = quest_catalog(Path("/definitely/not/a/server"))
    assert missing["source"]["available"] is False
    assert missing["areas"] == {}


if __name__ == "__main__":
    main()
