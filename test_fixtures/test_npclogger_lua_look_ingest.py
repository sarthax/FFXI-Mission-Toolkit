#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import build_capture_index
import mob_look_decode


ROOT = Path(__file__).resolve().parent
FIXTURE_ROOTS = (
    ROOT / "captures" / "foxmulder_bhaflau_remnants",
    ROOT / "captures" / "tacocat_leujaoam_sanctum",
)
KNOWN_UKA_LOOK = "01000C07F5103121A53031411F50676100700000"


def _lua_files(src: build_capture_index.Source) -> list[str]:
    return (
        src.find(r'[Nn]pclogger/(?:[^/]+/)?tables/[^/]+\.lua$')
        + src.find(r'[Nn]pclogger/(?:[^/]+/)?database/[^/]+\.lua$')
    )


def _rows_from_lua(src: build_capture_index.Source, relname: str) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for raw_line in src.read_text(relname).splitlines():
        match = build_capture_index.NPCLOGGER_LUA_LINE_RE.match(raw_line)
        if not match:
            continue
        fields = {}
        for fm in build_capture_index.NPCLOGGER_LUA_FIELD_RE.finditer(match.group(2)):
            key, str_val, num_val = fm.group(1), fm.group(2), fm.group(3)
            fields[key.lower()] = str_val if str_val is not None else float(num_val)
        if "x" not in fields or "z" not in fields:
            continue
        entity_id = int(match.group(1))
        prior = rows.setdefault(entity_id, {})
        prior.update({k: v for k, v in fields.items() if v is not None})
    return rows


def _insert_capture(con: sqlite3.Connection, source_path: str, label: str) -> int:
    cur = con.execute(
        "INSERT INTO captures(source_path,capture_label,content_type) VALUES (?,?,?)",
        (source_path, label, "instances"),
    )
    return int(cur.lastrowid)


def _assert_direct_ingest(con: sqlite3.Connection) -> tuple[bytes, str]:
    seen_positive = 0
    seen_missing = 0
    known_blob = None
    known_hex = None

    for fixture_root in FIXTURE_ROOTS:
        assert fixture_root.exists(), fixture_root
        src = build_capture_index.Source(fixture_root)
        try:
            files = _lua_files(src)
            assert files, fixture_root
            fixture_positive = 0
            for index, relname in enumerate(files, 1):
                expected = _rows_from_lua(src, relname)
                assert expected, relname
                cid = _insert_capture(
                    con,
                    f"manual://legacy-lua-test/{fixture_root.name}/{index}",
                    f"{fixture_root.name}:{relname}",
                )
                leg = 2 if "/database/" in relname.lower() else 1
                build_capture_index.ingest_npclogger_lua(con, cid, src, relname, leg)
                zone_db = Path(relname).stem

                for entity_id, fields in expected.items():
                    row = con.execute(
                        """SELECT legacy_look,door_id,act_index,flags0,flags1,flags2,flags3,
                                  legacy_flag,sub_kind
                           FROM capture_npc_entries
                           WHERE capture_id=? AND zone_db=? AND entity_id=?""",
                        (cid, zone_db, entity_id),
                    ).fetchone()
                    assert row is not None, (relname, entity_id)
                    look_hex = fields.get("look")
                    if look_hex:
                        expected_blob = bytes.fromhex(str(look_hex))
                        assert row[0] == expected_blob, (relname, entity_id, row[0], expected_blob)
                        fixture_positive += 1
                        seen_positive += 1
                        if str(look_hex).upper() == KNOWN_UKA_LOOK:
                            known_blob = row[0]
                            known_hex = str(look_hex).upper()
                    else:
                        assert row[0] is None, (relname, entity_id, row[0])
                        seen_missing += 1

                    optional = build_capture_index._npclogger_lua_optional_fields(fields)
                    for stored, expected_value in zip(row, optional):
                        if expected_value is not None:
                            assert stored == expected_value, (
                                relname, entity_id, stored, expected_value
                            )
            assert fixture_positive > 0, f"no look-bearing rows found in {fixture_root}"
        finally:
            src.close()

    assert seen_positive > 0
    # Real fixtures may or may not contain a final row with no look; a synthetic NULL case below
    # guarantees the never-invent rule independently.
    assert known_blob is not None and known_hex == KNOWN_UKA_LOOK, (
        "known Uka Totlihn look was not found in the legacy fixture corpus"
    )
    return known_blob, known_hex


def _assert_missing_stays_null(con: sqlite3.Connection):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        rel = "npclogger/Tester/database/Test Zone.lua"
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[17000001] = {['id']=17000001, ['name']=\"No Look\", "
            "['x']=1, ['y']=2, ['z']=3, ['r']=0}\n",
            encoding="utf-8",
        )
        src = build_capture_index.Source(root)
        try:
            cid = _insert_capture(con, "manual://legacy-lua-test/no-look", "no-look")
            build_capture_index.ingest_npclogger_lua(con, cid, src, rel, 2)
            row = con.execute(
                "SELECT legacy_look,door_id,act_index,flags0,flags1,flags2,flags3,legacy_flag,sub_kind "
                "FROM capture_npc_entries WHERE capture_id=? AND entity_id=17000001",
                (cid,),
            ).fetchone()
            assert row == (None, None, None, None, None, None, None, None, None), row
        finally:
            src.close()


def _assert_backfill():
    con = sqlite3.connect(":memory:")
    build_capture_index.init_db(con)
    expected_by_capture: dict[int, dict[tuple[str, int], bytes | None]] = {}

    for fixture_root in FIXTURE_ROOTS:
        assert fixture_root.exists(), fixture_root
        cid = _insert_capture(con, str(fixture_root.resolve()), fixture_root.name)
        expected_by_capture[cid] = {}
        src = build_capture_index.Source(fixture_root)
        try:
            files = _lua_files(src)
            assert files, fixture_root
            for relname in files:
                zone_db = Path(relname).stem
                for entity_id, fields in _rows_from_lua(src, relname).items():
                    con.execute(
                        """INSERT OR IGNORE INTO capture_npc_entries
                           (capture_id,zone_db,entity_id,name)
                           VALUES (?,?,?,?)""",
                        (cid, zone_db, entity_id, fields.get("name")),
                    )
                    look_hex = fields.get("look")
                    key = (zone_db, entity_id)
                    if look_hex:
                        expected_by_capture[cid][key] = bytes.fromhex(str(look_hex))
                    else:
                        expected_by_capture[cid].setdefault(key, None)
        finally:
            src.close()

    build_capture_index.backfill_npc_fields(con)

    for cid, expected in expected_by_capture.items():
        assert any(blob is not None for blob in expected.values()), cid
        for (zone_db, entity_id), blob in expected.items():
            stored = con.execute(
                """SELECT legacy_look FROM capture_npc_entries
                   WHERE capture_id=? AND zone_db=? AND entity_id=?""",
                (cid, zone_db, entity_id),
            ).fetchone()
            assert stored is not None
            assert stored[0] == blob, (cid, zone_db, entity_id, stored[0], blob)
    con.close()


def main():
    con = sqlite3.connect(":memory:")
    build_capture_index.init_db(con)
    blob, source_hex = _assert_direct_ingest(con)
    _assert_missing_stays_null(con)

    assert len(blob) == 20, len(blob)
    assert blob.hex().upper() == source_hex == KNOWN_UKA_LOOK
    decoded = mob_look_decode.decode_look_data(blob)
    assert "error" not in decoded, decoded
    assert decoded["size"] == 1 and decoded["kind"] == "gear", decoded
    assert decoded["race_name"] == "Mithra", decoded
    con.close()

    _assert_backfill()

    print(
        "NPCLogger legacy Lua look regression: PASS "
        f"(Uka look {KNOWN_UKA_LOOK} -> {decoded['race_name']} gear look)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
