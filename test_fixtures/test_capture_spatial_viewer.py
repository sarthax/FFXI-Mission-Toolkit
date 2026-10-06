#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import build_capture_index
from workbench.core.services import capture_spatial


def main():
    with TemporaryDirectory() as tmp:
        con = sqlite3.connect(Path(tmp) / "capture.db")
        con.row_factory = sqlite3.Row
        build_capture_index.init_db(con)
        cid = build_capture_index.create_manual_capture(con, "spatial viewer", "Research", None)

        rows = [
            (cid, "Test Zone", 17000001, "Walking Mob", 101, 10.0, 2.0, 30.0, 90),
            (cid, "Test Zone", 17000002, "Fixed Rune", 202, -5.0, 1.0, 7.0, 100),
            (cid, "Other Zone", 17000003, "Other Entity", 303, 1.0, 1.0, 1.0, 100),
        ]
        for row in rows:
            con.execute(
                """INSERT INTO capture_npc_entries
                   (capture_id,zone_db,entity_id,name,model_id,x,y,z,hpp)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                row,
            )
        con.execute(
            """INSERT INTO capture_npc_path
               (capture_id,zone_db,entity_id,leg,step,x,y,z,dir,delta)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (cid, "Test Zone", 17000001, 0, 0, 10.0, 2.0, 30.0, 0, 0),
        )
        con.commit()

        spatial = capture_spatial.capture_spatial_entities(con, cid, "Test Zone")
        assert [e["id"] for e in spatial] == [17000002, 17000001], spatial
        by_id = {e["id"]: e for e in spatial}
        assert by_id[17000001]["has_path"] is True, by_id[17000001]
        assert by_id[17000002]["has_path"] is False, by_id[17000002]
        assert by_id[17000002]["x"] == -5.0 and by_id[17000002]["z"] == 7.0

        by_name = capture_spatial.capture_spatial_entities(con, cid, "Test Zone", "rune")
        assert [e["id"] for e in by_name] == [17000002], by_name
        by_id_search = capture_spatial.capture_spatial_entities(con, cid, "Test Zone", "00001")
        assert [e["id"] for e in by_id_search] == [17000001], by_id_search
        assert not capture_spatial.capture_spatial_entities(con, cid, "Missing Zone")

        root = Path(__file__).resolve().parents[1]
        two_d = (root / "gui" / "templates" / "path_plot_all.html").read_text(encoding="utf-8")
        three_d = (root / "gui" / "templates" / "zone_view3d.html").read_text(encoding="utf-8")
        server = (root / "src" / "workbench" / "app" / "_host_impl.py").read_text(encoding="utf-8")

        assert "name / entity id" in two_d
        assert "labels / IDs / XYZ" in two_d
        assert "position (x, y, z)" in two_d
        assert "fixed / snapshot only" in two_d
        assert "capture-spatial-search" in three_d
        assert "capture-spatial-results" in three_d
        assert "CAPTURE_SPATIAL_URL" in three_d
        assert "toFixed(1)" in three_d
        assert "/captures/{capture_id}/spatial.json" in server

        con.close()

    print("Capture spatial viewer parity regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
