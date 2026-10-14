"""Focused synthetic regression for read-only zone mismatch reporting."""
import sqlite3
from pathlib import Path
from workbench.devtools.research.entity_mismatch_report import build_report


def test_zone_mismatch_types(tmp_path: Path):
    db = tmp_path / "index.db"
    with sqlite3.connect(db) as c:
        c.executescript("""
        CREATE TABLE npc_names(npcid INTEGER, name TEXT, zoneid INTEGER);
        CREATE TABLE dsp_npc_list(npcid INTEGER,name TEXT,zoneid INTEGER,pos_x REAL,pos_y REAL,pos_z REAL);
        CREATE TABLE lsb_npc_list(npcid INTEGER,name TEXT,zoneid INTEGER,pos_x REAL,pos_y REAL,pos_z REAL);
        CREATE TABLE dsp_mob_spawn_points(mobid INTEGER,mobname TEXT,pos_x REAL,pos_y REAL,pos_z REAL);
        CREATE TABLE lsb_mob_spawn_points(mobid INTEGER,mobname TEXT,pos_x REAL,pos_y REAL,pos_z REAL);
        """)
        c.executemany("INSERT INTO npc_names VALUES(?,?,?)", [
            (100, "Client_Name", 44), (101, "MissingServer", 44)])
        c.executemany("INSERT INTO dsp_npc_list VALUES(?,?,?,?,?,?)", [
            (100, "Server_Name", 44, 0, 0, 0), (102, "Extra", 44, 1, 2, 3)])
        c.executemany("INSERT INTO lsb_npc_list VALUES(?,?,?,?,?,?)", [
            (100, "Client_Name", 44, 20, 0, 0), (103, "Other", 44, 1, 2, 3)])
    r = build_report(db, 44)
    assert r["coverage"] == {"client":"indexed", "dsp":"indexed", "lsb":"indexed"}
    types = {x["type"] for x in r["rows"]}
    assert {"missing_server", "missing_client", "name_mismatch", "zero_position",
            "server_name_disagreement", "position_disagreement"} <= types
    assert {x["source"] for x in r["rows"] if x["type"] == "position_disagreement"} == {"dsp/lsb"}
    assert all(x["zone"] == 44 for x in r["rows"])
    assert {x["type"] for x in build_report(db, 44, kind="name_mismatch")["rows"]} == {"name_mismatch"}


def test_unindexed_client_is_not_reported_as_missing(tmp_path: Path):
    db = tmp_path / "index.db"
    with sqlite3.connect(db) as c:
        c.executescript("""
        CREATE TABLE npc_names(npcid INTEGER,name TEXT,zoneid INTEGER);
        CREATE TABLE dsp_npc_list(npcid INTEGER,name TEXT,zoneid INTEGER,pos_x REAL,pos_y REAL,pos_z REAL);
        CREATE TABLE dsp_mob_spawn_points(mobid INTEGER,mobname TEXT,pos_x REAL,pos_y REAL,pos_z REAL);
        INSERT INTO dsp_npc_list VALUES(4,'Exists',2,1,2,3);
        """)
    r = build_report(db, 2, sources=("dsp",))
    assert r["coverage"]["client"] == "unavailable_or_empty"
    assert not any(x["type"] == "missing_client" for x in r["rows"])
    assert any(x["type"] == "client_index_unavailable" for x in r["rows"])
