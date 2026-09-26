#!/usr/bin/env python3
"""Regression checks for safe migration package materialization."""
from pathlib import Path
import tempfile

from workbench.migrations.package_materialize import materialize_package, write_materialization_journal


def main():
    manifest={
        "migration":{"migration_id":"migration:test","status":"READY"},
        "execution":{"steps":[
            {"backend":"lua","path":"scripts/test.lua"},
            {"backend":"sql","path":"sql/test.sql"},
            {"backend":"manual","path":"notes.md"},
        ]},
    }
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        source=root/"source"
        package=root/"package"
        (source/"scripts").mkdir(parents=True)
        (source/"sql").mkdir(parents=True)
        (source/"scripts"/"test.lua").write_text("return 1\n",encoding="utf-8")
        (source/"sql"/"test.sql").write_text("SELECT 1;\n",encoding="utf-8")

        result=materialize_package(manifest,source,package)
        assert result.status=="MATERIALIZED",result
        assert (package/"lua"/"scripts"/"test.lua").exists(),result
        assert (package/"sql"/"test.sql").exists(),result
        assert len(result.artifacts)==2,result
        assert all(len(a.sha256)==64 for a in result.artifacts),result
        journal=write_materialization_journal(package,manifest,result)
        assert journal.exists(),journal
        journal_text=journal.read_text(encoding="utf-8")
        assert "WORKBENCH_MATERIALIZATION_JOURNAL" in journal_text,journal_text

        second=materialize_package(manifest,source,package)
        assert second.status=="PARTIAL",second
        assert len(second.skipped)==2,second

        blocked=dict(manifest)
        blocked["migration"]={"migration_id":"migration:test","status":"BLOCKED"}
        try:
            materialize_package(blocked,source,package)
        except ValueError:
            pass
        else:
            raise AssertionError("BLOCKED plan must not materialize")

        unsafe={
            "migration":{"status":"READY"},
            "execution":{"steps":[{"backend":"lua","path":"../escape.lua"}]},
        }
        try:
            materialize_package(unsafe,source,package)
        except ValueError:
            pass
        else:
            raise AssertionError("path traversal must be rejected")

    print("migration package materialization self-test: PASS")


if __name__=="__main__":
    main()
