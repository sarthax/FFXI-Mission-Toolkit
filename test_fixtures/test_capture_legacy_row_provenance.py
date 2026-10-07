#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index


LUA_TABLES = """[17000021] = {['id']=17000021, ['name']="Legacy NPC", ['x']=1.0, ['y']=2.0, ['z']=3.0, ['r']=64, ['flags']=1, ['status']=0, ['animation']=0, ['speed']=40},
[17000021] = {['id']=17000021, ['name']="Legacy NPC", ['x']=1.5, ['y']=2.0, ['z']=3.5, ['r']=65, ['flags']=1, ['status']=0, ['animation']=0, ['speed']=40},
"""

LUA_DATABASE = """[17000021] = {['id']=17000021, ['name']="Legacy NPC DB", ['x']=10.0, ['y']=20.0, ['z']=30.0, ['r']=66, ['flags']=2, ['status']=1, ['animation']=1, ['speed']=50},
"""

NPC_PATH = """leg,x,y,z,dir,delta
9,11.0,12.0,13.0,80,100
9,11.5,12.0,13.5,81,200
"""

PC_PATH = """leg,x,y,z,dir,delta
3,21.0,22.0,23.0,90,100
3,21.5,22.0,23.5,91,200
"""

WIDESCAN = """[1] = {['id']=17000031, ['name']="Wide Mob", ['index']=12, ['level']=75}
[2] = {['id']=17000032, ['name']="Wide Mob Two", ['index']=13, ['level']=76}
"""

ATTACK = """Wide Mob (4 hits) - Delay: 240-260
Avg: 250 | Med: 251 | StdDev: 5
Reverse calculation: 240 (3 samples)
Multi-hit: none
Slots/rnd: 1
Wide Mob Two (5 hits) - Delay: 300-340
Avg: 320 | Med: 321 | StdDev: 7
Reverse calculation: 310 (4 samples)
Multi-hit: double
Slots/rnd: 2
"""


def write(root: Path, rel: str, text: str) -> bytes:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = text.encode("utf-8")
    p.write_bytes(payload)
    return payload


def locators(con, cid, filename, table):
    return con.execute(
        """SELECT row_key,source_sha256,locator_basis,start_line,end_line,start_offset,end_offset,details_json
           FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table=?
           ORDER BY start_line,row_key""",
        (cid, filename, table),
    ).fetchall()


def test_old_path_pk_migration(root: Path):
    db = root / "legacy_schema.db"
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE capture_npc_path (
        capture_id INTEGER, zone_db TEXT, entity_id INTEGER, leg INTEGER, step INTEGER,
        x REAL, y REAL, z REAL, dir INTEGER, delta INTEGER,
        PRIMARY KEY (capture_id, zone_db, entity_id, step)
    )""")
    con.execute(
        "INSERT INTO capture_npc_path VALUES (?,?,?,?,?,?,?,?,?,?)",
        (99, "Legacy Zone", 17009999, 2, 0, 1.0, 2.0, 3.0, 64, 0),
    )
    con.commit()
    build_capture_index.init_db(con)
    pk = [
        row[1] for row in sorted(
            (row for row in con.execute("PRAGMA table_info(capture_npc_path)") if row[5]),
            key=lambda row: row[5],
        )
    ]
    assert pk == ["capture_id", "zone_db", "entity_id", "leg", "step"], pk
    preserved = con.execute(
        "SELECT leg,x,y,z FROM capture_npc_path WHERE capture_id=99"
    ).fetchone()
    assert preserved == (2, 1.0, 2.0, 3.0), preserved
    con.close()


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        test_old_path_pk_migration(root)

        source = root / "source"
        payloads = {
            "npclogger/Tester/tables/Test Zone.lua": write(
                source, "npclogger/Tester/tables/Test Zone.lua", LUA_TABLES
            ),
            "npclogger/Tester/database/Test Zone.lua": write(
                source, "npclogger/Tester/database/Test Zone.lua", LUA_DATABASE
            ),
            "PathLog/Tester/Test_Zone/Path_NPC/17000041.csv": write(
                source, "PathLog/Tester/Test_Zone/Path_NPC/17000041.csv", NPC_PATH
            ),
            "PathLog/Tester/PC_Test_Zone.csv": write(
                source, "PathLog/Tester/PC_Test_Zone.csv", PC_PATH
            ),
            "npclogger/widescan/Test Zone.log": write(
                source, "npclogger/widescan/Test Zone.log", WIDESCAN
            ),
            "AttackDelay/Test_Zone.log": write(
                source, "AttackDelay/Test_Zone.log", ATTACK
            ),
        }

        con = sqlite3.connect(root / "capture.db")
        build_capture_index.init_db(con)
        cid = build_capture_index.ingest(con, str(source), content_type="overworld")

        # The corrected PK must retain both legacy Lua source legs for the same entity/step.
        legs = con.execute(
            """SELECT leg,step,x,z FROM capture_npc_path
               WHERE capture_id=? AND zone_db='Test Zone' AND entity_id=17000021
               ORDER BY leg,step""",
            (cid,),
        ).fetchall()
        assert legs == [
            (1, 0, 1.0, 3.0), (1, 1, 1.5, 3.5), (2, 0, 10.0, 30.0)
        ], legs

        # NPCLogger Lua rows: every path sample has its exact source line; the normalized
        # current-entry locator in each source points at that source's last-seen snapshot.
        table_rel = "npclogger/Tester/tables/Test Zone.lua"
        db_rel = "npclogger/Tester/database/Test Zone.lua"
        table_path = locators(con, cid, table_rel, "capture_npc_path")
        table_entry = locators(con, cid, table_rel, "capture_npc_entries")
        db_path = locators(con, cid, db_rel, "capture_npc_path")
        assert len(table_path) == 2 and len(table_entry) == 1 and len(db_path) == 1
        assert [json.loads(r[0])["leg"] for r in table_path] == [1, 1]
        assert json.loads(db_path[0][0])["leg"] == 2
        assert table_entry[0][3:5] == (2, 2), table_entry

        # CSV rows preserve the physical row after the header and exact byte slice.
        npc_rel = "PathLog/Tester/Test_Zone/Path_NPC/17000041.csv"
        pc_rel = "PathLog/Tester/PC_Test_Zone.csv"
        npc_rows = locators(con, cid, npc_rel, "capture_npc_path")
        pc_rows = locators(con, cid, pc_rel, "capture_pc_path")
        assert len(npc_rows) == 2 and all(r[2] == "csv-row" for r in npc_rows)
        assert len(pc_rows) == 2 and all(r[2] == "csv-row" for r in pc_rows)
        assert [r[3] for r in npc_rows] == [2, 3], npc_rows
        assert [r[3] for r in pc_rows] == [2, 3], pc_rows
        assert payloads[npc_rel][npc_rows[0][5]:npc_rows[0][6]].decode().startswith("9,11.0")
        assert payloads[pc_rel][pc_rows[1][5]:pc_rows[1][6]].decode().startswith("3,21.5")

        # Widescan owns both normalized rows only when it really inserted/replaced them.
        wide_rel = "npclogger/widescan/Test Zone.log"
        wide_entries = locators(con, cid, wide_rel, "capture_npc_entries")
        wide_levels = locators(con, cid, wide_rel, "capture_level_range")
        assert len(wide_entries) == 2 and len(wide_levels) == 2
        assert all(r[2] == "line" for r in wide_entries + wide_levels)
        assert json.loads(wide_levels[0][7])["level"] == 75

        # AttackDelay uses exact header-delimited blocks, not a fabricated single-line locator.
        attack_rel = "AttackDelay/Test_Zone.log"
        attack_rows = locators(con, cid, attack_rel, "capture_attack_delay")
        assert len(attack_rows) == 2 and all(r[2] == "block" for r in attack_rows)
        first_block = payloads[attack_rel][attack_rows[0][5]:attack_rows[0][6]].decode()
        second_block = payloads[attack_rel][attack_rows[1][5]:attack_rows[1][6]].decode()
        assert first_block.startswith("Wide Mob (4 hits)") and "Reverse calculation: 240" in first_block
        assert second_block.startswith("Wide Mob Two (5 hits)") and "Multi-hit: double" in second_block

        # Every locator points back to the exact current source hash.
        for rel, table in [
            (table_rel, "capture_npc_path"),
            (db_rel, "capture_npc_path"),
            (npc_rel, "capture_npc_path"),
            (pc_rel, "capture_pc_path"),
            (wide_rel, "capture_level_range"),
            (attack_rel, "capture_attack_delay"),
        ]:
            digest = hashlib.sha256(payloads[rel]).hexdigest()
            assert all(row[1] == digest for row in locators(con, cid, rel, table))

        inventory = {
            row["filename"]: row
            for row in build_capture_index.capture_rebuild_inventory(con, cid)
        }
        assert inventory[npc_rel]["rebuildable"], inventory[npc_rel]
        assert inventory[pc_rel]["rebuildable"], inventory[pc_rel]
        assert inventory[wide_rel]["rebuildable"], inventory[wide_rel]
        assert inventory[attack_rel]["rebuildable"], inventory[attack_rel]
        # Both Lua files write the same current-state capture_npc_entries row, so rebuilding one
        # in isolation is intentionally refused even though their path-leg rows are independent.
        assert not inventory[table_rel]["rebuildable"], inventory[table_rel]
        assert "ownership" in inventory[table_rel]["reason"] or "overlap" in inventory[table_rel]["reason"]

        # Safe rebuild restores corrupted parser-owned rows from unchanged source bytes.
        con.execute(
            """UPDATE capture_attack_delay SET delay_avg=-1
               WHERE capture_id=? AND zone_db='Test Zone' AND mob_name='Wide Mob'""",
            (cid,),
        )
        con.execute(
            """UPDATE capture_pc_path SET x=-999
               WHERE capture_id=? AND zone_db='Test Zone' AND step=0""",
            (cid,),
        )
        con.commit()
        assert build_capture_index.rebuild_capture_source(con, cid, attack_rel)["rows"] == 2
        assert build_capture_index.rebuild_capture_source(con, cid, pc_rel)["rows"] == 2
        assert con.execute(
            """SELECT delay_avg FROM capture_attack_delay
               WHERE capture_id=? AND zone_db='Test Zone' AND mob_name='Wide Mob'""",
            (cid,),
        ).fetchone()[0] == 250
        assert con.execute(
            """SELECT x FROM capture_pc_path
               WHERE capture_id=? AND zone_db='Test Zone' AND step=0""",
            (cid,),
        ).fetchone()[0] == 21.0

        con.close()

    print("Legacy capture row provenance regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
