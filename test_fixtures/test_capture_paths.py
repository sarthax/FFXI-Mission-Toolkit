#!/usr/bin/env python3
"""Zone Editor Paths tab backend: per-leg PathLog traces keyed by zone."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index
from workbench.captures import paths as capture_paths


def main():
    with TemporaryDirectory() as tmp:
        con = sqlite3.connect(Path(tmp) / "capture.db")
        con.row_factory = sqlite3.Row
        build_capture_index.init_db(con)
        con.execute("CREATE TABLE IF NOT EXISTS zones (zoneid INTEGER, name TEXT)")
        con.execute("INSERT INTO zones VALUES (66, 'MAMOOL_JA_TRAINING_GROUNDS')")
        cid = build_capture_index.create_manual_capture(con, "paths", "Research", None)
        zdb = "Mamool Ja Training Grounds"
        con.execute("INSERT INTO capture_npc_entries (capture_id,zone_db,entity_id,name,x,y,z) VALUES (?,?,?,?,?,?,?)",
                    (cid, zdb, 17000001, "Walker", 0.0, 0.0, 0.0))
        # two legs: the jump between them (0,0 -> 100,100) must NOT count toward length
        for leg, step, x, z in [(1, 0, 0.0, 0.0), (1, 1, 3.0, 4.0), (2, 2, 100.0, 100.0), (2, 3, 100.0, 110.0)]:
            con.execute("INSERT INTO capture_npc_path VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (cid, zdb, 17000001, leg, step, x, 0.0, z, 0, 0))
        con.execute("INSERT INTO capture_pc_path VALUES (?,?,?,?,?,?,?,?,?)", (cid, zdb, 1, 0, 1.0, 2.0, 3.0, 64, 0))
        con.commit()

        listed = capture_paths.captures_for_zone(con, 66)
        assert [c["capture_id"] for c in listed] == [cid], listed
        assert listed[0]["npc_entities"] == 1 and listed[0]["pc_points"] == 1
        assert capture_paths.captures_for_zone(con, 999) == []

        data = capture_paths.capture_paths(con, 66, cid)
        assert len(data["npcs"]) == 1 and len(data["pc"]) == 1
        npc = data["npcs"][0]
        assert npc["name"] == "Walker" and len(npc["legs"]) == 2 and npc["n_points"] == 4
        assert npc["length"] == 15.0, npc["length"]  # 5 + 10, not the inter-leg jump
        assert data["pc"][0]["points"][0] == [1.0, 2.0, 3.0, 64, 0]
        con.close()
    print("capture paths: OK")


if __name__ == "__main__":
    main()
