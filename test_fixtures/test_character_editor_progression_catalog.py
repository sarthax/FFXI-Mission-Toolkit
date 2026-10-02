#!/usr/bin/env python3
"""Focused regressions for checkout-local Character Editor progression/unlock catalogs."""
from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from workbench.editors.character.progression_catalog import (
    ability_catalog,
    blue_spell_catalog,
    key_item_catalog,
    mission_catalog,
    title_catalog,
    visited_zone_catalog,
    weaponskill_unlock_catalog,
)


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

ABILITY_SQL = """
INSERT INTO `abilities` VALUES (16,'mighty_strikes',1,0,1);
INSERT INTO `abilities` VALUES (97,'phantom_roll',17,5,1);
"""

SPELL_SQL = """
INSERT INTO `spell_list` VALUES (512,'not_a_slot_value',0x00);
INSERT INTO `spell_list` VALUES (513,'pollen',0x00);
INSERT INTO `spell_list` VALUES (546,'head_butt',0x00);
INSERT INTO `spell_list` VALUES (767,'last_blue_slot',0x00);
INSERT INTO `spell_list` VALUES (768,'outside_slot_range',0x00);
"""

WS_UNLOCK_LUA = """
xi = xi or {}
xi.wsUnlock =
{
    ASURAN_FISTS = 1,
    WILDFIRE = 48,
    UPHEAVAL = 63,
}
"""

TITLE_LUA = """
xi = xi or {}
xi.title =
{
    FODDERCHIEF_FLAYER = 1,
    CAIT_SITHS_ASSISTANT = 599,
}
"""

ZONE_SQL = """
INSERT INTO `zone_settings` VALUES (0,1,'127.0.0.1',54230,'unknown',0);
INSERT INTO `zone_settings` VALUES (33,2,'127.0.0.1',54230,'AlTaieu',0);
INSERT INTO `zone_settings` VALUES (230,1,'127.0.0.1',54230,'Southern_San_dOria',0);
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

        sql_dir = root / "sql"
        sql_dir.mkdir(parents=True)
        (sql_dir / "abilities.sql").write_text(ABILITY_SQL, encoding="utf-8")
        abilities = ability_catalog(root)
        assert abilities["source"]["kind"] == "abilities.sql"
        assert abilities["items"]["16"]["label"] == "Mighty Strikes"
        assert abilities["items"]["97"]["symbol"] == "PHANTOM_ROLL"

        (sql_dir / "spell_list.sql").write_text(SPELL_SQL, encoding="utf-8")
        blue_spells = blue_spell_catalog(root)
        assert blue_spells["source"]["kind"] == "spell_list.sql"
        assert blue_spells["items"]["513"]["label"] == "Pollen"
        assert blue_spells["items"]["546"]["symbol"] == "HEAD_BUTT"
        assert blue_spells["items"]["767"]["label"] == "Last Blue Slot"
        assert "512" not in blue_spells["items"]
        assert "768" not in blue_spells["items"]

        script_enum = root / "scripts" / "enum"
        script_enum.mkdir(parents=True)
        (script_enum / "ws_unlock.lua").write_text(WS_UNLOCK_LUA, encoding="utf-8")
        ws = weaponskill_unlock_catalog(root)
        assert ws["source"]["kind"] == "ws_unlock.lua"
        assert ws["items"]["1"]["label"] == "Asuran Fists"
        assert ws["items"]["48"]["symbol"] == "WILDFIRE"
        assert ws["items"]["63"]["label"] == "Upheaval"

        (script_enum / "title.lua").write_text(TITLE_LUA, encoding="utf-8")
        titles = title_catalog(root)
        assert titles["source"]["kind"] == "title.lua"
        assert titles["items"]["599"]["label"] == "Cait Siths Assistant"

        (sql_dir / "zone_settings.sql").write_text(ZONE_SQL, encoding="utf-8")
        zones = visited_zone_catalog(root)
        assert zones["source"]["kind"] == "zone_settings.sql"
        assert zones["items"]["33"]["label"] == "AlTaieu"
        assert zones["items"]["230"]["label"] == "Southern San dOria"

        # Never substitute a normal weaponskill table when the explicit unlock-ID enum is absent.
        (script_enum / "ws_unlock.lua").unlink()
        unavailable_ws = weaponskill_unlock_catalog(root)
        assert unavailable_ws["source"]["available"] is False
        assert unavailable_ws["items"] == {}

    missing = mission_catalog(Path("/definitely/not/a/server"))
    assert missing["source"]["available"] is False
    assert missing["areas"] == {}
    missing_blue = blue_spell_catalog(Path("/definitely/not/a/server"))
    assert missing_blue["source"]["available"] is False
    assert missing_blue["items"] == {}


if __name__ == "__main__":
    main()
