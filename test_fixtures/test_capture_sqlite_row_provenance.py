#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index


def make_npclogger(path: Path):
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE entries (
        UniqueNo INTEGER, Name TEXT, model_id INTEGER, x REAL, y REAL, z REAL, dir INTEGER, Hpp INTEGER,
        legacy_flags INTEGER, legacy_status INTEGER, legacy_animation INTEGER, Speed INTEGER,
        created_at INTEGER, updated_at INTEGER, legacy_look TEXT, DoorId INTEGER, ActIndex INTEGER,
        Flags0 INTEGER, Flags1 INTEGER, Flags2 INTEGER, Flags3 INTEGER, legacy_flag INTEGER, SubKind INTEGER
    )""")
    con.execute("""INSERT INTO entries VALUES
        (17000001,'Test NPC',1234,1.0,2.0,3.0,64,100,1,2,3,40,10,20,'0000D204',777,8,11,12,13,14,15,16)""")
    con.execute("CREATE TABLE history (id INTEGER, entry_id TEXT, time INTEGER, delta TEXT)")
    con.execute(
        "INSERT INTO history VALUES (?,?,?,?,?)".replace("(?,?,?,?,?)","(?,?,?,?)"),
        (7, "17000001-test", 123456, '{"x":1.5,"z":3.5}'),
    )
    con.commit()
    con.close()


def make_actionview(path: Path):
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE entries (
        id INTEGER, actor INTEGER, actor_name TEXT, ActionType TEXT, animation INTEGER,
        category INTEGER, message INTEGER, name TEXT, updated_at INTEGER
    )""")
    con.execute(
        "INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?)",
        (55, 17000002, "Test Mob", "ability", 330, 4, 31, "Doton: Ni", 999),
    )
    con.commit()
    con.close()


def make_levelrange(path: Path):
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE entries (
        UniqueNo INTEGER, sName TEXT, Level_min INTEGER, Level_max INTEGER, ActIndex INTEGER
    )""")
    con.execute("INSERT INTO entries VALUES (?,?,?,?,?)", (17000003, "Level Mob", 74, 76, 21))
    con.commit()
    con.close()


def rows(con, cid, filename, table):
    return con.execute(
        """SELECT row_key,source_sha256,locator_basis,start_line,end_line,start_offset,end_offset,details_json
           FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table=?
           ORDER BY row_key""",
        (cid, filename, table),
    ).fetchall()


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "NPCLogger").mkdir()
        (root / "ActionView" / "Tester").mkdir(parents=True)
        (root / "LevelRangeTrack").mkdir()
        npc_rel = "NPCLogger/Test Zone.db"
        act_rel = "ActionView/Tester/Actions.db"
        lvl_rel = "LevelRangeTrack/Test Zone.db"
        make_npclogger(root / npc_rel)
        make_actionview(root / act_rel)
        make_levelrange(root / lvl_rel)

        con = sqlite3.connect(root / "capture.db")
        build_capture_index.init_db(con)
        cid = build_capture_index.create_manual_capture(con, "sqlite provenance", "Research", None)
        src = build_capture_index.Source(root)
        try:
            assert build_capture_index.ingest_npc_db(con, cid, src, npc_rel) == (1, 1)
            assert build_capture_index.ingest_actions_db(con, cid, src, act_rel) == 1
            assert build_capture_index.ingest_level_range_db(con, cid, src, lvl_rel) == 1
        finally:
            src.close()

        npc_entry = rows(con, cid, npc_rel, "capture_npc_entries")
        npc_hist = rows(con, cid, npc_rel, "capture_npc_history")
        action = rows(con, cid, act_rel, "capture_actions")
        level = rows(con, cid, lvl_rel, "capture_level_range")
        assert len(npc_entry) == len(npc_hist) == len(action) == len(level) == 1

        for group, rel in [
            (npc_entry, npc_rel), (npc_hist, npc_rel), (action, act_rel), (level, lvl_rel)
        ]:
            row = group[0]
            assert row[2] == "sqlite-row", row
            assert row[3:7] == (None, None, None, None), row
            expected = hashlib.sha256((root / rel).read_bytes()).hexdigest()
            assert row[1] == expected, (row[1], expected)
            details = json.loads(row[7])
            assert details["source_table"] in {"entries", "history"}
            assert isinstance(details["source_rowid"], int) and details["source_rowid"] >= 1

        assert json.loads(npc_entry[0][0]) == {"entity_id": 17000001, "zone_db": "Test Zone"}
        assert json.loads(npc_hist[0][0]) == {
            "entity_id": 17000001, "seq": 7, "zone_db": "Test Zone"
        }
        assert json.loads(action[0][0]) == {"action_key": "17000002-55"}
        assert json.loads(level[0][0]) == {"entity_id": 17000003, "zone_db": "Test Zone"}

        assert json.loads(npc_entry[0][7])["UniqueNo"] == 17000001
        assert json.loads(npc_hist[0][7])["source_id"] == 7
        assert json.loads(action[0][7])["source_id"] == 55
        assert json.loads(level[0][7])["UniqueNo"] == 17000003

        # Re-ingestion replaces locators rather than duplicating them.
        src = build_capture_index.Source(root)
        try:
            build_capture_index.ingest_npc_db(con, cid, src, npc_rel)
            build_capture_index.ingest_actions_db(con, cid, src, act_rel)
            build_capture_index.ingest_level_range_db(con, cid, src, lvl_rel)
        finally:
            src.close()
        assert len(rows(con, cid, npc_rel, "capture_npc_entries")) == 1
        assert len(rows(con, cid, npc_rel, "capture_npc_history")) == 1
        assert len(rows(con, cid, act_rel, "capture_actions")) == 1
        assert len(rows(con, cid, lvl_rel, "capture_level_range")) == 1

        con.close()

    print("Capture SQLite row provenance regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
