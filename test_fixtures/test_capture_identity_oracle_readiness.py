#!/usr/bin/env python3
"""Synthetic-only source candidate, oracle readiness, and drift regressions."""
from __future__ import annotations

from copy import deepcopy
import sqlite3
from unittest.mock import patch

from test_evidence_to_scenario_handoff import synthetic_interaction_with_key_item
from workbench.captures.scenario_handoff import reconstruct_review_draft, apply_binding_decisions
from workbench.captures.scenario_identity_readiness import (
    assess_evidence_readiness, candidate_dsp_catalogs,
)


def fixture():
    db = synthetic_interaction_with_key_item()
    db.execute("PRAGMA query_only=ON")
    return db, reconstruct_review_draft(db, 1)


def binding(draft, step_no, kind):
    return next(b for b in draft["steps"][step_no]["bindings"] if b["kind"] == kind)


def source(kind, rows, *, complete=False, dsp_commit=None):
    return {
        "kind": kind, "query": "SYNTHETIC_ONLY",
        "choices": rows, "source_lineage": "configured_local_dsp",
        "source_revision": "a" * 64 if complete else None,
        "completeness": "attested_complete_scoped_export" if complete
            else "bounded_catalog_query_not_full_inventory",
        "dsp_commit": dsp_commit, "binding_verified": False,
        "execution_enabled": False, "operator_review_required": True,
    }


def record(kind, key, name, *, path=None, zone=None):
    filenames = {"npc": "sql/npc_list.sql", "item": "sql/item_basic.sql",
                 "keyitem": "scripts/globals/keyitems.lua",
                 "zone": "sql/zone_settings.sql",
                 "event": "scripts/zones/SYNTHETIC_ZONE/npcs/SYNTHETIC_ACTOR.lua",
                 "dialog": "scripts/zones/SYNTHETIC_ZONE/npcs/SYNTHETIC_ACTOR.lua"}
    row = {
        "kind": kind, ("id" if kind not in {"event", "dialog"} else "value"): key,
        "name": name, "source_path": path or filenames[kind],
        "identity_status": "unreconciled_source_candidate",
        "binding_verified": False, "execution_enabled": False,
    }
    if zone is not None:
        row["zone_db"] = zone
    return row


def proof_for(b, kind, rec):
    return {
        "classification": "independent_reconciliation",
        "binding_id": b["binding_id"],
        "source_revision": "a" * 64, "source_kind": kind,
        "observed_value": deepcopy(b["observed_value"]),
        "source_id": rec.get("id", rec.get("value")),
        "source_path": rec["source_path"], "line": 42,
        "reconciliation_ref": "SYNTHETIC_3RD_PARTY_IDENTITY_CROSSWALK",
    }


def independent_oracle(step):
    return {
        "step_id": step["step_id"], "origin": "independent_dsp_source",
        "from_capture": False, "execution_enabled": False,
        "path": "scripts/zones/SYNTHETIC_ZONE/npcs/SYNTHETIC_ACTOR.lua",
        "line": 82, "dsp_commit": "d" * 40, "file_sha256": "e" * 64,
        "preconditions": ["Synthetic branch guard", "Synthetic player state predicate"],
        "readback": "Independent persisted server flag after approved save boundary",
        "expected_candidate": "SYNTHETIC_SOURCE_DERIVED_STATE",
    }


def test_synthetic_npc_exact_source_record_and_ambiguous_names():
    con, draft = fixture()
    npc = binding(draft, 0, "npc")
    npc_name = binding(draft, 0, "npc_name")
    event = binding(draft, 0, "event")
    dialog = binding(draft, 0, "dialog")
    row = record("npc", 7000, "SYNTHETIC_ACTOR", zone="SYNTHETIC_ZONE")
    rows = [row, record("npc", 7001, "CONTRADICTING_SYNTHETIC_LABEL",
                        zone="SYNTHETIC_ZONE")]
    snapshots = {
        npc["binding_id"]: source("npc", [row], complete=True, dsp_commit="d" * 40),
        npc_name["binding_id"]: source("npc", rows),
        event["binding_id"]: source("event", [
            record("event", "SYNTHETIC_EVENT", "SYNTHETIC_EVENT",
                   zone="SYNTHETIC_ZONE")], complete=True),
        dialog["binding_id"]: source("dialog", [
            record("dialog", 15, "SYNTHETIC_DIALOG", zone="SYNTHETIC_ZONE")]),
    }
    original = deepcopy(draft)
    results = assess_evidence_readiness(
        draft, catalog_snapshots=snapshots,
        reconciliations=[proof_for(npc, "npc", row)],
        independent_oracles=[independent_oracle(draft["steps"][0])],
    )
    step = results["steps"][0]
    matched = {x["kind"]: x for x in step["identity_candidates"]}
    assert matched["npc"]["classification"] == "EXACT"
    assert matched["npc"]["selected_source"]["id"] == 7000
    assert matched["npc"]["source_identity_verified"] is False
    assert matched["npc_name"]["classification"] == "AMBIGUOUS"
    assert len(matched["npc_name"]["source_candidates"]) == 2
    assert matched["event"]["classification"] == "INFERRED"
    assert matched["dialog"]["classification"] == "INFERRED"
    assert matched["zone"]["classification"] == "UNRESOLVED"
    assert step["oracle"]["readiness"] == "SOURCE_CANDIDATE_REVIEW_REQUIRED"
    assert step["oracle"]["expected_candidate"] == "SYNTHETIC_SOURCE_DERIVED_STATE"
    assert step["oracle"]["normative_expected"] is None
    assert step["oracle"]["independent_source"]["line"] == 82
    assert "INDEPENDENT_READBACK_NOT_YET_OBSERVED" in step["missing_observations_or_review"]
    assert "Ambiguous, unavailable or unverifiable original source-file locator" in step["missing_observations_or_review"]
    assert all(x["normative_expected"] is None and x["verdict"] == "UNKNOWN"
               and x["execution_enabled"] is False for x in results["steps"])
    assert results["schema_compatibility"]["automatic_import"] is False
    assert results["source_integrity"] == "INDEXED_HASHES_ONLY_NOT_REHASHED"
    assert draft == original
    # Reviewing a binding never authenticates source or changes oracle readiness.
    reviewed = apply_binding_decisions(draft, [
        {"binding_id": npc["binding_id"], "decision": "ACCEPT",
         "note": "Synthetic candidate only; not independently source byte checked"},
    ])
    again = assess_evidence_readiness(reviewed, catalog_snapshots=snapshots,
                                      reconciliations=[proof_for(npc, "npc", row)])
    assert again["steps"][0]["identity_candidates"][1]["review_decision"]["decision"] == "ACCEPT"
    assert again["steps"][0]["identity_candidates"][1]["source_identity_verified"] is False
    assert again["steps"][0]["oracle"]["readiness"] == "UNKNOWN"
    con.close()


def test_single_bounded_catalog_hit_never_claims_exact():
    con, draft = fixture()
    npc = binding(draft, 0, "npc")
    row = record("npc", 7000, "SYNTHETIC_ACTOR", zone="SYNTHETIC_ZONE")
    limited = source("npc", [row], complete=False)
    result = assess_evidence_readiness(draft, catalog_snapshots={npc["binding_id"]: limited},
                                      reconciliations=[proof_for(npc, "npc", row)])
    match = next(b for b in result["steps"][0]["identity_candidates"] if b["kind"] == "npc")
    assert match["classification"] == "INFERRED"
    assert match["source_identity_verified"] is False
    bad = source("npc", [row, dict(row)], complete=True)
    result = assess_evidence_readiness(draft, catalog_snapshots={npc["binding_id"]: bad},
                                      reconciliations=[proof_for(npc, "npc", row)])
    assert next(b for b in result["steps"][0]["identity_candidates"]
                if b["kind"] == "npc")["classification"] == "AMBIGUOUS"
    assert next(b for b in result["steps"][-1]["identity_candidates"]
                if b["kind"] == "packet")["classification"] == "UNSUPPORTED"
    con.close()


def test_oracle_revision_mismatch_and_invalid_source_inputs_fail_closed():
    con, draft = fixture()
    npc = binding(draft, 0, "npc")
    row = record("npc", 7000, "SYNTHETIC_ACTOR", zone="SYNTHETIC_ZONE")
    snap = source("npc", [row], complete=True, dsp_commit="f" * 40)
    result = assess_evidence_readiness(draft,
        catalog_snapshots={npc["binding_id"]: snap},
        independent_oracles=[independent_oracle(draft["steps"][0])])
    assert result["steps"][0]["oracle"]["readiness"] == "REVISION_BLOCKED"
    assert "DSP_SOURCE_REVISION_MISMATCH" in result["steps"][0]["oracle"]["blockers"]
    for altered in (
        lambda x: x.update(from_capture=True),
        lambda x: x.update(dsp_commit="not-a-revision"),
        lambda x: x.update(path="../unsafe.lua"),
        lambda x: x.update(preconditions=[]),
        lambda x: x.update(readback=""),
        lambda x: x.update(expected_candidate=None),
        lambda x: x.update(execution_enabled=True),
    ):
        bad = independent_oracle(draft["steps"][0])
        altered(bad)
        try:
            assess_evidence_readiness(draft, independent_oracles=[bad])
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe/unpinned oracle accepted")
    con.close()


def second_capture(con, *, changed_message=16, drift=False):
    con.execute("INSERT INTO captures VALUES (2)")
    tables = ("capture_events", "capture_eventview", "capture_raw_packets",
              "capture_ki_events", "capture_structured_records",
              "capture_source_manifest", "capture_row_locators")
    for table in tables:
        cols = [r[1] for r in con.execute("PRAGMA table_info(" + table + ")").fetchall()]
        source_cols = ",".join('"' + x + '"' for x in cols[1:])
        con.execute(f'INSERT INTO "{table}" SELECT 2,{source_cols} FROM "{table}" WHERE capture_id=1')
    con.execute("UPDATE capture_events SET message_id=? WHERE capture_id=2 AND zone_db=? AND seq=1",
                (changed_message, "SYNTHETIC_ZONE"))
    if drift:
        con.execute("UPDATE capture_source_manifest SET parser_version=? WHERE capture_id=2",
                    ("SYNTHETIC_PARSER_CHANGED",))
    con.commit()
    return reconstruct_review_draft(con, 2)


def test_cross_capture_variation_not_false_gameplay_failure():
    con = synthetic_interaction_with_key_item()
    first = reconstruct_review_draft(con, 1)
    other = second_capture(con)
    output = assess_evidence_readiness(first, comparison_drafts=[other])
    assert output["repeated_capture_variations"]
    found = next(v for v in output["repeated_capture_variations"] if v["field"] == "dialog")
    assert found["recorded_values"] == [15, 16]
    assert found["capture_ids"] == [1, 2]
    assert found["kind"] == "REPEATED_CAPTURE_VARIATION_NOT_PROVEN_CONTRADICTION"
    assert found["comparability"] == "SOURCE_REVISIONS_INDEXED_PRECONDITIONS_NOT_ESTABLISHED"
    assert output["verdict"] == "UNKNOWN"
    # Indexed parser drift makes the comparison even less defensible.
    con.execute("UPDATE capture_source_manifest SET parser_version=? WHERE capture_id=2",
                ("SYNTHETIC_REVISION_DIFFERENT",))
    other = reconstruct_review_draft(con, 2)
    result = assess_evidence_readiness(first, comparison_drafts=[other])
    assert next(v for v in result["repeated_capture_variations"]
                if v["field"] == "dialog")["comparability"] == "SOURCE_OR_PARSER_REVISION_DIFFERENT"
    con.close()


def test_existing_catalog_adapter_is_only_bounded_read_only_source(monkey_patch=None):
    con, draft = fixture()
    calls = []
    def fake_search(root, kind, query, *, limit):
        calls.append((root, kind, query, limit))
        return source(kind, [])
    with patch("workbench.server_admin.scenario_authoring.catalog_adapter.search_catalog",
               side_effect=fake_search):
        snapshots = candidate_dsp_catalogs(draft, "/SYNTHETIC_READ_ONLY_DSP", limit=10)
    assert calls
    assert all(kind in {"npc", "zone", "item", "keyitem"} for _, kind, _, _ in calls)
    assert not any(kind in {"event", "dialog", "gm"} for _, kind, _, _ in calls)
    assert all(entry["source_revision"] is None for entry in snapshots.values())
    assert all(entry["binding_verified"] is False for entry in snapshots.values())
    con.close()


def main():
    test_synthetic_npc_exact_source_record_and_ambiguous_names()
    test_single_bounded_catalog_hit_never_claims_exact()
    test_oracle_revision_mismatch_and_invalid_source_inputs_fail_closed()
    test_cross_capture_variation_not_false_gameplay_failure()
    test_existing_catalog_adapter_is_only_bounded_read_only_source()
    print("synthetic catalog identity and source-oracle readiness: PASS")


if __name__ == "__main__":
    main()
