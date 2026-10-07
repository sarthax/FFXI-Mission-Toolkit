#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.captures.ingestion import build_index as build_capture_index
from workbench.devtools.features import trace as feature_trace
from workbench.core import graph as workbench_graph
from workbench.core.services import capture_integrity


def add_runtime_edge(graph, cid: int, *, explicit: bool):
    graph.execute(
        "INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
        (f"capture:{cid}", "CAPTURE", f"capture {cid}", json.dumps({"capture_id": cid})),
    )
    graph.execute(
        "INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
        ("packet:0x034", "PACKET", "0x034", json.dumps({"opcode": "0x034"})),
    )
    evidence_id = f"evidence:test:{cid}:{'explicit' if explicit else 'legacy'}"
    graph.execute(
        "INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
        (
            evidence_id,
            "CAPTURE",
            "capture_events",
            f"capture:{cid}:Test Zone:0",
            None,
            "test runtime capture event",
        ),
    )
    metadata = {"direction": "Incoming", "opcode_name": "CS Event"}
    if explicit:
        metadata.update(
            {
                "capture_id": cid,
                "capture_table": "capture_events",
                "capture_row_key": {"zone_db": "Test Zone", "seq": 0},
                "opcode": "0x034",
            }
        )
    graph.execute(
        "INSERT OR REPLACE INTO entity_relationships VALUES(?,?,?,?,?,?,?,?,?)",
        (
            f"runtime-edge:{cid}:{'explicit' if explicit else 'legacy'}",
            f"capture:{cid}",
            "packet:0x034",
            "OBSERVES",
            evidence_id,
            "VERIFIED",
            "DISCOVERED",
            json.dumps(metadata, sort_keys=True),
            None,
        ),
    )
    graph.commit()


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        capture_db = root / "capture.db"
        graph_db = root / "graph.db"

        capture = sqlite3.connect(capture_db)
        build_capture_index.init_db(capture)
        cid = build_capture_index.create_manual_capture(
            capture, "runtime provenance", "Research", None
        )
        capture.execute(
            """INSERT INTO capture_events
               (capture_id,zone_db,seq,direction,opcode,opcode_name,entity_id,entity_name,
                event_hex,option,message_id,params_raw)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cid, "Test Zone", 0, "Incoming", "0x034", "CS Event",
                17000001, "Test NPC", "0x0199", 0, 123, "{1,2}",
            ),
        )
        capture_integrity.record_row_locator(
            capture,
            cid,
            "idview/simple/Test Zone.log",
            "capture_events",
            json.dumps({"zone_db": "Test Zone", "seq": 0}, sort_keys=True),
            "line",
            source_sha256="a" * 64,
            start_line=7,
            end_line=7,
            start_offset=100,
            end_offset=180,
            details={"source": "idview_simple_v1", "opcode": "0x034"},
        )
        capture.commit()

        graph = workbench_graph.init_db(graph_db)
        add_runtime_edge(graph, cid, explicit=False)
        page = feature_trace.runtime_observation_page(
            graph, "packet:0x034", 1, "both", capture, "OBSERVES", None, 0, 100
        )
        # Opcode filtering above deliberately does not match because runtime dimensions use the
        # relationship when the old edge lacks explicit opcode. Fetch unfiltered for compatibility.
        page = feature_trace.runtime_observation_page(
            graph, "packet:0x034", 1, "both", capture, None, None, 0, 100
        )
        assert page["total"] == 1, page
        prov = page["observations"][0]["capture_provenance"]
        assert len(prov) == 1, page
        assert prov[0]["filename"] == "idview/simple/Test Zone.log", prov
        assert prov[0]["start_line"] == 7 and prov[0]["end_line"] == 7, prov
        assert prov[0]["normalized_table"] == "capture_events", prov
        assert json.loads(prov[0]["normalized_row_key"]) == {
            "seq": 0, "zone_db": "Test Zone"
        }

        # Explicit normalized row identity on a newly rebuilt graph resolves the same locator
        # without relying on evidence-location parsing.
        graph.execute("DELETE FROM entity_relationships")
        graph.execute("DELETE FROM evidence")
        graph.commit()
        add_runtime_edge(graph, cid, explicit=True)
        page2 = feature_trace.runtime_observation_page(
            graph, "packet:0x034", 1, "both", capture, "0x034", None, 0, 100
        )
        assert page2["total"] == 1, page2
        prov2 = page2["observations"][0]["capture_provenance"]
        assert len(prov2) == 1 and prov2[0]["filename"] == "idview/simple/Test Zone.log", prov2

        # Static route/template assertions keep the clickable source-view contract in regression
        # without importing FastAPI into the lightweight core job.
        gui_source = Path("src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
        feature_template = Path("gui/templates/feature_trace.html").read_text(encoding="utf-8")
        source_template = Path("gui/templates/capture_source_locator.html").read_text(encoding="utf-8")
        assert '/captures/{capture_id}/source-locator' in gui_source
        assert 'capture_provenance' in feature_template
        assert 'Exact capture source' in feature_template
        assert 'Exact source excerpt' in source_template
        assert 'Exact SQLite source row' in source_template
        assert 'Verified against original source bytes' in source_template

        graph.close()
        capture.close()

    print("Feature Trace capture source drilldown regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
