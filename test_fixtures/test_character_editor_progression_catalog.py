#!/usr/bin/env python3
"""Focused regression for mission/key-item catalogs parsed from a selected server checkout."""
from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.progression_catalog import key_item_catalog, mission_catalog


MISSION_SAMPLE = """
dsp = dsp or {}
dsp.mission = dsp.mission or {}
dsp.mission.id =
{
    [dsp.mission.area[dsp.mission.log_id.SANDORIA]] =
    {
        SMASH_THE_ORCISH_SCOUTS = 0,
        BAT_HUNT = 1,
        NONE = 255,
    },
    [dsp.mission.area[dsp.mission.log_id.COP]] =
    {
        THE_RITES_OF_LIFE = 1,
        DAWN = 92,
    },
}
"""

KEYITEM_LUA = """
dsp = dsp or {}
dsp.keyItem =
{
    ZERUHN_REPORT = 1,
    AIRSHIP_PASS = 8,
}
"""

KEYITEM_YAML = """
meta:
  cpp:
    underlying: uint16_t
values:
  none: 0
  zeruhn_report: 1
  airship_pass: 8
"""


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        globals_dir = root / "scripts" / "globals"
        globals_dir.mkdir(parents=True)
        (globals_dir / "missions.lua").write_text(MISSION_SAMPLE, encoding="utf-8")
        (globals_dir / "keyitems.lua").write_text(KEYITEM_LUA, encoding="utf-8")

        missions = mission_catalog(root)
        assert missions["source"]["available"] is True
        assert missions["areas"]["0"][0]["symbol"] == "SMASH_THE_ORCISH_SCOUTS"
        assert missions["areas"]["0"][1]["label"] == "Bat Hunt"
        assert missions["areas"]["6"][92]["label"] == "Dawn"
        assert 255 not in missions["areas"]["0"]

        dsp_keys = key_item_catalog(root, "dsp")
        assert dsp_keys["source"]["kind"] == "keyitems.lua"
        assert dsp_keys["items"]["1"]["label"] == "Zeruhn Report"
        assert dsp_keys["items"]["8"]["symbol"] == "AIRSHIP_PASS"

        enum_dir = root / "data" / "enums"
        enum_dir.mkdir(parents=True)
        (enum_dir / "key_item.yaml").write_text(KEYITEM_YAML, encoding="utf-8")
        lsb_keys = key_item_catalog(root, "lsb")
        assert lsb_keys["source"]["kind"] == "key_item.yaml"
        assert lsb_keys["items"]["1"]["symbol"] == "zeruhn_report"
        assert lsb_keys["items"]["8"]["label"] == "Airship Pass"

    missing = mission_catalog(Path("/definitely/not/a/server"))
    assert missing["source"]["available"] is False
    assert missing["areas"] == {}


if __name__ == "__main__":
    main()
