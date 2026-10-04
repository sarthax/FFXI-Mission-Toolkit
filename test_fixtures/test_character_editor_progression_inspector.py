from __future__ import annotations

from pathlib import Path
import shutil

from workbench.devtools.features.state_surface_scoped import build_state_surface
from workbench.editors.character.progression_inspector import build_progression_inspector


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "test_fixtures" / "fixtures"


def _server_with(tmp_path: Path, fixture_name: str) -> Path:
    root = tmp_path / "server"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(FIX / fixture_name, scripts / fixture_name)
    return root


def _quest_catalog(*rows: tuple[int, int, str, str]) -> dict:
    areas: dict[str, dict[str, dict]] = {}
    for area_id, entry_id, symbol, label in rows:
        areas.setdefault(str(area_id), {})[str(entry_id)] = {
            "id": entry_id,
            "symbol": symbol,
            "label": label,
        }
    return {"areas": areas}


def _mission_catalog(*rows: tuple[int, int, str, str]) -> dict:
    return _quest_catalog(*rows)


def test_fires_prog_three_identifies_grauberg_event_as_next_progression(tmp_path: Path):
    root = _server_with(tmp_path, "lsb_wotg_bastok2_fires_of_discontent.lua")
    surface = build_state_surface(
        root,
        kind="quest",
        area_id=7,
        entry_id=13,
        symbol="FIRES_OF_DISCONTENT",
        label="Fires of Discontent",
    )
    packed = {
        "quest": {7: {"current": {13}, "completed": set()}},
        "mission": {},
        "key_items": {},
    }
    inspector = build_progression_inspector(
        surface,
        root,
        variables={"Quest[7][13]Prog": 3},
        packed=packed,
        mission_catalog=_mission_catalog(),
        quest_catalog=_quest_catalog(
            (7, 13, "FIRES_OF_DISCONTENT", "Fires of Discontent"),
            (7, 12, "BETTER_PART_OF_VALOR", "Better Part of Valor"),
        ),
    )

    assert inspector["available"] is True
    assert inspector["status"] == "QUEST_ACCEPTED"
    assert inspector["diagnosis"] == "CURRENT"
    assert inspector["current_step"]["section_index"] == 2
    assert {row["key"]: row["value"] for row in inspector["feature_vars"]}["Prog"] == 3
    primary = inspector["primary_action"]
    assert primary is not None
    assert primary["event"] == {"zone": "GRAUBERG_S", "actor": "qm5", "event_id": 11}
    assert any(
        effect["effect"] in {"SET_VAR", "SET_CHANNEL"}
        and effect["subject"] == "quest_var:Prog"
        and int(effect["value"]) == 4
        for effect in primary["effects"]
    ), primary


def test_light_prog_three_identifies_zone_in_progression(tmp_path: Path):
    root = _server_with(tmp_path, "lsb_wotg_bastok3_light_in_the_darkness.lua")
    surface = build_state_surface(
        root,
        kind="quest",
        area_id=7,
        entry_id=19,
        symbol="LIGHT_IN_THE_DARKNESS",
        label="Light in the Darkness",
    )
    packed = {
        "quest": {7: {"current": {19}, "completed": {13}}},
        "mission": {5: {"current": 3, "completed": {1}}},
        "key_items": {"MINE_SHAFT_KEY": True},
    }
    inspector = build_progression_inspector(
        surface,
        root,
        variables={"Quest[7][19]Prog": 3},
        packed=packed,
        mission_catalog=_mission_catalog((5, 1, "BACK_TO_THE_BEGINNING", "Back to the Beginning")),
        quest_catalog=_quest_catalog(
            (7, 13, "FIRES_OF_DISCONTENT", "Fires of Discontent"),
            (7, 19, "LIGHT_IN_THE_DARKNESS", "Light in the Darkness"),
        ),
    )

    assert inspector["diagnosis"] == "CURRENT"
    assert inspector["current_step"]["section_index"] == 5
    primary = inspector["primary_action"]
    assert primary is not None
    assert primary["event"]["zone"] == "PASHHOW_MARSHLANDS_S"
    assert primary["event"]["event_id"] == 901
    assert any(
        effect["subject"] == "quest_var:Prog" and int(effect["value"]) == 4
        for effect in primary["effects"]
    ), primary


def test_cait_sith_current_mission_identifies_event_67_completion(tmp_path: Path):
    root = _server_with(tmp_path, "lsb_wotg03_cait_sith.lua")
    surface = build_state_surface(
        root,
        kind="mission",
        area_id=5,
        entry_id=2,
        symbol="CAIT_SITH",
        label="Cait Sith",
    )
    packed = {
        "quest": {},
        "mission": {5: {"current": 2, "completed": set()}},
        "key_items": {"LIGHTSWORM": False},
    }
    inspector = build_progression_inspector(
        surface,
        root,
        variables={},
        packed=packed,
        mission_catalog=_mission_catalog((5, 2, "CAIT_SITH", "Cait Sith")),
        quest_catalog=_quest_catalog(),
    )

    assert inspector["status"] == "MISSION_CURRENT"
    assert inspector["diagnosis"] == "CURRENT"
    primary = inspector["primary_action"]
    assert primary is not None
    assert primary["event"] == {"zone": "SOUTHERN_SAN_DORIA_S", "actor": None, "event_id": 67}
    assert any(effect["effect"] == "COMPLETE" for effect in primary["effects"]), primary


def test_completed_target_is_not_presented_as_current_step(tmp_path: Path):
    root = _server_with(tmp_path, "lsb_wotg_bastok2_fires_of_discontent.lua")
    surface = build_state_surface(
        root,
        kind="quest",
        area_id=7,
        entry_id=13,
        symbol="FIRES_OF_DISCONTENT",
        label="Fires of Discontent",
    )
    inspector = build_progression_inspector(
        surface,
        root,
        variables={},
        packed={"quest": {7: {"current": set(), "completed": {13}}}, "mission": {}, "key_items": {}},
        mission_catalog=_mission_catalog(),
        quest_catalog=_quest_catalog((7, 13, "FIRES_OF_DISCONTENT", "Fires of Discontent")),
    )
    assert inspector["status"] == "QUEST_COMPLETED"
    assert inspector["diagnosis"] == "COMPLETED"
    assert inspector["current_step"] is None
    assert inspector["primary_action"] is None
