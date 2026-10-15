"""Synthetic source/zone/identity guard regressions for live reconciliation."""
import sqlite3

import pytest

from workbench.devtools.research.entity_live_reconciliation import reconcile_reported_id


def _db(tmp_path):
    db = tmp_path / "entities.db"
    with sqlite3.connect(db) as con:
        con.executescript("""
        CREATE TABLE dsp_npc_list(npcid INTEGER,name TEXT,zoneid INTEGER);
        CREATE TABLE dsp_mob_spawn_points(mobid INTEGER,mobname TEXT);
        CREATE TABLE lsb_npc_list(npcid INTEGER,name TEXT,zoneid INTEGER);
        CREATE TABLE lsb_mob_spawn_points(mobid INTEGER,mobname TEXT);
        """)
    return db


def test_exact_zone_source_and_ambiguous_id(tmp_path):
    db = _db(tmp_path)
    entity_id = (44 << 12) + 17
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO dsp_mob_spawn_points VALUES(?,?)", (entity_id, "Crab"))
        con.execute("INSERT INTO lsb_npc_list VALUES(?,?,?)", (entity_id, "Other", 44))
    exact = reconcile_reported_id(db, zone=44, server_entity_id=entity_id)
    assert exact["status"] == "exact" and exact["matches"][0]["kind"] == "mob"
    assert reconcile_reported_id(db, zone=43, server_entity_id=entity_id)["status"] == "no_match"
    assert reconcile_reported_id(db, zone=44, server_entity_id=entity_id, source="lsb")["matches"][0]["kind"] == "npc"
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO dsp_npc_list VALUES(?,?,?)", (entity_id, "Duplicate", 44))
    ambiguous = reconcile_reported_id(db, zone=44, server_entity_id=entity_id)
    assert ambiguous["status"] == "ambiguous"
    assert {row["kind"] for row in ambiguous["matches"]} == {"npc", "mob"}


def test_missing_id_is_not_slot_fallback_or_absence_verdict(tmp_path):
    db = _db(tmp_path)
    assert reconcile_reported_id(db, zone=44, server_entity_id=None)["status"] == "unavailable"
    miss = reconcile_reported_id(db, zone=44, server_entity_id=12345)
    assert miss["status"] == "no_match"
    assert "not proof" in miss["note"]


def test_missing_or_incomplete_index_fails_closed(tmp_path):
    db = tmp_path / "partial.db"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE dsp_npc_list(npcid INTEGER,name TEXT,zoneid INTEGER)")
    assert reconcile_reported_id(db, zone=44, server_entity_id=100)["status"] == "unavailable"
    with pytest.raises(ValueError):
        reconcile_reported_id(db, zone=44, server_entity_id=100, source="unknown")
    with pytest.raises(ValueError):
        reconcile_reported_id(db, zone=-1, server_entity_id=100)
