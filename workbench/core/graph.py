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
  status TEXT NOT NULL DEFAULT 'DISCOVERED', metadata_json TEXT NOT NULL DEFAULT '{}',
  source_snapshot_id TEXT
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
CREATE TABLE IF NOT EXISTS functions (
  function_id TEXT PRIMARY KEY, qualified_name TEXT NOT NULL, name TEXT NOT NULL,
  namespace TEXT, class_name TEXT, source_snapshot_id TEXT, path TEXT, line INTEGER,
  kind TEXT, declaration INTEGER NOT NULL DEFAULT 0, definition INTEGER NOT NULL DEFAULT 0,
  signature_json TEXT NOT NULL DEFAULT '{}', evidence_id TEXT, notes_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS bindings (
  binding_id TEXT PRIMARY KEY, lua_name TEXT NOT NULL, binding_system TEXT NOT NULL,
  cpp_symbol TEXT, class_name TEXT, function_id TEXT, source_snapshot_id TEXT, path TEXT, line INTEGER,
  evidence_id TEXT, status TEXT NOT NULL DEFAULT 'UNKNOWN', notes_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS enum_definitions (
  enum_id TEXT PRIMARY KEY, enum_name TEXT NOT NULL, source_snapshot_id TEXT, path TEXT, line INTEGER,
  format TEXT NOT NULL, value TEXT NOT NULL, symbol TEXT NOT NULL, evidence_id TEXT,
  notes_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS build_targets (
  target_id TEXT PRIMARY KEY, name TEXT NOT NULL, build_system TEXT NOT NULL, path TEXT,
  source_snapshot_id TEXT, artifact_id TEXT, status TEXT NOT NULL DEFAULT 'DISCOVERED',
  notes_json TEXT NOT NULL DEFAULT '[]'
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
  notes_json TEXT NOT NULL DEFAULT '[]', source_snapshot_id TEXT
);
CREATE TABLE IF NOT EXISTS capabilities (
  capability_id TEXT PRIMARY KEY, name TEXT NOT NULL, capability_type TEXT NOT NULL,
  subject_id TEXT, source_snapshot_id TEXT, status TEXT NOT NULL DEFAULT 'UNKNOWN',
  value_json TEXT, evidence_id TEXT, notes_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS capability_requirements (
  requirement_id TEXT PRIMARY KEY, feature_id TEXT NOT NULL, capability_id TEXT NOT NULL,
  required INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'UNKNOWN',
  evidence_id TEXT, notes_json TEXT NOT NULL DEFAULT '[]'
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
CREATE INDEX IF NOT EXISTS idx_build_targets_artifact ON build_targets(artifact_id);
CREATE INDEX IF NOT EXISTS idx_capabilities_subject ON capabilities(subject_id);
CREATE INDEX IF NOT EXISTS idx_capability_requirements_feature ON capability_requirements(feature_id);
CREATE INDEX IF NOT EXISTS idx_capability_requirements_capability ON capability_requirements(capability_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_feature ON artifacts(feature_id);
CREATE INDEX IF NOT EXISTS idx_functions_symbol ON functions(qualified_name);
CREATE INDEX IF NOT EXISTS idx_bindings_cpp_symbol ON bindings(cpp_symbol);
CREATE INDEX IF NOT EXISTS idx_enums_symbol ON enum_definitions(symbol);
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
    if cls == "Function":
        sig=d["signature"]
        con.execute("INSERT OR REPLACE INTO functions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d["function_id"],d["qualified_name"],d["name"],d["namespace"],d["class_name"],
                     d["source_snapshot_id"],d["path"],d["line"],d["kind"],int(d["declaration"]),
                     int(d["definition"]),_json(sig),d["evidence_id"],_json(d["notes"])))
    elif cls == "Binding":
        con.execute("INSERT OR REPLACE INTO bindings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (d["binding_id"],d["lua_name"],d["binding_system"],d["cpp_symbol"],d["class_name"],
                     d["function_id"],d["source_snapshot_id"],d["path"],d["line"],d["evidence_id"],
                     d["status"],_json(d["notes"])))
        if d.get("function_id"):
            con.execute("INSERT OR REPLACE INTO entity_relationships VALUES (?,?,?,?,?,?,?,?,?)",
                        (f"binds:{d['binding_id']}:{d['function_id']}",d["binding_id"],d["function_id"],
                         "BINDS",d.get("evidence_id"),"VERIFIED" if d.get("status")=="RESOLVED" else "UNKNOWN",
                         "DISCOVERED",_json({"binding_system":d["binding_system"]}),d.get("source_snapshot_id")))
    elif cls == "EnumDefinition":
        con.execute("INSERT OR REPLACE INTO enum_definitions VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (d["enum_id"],d["enum_name"],d["source_snapshot_id"],d["path"],d["line"],
                     d["format"],d["value"],d["symbol"],d["evidence_id"],_json(d["notes"])))
    elif cls == "BuildTarget":
        con.execute("INSERT OR REPLACE INTO build_targets VALUES (?,?,?,?,?,?,?,?)",
                    (d["target_id"], d["name"], d["build_system"], d["path"], d["source_snapshot_id"],
                     d["artifact_id"], d["status"], _json(d["notes"])))
    elif cls == "Artifact":
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
        con.execute("INSERT OR REPLACE INTO entity_relationships VALUES (?,?,?,?,?,?,?,?,?)",
                    (d["edge_id"], d["source_node"], d["target_node"], d["relationship"],
                     d["evidence_id"], d["confidence"], d["status"], _json(d["notes"]),
                     d.get("source_snapshot_id")))
    elif cls == "Capability":
        con.execute("INSERT OR REPLACE INTO capabilities VALUES (?,?,?,?,?,?,?,?,?)",
                    (d["capability_id"], d["name"], d["capability_type"], d["subject_id"],
                     d["source_snapshot_id"], d["status"], _json(d["value"]), d["evidence_id"], _json(d["notes"])))
    elif cls == "CapabilityRequirement":
        con.execute("INSERT OR REPLACE INTO capability_requirements VALUES (?,?,?,?,?,?,?)",
                    (d["requirement_id"], d["feature_id"], d["capability_id"], int(d["required"]),
                     d["status"], d["evidence_id"], _json(d["notes"])))
        # Requirements are first-class graph edges so feature tracing can move from a
        # feature to the client/server capability it depends on.
        con.execute("INSERT OR REPLACE INTO entity_relationships VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"requires:{d['requirement_id']}", d["feature_id"], d["capability_id"],
                     "REQUIRES", d.get("evidence_id"), "VERIFIED",
                     "DISCOVERED", _json({"required": bool(d["required"]), "requirement_id": d["requirement_id"]}), None))
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
        con.execute("INSERT OR REPLACE INTO analysis_results VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (d["analysis_id"], d["analysis_type"], d["source"], d["target"], d["feature_id"],
                     d["status"], d["created_at"], d["tool_version"], _json(d["findings"]), _json(d["notes"]),
                     d.get("source_snapshot_id")))
    elif cls == "ValidationRun":
        con.execute("INSERT OR REPLACE INTO validation_runs VALUES (?,?,?,?,?,?,?,?,?)",
                    (d["run_id"], d["name"], d["source_snapshot_id"], d["target_snapshot_id"], d["feature_id"],
                     d["status"], d["started_at"], d["finished_at"], _json(d["metadata"])))
    else:
        raise TypeError(f"Unsupported Workbench record: {cls}")
def resolve_relationships(con: sqlite3.Connection) -> int:
    """Resolve deterministic lexical node aliases after all records are imported."""
    changed = 0
    rows = con.execute("SELECT relationship_id, target_node FROM entity_relationships").fetchall()
    for rid, target in rows:
        if target.startswith("cpp-symbol:"):
            symbol = target[len("cpp-symbol:"):]
            hit = con.execute(
                "SELECT function_id FROM functions WHERE qualified_name=? ORDER BY definition DESC, line LIMIT 1",
                (symbol,),
            ).fetchone()
            if hit:
                con.execute(
                    "UPDATE entity_relationships SET target_node=?, confidence=?, metadata_json=? WHERE relationship_id=?",
                    (hit[0], "VERIFIED", _json({"resolved_from": target, "resolution": "exact qualified C++ symbol"}), rid),
                )
                changed += 1
    return changed


def import_json(path: Path, db: Path):
    payload=json.loads(path.read_text(encoding="utf-8"))
    con=init_db(db)
    for key, record_type in (
        ("features","Feature"),("artifacts","Artifact"),("build_targets","BuildTarget"),("functions","Function"),("bindings","Binding"),("enums_constants","EnumDefinition"),("findings","Finding"),("capabilities","Capability"),("capability_requirements","CapabilityRequirement"),
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
    if isinstance(payload.get("validation_run"),dict):
        insert_record(con,payload["validation_run"],"ValidationRun")
    elif isinstance(payload.get("validation_run"),list):
        for row in payload["validation_run"]:
            insert_record(con,row,"ValidationRun")
    if isinstance(payload.get("validation"),dict):
        insert_record(con,payload["validation"],"ValidationResult")
    if "analysis" in payload:
        insert_record(con,payload["analysis"],"AnalysisResult")
    resolve_relationships(con)
    con.commit()
    con.close()


def self_test() -> None:
    from tempfile import NamedTemporaryFile
    from workbench.core.schema import (
        Artifact, Feature, MigrationAction, ValidationResult, ValidationRun,
        Implementation, AnalysisResult, Function, Binding, EnumDefinition, DependencyEdge, Capability, CapabilityRequirement,
    )
    with NamedTemporaryFile(suffix=".db") as tmp:
        con = init_db(Path(tmp.name))
        insert_record(con, Feature("f", "Feature", "system", "domain", "src", "dst"))
        insert_record(con, Artifact("a", "LUA", "x.lua", "src", "dst", "f"))
        insert_record(con, MigrationAction("ma", "m", "CONVERT", "a"))
        insert_record(con, ValidationRun("vr", "test", "src", "dst", "f", "VERIFIED"))
        insert_record(con, ValidationResult("v", "syntax", "a", "VERIFIED"))
        insert_record(con, Implementation("i", "f", "src", "dst", "a", "LUA", "MIGRATED"))
        insert_record(con, AnalysisResult("ar", "TEST", "src", notes=["test"]))
        fn = Function("fn", "Foo::bar", "bar", class_name="Foo", definition=True)
        insert_record(con, fn)
        insert_record(con, Binding("b", "bar", "SOL2", "Foo::bar", "Foo", "fn", status="RESOLVED"))
        insert_record(con, EnumDefinition("e", "State", None, "state.h", 1, "CXX_ENUM", "1", "READY"))
        insert_record(con, DependencyEdge("de", "packet:1", "cpp-symbol:Foo::bar", "HANDLED_BY", confidence="VERIFIED", source_snapshot_id="src"))
        insert_record(con, Capability("cap", "wardrobe_slots", "CLIENT", subject_id="client:test", status="UNKNOWN"))
        insert_record(con, CapabilityRequirement("req", "f", "cap", required=True, status="UNKNOWN"))
        resolve_relationships(con)
        con.commit()
        expected = {
            "features": 1, "artifacts": 1, "migration_actions": 1,
            "validation_results": 1, "validation_runs": 1, "implementations": 1, "analysis_results": 1,
            "functions": 1, "bindings": 1, "enum_definitions": 1, "entity_relationships": 3, "capabilities": 1, "capability_requirements": 1,
        }
        actual = {k: con.execute(f"SELECT COUNT(*) FROM {k}").fetchone()[0] for k in expected}
        assert actual == expected, (actual, expected)
        target = con.execute("SELECT target_node, confidence FROM entity_relationships WHERE relationship_id='de'").fetchone()
        assert target == ("fn", "VERIFIED"), target
        binding = con.execute("SELECT relationship, target_node, confidence FROM entity_relationships WHERE relationship_id='binds:b:fn'").fetchone()
        assert binding == ("BINDS", "fn", "VERIFIED"), binding
        requirement = con.execute("SELECT source_node, target_node, relationship, confidence FROM entity_relationships WHERE relationship_id='requires:req'").fetchone()
        assert requirement == ("f", "cap", "REQUIRES", "VERIFIED"), requirement
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
