"""SYNTHETIC tests for the durable offline receipt store (#1202 Phase A). tmp_path SQLite only."""
import sqlite3

import pytest

from workbench.server_admin.feature_testing import offline_receipt_store as store
from workbench.server_admin.feature_testing.results import init_db
from test_offline_evidence_reconciliation_1202 import receipt, terminal


def db(tmp_path):
    return tmp_path / "results.sqlite"


def count(path, table="offline_receipts"):
    with sqlite3.connect(str(path)) as c:
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_replay_across_reopen_is_no_change_and_writes_nothing(tmp_path):
    p, r = db(tmp_path), receipt()
    assert store.ingest(p, r)["status"] == "FIRST_SEEN"
    assert store.ingest(p, r)["status"] == "NO_CHANGE"
    assert count(p) == 1


def test_conflict_across_reopen_blocks_and_persists_nothing(tmp_path):
    p, r = db(tmp_path), receipt()
    store.ingest(p, r)
    other = receipt(evidence={"reported": "different"})
    assert store.ingest(p, other)["status"] == "BLOCKED"
    assert count(p) == 1


def test_partial_to_terminal_then_terminal_immutable(tmp_path):
    p, r = db(tmp_path), receipt()
    store.ingest(p, r)
    assert store.ingest(p, terminal(r))["status"] == "PARTIAL_TO_TERMINAL"
    late = terminal(r, receipt_id="synthetic-receipt-late", evidence={"reported": "late"})
    assert store.ingest(p, late)["status"] == "BLOCKED"
    snap = store.snapshot(p, "synthetic-run-01", "synthetic-execution-01", 1)
    assert snap["durable"] is True and snap["v1_import_eligible"] is False
    assert snap["authoritative_gameplay_verdict"] == "UNKNOWN"


def test_db_level_second_terminal_rejected_even_if_code_bypassed(tmp_path):
    p, r = db(tmp_path), receipt()
    store.ingest(p, r)
    store.ingest(p, terminal(r))
    with sqlite3.connect(str(p)) as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO offline_receipts (receipt_id, run_id, execution_id, attempt, operation_id, phase,"
                      " operation_state, evidence_sha256, receipt_json, ingested_at, outcome)"
                      " VALUES ('x','synthetic-run-01','synthetic-execution-01',1,'synthetic-operation-01',"
                      "'TERMINAL','failed','0','{}','t','o')")


def test_batch_is_atomic(tmp_path):
    p, r = db(tmp_path), receipt()
    bad = receipt(receipt_id="synthetic-receipt-02", evidence={"reported": "x"}, feature_id="other")
    assert store.ingest_many(p, [r, bad])["status"] == "BLOCKED"
    assert not p.exists() or count(p) == 0


def test_tampered_row_fails_integrity_check(tmp_path):
    p, r = db(tmp_path), receipt()
    store.ingest(p, r)
    with sqlite3.connect(str(p)) as c:
        c.execute("UPDATE offline_receipts SET receipt_json = replace(receipt_json, 'synthetic_observation_a', 'edited')")
    with pytest.raises(store.StoreIntegrityError):
        store.snapshot(p, "synthetic-run-01", "synthetic-execution-01", 1)
    with pytest.raises(store.StoreIntegrityError):
        store.ingest(p, r)


def test_never_writes_v1_results_and_coexists_with_results_table(tmp_path):
    p = db(tmp_path)
    init_db(p)
    store.ingest(p, receipt())
    assert count(p, "feature_test_results") == 0


def test_relative_path_and_missing_snapshot(tmp_path):
    with pytest.raises(ValueError):
        store.ingest("relative.sqlite", receipt())
    assert store.snapshot(db(tmp_path), "a", "b", 1) is None
