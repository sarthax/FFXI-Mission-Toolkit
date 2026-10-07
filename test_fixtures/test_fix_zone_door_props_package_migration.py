from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_root_launcher_is_retired():
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "fix_zone_door_props.py").exists()


def test_loaders_use_configured_repository_data_paths(monkeypatch, tmp_path: Path):
    mod = importlib.import_module("workbench.devtools.spatial.fix_zone_door_props")

    entities = tmp_path / "Entities"
    entities.mkdir()
    (entities / "55.json").write_text(
        json.dumps({"entities": [{"serverID": 100}, {"serverID": 101}]}),
        encoding="utf-8",
    )
    doors = tmp_path / "Door or Objects.json"
    doors.write_text(
        json.dumps([
            {"ZoneId": 55, "Identifier": "_abc", "X": 1.0, "Y": 2.0, "Z": 3.0},
            {"ZoneId": 56, "Identifier": "_def", "X": 4.0, "Y": 5.0, "Z": 6.0},
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "ENTITIES_DIR", entities)
    monkeypatch.setattr(mod, "DOOR_JSON_PATH", doors)

    assert mod.load_valid_ids(55) == {100, 101}
    assert mod.load_valid_ids(99) == set()
    assert [row["Identifier"] for row in mod.load_door_props(55)] == ["_abc"]


def test_apply_writes_only_temporary_sql(monkeypatch, tmp_path: Path):
    mod = importlib.import_module("workbench.devtools.spatial.fix_zone_door_props")

    sql_path = tmp_path / "npc_list.sql"
    sql_path.write_text(
        "INSERT INTO `npc_list` VALUES (100,'_old','_old',0,0,0,0,0);\n",
        encoding="utf-8",
    )
    entities = tmp_path / "Entities"
    entities.mkdir()
    (entities / "55.json").write_text(json.dumps({"entities": [{"serverID": 100}]}), encoding="utf-8")
    doors = tmp_path / "Door or Objects.json"
    doors.write_text(
        json.dumps([{"ZoneId": 55, "Identifier": "_new", "X": 1.0, "Y": 2.0, "Z": 3.0}]),
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "NPC_LIST_PATH", sql_path)
    monkeypatch.setattr(mod, "ENTITIES_DIR", entities)
    monkeypatch.setattr(mod, "DOOR_JSON_PATH", doors)
    monkeypatch.setattr("sys.argv", ["fix_zone_door_props.py", "55", "--apply"])

    mod.main()
    text = sql_path.read_text(encoding="utf-8")
    assert "(100,'_new','_new',0,1.0000,2.0000,3.0000," in text
