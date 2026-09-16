#!/usr/bin/env python3
"""
test_backport_sql_convert.py -- regression test for backport_sql_convert.py, matching this
project's existing test_capture_ingestion.py / test_backport_lua_convert.py convention (no pytest).

Usage:
    py -3 test_backport_sql_convert.py
"""
from __future__ import annotations

import sqlite3
import sys

import backport_sql_convert as bsc

FAILURES: list[str] = []


def check(name: str, condition: bool, detail=""):
    if condition:
        print(f"  [ok] {name}")
    else:
        print(f"  [FAIL] {name}  {detail}")
        FAILURES.append(name)


def test_parse_insert_values_basic():
    print("parse_insert_values (multiple rows, one statement)")
    sql = ("INSERT INTO `npc_list` VALUES (1,'Foo','Foo',0,1.000,2.000,3.000,0,40,40,0,0,0,0,3,"
           "0x00,0,'TOAU',1),(2,'Bar','Bar',0,4.000,5.000,6.000,0,40,40,0,0,0,0,3,0x00,0,'TOAU',1);")
    rows = bsc.parse_insert_values(sql)
    check("parsed 2 rows", len(rows) == 2, rows)
    check("table name correct", all(t == "npc_list" for t, _ in rows), rows)
    check("first row id field", rows[0][1][0] == "1", rows[0])
    check("first row name field quoted", rows[0][1][1] == "'Foo'", rows[0])


def test_parse_insert_values_skips_commented_out_rows():
    print("parse_insert_values (commented-out '-- INSERT ...' rows must be skipped, not parsed as data)")
    sql = ("INSERT INTO `t` VALUES (1,'real');\n"
           "-- INSERT INTO `t` VALUES (2,?);\n"
           "  -- INSERT INTO `t` VALUES (3,'also fake');\n"
           "INSERT INTO `t` VALUES (4,'real2');\n")
    rows = bsc.parse_insert_values(sql)
    ids = [r[1][0] for r in rows]
    check("only the 2 real (non-commented) rows parsed", ids == ["1", "4"], rows)


def test_parse_insert_values_multiple_statements():
    print("parse_insert_values (multiple separate INSERT statements)")
    sql = "INSERT INTO `t` VALUES (1,'a');\nINSERT INTO `t` VALUES (2,'b');\n"
    rows = bsc.parse_insert_values(sql)
    check("parsed 2 rows across 2 statements", len(rows) == 2, rows)


def test_convert_table_identical_schema():
    print("convert_table (npc_list -- identical schema, no warnings)")
    schema_map = bsc.load_schema_map()
    row = ["1", "'Foo'", "'Foo'", "0", "1.000", "2.000", "3.000", "0", "40", "40", "0", "0", "0",
           "0", "3", "0x00", "0", "'TOAU'", "1"]
    res = bsc.convert_table("npc_list", [row], schema_map)
    check("no warnings for an identical-schema table", not res.warnings, res.warnings)
    check("converted SQL references all 19 columns", res.converted_sql.count(",") >= 18, res.converted_sql)
    check("id captured", res.converted_ids == ["1"], res.converted_ids)
    check("name captured for collision classification", res.id_to_name.get(1) == "Foo", res.id_to_name)


def test_convert_table_mob_groups_flags_dropped_column():
    print("convert_table (mob_groups -- dropped 'name' column + PK-shape warning)")
    schema_map = bsc.load_schema_map()
    row = ["100", "50", "77", "'Some Group'", "3600", "0", "10", "500", "0", "1", "10", "0"]
    res = bsc.convert_table("mob_groups", [row], schema_map)
    check("flags the dropped 'name' column", any("dropped" in w["reason"] for w in res.warnings), res.warnings)
    check("flags the PK-shape warning (global vs per-zone groupid)",
          any("global" in w["reason"].lower() or "collision" in w["reason"].lower() for w in res.warnings),
          res.warnings)
    check("converted SQL has no 'name' column reference", "`name`" not in res.converted_sql, res.converted_sql)
    check("id captured despite no name_column configured for mob_groups", res.converted_ids == ["100"], res.converted_ids)


def test_convert_table_instance_list_flags_dropped_column():
    print("convert_table (instance_list -- dropped 'instance_zone' column)")
    schema_map = bsc.load_schema_map()
    row = ["1", "'Some Instance'", "77", "10", "600", "0.0", "0.0", "0.0", "0", "-1", "-1", "-1", "-1"]
    res = bsc.convert_table("instance_list", [row], schema_map)
    check("flags the dropped instance_zone column", any("instance_zone" in w["reason"] for w in res.warnings), res.warnings)
    check("converted SQL has no instance_zone reference", "instance_zone" not in res.converted_sql, res.converted_sql)


def test_convert_table_unknown_table():
    print("convert_table (a table with no schema map entry -- flagged, not guessed)")
    schema_map = bsc.load_schema_map()
    res = bsc.convert_table("totally_made_up_table", [["1", "2"]], schema_map)
    check("flags missing schema mapping", any("no schema mapping" in w["reason"] for w in res.warnings), res.warnings)
    check("emits a TODO comment instead of guessing a conversion", "SQL-PORT-TODO" in res.converted_sql, res.converted_sql)


def test_convert_table_row_length_mismatch():
    print("convert_table (a row with the wrong field count -- skipped and flagged, not silently mis-mapped)")
    schema_map = bsc.load_schema_map()
    short_row = ["1", "'Foo'"]  # npc_list needs 19 fields
    res = bsc.convert_table("npc_list", [short_row], schema_map)
    check("flags the malformed row", any("expected" in w["reason"] for w in res.warnings), res.warnings)
    check("no INSERT emitted for the bad row", "INSERT INTO" not in res.converted_sql, res.converted_sql)


def test_check_id_collisions_same_entity_vs_mismatch():
    print("check_id_collisions (in-memory DSP-shaped table -- same_entity vs name_mismatch classification)")
    schema_map = bsc.load_schema_map()
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE dsp_npc_list (npcid INTEGER, name TEXT)")
    con.executemany("INSERT INTO dsp_npc_list VALUES (?, ?)", [
        (100, "SameName"),   # will match -- same_entity
        (101, "DspName"),    # will mismatch -- name_mismatch
        # 102 intentionally absent -- no collision at all
    ])
    id_to_name = {100: "SameName", 101: "TopazName", 102: "Whatever"}
    result = bsc.check_id_collisions(con, "npc_list", ["100", "101", "102"], schema_map, id_to_name=id_to_name)
    check("id 100 classified same_entity", any(e["id"] == 100 for e in result["same_entity"]), result)
    check("id 101 classified name_mismatch", any(e["id"] == 101 for e in result["name_mismatch"]), result)
    check("id 102 not reported as any kind of collision", not any(
        e["id"] == 102 for e in result["same_entity"] + result["name_mismatch"] + result["unclassified"]), result)


def test_check_id_collisions_no_collision():
    print("check_id_collisions (no overlap at all)")
    schema_map = bsc.load_schema_map()
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE dsp_npc_list (npcid INTEGER, name TEXT)")
    con.execute("INSERT INTO dsp_npc_list VALUES (1, 'Something')")
    result = bsc.check_id_collisions(con, "npc_list", ["999999"], schema_map, id_to_name={999999: "New"})
    check("no collisions reported", not result["same_entity"] and not result["name_mismatch"] and not result["unclassified"], result)


def test_check_id_collisions_dedupes_non_unique_id_table():
    print("check_id_collisions (mob_droplist -- dropId is not unique, must not multiply-report)")
    schema_map = bsc.load_schema_map()
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE dsp_mob_droplist (dropId INTEGER, dropType INTEGER)")
    # dropId 5 appears 3 times in DSP's real data (one dropId groups several item rows) --
    # this must classify as ONE collision, not three.
    con.executemany("INSERT INTO dsp_mob_droplist VALUES (?, ?)", [(5, 1), (5, 1), (5, 2)])
    result = bsc.check_id_collisions(con, "mob_droplist", ["5", "5", "5"], schema_map)
    total = len(result["same_entity"]) + len(result["name_mismatch"]) + len(result["unclassified"])
    check("dropId 5 counted exactly once despite 3 underlying rows", total == 1, result)


def test_check_content_duplication_finds_existing_row_under_different_id():
    print("check_content_duplication (mob_groups -- real 2026-09-15 incident shape: a fresh, "
          "non-colliding candidate groupid, but DSP already has this (poolid, zoneid) elsewhere)")
    schema_map = bsc.load_schema_map()
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE dsp_mob_groups (zoneid INTEGER, groupid INTEGER, poolid INTEGER, "
                "name TEXT, respawntime INTEGER, dropid INTEGER)")
    # DSP already has poolid=2394/zoneid=77 under groupid=2593 -- a prior, correctly-remapped
    # backport pass. The candidate row below uses a totally different, genuinely-free groupid (36,
    # the raw Topaz id) for the SAME content -- exactly the shape that let the real incident happen.
    con.execute("INSERT INTO dsp_mob_groups VALUES (77, 2593, 2394, 'Leshy', 0, 2042)")
    topaz_cols = schema_map["mob_groups"]["topaz_columns"]
    row = ["36" if c == "groupid" else "2394" if c == "poolid" else "77" if c == "zoneid" else
           "'Leshy'" if c == "name" else "503" if c == "dropid" else "0" for c in topaz_cols]
    result = bsc.check_content_duplication(con, "mob_groups", [row], schema_map)
    check("exactly 1 duplicate found", len(result["duplicates"]) == 1, result)
    dup = result["duplicates"][0]
    check("content_key is (poolid, zoneid)", dup["content_key"] == {"poolid": 2394, "zoneid": 77}, dup)
    check("candidate_id is the candidate row's own groupid", dup["candidate_id"] == 36, dup)
    check("existing row's real groupid (2593) surfaced, not the candidate's (36)",
          dup["existing"][0]["groupid"] == 2593, dup)


def test_check_content_duplication_no_existing_content():
    print("check_content_duplication (candidate content key genuinely new -- no false positive)")
    schema_map = bsc.load_schema_map()
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE dsp_mob_groups (zoneid INTEGER, groupid INTEGER, poolid INTEGER, "
                "name TEXT, respawntime INTEGER, dropid INTEGER)")
    con.execute("INSERT INTO dsp_mob_groups VALUES (77, 2593, 2394, 'Leshy', 0, 2042)")
    topaz_cols = schema_map["mob_groups"]["topaz_columns"]
    row = ["999" if c == "groupid" else "888888" if c == "poolid" else "999999" if c == "zoneid" else
           "'Nobody'" if c == "name" else "0" for c in topaz_cols]
    result = bsc.check_content_duplication(con, "mob_groups", [row], schema_map)
    check("no duplicates found for genuinely new content", result["duplicates"] == [], result)


def test_check_content_duplication_no_key_columns_defined():
    print("check_content_duplication (table with no CONTENT_KEY_COLUMNS entry -- explicit note, not a crash)")
    schema_map = bsc.load_schema_map()
    con = sqlite3.connect(":memory:")
    result = bsc.check_content_duplication(con, "npc_list", [["1"]], schema_map)
    check("no duplicates reported", result["duplicates"] == [], result)
    check("note explains why (no content-key columns defined)",
          "No content-key columns defined" in result["note"], result["note"])


TESTS = [
    test_parse_insert_values_basic,
    test_parse_insert_values_skips_commented_out_rows,
    test_parse_insert_values_multiple_statements,
    test_convert_table_identical_schema,
    test_convert_table_mob_groups_flags_dropped_column,
    test_convert_table_instance_list_flags_dropped_column,
    test_convert_table_unknown_table,
    test_convert_table_row_length_mismatch,
    test_check_id_collisions_same_entity_vs_mismatch,
    test_check_id_collisions_no_collision,
    test_check_id_collisions_dedupes_non_unique_id_table,
    test_check_content_duplication_finds_existing_row_under_different_id,
    test_check_content_duplication_no_existing_content,
    test_check_content_duplication_no_key_columns_defined,
]


def main():
    for t in TESTS:
        t()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {', '.join(FAILURES)}")
        sys.exit(1)
    print(f"All {len(TESTS)} test functions passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
