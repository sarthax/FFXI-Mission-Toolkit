from __future__ import annotations

import importlib
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    sql_convert = importlib.import_module("workbench.packages.migration.sql_convert")
    assert not (REPO_ROOT / "backport_sql_convert.py").exists()

    real_map = sql_convert.load_schema_map()
    assert "npc_list" in real_map
    assert "mob_groups" in real_map

    parsed = sql_convert.parse_insert_values(
        "-- INSERT INTO demo VALUES (0, 'ignored');\n"
        "INSERT INTO demo VALUES (1, 'alpha'), (2, 'beta');\n"
    )
    assert parsed == [("demo", ["1", "'alpha'"]), ("demo", ["2", "'beta'"])]

    demo_map = {
        "demo": {
            "topaz_columns": ["id", "name"],
            "dsp_columns": ["id", "name"],
            "dropped_from_topaz": [],
            "added_by_dsp": [],
            "id_column": "id",
            "name_column": "name",
        }
    }
    converted = sql_convert.convert_table("demo", [row for _table, row in parsed], demo_map)
    assert converted.converted_ids == ["1", "2"]
    assert converted.id_to_name == {1: "alpha", 2: "beta"}
    assert "INSERT INTO `demo` (`id`, `name`) VALUES (1, 'alpha');" in converted.converted_sql

    unmapped = sql_convert.convert_table("unknown_table", [["1"]], demo_map)
    assert unmapped.warnings[0]["reason"] == "no schema mapping"
    assert "SQL-PORT-TODO" in unmapped.converted_sql

    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE TABLE dsp_npc_list (npcid INTEGER, name TEXT)")
        con.executemany(
            "INSERT INTO dsp_npc_list (npcid, name) VALUES (?, ?)",
            [(100, "Same"), (200, "Other")],
        )
        collision_map = {"npc_list": {"id_column": "npcid", "name_column": "name"}}
        checked = sql_convert.check_id_collisions(
            con,
            "npc_list",
            ["100", "200", "300"],
            collision_map,
            id_to_name={100: "Same", 200: "Expected", 300: "Missing"},
        )
        assert checked["same_entity"] == [{"id": 100, "name": "Same"}]
        assert checked["name_mismatch"] == [
            {"id": 200, "dsp_name": "Other", "topaz_name": "Expected"}
        ]
    finally:
        con.close()

    code = (
        "from workbench.packages.migration import sql_convert; "
        "print('mob_groups' in sql_convert.load_schema_map())"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)


if __name__ == "__main__":
    main()
