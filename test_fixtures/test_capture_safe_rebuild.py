#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import build_capture_index
from workbench.core.services import capture_integrity, timeline_alignment


EVENTVIEW = """[2026-09-28 10:00:00] << [0x034] CEventPacket (GP_SERV_COMMAND_EVENT)
{
UniqueNo = 17000001,
MesNum = 42,
MessageNumber = 99,
}
"""

PACKET_32 = """[2026-09-28 10:00:01] Packet 0x032
0 | AA BB CC DD EE FF 01 02 8 |
"""

PACKET_34 = """[2026-09-28 10:00:02] Packet 0x034
0 | 01 02 03 04 05 06 07 08 8 |
"""


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "source"
        (source / "EventView" / "Tester").mkdir(parents=True)
        (source / "PacketLogger" / "incoming").mkdir(parents=True)
        ev_path = source / "EventView" / "Tester" / "Test Zone.log"
        p32 = source / "PacketLogger" / "incoming" / "0x032.log"
        p34 = source / "PacketLogger" / "incoming" / "0x034.log"
        ev_path.write_text(EVENTVIEW, encoding="utf-8")
        p32.write_text(PACKET_32, encoding="utf-8")
        p34.write_text(PACKET_34, encoding="utf-8")

        con = sqlite3.connect(root / "capture.db")
        con.row_factory = sqlite3.Row
        build_capture_index.init_db(con)
        cid = build_capture_index.ingest(con, str(source), content_type="overworld")

        # User-maintained metadata/evidence that rebuild must never replace.
        con.execute(
            """UPDATE captures SET mission_name=?,capturer=?,video_url=? WHERE capture_id=?""",
            ("Keep Mission", "Keep Capturer", "https://example.invalid/video", cid),
        )
        con.commit()
        build_capture_index.set_capture_tags(con, cid, ["Research"])
        timeline_alignment.init_db(con)
        anchor_id = timeline_alignment.add_anchor(
            con, cid, video_ts=10.0, capture_ts=100.0,
            clock_kind=timeline_alignment.CLOCK_LOGGER_SECONDS,
            label="keep anchor",
        )
        evidence_id = timeline_alignment.add_key_evidence(
            con, cid, evidence_type="KEY_EVENT", label="keep evidence",
            video_ts=10.0, capture_ts=100.0,
            clock_kind=timeline_alignment.CLOCK_LOGGER_SECONDS,
            anchor_id=anchor_id,
        )

        identity_before = capture_integrity.content_identity(con, cid)
        assert identity_before and identity_before["sha256"]

        inventory = {
            row["filename"]: row
            for row in build_capture_index.capture_rebuild_inventory(con, cid)
        }
        ev_rel = "EventView/Tester/Test Zone.log"
        p32_rel = "PacketLogger/incoming/0x032.log"
        assert inventory[ev_rel]["rebuildable"], inventory[ev_rel]
        assert inventory[p32_rel]["rebuildable"], inventory[p32_rel]

        # Corrupt normalized outputs without touching source bytes; rebuild must restore them.
        con.execute(
            "UPDATE capture_eventview SET fields_json='CORRUPT' WHERE capture_id=?",
            (cid,),
        )
        con.execute(
            "UPDATE capture_raw_packets SET raw_hex='CORRUPT' WHERE capture_id=? AND seq=0",
            (cid,),
        )
        con.commit()

        ev_result = build_capture_index.rebuild_capture_source(con, cid, ev_rel)
        assert ev_result["scope"] == "single_source", ev_result
        assert ev_result["rows"] == 1, ev_result
        ev = con.execute(
            """SELECT fields_json,entity_id,mes_num,message_number
               FROM capture_eventview WHERE capture_id=?""",
            (cid,),
        ).fetchone()
        assert ev["fields_json"] != "CORRUPT", ev
        assert (ev["entity_id"], ev["mes_num"], ev["message_number"]) == (17000001, 42, 99), ev

        packet_result = build_capture_index.rebuild_capture_source(con, cid, p32_rel)
        assert packet_result["scope"] == "packetlogger_family", packet_result
        assert set(packet_result["source_files"]) == {p32_rel, "PacketLogger/incoming/0x034.log"}
        packets = con.execute(
            "SELECT seq,opcode,raw_hex FROM capture_raw_packets WHERE capture_id=? ORDER BY seq",
            (cid,),
        ).fetchall()
        assert len(packets) == 2, packets
        assert all(row["raw_hex"] != "CORRUPT" for row in packets), packets

        # Capture-level identity and user curation survive rebuild.
        cap = con.execute(
            "SELECT capture_id,mission_name,capturer,video_url FROM captures WHERE capture_id=?",
            (cid,),
        ).fetchone()
        assert tuple(cap) == (
            cid, "Keep Mission", "Keep Capturer", "https://example.invalid/video"
        ), cap
        assert build_capture_index.get_capture_tags(con, cid) == ["Research"]
        assert con.execute(
            "SELECT COUNT(*) FROM capture_alignment_anchors WHERE capture_id=? AND anchor_id=?",
            (cid, anchor_id),
        ).fetchone()[0] == 1
        assert con.execute(
            "SELECT COUNT(*) FROM capture_key_evidence WHERE capture_id=? AND evidence_id=?",
            (cid, evidence_id),
        ).fetchone()[0] == 1
        identity_after = capture_integrity.content_identity(con, cid)
        assert identity_after["sha256"] == identity_before["sha256"], (identity_before, identity_after)

        # If source bytes drift, inventory and rebuild both refuse before normalized-row mutation.
        good_fields = con.execute(
            "SELECT fields_json FROM capture_eventview WHERE capture_id=?", (cid,)
        ).fetchone()[0]
        ev_path.write_text(EVENTVIEW + "\n", encoding="utf-8")
        changed = {
            row["filename"]: row
            for row in build_capture_index.capture_rebuild_inventory(con, cid)
        }[ev_rel]
        assert not changed["rebuildable"], changed
        assert "hash" in changed["reason"], changed
        try:
            build_capture_index.rebuild_capture_source(con, cid, ev_rel)
        except ValueError as ex:
            assert "changed" in str(ex) or "hash" in str(ex), ex
        else:
            raise AssertionError("changed source bytes should refuse safe rebuild")
        assert con.execute(
            "SELECT fields_json FROM capture_eventview WHERE capture_id=?", (cid,)
        ).fetchone()[0] == good_fields

        # Manual/upload capture without retained source bytes is accurately reported unavailable.
        manual = build_capture_index.create_manual_capture(con, "manual", "overworld", None)
        con.execute(
            """INSERT INTO capture_source_manifest
               (capture_id,filename,sha256,byte_size,format_detected,parser_name,parser_version,
                row_count,ingest_status,error)
               VALUES (?,?,?,?,?,?,?,?,?,NULL)""",
            (manual, "manual.log", "0" * 64, 1, "eventview", "eventview",
             capture_integrity.PARSER_VERSION, 1, "RECOGNIZED"),
        )
        con.commit()
        manual_inventory = build_capture_index.capture_rebuild_inventory(con, manual)
        assert len(manual_inventory) == 1
        assert not manual_inventory[0]["rebuildable"]
        assert "not persisted" in manual_inventory[0]["reason"]

        con.close()

    print("Safe capture source rebuild regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
