#!/usr/bin/env python3
"""Regression checks for package dependency closure and user scope review."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from workbench.core import graph
from workbench.core.schema import Artifact, DependencyEdge, MigrationAction
from workbench.migrations.package_scope import (
    build_dependency_scope,
    save_scope_decision,
    set_scope_review_status,
)


def main():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "workbench.db"
        con = graph.init_db(db)
        con.row_factory = sqlite3.Row
        con.execute(
            "INSERT INTO migrations VALUES (?,?,?,?,?,?)",
            ("migration:test", "feature:test", "src", "dst", "DISCOVERED", "{}"),
        )

        root = Artifact("artifact:root", "LUA", "scripts/root.lua", "src", "dst", "feature:test")
        dep = Artifact("artifact:dep", "SQL", "sql/dep.sql", "src", "dst", "feature:test")
        graph.insert_record(con, root)
        graph.insert_record(con, dep)
        graph.insert_record(
            con,
            MigrationAction(
                "action:root", "migration:test", "CONVERT", "artifact:root",
                "AUTO_MIGRATABLE", "Root artifact needs migration.",
            ),
        )
        con.execute(
            "INSERT INTO functions(function_id,qualified_name,name,namespace,class_name,"
            "source_snapshot_id,path,line,kind,declaration,definition,signature_json,evidence_id,notes_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "function:dep", "Engine::dep", "dep", "Engine", "Engine", "src",
                "src/engine.cpp", 10, "FUNCTION", 0, 1, "{}", "evidence:function", "[]",
            ),
        )
        graph.insert_record(
            con,
            DependencyEdge(
                "edge:root-dep", "artifact:root", "artifact:dep", "REQUIRES",
                confidence="VERIFIED", status="DISCOVERED", source_snapshot_id="src",
            ),
        )
        graph.insert_record(
            con,
            DependencyEdge(
                "edge:dep-function", "artifact:dep", "function:dep", "CALLS",
                evidence_id="evidence:function", confidence="INFERRED",
                status="DISCOVERED", source_snapshot_id="src",
            ),
        )
        con.commit()

        scope = build_dependency_scope(con, "migration:test")
        by_id = {item["node_id"]: item for item in scope["items"]}
        assert scope["discovered_count"] == 3, scope
        assert by_id["artifact:root"]["effective_decision"] == "INCLUDE", scope
        assert by_id["artifact:dep"]["effective_decision"] == "QUESTIONABLE", scope
        assert by_id["function:dep"]["effective_decision"] == "QUESTIONABLE", scope
        assert scope["closure_status"] == "MANUAL_REQUIRED", scope
        assert scope["package_gate"] == "REVIEW_REQUIRED", scope

        save_scope_decision(con, "migration:test", "artifact:dep", "INCLUDE", tags=("sql", "investigate"))
        save_scope_decision(con, "migration:test", "function:dep", "INCLUDE")
        scope = build_dependency_scope(con, "migration:test")
        fn = next(item for item in scope["items"] if item["node_id"] == "function:dep")
        assert fn["review_required"] is True, fn
        assert scope["closure_status"] == "MANUAL_REQUIRED", scope

        try:
            save_scope_decision(con, "migration:test", "function:dep", "TARGET_EQUIVALENT")
            raise AssertionError("TARGET_EQUIVALENT without reason should fail")
        except ValueError:
            pass

        save_scope_decision(
            con,
            "migration:test",
            "function:dep",
            "TARGET_EQUIVALENT",
            reason="Verified equivalent target engine function.",
            tags=("engine", "verified-target"),
        )
        scope = build_dependency_scope(con, "migration:test")
        assert not scope["unresolved_node_ids"], scope
        assert scope["closure_status"] == "COMPLETE_WITH_REVIEWED_EXCLUSIONS", scope
        assert scope["package_gate"] == "REVIEW_REQUIRED", scope

        set_scope_review_status(
            con,
            "migration:test",
            "REVIEWED",
            notes="Fixture review complete.",
            scope_hash=scope["scope_hash"],
        )
        reviewed = build_dependency_scope(con, "migration:test")
        assert reviewed["review"]["status"] == "REVIEWED", reviewed
        assert reviewed["package_gate"] == "READY", reviewed

        late = Artifact("artifact:late", "SQL", "sql/late.sql", "src", "dst", "feature:test")
        graph.insert_record(con, late)
        graph.insert_record(
            con,
            DependencyEdge(
                "edge:late", "artifact:dep", "artifact:late", "REQUIRES",
                confidence="VERIFIED", status="DISCOVERED", source_snapshot_id="src",
            ),
        )
        con.commit()

        stale = build_dependency_scope(con, "migration:test")
        assert stale["review"]["status"] == "STALE", stale
        assert stale["package_gate"] != "READY", stale
        assert "artifact:late" in stale["unresolved_node_ids"], stale
        con.close()

    print("package scope review self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
