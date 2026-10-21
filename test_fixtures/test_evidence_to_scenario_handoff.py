#!/usr/bin/env python3
"""Synthetic-only end-to-end review handoff; no DATs, live client or DB writes."""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3

from test_capture_reverse_scenario_draft import synthetic_index
from workbench.captures.scenario_draft import reconstruct_observed_draft
from workbench.captures.scenario_handoff import (
    apply_binding_decisions, build_scenario_handoff, reconstruct_review_draft,
)
from workbench.server_admin.feature_testing.test_specifications import validate_spec


def synthetic_interaction_with_key_item():
    con = synthetic_index()
    # Add synthetic contradiction: same source-local entity id, conflicting label.
    con.execute(
        "INSERT INTO capture_events VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (1, "SYNTHETIC_ZONE", 3, "Incoming", None, "synthetic observation",
         7000, "CONTRADICTING_SYNTHETIC_LABEL", None, None, None),
    )
    con.execute("""CREATE TABLE capture_ki_events (
        capture_id INTEGER, seq INTEGER, ts TEXT, event_type TEXT,
        keyitem_id INTEGER, keyitem_name TEXT, zone_name TEXT
    )""")
    con.execute(
        "INSERT INTO capture_ki_events VALUES (?,?,?,?,?,?,?)",
        (1, 4, None, "SYNTHETIC_KI_LOG_EVENT", 9000, "SYNTHETIC_KI", "SYNTHETIC_ZONE"),
    )
    # Add a second exact indexed source mapping for event row 1: ambiguity is visible.
    con.execute(
        "INSERT INTO capture_row_locators VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (1, "CONFLICTING_SYNTHETIC_SOURCE.log", "capture_events",
         json.dumps({"zone_db": "SYNTHETIC_ZONE", "seq": 1}, sort_keys=True),
         "b" * 64, "line", 8, 8, None, None, "{}"),
    )
    # An explicitly synthetic opcode permits testing the raw *metadata* binding.
    # The base fixture intentionally leaves it absent, in which case no opcode
    # identity candidate must be invented.
    con.execute("UPDATE capture_raw_packets SET opcode=? WHERE capture_id=1 AND seq=1",
                ("SYNTHETIC_OPCODE",))
    # Ordinary items are a different capture family from Key Item logger events.
    con.execute("""CREATE TABLE capture_structured_records (
        capture_id INTEGER, source_file TEXT, family TEXT, record_key TEXT,
        record_type TEXT, ts TEXT, zone TEXT, entity_id INTEGER,
        entity_name TEXT, item_id INTEGER, item_name TEXT
    )""")
    con.execute(
        "INSERT INTO capture_structured_records VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (1, "SYNTHETIC_ITEMS.csv", "synthetic_item_report", "row:1", "observed-item",
         None, "SYNTHETIC_ZONE", 7000, "SYNTHETIC_ACTOR", 5000, "SYNTHETIC_ORDINARY_ITEM"),
    )
    item_hash = hashlib.sha256(b"synthetic item source bytes only\\n").hexdigest()
    con.execute(
        "INSERT INTO capture_source_manifest VALUES (?,?,?,?,?,?)",
        (1, "SYNTHETIC_ITEMS.csv", item_hash, "synthetic structured", "0", "RECOGNIZED"),
    )
    con.execute(
        "INSERT INTO capture_row_locators VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (1, "SYNTHETIC_ITEMS.csv", "capture_structured_records",
         json.dumps({"source_file": "SYNTHETIC_ITEMS.csv",
                     "family": "synthetic_item_report", "record_key": "row:1"}, sort_keys=True),
         item_hash, "csv-row", 2, 2, None, None, "{}"),
    )
    con.commit()
    return con


def test_synthetic_npc_interaction_draft_and_provenance():
    con = synthetic_interaction_with_key_item()
    con.execute("PRAGMA query_only=ON")
    draft = reconstruct_review_draft(con, 1)
    assert draft["contract"] == "evidence_to_scenario_review_v0_NONCANONICAL"
    assert draft["scenario_status"] == "DRAFT_REVIEW_REQUIRED"
    assert draft["execution_enabled"] is False
    assert draft["approved_for_execution"] is False
    assert draft["normative_expected"] is None
    assert draft["observation_verdict"] == "UNKNOWN"
    assert draft["canonical_validation_status"].startswith("BLOCKED_")
    assert len(draft["steps"]) == 5, draft["steps"]
    step = draft["steps"][0]
    assert step["lane"] == "capture_events"
    assert "Captured interaction candidate" in step["observed_summary"]
    assert "CONTRADICTING_SYNTHETIC_LABEL" in step["observed_summary"]
    assert step["relationship"]["classification"] == "INFERRED"
    assert step["relationship"]["proof"] == "NOT_A_CONFIRMED_GAMEPLAY_TRANSACTION"
    assert step["normative_expected"] is None
    assert step["verdict"] == "UNKNOWN"
    assert len(step["evidence_refs"]) == 3
    npc_name = next(b for b in step["bindings"] if b["kind"] == "npc_name")
    assert npc_name["classification"] == "AMBIGUOUS"
    assert npc_name["observed_value"] == ["SYNTHETIC_ACTOR", "CONTRADICTING_SYNTHETIC_LABEL"]
    assert "CONTRADICTORY_NPC_NAMES_FOR_INTERACTION" in step["review_gaps"]
    assert "SOURCE_AMBIGUOUS" in step["review_gaps"]
    assert "GROUPED_BY_ADJACENCY_NOT_PROVEN_TRANSACTION" in step["review_gaps"]

    refs = [draft["evidence_map"][ref] for ref in step["evidence_refs"]]
    first = next(r for r in refs if r["row_key"]["seq"] == 1)
    assert first["table"] == "capture_events"
    assert first["row_key"] == {"zone_db": "SYNTHETIC_ZONE", "seq": 1}
    assert first["source"]["status"] == "AMBIGUOUS"
    assert len(first["source"]["references"]) == 2
    original = next(r for r in first["source"]["references"] if r["filename"] == "SYNTHETIC_ONLY.log")
    assert original["source_sha256"] == hashlib.sha256(b"synthetic source bytes only\n").hexdigest()
    assert original["start_line"] == original["end_line"] == 4
    assert original["source_manifest"]["parser_version"] == "0"

    eventview = next(s for s in draft["steps"] if s["lane"] == "capture_eventview")
    mes = next(b for b in eventview["bindings"] if b["kind"] == "message_or_event")
    assert mes["classification"] == "AMBIGUOUS"
    assert "meaning unresolved" in eventview["observed_summary"]
    ki = next(s for s in draft["steps"] if s["lane"] == "capture_ki_events")
    assert next(b["observed_value"] for b in ki["bindings"] if b["kind"] == "key_item") == 9000
    item = next(s for s in draft["steps"] if s["lane"] == "capture_structured_records")
    assert "ordinary" not in item["observed_summary"].lower() or "ownership" in item["observed_summary"]
    assert next(b["observed_value"] for b in item["bindings"] if b["kind"] == "item") == 5000
    assert "SYNTHETIC_ORDINARY_ITEM" in item["observed_summary"]
    item_source = draft["evidence_map"][item["evidence_refs"][0]]["source"]
    assert item_source["status"] == "LOCATED_SOURCE_SPAN"
    assert item_source["references"][0]["source_sha256"] == hashlib.sha256(b"synthetic item source bytes only\\n").hexdigest()
    packet = next(s for s in draft["steps"] if s["lane"] == "capture_raw_packets")
    assert packet["record_class"] == "INDEXED_RAW"
    assert next(b["classification"] for b in packet["bindings"] if b["kind"] == "packet") == "UNSUPPORTED"
    assert "PACKET_INJECTED_OR_BLOCKED_NOT_RECEIPT" in packet["review_gaps"]
    assert draft["canonical_step_evidence_map"][step["step_id"]] == step["evidence_refs"]
    assert all(d["review"]["decision"] == "PENDING" for s in draft["steps"] for d in s["bindings"])
    con.close()


def test_compatibility_scaffold_is_deliberately_not_importable_specification():
    con = synthetic_interaction_with_key_item()
    result = reconstruct_review_draft(con, 1)
    seed = result["canonical_specification_seed"]
    assert seed["runner"] == "unassigned"
    assert seed["execution_status"] == "design_only"
    assert seed["schema_version"] == 1
    assert set(seed["behavior"]) == {"given", "when", "then"}
    assert set(seed["authoring"]) == {"state", "execution_policy", "evidence_provenance",
                                      "blocking_gaps", "review_required"}
    assert set(seed["steps"][0]) == {"id", "title", "intent", "expected",
                                    "assertion_ids", "evidence_refs", "confidence_note"}
    assert seed["feature_id"] is None and seed["case_id"] is None
    assert seed["assertions"] == [] and seed["observations"] == []
    assert all(not s["assertion_ids"] and not s["evidence_refs"] for s in seed["steps"])
    assert all(s["expected"].startswith("UNKNOWN") for s in seed["steps"])
    assert seed["authoring"]["review_required"] is True
    # With current and proposed #1263 validators, this is NOT a publishable spec.
    try:
        validate_spec(seed)
    except ValueError:
        pass
    else:
        raise AssertionError("unresolved observed-only scaffold became a validated spec")
    con.close()


def test_review_decisions_never_overwrite_observation_or_enable_execution():
    con = synthetic_interaction_with_key_item()
    source = reconstruct_review_draft(con, 1)
    original = copy.deepcopy(source)
    proposals = [b for s in source["steps"] for b in s["bindings"]]
    decisions = []
    for idx, proposal in enumerate(proposals):
        decision = ("ACCEPT", "EDIT", "REJECT")[idx % 3]
        item = {"binding_id": proposal["binding_id"], "decision": decision,
                "note": "Synthetic reviewer decision, NOT a source truth assertion"}
        if decision == "EDIT":
            item["edited_value"] = "SYNTHETIC_REVIEWER_SUGGESTION"
        decisions.append(item)
    amended = apply_binding_decisions(source, decisions)
    assert amended["review_complete"] is True
    assert source == original  # Pure update; original evidence stays untouched.
    assert amended["evidence_map"] == original["evidence_map"]
    assert amended["canonical_specification_seed"] == original["canonical_specification_seed"]
    assert amended["execution_enabled"] is False
    assert amended["approved_for_execution"] is False
    assert amended["normative_expected"] is None
    assert amended["scenario_status"] == "DRAFT_REVIEW_REQUIRED"
    amended_proposals = [b for s in amended["steps"] for b in s["bindings"]]
    assert [b["observed_value"] for b in amended_proposals] == [b["observed_value"] for b in proposals]
    assert [b["review"]["decision"] for b in amended_proposals] == [d["decision"] for d in decisions]
    edited = next(b for b in amended_proposals if b["review"]["decision"] == "EDIT")
    assert edited["review"]["edited_value"] == "SYNTHETIC_REVIEWER_SUGGESTION"
    con.close()


def test_incomplete_untrusted_preview_stays_blocked_and_bounded():
    con = synthetic_index()
    p = reconstruct_observed_draft(con, 1)
    draft = build_scenario_handoff(p, max_steps=1)
    assert draft["omitted_step_count"] == 2
    assert "DRAFT_STEP_PREVIEW_TRUNCATED" in draft["review_gaps"]
    assert "PARTIAL_CAPTURE_TABLE_COVERAGE" in draft["review_gaps"]
    assert draft["missing_tables"] == ["capture_ki_events"]
    assert len(draft["steps"]) == 1
    for edit in (
        lambda x: x.update(verdict="PASS"),
        lambda x: x.update(execution_enabled=True),
        lambda x: x.update(normative_expected="invented"),
        lambda x: x.update(contract="unsupported"),
    ):
        tampered = copy.deepcopy(p)
        edit(tampered)
        try:
            build_scenario_handoff(tampered)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe preview accepted")
    for bad in (0, 101, True):
        try:
            build_scenario_handoff(p, max_steps=bad)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid max_steps accepted")
    con.close()


def test_reviewer_contract_rejects_invalid_or_unreviewed_bindings():
    con = synthetic_index()
    draft = reconstruct_review_draft(con, 1)
    binding = draft["steps"][0]["bindings"][0]["binding_id"]
    for bad in (
        [{"binding_id": "not-a-binding", "decision": "ACCEPT", "note": "unknown"}],
        [{"binding_id": binding, "decision": "AUTO_APPROVE", "note": "not permitted"}],
        [{"binding_id": binding, "decision": "EDIT", "note": "needs value"}],
        [{"binding_id": binding, "decision": "ACCEPT", "note": ""}],
        [{"binding_id": binding, "decision": "REJECT", "note": "reject",
          "edited_value": "alter evidence"}],
        [{"binding_id": binding, "decision": "ACCEPT", "note": "test",
          "source_sha256": "forged"}],
        [{"binding_id": binding, "decision": "ACCEPT", "note": "ok"},
         {"binding_id": binding, "decision": "REJECT", "note": "duplicate"}],
    ):
        try:
            apply_binding_decisions(draft, bad)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid reviewer decision accepted: " + repr(bad))
    con.close()


def main():
    test_synthetic_npc_interaction_draft_and_provenance()
    test_compatibility_scaffold_is_deliberately_not_importable_specification()
    test_review_decisions_never_overwrite_observation_or_enable_execution()
    test_incomplete_untrusted_preview_stays_blocked_and_bounded()
    test_reviewer_contract_rejects_invalid_or_unreviewed_bindings()
    print("Evidence-to-scenario synthetic reviewer handoff: PASS")


if __name__ == "__main__":
    main()
