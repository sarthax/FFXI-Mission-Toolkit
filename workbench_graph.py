#!/usr/bin/env python3
"""Small SQLite-backed canonical Workbench graph.

SQLite is intentionally retained as the durable research/index store. The schema is generic and
stores domain-specific metadata as JSON rather than adding game-system columns to the core model.
"""
from __future__ import annotations
import argparse, json, sqlite3
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY, name TEXT NOT NULL, source_type TEXT NOT NULL, location TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS snapshots (
  snapshot_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, fingerprint TEXT, recorded_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}', FOREIGN KEY(source_id) REFERENCES sources(source_id)
);
CREATE TABLE IF NOT EXISTS entities (
  entity_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, display_name TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS entity_identifiers (
  entity_id TEXT NOT NULL, identifier_type TEXT NOT NULL, identifier_value TEXT NOT NULL,
  source_snapshot_id TEXT, PRIMARY KEY(entity_id, identifier_type, identifier_value),
  FOREIGN KEY(entity_id) REFERENCES entities(entity_id)
);
CREATE TABLE IF NOT EXISTS entity_relationships (
  relationship_id TEXT PRIMARY KEY, source_node TEXT NOT NULL, target_node TEXT NOT NULL,
  relationship TEXT NOT NULL, evidence_id TEXT, confidence TEXT NOT NULL DEFAULT 'UNKNOWN',
  status TEXT NOT NULL DEFAULT 'DISCOVERED', metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY, evidence_type TEXT NOT NULL, source TEXT NOT NULL,
  location TEXT, snapshot TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS findings (
  finding_id TEXT PRIMARY KEY, analysis_id TEXT, subject_id TEXT NOT NULL, field TEXT,
  value_json TEXT, status TEXT NOT NULL DEFAULT 'UNKNOWN', confidence TEXT NOT NULL DEFAULT 'UNKNOWN',
  evidence_id TEXT, source_snapshot_id TEXT, created_at TEXT, updated_at TEXT, notes_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS features (
  feature_id TEXT PRIMARY KEY, name TEXT NOT NULL, feature_type TEXT, domain_id TEXT,
  source_snapshot_id TEXT, target_snapshot_id TEXT, status TEXT NOT NULL DEFAULT 'DISCOVERED',
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY, artifact_type TEXT NOT NULL, path TEXT, source_snapshot_id TEXT,
  target_snapshot_id TEXT, feature_id TEXT, metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS implementations (
  implementation_id TEXT PRIMARY KEY, feature_id TEXT, source_snapshot_id TEXT,
  target_snapshot_id TEXT, artifact_id TEXT NOT NULL, artifact_type TEXT NOT NULL,
  status TEXT NOT NULL, language TEXT, path TEXT, symbol TEXT, change_type TEXT,
  scope TEXT, requires_build INTEGER NOT NULL DEFAULT 0, build_target TEXT,
  evidence_id TEXT, notes_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS validation_runs (
  run_id TEXT PRIMARY KEY, name TEXT NOT NULL, source_snapshot_id TEXT, target_snapshot_id TEXT,
  feature_id TEXT, status TEXT NOT NULL DEFAULT 'UNKNOWN', started_at TEXT, finished_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS validation_results (
  validation_id TEXT PRIMARY KEY, run_id TEXT, validation_type TEXT NOT NULL, subject_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'UNKNOWN', evidence_id TEXT, source TEXT, target TEXT,
  notes_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS analysis_results (
  analysis_id TEXT PRIMARY KEY, analysis_type TEXT NOT NULL, source TEXT NOT NULL,
  target TEXT, feature_id TEXT, status TEXT NOT NULL DEFAULT 'UNKNOWN',
  created_at TEXT, tool_version TEXT, findings_json TEXT NOT NULL DEFAULT '[]',
  notes_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS migrations (
  migration_id TEXT PRIMARY KEY, feature_id TEXT, source_snapshot_id TEXT,
  target_snapshot_id TEXT, status TEXT NOT NULL DEFAULT 'DISCOVERED', metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS migration_actions (
  action_id TEXT PRIMARY KEY, migration_id TEXT NOT NULL, action TEXT NOT NULL,
  artifact_id TEXT, status TEXT NOT NULL DEFAULT 'DISCOVERED', reason TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_artifacts_feature ON artifacts(feature_id);
CREATE INDEX IF NOT EXISTS idx_validation_results_run ON validation_results(run_id);
CREATE INDEX IF NOT EXISTS idx_validation_results_subject ON validation_results(subject_id);
CREATE INDEX IF NOT EXISTS idx_relationship_source ON entity_relationships(source_node);
CREATE INDEX IF NOT EXISTS idx_relationship_target ON entity_relationships(target_node);
CREATE INDEX IF NOT EXISTS idx_findings_subject ON findings(subject_id);
CREATE INDEX IF NOT EXISTS idx_implementations_feature ON implementations(feature_id);
"""

def init_db(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con

def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)

def insert_record(con: sqlite3.Connection, record: Any, record_type: str | None = None):
    d = asdict(record) if is_dataclass(record) else (dict(record) if isinstance(record, dict) else vars(record))
    cls = record_type or type(record).__name__
    if cls == "Artifact":
        con.execute("INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?,?,?,?)",
                    (d["artifact_id"], d["artifact_type"], d["path"], d["source_snapshot_id"],
                     d["target_snapshot_id"], d["feature_id"], _json(d["metadata"])))
    elif cls == "Feature":
        con.execute("INSERT OR REPLACE INTO features VALUES (?,?,?,?,?,?,?,?)",
                    (d["feature_id"], d["name"], d["feature_type"], d["domain_id"],
                     d["source_snapshot_id"], d["target_snapshot_id"], d["status"], _json(d["metadata"])))
    elif cls == "MigrationAction":
        con.execute("INSERT OR REPLACE INTO migration_actions VALUES (?,?,?,?,?,?,?)",
                    (d["action_id"], d["migration_id"], d["action"], d["artifact_id"],
                     d["status"], d["reason"], _json(d["metadata"])))
    elif cls == "ValidationResult":
        con.execute("INSERT OR REPLACE INTO validation_results VALUES (?,?,?,?,?,?,?,?,?)",
                    (d["validation_id"], d.get("run_id"), d["validation_type"], d["subject_id"],
                     d["status"], d["evidence_id"], d["source"], d["target"], _json(d["notes"])))
    elif cls == "Evidence":
        con.execute("INSERT OR REPLACE INTO evidence VALUES (?,?,?,?,?,?)",
                    (d["evidence_id"], d["evidence_type"], d["source"], d["location"], d["snapshot"], d["notes"]))
    elif cls == "DependencyEdge":
        con.execute("INSERT OR REPLACE INTO entity_relationships VALUES (?,?,?,?,?,?,?,?)",
                    (d["edge_id"], d["source_node"], d["target_node"], d["relationship"],
                     d["evidence_id"], d["confidence"], d["status"], _json(d["notes"])))
    elif cls == "Finding":
        con.execute("INSERT OR REPLACE INTO findings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d["finding_id"], d["analysis_id"], d["subject_id"], d["field"], _json(d["value"]),
                     d["status"], d["confidence"], d["evidence_id"], d["source_snapshot_id"],
                     d["created_at"], d["updated_at"], _json(d["notes"])))
    elif cls == "Implementation":
        con.execute("INSERT OR REPLACE INTO implementations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d["implementation_id"], d["feature_id"], d["source_snapshot_id"], d["target_snapshot_id"],
                     d["artifact_id"], d["artifact_type"], d["status"], d["language"], d["path"], d["symbol"],
                     d["change_type"], d["scope"], int(d["requires_build"]), d["build_target"],
                     d["evidence_id"], _json(d["notes"])))
    elif cls == "AnalysisResult":
        con.execute("INSERT OR REPLACE INTO analysis_results VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (d["analysis_id"], d["analysis_type"], d["source"], d["target"], d["feature_id"],
                     d["status"], d["created_at"], d["tool_version"], _json(d["findings"]), _json(d["notes"])))
    elif cls == "ValidationRun":
        con.execute("INSERT OR REPLACE INTO validation_runs VALUES (?,?,?,?,?,?,?,?,?)",
                    (d["run_id"], d["name"], d["source_snapshot_id"], d["target_snapshot_id"], d["feature_id"],
                     d["status"], d["started_at"], d["finished_at"], _json(d["metadata"])))
    else:
        raise TypeError(f"Unsupported Workbench record: {cls}")

def import_json(path: Path, db: Path):
    payload=json.loads(path.read_text(encoding="utf-8"))
    con=init_db(db)
    for key, record_type in (
        ("features","Feature"),("artifacts","Artifact"),("findings","Finding"),
        ("implementations","Implementation"),("edges","DependencyEdge"),
        ("migration_actions","MigrationAction"),("validation_runs","ValidationRun"),
        ("validation_results","ValidationResult"),
    ):
        for row in payload.get(key, []):
            insert_record(con,row,record_type)
    if isinstance(payload.get("feature"),dict):
        insert_record(con,payload["feature"],"Feature")
    if isinstance(payload.get("migration"),dict):
        m=payload["migration"]
        fid=m.get("feature_id") or payload.get("feature",{}).get("feature_id")
        con.execute("INSERT OR REPLACE INTO migrations VALUES (?,?,?,?,?,?)",
                    (m["migration_id"],fid,m.get("source_snapshot_id"),m.get("target_snapshot_id"),
                     m.get("status","DISCOVERED"),_json(m.get("metadata",{}))))
    for row in payload.get("actions",[]):
        insert_record(con,row,"MigrationAction")
    if isinstance(payload.get("validation"),dict):
        insert_record(con,payload["validation"],"ValidationResult")
    if "analysis" in payload:
        insert_record(con,payload["analysis"],"AnalysisResult")
    con.commit()
    con.close()


def self_test() -> None:
    from tempfile import NamedTemporaryFile
    from workbench_schema import Artifact, Feature, MigrationAction, ValidationResult, ValidationRun, Implementation, AnalysisResult
    with NamedTemporaryFile(suffix=".db") as tmp:
        con = init_db(Path(tmp.name))
        insert_record(con, Feature("f", "Feature", "system", "domain", "src", "dst"))
        insert_record(con, Artifact("a", "LUA", "x.lua", "src", "dst", "f"))
        insert_record(con, MigrationAction("ma", "m", "CONVERT", "a"))
        insert_record(con, ValidationRun("vr", "test", "src", "dst", "f", "VERIFIED"))
        insert_record(con, ValidationResult("v", "syntax", "a", "VERIFIED"))
        insert_record(con, Implementation("i", "f", "src", "dst", "a", "LUA", "MIGRATED"))
        insert_record(con, AnalysisResult("ar", "TEST", "src"))
        con.commit()
        expected = {
            "features": 1, "artifacts": 1, "migration_actions": 1,
            "validation_results": 1, "validation_runs": 1, "implementations": 1, "analysis_results": 1,
        }
        actual = {k: con.execute(f"SELECT COUNT(*) FROM {k}").fetchone()[0] for k in expected}
        assert actual == expected, (actual, expected)
        con.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path("workbench.db"))
    ap.add_argument("--import-json", type=Path)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        print("workbench_graph self-test: PASS")
        return
    if args.import_json:
        import_json(args.import_json, args.db)
    else:
        init_db(args.db).close()

if __name__ == "__main__":
    main()
