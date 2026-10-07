#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index


KI = """[2026-09-28 10:00:00] Obtained KI
{"ID", 321}
{"Name", "Test Key Item"}
{"X", 1.5}
{"Y", 2.5}
{"Z", 3.5}
{"Zone", "Test Zone"}

[2026-09-28 10:05:00] Lost KI
{"ID", 321}
{"Name", "Test Key Item"}
{"Zone", "Test Zone"}
"""

IDV1 = """Incoming Packet: 0x034 (CS Event + Params), NPC: 17000001 (Test NPC), Event: 0x0199, Option: 2, Message: 123, Params: {1,2}
"""

IDV2 = """INCOMING < CS Event + Params (0x034): NPC: 17000001 (Test NPC)
Event: 409
Option: 2
Message: 123
Params: {1,2}

OUTGOING > Event Response (0x05B): Actor: 17000001 (Test NPC)
Event: 410
Option: 3
"""

HP = """Defeated Test Mob: 100~120 HP
[HP Track] Killed 17000002 (Other Mob): 200~240HP
"""

ACTION = """[Actor: 17000001 (Test NPC)] Doton: Ni > Cat: 4 ID: 330 Anim: 330 Msg: 31
not a record
[Actor: 17000002 (Other Mob)] Head Butt > Cat: 7 ID: 12 Anim: 44 Msg: 185
"""


def write(root: Path, rel: str, text: str) -> bytes:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = text.encode("utf-8")
    p.write_bytes(payload)
    return payload


def locators(con, cid: int, filename: str, table: str):
    return con.execute(
        """SELECT row_key,source_sha256,locator_basis,start_line,end_line,start_offset,end_offset,details_json
           FROM capture_row_locators
           WHERE capture_id=? AND filename=? AND target_table=?
           ORDER BY start_line,start_offset""",
        (cid, filename, table),
    ).fetchall()


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        payloads = {
            "KITrack/test.log": write(root, "KITrack/test.log", KI),
            "idview/simple/V1 Zone.log": write(root, "idview/simple/V1 Zone.log", IDV1),
            "idview/simple/V2 Zone.log": write(root, "idview/simple/V2 Zone.log", IDV2),
            "hptrack/simple/Test Zone.log": write(root, "hptrack/simple/Test Zone.log", HP),
            "actionview/simple/Test Zone.log": write(root, "actionview/simple/Test Zone.log", ACTION),
        }

        con = sqlite3.connect(root / "capture.db")
        build_capture_index.init_db(con)
        cid = build_capture_index.create_manual_capture(con, "more locator formats", "Research", None)
        src = build_capture_index.Source(root)
        try:
            assert build_capture_index.ingest_kitrack(con, cid, src, "KITrack/test.log") == 2
            assert build_capture_index.ingest_idview_simple(con, cid, src, "idview/simple/V1 Zone.log") == 1
            assert build_capture_index.ingest_idview_simple(con, cid, src, "idview/simple/V2 Zone.log") == 2
            assert build_capture_index.ingest_hptrack(con, cid, src, "hptrack/simple/Test Zone.log") == 2
            assert build_capture_index.ingest_actionview_simple(con, cid, src, "actionview/simple/Test Zone.log") == 2
        finally:
            src.close()

        # KITrack: two exact header-delimited blocks.
        ki = locators(con, cid, "KITrack/test.log", "capture_ki_events")
        assert len(ki) == 2, ki
        assert [json.loads(r[0])["seq"] for r in ki] == [0, 1], ki
        assert all(r[2] == "block" for r in ki), ki
        assert all(r[1] == hashlib.sha256(payloads["KITrack/test.log"]).hexdigest() for r in ki)
        first_slice = payloads["KITrack/test.log"][ki[0][5]:ki[0][6]].decode("utf-8")
        second_slice = payloads["KITrack/test.log"][ki[1][5]:ki[1][6]].decode("utf-8")
        assert first_slice.startswith("[2026-09-28 10:00:00] Obtained KI")
        assert "Test Key Item" in first_slice
        assert second_slice.startswith("[2026-09-28 10:05:00] Lost KI")

        # IDView v1: one physical line.
        v1 = locators(con, cid, "idview/simple/V1 Zone.log", "capture_events")
        assert len(v1) == 1 and v1[0][2] == "line", v1
        assert v1[0][3:5] == (1, 1), v1
        assert payloads["idview/simple/V1 Zone.log"][v1[0][5]:v1[0][6]].decode("utf-8").startswith("Incoming Packet:")

        # IDView v2: two blank-line-delimited blocks with stable normalized keys.
        v2 = locators(con, cid, "idview/simple/V2 Zone.log", "capture_events")
        assert len(v2) == 2 and all(r[2] == "block" for r in v2), v2
        assert [json.loads(r[0])["seq"] for r in v2] == [0, 1], v2
        v2_first = payloads["idview/simple/V2 Zone.log"][v2[0][5]:v2[0][6]].decode("utf-8")
        v2_second = payloads["idview/simple/V2 Zone.log"][v2[1][5]:v2[1][6]].decode("utf-8")
        assert "Event: 409" in v2_first and "Message: 123" in v2_first
        assert "Event: 410" in v2_second

        # HPTrack: each observation maps to exactly its source line.
        hp = locators(con, cid, "hptrack/simple/Test Zone.log", "capture_hp_events")
        assert len(hp) == 2 and all(r[2] == "line" for r in hp), hp
        assert [json.loads(r[0])["seq"] for r in hp] == [1, 2], hp
        assert hp[0][3:5] == (1, 1) and hp[1][3:5] == (2, 2), hp

        # ActionView/simple: invalid lines are skipped but physical line numbers remain real.
        act = locators(con, cid, "actionview/simple/Test Zone.log", "capture_actions")
        assert len(act) == 2 and all(r[2] == "line" for r in act), act
        assert act[0][3:5] == (1, 1), act
        assert act[1][3:5] == (3, 3), act
        assert json.loads(act[0][0])["action_key"] == "17000001-simple-0"
        assert json.loads(act[1][0])["action_key"] == "17000002-simple-2"

        # All emitted locator byte spans reconstruct real source text.
        for filename, table in [
            ("KITrack/test.log", "capture_ki_events"),
            ("idview/simple/V1 Zone.log", "capture_events"),
            ("idview/simple/V2 Zone.log", "capture_events"),
            ("hptrack/simple/Test Zone.log", "capture_hp_events"),
            ("actionview/simple/Test Zone.log", "capture_actions"),
        ]:
            for row in locators(con, cid, filename, table):
                assert row[5] is not None and row[6] is not None, (filename, row)
                assert payloads[filename][row[5]:row[6]], (filename, row)

        # Re-ingestion replaces, rather than duplicates, locators for each source file.
        src = build_capture_index.Source(root)
        try:
            build_capture_index.ingest_kitrack(con, cid, src, "KITrack/test.log")
            build_capture_index.ingest_idview_simple(con, cid, src, "idview/simple/V2 Zone.log")
            build_capture_index.ingest_hptrack(con, cid, src, "hptrack/simple/Test Zone.log")
            build_capture_index.ingest_actionview_simple(con, cid, src, "actionview/simple/Test Zone.log")
        finally:
            src.close()
        assert len(locators(con, cid, "KITrack/test.log", "capture_ki_events")) == 2
        assert len(locators(con, cid, "idview/simple/V2 Zone.log", "capture_events")) == 2
        assert len(locators(con, cid, "hptrack/simple/Test Zone.log", "capture_hp_events")) == 2
        assert len(locators(con, cid, "actionview/simple/Test Zone.log", "capture_actions")) == 2

        con.close()

    print("Additional capture row locator regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
