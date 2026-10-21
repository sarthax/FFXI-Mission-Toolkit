#!/usr/bin/env python3
"""Synthetic-only offline reviewer roundtrip, schema, evidence and trust boundaries."""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from test_evidence_to_scenario_handoff import synthetic_interaction_with_key_item
from workbench.captures.scenario_handoff import reconstruct_review_draft
from workbench.captures.scenario_review_workflow import (
    apply_step_decisions, behavior_preview, manual_editor_handoff,
    replay_offline_review, timeline,
)
from workbench.captures.scenario_review_offline import main as offline_main, render_review_html
from workbench.server_admin.feature_testing.test_specifications import validate_spec


def synthetic_review():
    con = synthetic_interaction_with_key_item()
    con.execute("PRAGMA query_only=ON")
    return con, reconstruct_review_draft(con, 1)


def test_source_local_timeline_and_related_candidate_rows():
    con, draft = synthetic_review()
    result = timeline(draft)
    assert result["ordering"] == "PER_SOURCE_LANE_ONLY"
    assert result["cross_stream_clock_alignment"] == "UNPROVEN"
    assert len(result["lanes"]) == 5
    original = next(x for x in result["lanes"] if x["table"] == "capture_events")
    assert len(original["events"]) == 1
    ev = original["events"][0]
    assert ev["summary"].startswith("Captured interaction candidate")
    assert ev["interpretation"] == "AMBIGUOUS"
    assert ev["relationship"]["classification"] == "INFERRED"
    assert "CONTRADICTORY_NPC_NAMES_FOR_INTERACTION" in ev["gaps"]
    assert len(ev["sources"]) == 3
    sha = hashlib.sha256(b"synthetic source bytes only\n").hexdigest()
    one = next(x for x in ev["sources"] if x["row_key"]["seq"] == 1)
    assert one["source_status"] == "AMBIGUOUS"
    assert one["recorded_metadata"]["message_id"] == 15
    assert one["recorded_metadata"]["direction"] == "Incoming"
    assert "raw_hex" not in one["recorded_metadata"]
    assert any(x["source_sha256"] == sha and x["start_line"] == 4
               and x["source_manifest"]["parser_version"] == "0"
               for x in one["references"])
    assert all(x["classification"] == "INFERRED" and x["causality"] == "UNPROVEN"
               for x in result["candidate_associations"])
    assert all(x["identity"] == "UNVERIFIED_CROSS_SOURCE"
               for x in result["candidate_associations"])
    assert any(x["basis"] == "MATCHING_CAPTURE_ENTITY_FIELD_AND_EXACT_ZONE_LABEL"
               for x in result["candidate_associations"])
    assert any(x["basis"] == "MATCHING_ZONE_LABEL_ONLY"
               for x in result["candidate_associations"])
    assert not any(x["left_step_id"] == "OBS-S002" or x["right_step_id"] == "OBS-S002"
                   for x in result["candidate_associations"])
    assert "Raw packet metadata" in next(
        lane["events"][0]["summary"] for lane in result["lanes"]
        if lane["table"] == "capture_raw_packets"
    )
    packet = next(lane["events"][0] for lane in result["lanes"]
                  if lane["table"] == "capture_raw_packets")
    pkt_meta = packet["sources"][0]["recorded_metadata"]
    assert pkt_meta["opcode"] == "SYNTHETIC_OPCODE"
    assert pkt_meta["is_injected"] == 1
    assert "raw_hex" not in pkt_meta
    con.close()


def test_bdd_preview_and_schema_handoff_cannot_create_oracle():
    con, draft = synthetic_review()
    bdd = behavior_preview(draft)
    assert bdd["classification"] == "PROPOSED_OBSERVATION_NARRATIVE"
    assert len(bdd["when"]) == len(draft["steps"])
    assert bdd["normative_expected"] is None
    assert bdd["verdict"] == "UNKNOWN"
    assert bdd["then"][0].startswith("UNKNOWN")
    export = manual_editor_handoff(draft)
    assert export["contract"] == "scenario_developer_manual_handoff_v1_DESIGN_ONLY"
    assert export["execution_enabled"] is False
    assert export["approved_for_execution"] is False
    assert export["verdict"] == "UNKNOWN"
    assert export["review_complete"] is False
    assert export["continue_in_scenario_developer"]["automatic_import"] is False
    assert export["continue_in_scenario_developer"]["not_a_save_payload"] is True
    assert export["continue_in_scenario_developer"]["route"] == "/scenario-developer"
    assert export["canonical_specification_seed"]["runner"] == "unassigned"
    assert export["canonical_specification_seed"]["execution_status"] == "design_only"
    assert export["canonical_specification_seed"]["feature_id"] is None
    assert export["canonical_specification_seed"]["case_id"] is None
    assert export["canonical_specification_seed"]["assertions"] == []
    assert export["canonical_specification_seed"]["observations"] == []
    try:
        validate_spec(export["canonical_specification_seed"])
    except ValueError:
        pass
    else:
        raise AssertionError("captured observation was treated as valid canonical oracle")
    con.close()


def test_step_and_binding_review_roundtrip_preserves_evidence():
    con, source = synthetic_review()
    snapshot = copy.deepcopy(source)
    step_decisions = []
    binding_decisions = []
    for i, step in enumerate(source["steps"]):
        choice = ("EDIT", "REJECT", "ACCEPT")[i % 3]
        entry = {"step_id": step["step_id"], "decision": choice,
                 "note": "Synthetic step reviewer comment"}
        if choice == "EDIT":
            entry["edited_title"] = "Synthetic suggested title only"
        step_decisions.append(entry)
        for j, b in enumerate(step["bindings"]):
            decision = ("ACCEPT", "EDIT", "REJECT")[j % 3]
            item = {"binding_id": b["binding_id"], "decision": decision,
                    "note": "Synthetic binding reviewer comment"}
            if decision == "EDIT":
                item["edited_value"] = "Synthetic reviewer-proposed candidate"
            binding_decisions.append(item)
    file_payload = {
        "contract": "offline_capture_review_decisions_v1_NONCANONICAL",
        "capture_id": 1,
        "capture_projection_sha256": manual_editor_handoff(source)["capture_projection_sha256"],
        "observed_handoff": manual_editor_handoff(source),
        "step_decisions": step_decisions,
        "binding_decisions": binding_decisions,
        "review_status": "MANUAL_AUTHORING_REQUIRED",
        "normative_expected": None, "verdict": "UNKNOWN",
        "execution_enabled": False, "approved_for_execution": False,
    }
    # JSON serialization simulates a browser-downloaded review file.
    file_payload = json.loads(json.dumps(file_payload))
    replay = replay_offline_review(source, file_payload)
    assert source == snapshot
    assert replay["review_complete"] is True
    assert replay["step_review_complete"] is True
    assert replay["binding_review_complete"] is True
    assert replay["execution_enabled"] is False
    assert replay["normative_expected"] is None
    assert replay["verdict"] == "UNKNOWN"
    assert replay["review_status"] == "MANUAL_AUTHORING_REQUIRED"
    assert replay["evidence_map"] == snapshot["evidence_map"]
    assert replay["canonical_specification_seed"] == snapshot["canonical_specification_seed"]
    assert replay["capture_projection_sha256"] == file_payload["capture_projection_sha256"]
    first = replay["reviewed_steps"][0]
    assert first["review"]["edited_title"] == "Synthetic suggested title only"
    assert first["observed_summary"] == snapshot["steps"][0]["observed_summary"]
    assert first["bindings"][0]["observed_value"] == snapshot["steps"][0]["bindings"][0]["observed_value"]
    con.close()


def test_incomplete_ambiguous_and_untrusted_file_fail_closed():
    con, draft = synthetic_review()
    pending = apply_step_decisions(draft, [
        {"step_id": draft["steps"][0]["step_id"], "decision": "REJECT",
         "note": "Evidence is ambiguous"},
    ])
    assert pending["step_review_complete"] is False
    incomplete = manual_editor_handoff(pending)
    assert incomplete["review_complete"] is False
    assert incomplete["execution_enabled"] is False
    for bad in [
        [{"step_id": "DOES-NOT-EXIST", "decision": "ACCEPT", "note": "fake"}],
        [{"step_id": draft["steps"][0]["step_id"], "decision": "EDIT",
          "note": "missing title"}],
        [{"step_id": draft["steps"][0]["step_id"], "decision": "ACCEPT",
          "note": "fine", "edited_title": "not allowed"}],
        [{"step_id": draft["steps"][0]["step_id"], "decision": "REJECT",
          "note": ""}],
        [{"step_id": draft["steps"][0]["step_id"], "decision": "ACCEPT", "note": "x",
          "execute": True}],
    ]:
        try:
            apply_step_decisions(draft, bad)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid review allowed")
    # A forged "reviewed" or source-backed oracle on the draft itself must
    # also fail closed, even before a browser decision envelope exists.
    for change in (
        lambda x: x["canonical_specification_seed"]["authoring"].update(state="reviewed"),
        lambda x: x["canonical_specification_seed"]["authoring"].update(execution_policy="write"),
        lambda x: x["canonical_specification_seed"]["steps"][0].update(expected="PASS is normative"),
        lambda x: x["canonical_specification_seed"]["steps"][0].update(assertion_ids=["invented"]),
    ):
        forged = copy.deepcopy(draft)
        change(forged)
        try:
            manual_editor_handoff(forged)
        except ValueError:
            pass
        else:
            raise AssertionError("forged canonical maturity/oracle accepted")
    baseline = manual_editor_handoff(draft)
    payload = {
        "contract": "offline_capture_review_decisions_v1_NONCANONICAL",
        "capture_id": 1,
        "capture_projection_sha256": baseline["capture_projection_sha256"],
        "observed_handoff": baseline,
        "step_decisions": [], "binding_decisions": [],
        "review_status": "MANUAL_AUTHORING_REQUIRED",
        "normative_expected": None, "verdict": "UNKNOWN",
        "execution_enabled": False, "approved_for_execution": False,
    }
    for modify in [
        lambda x: x.update(verdict="PASS"),
        lambda x: x.update(execution_enabled=True),
        lambda x: x.update(capture_projection_sha256="0" * 64),
        lambda x: x["observed_handoff"]["evidence_map"].clear(),
        lambda x: x["observed_handoff"]["canonical_specification_seed"].update(
            runner="xiheadless_observation_v1"),
    ]:
        item = copy.deepcopy(payload)
        modify(item)
        try:
            replay_offline_review(draft, item)
        except ValueError:
            pass
        else:
            raise AssertionError("tampered review payload accepted")
    con.close()


def test_html_is_standalone_escaped_and_offline_cli_never_edits_capture_db():
    con, draft = synthetic_review()
    injected = copy.deepcopy(draft)
    injected["steps"][0]["observed_summary"] = '</script><img src=x onerror=alert(1)>'
    html = render_review_html(injected)
    assert "</script><img" not in html
    assert "&lt;/script&gt;&lt;img" in html
    assert "\\u003c/script\\u003e" in html
    assert "connect-src 'none'" in html
    assert "Candidate cross-source associations" in html
    assert "Original indexed evidence / SHA-256 / parser version / packet metadata" in html
    assert "Export design-only review JSON" in html
    assert "Continue in Scenario Developer" in html
    assert "No scenario saved or executed" in html
    con.close()
    with TemporaryDirectory() as td:
        root = Path(td)
        db = root / "synthetic.sqlite"
        output = root / "review.html"
        writable = synthetic_interaction_with_key_item()
        destination = sqlite3.connect(db)
        writable.backup(destination)
        destination.close()
        writable.close()
        before = hashlib.sha256(db.read_bytes()).hexdigest()
        offline_main(["--database", str(db), "--capture-id", "1",
                      "--output", str(output)])
        assert output.exists()
        assert "OBSERVED ONLY" in output.read_text(encoding="utf-8")
        assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def main():
    test_source_local_timeline_and_related_candidate_rows()
    test_bdd_preview_and_schema_handoff_cannot_create_oracle()
    test_step_and_binding_review_roundtrip_preserves_evidence()
    test_incomplete_ambiguous_and_untrusted_file_fail_closed()
    test_html_is_standalone_escaped_and_offline_cli_never_edits_capture_db()
    print("Offline capture scenario review workflow (synthetic): PASS")


if __name__ == "__main__":
    main()
