from __future__ import annotations

from pathlib import Path
import shutil

from workbench.devtools.features.state_surface_scoped import build_state_surface


ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "test_fixtures" / "fixtures"


def _server_with(tmp_path: Path, *fixture_names: str) -> Path:
    root = tmp_path / "server"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for name in fixture_names:
        shutil.copy2(FIX / name, scripts / name)
    return root


def _paths(surface: dict) -> set[str]:
    return {str(row.get("source_path")) for row in surface.get("references", ())}


def _refs(surface: dict, state_type: str) -> list[dict]:
    return [row for row in surface.get("references", ()) if row.get("state_type") == state_type]


def test_fires_of_discontent_trace_is_exact_feature_not_symbol_grep(tmp_path: Path):
    root = _server_with(
        tmp_path,
        "lsb_wotg_bastok2_fires_of_discontent.lua",
        "lsb_wotg_bastok3_light_in_the_darkness.lua",
        "lsb_wotg02_back_to_the_beginning.lua",
        "lsb_wotg_helpers_prereq.lua",
    )
    surface = build_state_surface(
        root,
        kind="quest",
        area_id=7,
        entry_id=13,
        symbol="FIRES_OF_DISCONTENT",
        label="Fires of Discontent",
    )

    assert surface["summary"]["selection_mode"] == "exact_lsb_definition"
    assert surface["summary"]["scripts_returned"] == 1
    assert surface["files"][0]["path"].endswith("lsb_wotg_bastok2_fires_of_discontent.lua")
    assert _paths(surface) == {"scripts/lsb_wotg_bastok2_fires_of_discontent.lua"}

    # The previous checkout-wide scan also matched Light in the Darkness, the WotG helper file,
    # and even a Back to the Beginning comment because all contained this symbol.
    assert not any("light_in_the_darkness" in path for path in _paths(surface))
    assert not any("helpers_prereq" in path for path in _paths(surface))
    assert not any("back_to_the_beginning" in path for path in _paths(surface))

    prog = _refs(surface, "quest_var")
    required = {row.get("expectation_value") for row in prog if row.get("operation") == "require"}
    written = {str(row.get("value")) for row in prog if row.get("operation") == "set"}
    assert {"0", "1", "2", "3", "4", "5", "6"} <= required | written
    assert {"1", "2", "3", "4", "5", "6"} <= written

    events = {row.get("key") for row in _refs(surface, "event")}
    assert {"11", "120", "122", "124", "126", "160", "164", "956"} <= events
    assert any(
        row.get("state_type") == "quest"
        and "BETTER_PART_OF_VALOR" in str(row.get("key"))
        for row in surface["references"]
    )
    assert any(
        row.get("state_type") == "quest"
        and row.get("key") == "FIRES_OF_DISCONTENT"
        and row.get("operation") == "complete"
        for row in surface["references"]
    )


def test_light_in_the_darkness_trace_keeps_real_prerequisites_and_side_effects(tmp_path: Path):
    root = _server_with(
        tmp_path,
        "lsb_wotg_bastok2_fires_of_discontent.lua",
        "lsb_wotg_bastok3_light_in_the_darkness.lua",
        "lsb_wotg02_back_to_the_beginning.lua",
        "lsb_wotg_helpers_prereq.lua",
    )
    surface = build_state_surface(
        root,
        kind="quest",
        area_id=7,
        entry_id=19,
        symbol="LIGHT_IN_THE_DARKNESS",
        label="Light in the Darkness",
    )

    assert _paths(surface) == {"scripts/lsb_wotg_bastok3_light_in_the_darkness.lua"}
    assert any(
        row.get("state_type") == "mission" and "BACK_TO_THE_BEGINNING" in str(row.get("key"))
        for row in surface["references"]
    )
    assert any(
        row.get("state_type") == "quest" and "FIRES_OF_DISCONTENT" in str(row.get("key"))
        for row in surface["references"]
    )
    assert any(
        row.get("state_type") == "key_item"
        and row.get("key") == "MINE_SHAFT_KEY"
        and row.get("operation") == "grant"
        for row in surface["references"]
    )
    assert any(
        row.get("state_type") == "quest_var"
        and row.get("key") == "Prog"
        and row.get("operation") == "set"
        and str(row.get("value")) == "6"
        for row in surface["references"]
    )
    events = {row.get("key") for row in _refs(surface, "event")}
    assert {"16", "19", "21", "23", "27", "901", "902"} <= events


def test_cait_sith_trace_stays_on_mission_definition(tmp_path: Path):
    root = _server_with(
        tmp_path,
        "lsb_wotg03_cait_sith.lua",
        "lsb_wotg_bastok3_light_in_the_darkness.lua",
        "lsb_wotg02_back_to_the_beginning.lua",
    )
    surface = build_state_surface(
        root,
        kind="mission",
        area_id=5,
        entry_id=2,
        symbol="CAIT_SITH",
        label="Cait Sith",
    )

    assert surface["summary"]["selection_mode"] == "exact_lsb_definition"
    assert _paths(surface) == {"scripts/lsb_wotg03_cait_sith.lua"}
    assert any(
        row.get("state_type") == "key_item"
        and row.get("key") == "LIGHTSWORM"
        and row.get("operation") == "grant"
        for row in surface["references"]
    )
    assert any(
        row.get("state_type") == "mission"
        and row.get("key") == "CAIT_SITH"
        and row.get("operation") == "complete"
        for row in surface["references"]
    )
    assert any(row.get("state_type") == "event" and row.get("key") == "67" for row in surface["references"])
    # Light in the Darkness contains a TODO comment mentioning Cait Sith; it must not contaminate
    # the mission's primary trace surface.
    assert not any("light_in_the_darkness" in path for path in _paths(surface))
