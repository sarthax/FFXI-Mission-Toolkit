#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index
from workbench.core.contracts import capture_row_locators
from workbench.core.services import capture_integrity


EVENTVIEW_SAMPLE = """[2026-09-28 12:34:56] << [0x034] CEventPacket (GP_SERV_COMMAND_EVENT)
{
UniqueNo = 17000001,
MesNum = 42,
MessageNumber = 99,
}
"""


def main():
    with TemporaryDirectory() as tmp:
        con = sqlite3.connect(Path(tmp) / "capture.db")
        build_capture_index.init_db(con)
        cid = build_capture_index.create_manual_capture(con, "row locator test", "Research", None)

        payload = EVENTVIEW_SAMPLE.encode("utf-8")
        result = build_capture_index.ingest_single_file(
            con, cid, "Locator Zone.log", payload
        )
        assert result["format"] == "eventview", result
        assert result["rows"] == 1, result

        row = con.execute(
            """SELECT filename,target_table,row_key,source_sha256,locator_basis,
                      start_line,end_line,start_offset,end_offset,details_json
               FROM capture_row_locators
               WHERE capture_id=?""",
            (cid,),
        ).fetchone()
        assert row is not None
        filename, target_table, row_key, digest, basis, start_line, end_line, start_offset, end_offset, details_json = row
        assert filename == "Locator Zone.log", row
        assert target_table == "capture_eventview", row
        assert json.loads(row_key) == {"seq": 0, "zone_db": "Locator Zone"}, row_key
        assert digest == hashlib.sha256(payload).hexdigest(), digest
        assert basis == "block", basis
        assert start_line == 1 and end_line == 6, (start_line, end_line)
        assert start_offset == 0 and end_offset == len(payload.rstrip(b"\n")), (start_offset, end_offset)

        exact = payload[start_offset:end_offset].decode("utf-8")
        assert exact == EVENTVIEW_SAMPLE.rstrip("\n"), exact
        details = json.loads(details_json)
        assert details["opcode"] == "0x034", details
        assert details["packet_class"] == "CEventPacket", details
        assert details["gp_command"] == "GP_SERV_COMMAND_EVENT", details

        normalized = con.execute(
            """SELECT opcode,entity_id,mes_num,message_number
               FROM capture_eventview
               WHERE capture_id=? AND zone_db='Locator Zone' AND seq=0""",
            (cid,),
        ).fetchone()
        assert normalized == ("0x034", 17000001, 42, 99), normalized

        # Cross-component consumers use the Core contract, while Captures retains the ingestion
        # implementation. Both query paths must preserve the same exact locator evidence.
        contract_rows = capture_row_locators.find_row_locators(
            con, cid, "capture_eventview", {"seq": 0, "zone_db": "Locator Zone"}
        )
        integrity_rows = capture_integrity.find_row_locators(
            con, cid, "capture_eventview", {"zone_db": "Locator Zone", "seq": 0}
        )
        assert contract_rows == integrity_rows, (contract_rows, integrity_rows)
        assert len(contract_rows) == 1, contract_rows
        assert contract_rows[0]["filename"] == "Locator Zone.log", contract_rows
        assert contract_rows[0]["details"]["opcode"] == "0x034", contract_rows
        assert capture_row_locators.canonical_row_key({"b": 2, "a": 1}) == '{"a": 1, "b": 2}'

        health = capture_integrity.capture_health(con, cid)
        assert health["dimensions"]["lineage"]["exact_row_locators"] == 1, health
        assert health["dimensions"]["lineage"]["precision"] == "exact_rows_available", health

        deleted = build_capture_index.delete_capture(con, cid)
        assert deleted["captures"] == 1, deleted
        assert con.execute(
            "SELECT COUNT(*) FROM capture_row_locators WHERE capture_id=?", (cid,)
        ).fetchone()[0] == 0

        con.close()

    print("Capture exact row locator regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
