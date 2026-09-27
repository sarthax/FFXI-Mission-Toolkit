#!/usr/bin/env python3
"""Focused regression matrix for snapshot-aware binding compatibility."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from workbench.analyzers.server.binding_compatibility import compare_bindings


def function(snapshot, ident, symbol, return_type="int"):
    cls, name = symbol.rsplit("::", 1)
    return {"function_id": ident, "qualified_name": symbol, "name": name,
            "class_name": cls, "source_snapshot_id": snapshot, "path": f"src/{cls}.cpp",
            "line": 10, "definition": True, "declaration": False,
            "evidence_id": f"evidence:{ident}", "signature": {"return_type": return_type,
            "parameters": [], "const": False, "static": False, "noexcept": False}}


def binding(snapshot, ident, lua_name, system, symbol=None, cls=None, function_id=None):
    return {"binding_id": ident, "lua_name": lua_name, "binding_system": system,
            "cpp_symbol": symbol, "class_name": cls, "function_id": function_id,
            "source_snapshot_id": snapshot, "path": f"src/{ident}.cpp", "line": 20,
            "evidence_id": f"evidence:{ident}",
            "status": "RESOLVED" if function_id else "UNRESOLVED", "notes": []}


def payload(snapshot, functions, bindings):
    return {"schema": 1, "analysis": {"source_snapshot_id": snapshot},
            "binding_coverage": {"status": "PARTIAL", "systems": ["SOL2", "LUNAR"]},
            "functions": functions, "bindings": bindings}


def main():
    ss, ts = "snapshot:source", "snapshot:target"
    source_specs = [("exact", "same", "A", "A::same"),
                    ("representation", "repr", "A", "A::repr"),
                    ("rename", "oldName", "A", "A::renamed"),
                    ("class", "moved", "OldClass", "OldClass::moved"),
                    ("implementation", "impl", "A", "A::impl"),
                    ("missing", "gone", "A", "A::gone"),
                    ("ambiguous", "shared", "MissingClass", "MissingClass::shared")]
    sf = [function(ss, f"sf:{key}", symbol) for key, _name, _cls, symbol in source_specs]
    sb = [binding(ss, f"sb:{key}", name, "SOL2", symbol, cls, f"sf:{key}")
          for key, name, cls, symbol in source_specs]
    sb.append(binding(ss, "sb:unresolved", "unknown", "SOL2"))
    target_specs = [("exact", "same", "A", "A::same", "SOL2"),
                    ("representation", "repr", "A", "A::repr", "LUNAR"),
                    ("rename", "newName", "A", "A::renamed", "SOL2"),
                    ("class", "moved", "NewClass", "NewClass::moved", "SOL2"),
                    ("implementation", "impl", "A", "A::implV2", "SOL2"),
                    ("ambiguous1", "shared", "One", "One::shared", "SOL2"),
                    ("ambiguous2", "shared", "Two", "Two::shared", "LUNAR")]
    tf = [function(ts, f"tf:{key}", symbol)
          for key, _name, _cls, symbol, _system in target_specs]
    tb = [binding(ts, f"tb:{key}", name, system, symbol, cls, f"tf:{key}")
          for key, name, cls, symbol, system in target_specs]
    source, target = payload(ss, sf, sb), payload(ts, tf, tb)
    result = compare_bindings(source, target)
    categories = {row["source"]["binding_id"]: row["category"] for row in result["results"]}
    assert categories == {"sb:ambiguous": "AMBIGUOUS",
                          "sb:class": "RENAMED_CLASS_DRIFT_CANDIDATE",
                          "sb:exact": "EXACT_MATCH",
                          "sb:implementation": "IMPLEMENTATION_DRIFT",
                          "sb:missing": "MISSING_BINDING",
                          "sb:rename": "RENAMED_CLASS_DRIFT_CANDIDATE",
                          "sb:representation": "REPRESENTATION_DRIFT",
                          "sb:unresolved": "UNRESOLVED"}, categories
    missing = next(row for row in result["results"] if row["source"]["binding_id"] == "sb:missing")
    assert missing["absence_scope"] == "INDEXED_SURFACE_ONLY" and missing["confidence"] == "UNKNOWN"
    assert result["coverage"]["target"]["status"] == "PARTIAL"
    assert all(row["source_snapshot_id"] == ss and row["target_snapshot_id"] == ts
               for row in result["results"])
    assert all(row["source"].get("evidence_id") for row in result["results"])
    exact = next(row for row in result["results"] if row["source"]["binding_id"] == "sb:exact")
    assert exact["match_basis"] == ["LUA_NAME", "CLASS"]
    assert exact["evidence"]["source"]["source_snapshot_id"] == ss
    assert result == compare_bindings(source, target), "output and IDs must be deterministic"
    bad = json.loads(json.dumps(source))
    bad["bindings"][0]["source_snapshot_id"] = "wrong"
    try:
        compare_bindings(bad, target)
        raise AssertionError("mixed snapshots must fail closed")
    except ValueError:
        pass
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source_path, target_path = root / "source.json", root / "target.json"
        output_path, db_path = root / "result.json", root / "graph.db"
        source_path.write_text(json.dumps(source), encoding="utf-8")
        target_path.write_text(json.dumps(target), encoding="utf-8")
        subprocess.run([sys.executable, "-m", "workbench.cli.binding_compatibility",
                        str(source_path), str(target_path), "--json", str(output_path),
                        "--graph-db", str(db_path)], check=True)
        emitted = json.loads(output_path.read_text(encoding="utf-8"))
        assert emitted["analysis"]["analysis_type"] == "BINDING_COMPATIBILITY"
        con = sqlite3.connect(db_path)
        assert con.execute("SELECT COUNT(*) FROM analysis_results").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == len(sb)
        value = json.loads(con.execute(
            "SELECT value_json FROM findings WHERE subject_id='sb:representation'").fetchone()[0])
        assert value["category"] == "REPRESENTATION_DRIFT"
        con.close()
    print("binding compatibility self-test: PASS")


if __name__ == "__main__":
    main()
