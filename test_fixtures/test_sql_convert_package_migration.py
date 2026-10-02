from __future__ import annotations

import importlib
import importlib.util
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_root(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return sys.modules[name]


def main() -> None:
    canonical = importlib.import_module("workbench.packages.migration.sql_convert")
    from workbench.runtime.paths import DATA_ROOT

    legacy = _load_root("backport_sql_convert", REPO_ROOT / "backport_sql_convert.py")
    assert legacy is canonical
    assert canonical.MAP_PATH == DATA_ROOT / "dsp_sql_schema_map.json"

    schema = canonical.load_schema_map()
    assert "npc_list" in schema

    row = [
        "100", "'Test_NPC'", "'Test NPC'", "0", "1", "2", "3", "0", "40", "40",
        "0", "0", "0", "0", "0", "'0x00'", "0", "'TEST'", "0",
    ]
    result = canonical.convert_table("npc_list", [row], schema)
    assert "INSERT INTO `npc_list`" in result.converted_sql
    assert result.converted_ids == ["100"]
    assert result.id_to_name == {100: "Test_NPC"}

    unknown = canonical.convert_table("not_a_real_table", [["1"]], schema)
    assert unknown.warnings and unknown.warnings[0]["reason"] == "no schema mapping"
    assert "SQL-PORT-TODO" in unknown.converted_sql

    malformed = canonical.convert_table("npc_list", [["100"]], schema)
    assert any("expected" in warning["reason"] for warning in malformed.warnings)

    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE dsp_npc_list (npcid INTEGER PRIMARY KEY, name TEXT)")
    con.execute("INSERT INTO dsp_npc_list VALUES (100, 'Test_NPC')")
    con.execute("INSERT INTO dsp_npc_list VALUES (101, 'Other_NPC')")
    same = canonical.check_id_collisions(con, "npc_list", ["100"], schema, {100: "Test_NPC"})
    assert len(same["same_entity"]) == 1
    mismatch = canonical.check_id_collisions(con, "npc_list", ["101"], schema, {101: "Wanted_NPC"})
    assert len(mismatch["name_mismatch"]) == 1
    con.close()

    code = (
        "from workbench.packages.migration import sql_convert; "
        "from workbench.runtime.paths import DATA_ROOT; "
        "assert sql_convert.MAP_PATH == DATA_ROOT / 'dsp_sql_schema_map.json'; "
        "print(sql_convert.load_schema_map()['npc_list']['id_column'])"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tempfile.gettempdir(), check=True)


if __name__ == "__main__":
    main()
