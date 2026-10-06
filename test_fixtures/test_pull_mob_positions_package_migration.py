from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_root_launcher_is_retired():
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "pull_mob_positions.py").exists()


def test_csv_and_lua_capture_discovery(tmp_path: Path):
    mod = importlib.import_module("workbench.devtools.spatial.pull_mob_positions")

    csv_path = tmp_path / "PathLog" / "session" / "Zone" / "Mob" / "123.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text("x,y,z,dir\n1.5,2.5,3.5,64\n", encoding="utf-8")
    assert mod.find_csv(tmp_path, 123) == csv_path

    lua_path = tmp_path / "npclogger" / "database" / "Zone.lua"
    lua_path.parent.mkdir(parents=True)
    lua_path.write_text(
        "[456] = { ['x']=-1.25, ['y']=2.0, ['z']=3.75, ['r']=128, ['name']='Mob' },\n",
        encoding="utf-8",
    )
    assert mod.find_in_lua_dbs(tmp_path, {456}) == {456: (-1.25, 2.0, 3.75, 128)}


def test_apply_updates_only_temporary_sql(monkeypatch, tmp_path: Path, capsys):
    mod = importlib.import_module("workbench.devtools.spatial.pull_mob_positions")

    sql_path = tmp_path / "mob_spawn_points.sql"
    sql_path.write_text(
        "INSERT INTO `mob_spawn_points` VALUES (123,'Mob','Mob',99,0,0,0,0);\n",
        encoding="utf-8",
    )
    capture = tmp_path / "capture"
    csv_path = capture / "PathLog" / "session" / "Zone" / "Mob" / "123.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text("x,y,z,dir\n10.0,20.0,30.0,7\n", encoding="utf-8")

    monkeypatch.setattr(mod, "SQL_PATH", sql_path)
    monkeypatch.setattr(sys, "argv", ["pull_mob_positions.py", str(capture), "123", "--apply"])
    mod.main()

    text = sql_path.read_text(encoding="utf-8")
    assert "(123,'Mob','Mob',99,10.0,20.0,30.0,7);" in text
    assert "Applied 1 fixes" in capsys.readouterr().out
