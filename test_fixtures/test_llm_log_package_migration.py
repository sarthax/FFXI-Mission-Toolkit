from __future__ import annotations

import sqlite3
from pathlib import Path

from workbench.devtools.research.legacy_llm import log as canonical
from workbench.runtime.paths import DATABASE_PATH


def test_root_module_is_retired_and_packaged_log_is_canonical():
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "llm_log.py").exists()
    assert canonical.DB_PATH == DATABASE_PATH


def test_record_read_filter_and_source_listing_use_configured_db(tmp_path, monkeypatch):
    db_path = tmp_path / "llm-log.db"
    monkeypatch.setattr(canonical, "DB_PATH", db_path)

    canonical.record(
        "manual",
        "model-a",
        "first prompt",
        response="first response",
        usage={"response_token/s": 20.0, "total_duration": 2_000_000_000},
    )
    canonical.record("capture", "model-b", "second prompt", error="failed")

    rows = canonical.recent(limit=10)
    assert [row["source"] for row in rows] == ["capture", "manual"]
    assert rows[1]["usage_display"] == "20 tok/s, 2.0s"
    assert canonical.recent(source="manual")[0]["prompt"] == "first prompt"
    assert canonical.recent(model="model-b")[0]["error"] == "failed"
    assert canonical.recent(q="response")[0]["source"] == "manual"
    assert canonical.distinct_sources() == ["capture", "manual"]

    detail = canonical.get_by_id(rows[1]["id"])
    assert detail is not None
    assert detail["response"] == "first response"
    assert detail["usage"]["response_token/s"] == 20.0


def test_init_db_adds_usage_column_to_legacy_table(tmp_path):
    db_path = tmp_path / "legacy.db"
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            "CREATE TABLE llm_call_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL NOT NULL, source TEXT NOT NULL, "
            "model TEXT NOT NULL, prompt TEXT NOT NULL, response TEXT, error TEXT)"
        )
        con.commit()
        canonical.init_db(con)
        columns = {row[1] for row in con.execute("PRAGMA table_info(llm_call_log)").fetchall()}
        assert "usage_json" in columns
    finally:
        con.close()


def test_truncate_preserves_existing_marker_shape(monkeypatch):
    monkeypatch.setattr(canonical, "MAX_STORED_CHARS", 5)
    assert canonical._truncate("abcdefgh") == "abcde\n... [truncated, 8 chars total]"
