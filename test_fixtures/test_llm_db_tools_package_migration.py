from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from workbench.devtools.research.legacy_llm import db_tools as canonical


def _make_db(path):
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
        con.executemany("INSERT INTO sample(name) VALUES (?)", [("alpha",), ("beta",)])
        con.commit()
    finally:
        con.close()


def test_root_module_is_retired_and_packaged_tools_are_canonical():
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "llm_db_tools.py").exists()
    assert canonical.TOOLS


def test_packaged_tools_use_runtime_database_path_and_remain_read_only(tmp_path, monkeypatch):
    db_path = tmp_path / "fixture.db"
    _make_db(db_path)
    monkeypatch.setattr(canonical, "DATABASE_PATH", db_path)

    assert canonical.list_tables() == {"tables": {"sample": 2}}
    assert canonical.describe_table("sample")["columns"] == [
        {"name": "id", "type": "INTEGER"},
        {"name": "name", "type": "TEXT"},
    ]
    assert canonical.query_sql("SELECT id, name FROM sample ORDER BY id") == {
        "columns": ["id", "name"],
        "rows": [[1, "alpha"], [2, "beta"]],
        "truncated": False,
    }
    rejected = canonical.query_sql("SELECT * FROM sample; DELETE FROM sample")
    assert "single SQL statement" in rejected["error"]

    con = canonical._readonly_connection()
    try:
        with pytest.raises(sqlite3.OperationalError):
            con.execute("INSERT INTO sample(name) VALUES ('blocked')")
    finally:
        con.close()


def test_verified_relationship_text_is_preserved():
    relationships = canonical._relationships_for("dsp_instance_entities")
    notes = {item["from"]: item["note"] for item in relationships}
    assert "don't trust an unmatched instanceid as evidence of absence" in notes["dsp_instance_entities.instanceid"]
    assert "distinct real matches against both npc_list.npcid and mob_spawn_points.mobid" in notes["dsp_instance_entities.id"]
