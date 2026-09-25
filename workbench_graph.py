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
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS artifacts (\n  artifact_id TEXT PRIMARY KEY, artifact_type TEXT NOT NULL, path TEXT, source_snapshot_id TEXT,\n  target_snapshot_id TEXT, feature_id TEXT, metadata_json TEXT NOT NULL DEFAULT '{}'\n);\nCREATE TABLE IF NOT EXISTS implementations (
  implementation_id TEXT PRIMARY KEY, feature_id TEXT, source_snapshot_id TEXT,
  target_snapshot_id TEXT, artifact_id TEXT NOT NULL, artifact_type TEXT NOT NULL,
  status TEXT NOT NULL, language TEXT, path TEXT, symbol TEXT, change_type TEXT,
  scope TEXT, requires_build INTEGER NOT NULL DEFAULT 0, build_target TEXT,
  evidence_id TEXT, notes_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS validation_runs (\n  run_id TEXT PRIMARY KEY, name TEXT NOT NULL, source_snapshot_id TEXT, target_snapshot_id TEXT,\n  feature_id TEXT, status TEXT NOT NULL DEFAULT 'UNKNOWN', started_at TEXT, finished_at TEXT, metadata_json TEXT NOT NULL DEFAULT '{}'\n);\nCREATE TABLE IF NOT EXISTS validation_results (\n  validation_id TEXT PRIMARY KEY, run_id TEXT, validation_type TEXT NOT NULL, subject_id TEXT NOT NULL,\n  status TEXT NOT NULL DEFAULT 'UNKNOWN', evidence_id TEXT, source TEXT, target TEXT, notes_json TEXT NOT NULL DEFAULT '[]'\n);\nCREATE TABLE IF NOT EXISTS analysis_results (
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
CREATE INDEX IF NOT EXISTS idx_artifacts_feature ON artifacts(feature_id);\nCREATE INDEX IF NOT EXISTS idx_validation_results_run ON validation_results(run_id);\nCREATE INDEX IF NOT EXISTS idx_validation_results_subject ON validation_results(subject_id);\nCREATE INDEX IF NOT EXISTS idx_relationship_source ON entity_relationships(source_node);
CREATE INDEX IF NOT EXISTS idx_relationship_target ON entity_relationships(target_node);
CREATE INDEX IF NOT EXISTS idx_findings_subject ON findings(subject_id);
CREATE INDEX IF NOT EXISTS idx_implementations_feature ON implementations(feature_id);
"""

def init_db(path: Path) -> sqlite3.Connection:
    con=sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con

def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)

def insert_record(con: sqlite3.Connection, record: Any, record_type: str | None = None):
    d=asdict(record) if is_dataclass(record) else (dict(record) if isinstance(record, dict) else vars(record))
    cls=record_type or type(record).__name__
    if cls=="Artifact":\n        con.execute("INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?,?,?,?)", (d["artifact_id"],d["artifact_type"],d["path"],d["source_snapshot_id"],d["target_snapshot_id"],d["feature_id"],_json(d["metadata"])))\n    elif cls=="Feature":\n        con.execute("INSERT OR REPLACE INTO features VALUES (?,?,?,?,?,?,?,?)", (d["feature_id"],d["name"],d["feature_type"],d["domain_id"],d["source_snapshot_id"],d["target_snapshot_id"],d["status"],_json(d["metadata"])))\n    elif cls=="MigrationAction":\n        con.execute("INSERT OR REPLACE INTO migration_actions VALUES (?,?,?,?,?,?,?)", (d["action_id"],d["migration_id"],d["action"],d["artifact_id"],d["status"],d["reason"],_json(d["metadata"])))\n    elif cls=="ValidationResult":\n        con.execute("INSERT OR REPLACE INTO validation_results VALUES (?,?,?,?,?,?,?,?,?)", (d["validation_id"],d.get("run_id"),d["validation_type"],d["subject_id"],d["status"],d["evidence_id"],d["source"],d["target"],_json(d["notes"])))\n    elif cls=="Evidence":
        con.execute("INSERT OR REPLACE INTO evidence VALUES (?,?,?,?,?,?)",
                    (d["evidence_id"],d["evidence_type"],d["source"],d["location"],d["snapshot"],d["notes"]))
    elif cls=="DependencyEdge":
        con.execute("INSERT OR REPLACE INTO entity_relationships VALUES (?,?,?,?,?,?,?,?)",
                    (d["edge_id"],d["source_node"],d["target_node"],d["relationship"],d["evidence_id"],d["confidence"],d["status"],_json(d["notes"])))
    elif cls=="Finding":
        con.execute("INSERT OR REPLACE INTO findings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d["finding_id"],d["analysis_id"],d["subject_id"],d["field"],_json(d["value"]),d["status"],d["confidence"],d["evidence_id"],d["source_snapshot_id"],d["created_at"],d["updated_at"],_json(d["notes"])))
    elif cls=="Implementation":
        con.execute("INSERT OR REPLACE INTO implementations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d["implementation_id"],d["feature_id"],d["source_snapshot_id"],d["target_snapshot_id"],d["artifact_id"],d["artifact_type"],d["status"],d["language"],d["path"],d["symbol"],d["change_type"],d["scope"],int(d["requires_build"]),d["build_target"],d["evidence_id"],_json(d["notes"])))
    elif cls=="AnalysisResult":
        con.execute("INSERT OR REPLACE INTO analysis_results VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (d["analysis_id"],d["analysis_type"],d["source"],d["target"],d["feature_id"],d["status"],d["created_at"],d["tool_version"],_json(d["findings"]),_json(d["notes"])))
    else:
        raise TypeError(f"Unsupported Workbench record: {cls}")

def import_json(path: Path, db: Path):
    payload=json.loads(path.read_text(encoding="utf-8"))
    con=init_db(db)
    for key, record_type in (("features","Feature"),("artifacts","Artifact"),("findings","Finding"),("implementations","Implementation"),("edges","DependencyEdge"),("migration_actions","MigrationAction"),("validation_results","ValidationResult")):
        for row in payload.get(key,[]):
            insert_record(con,row,record_type)
    if "analysis" in payload:
        insert_record(con,payload["analysis"],"AnalysisResult")
    con.commit()
    con.close()

