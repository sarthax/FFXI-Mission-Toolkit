#!/usr/bin/env python3
from pathlib import Path
import sqlite3
import tempfile

from feature_package_analyzer import analyze, import_to_graph


def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        package=root/"demo"
        package.mkdir()
        (package/"FEATURE_MANIFEST.yaml").write_text(
            """{
  "feature": {"id":"feature:test:demo","name":"Demo","type":"MISSION","domain":"test"},
  "dependencies": [{"target":"capability:test","relationship":"REQUIRES","evidence":"fixture"}]
}
""",
            encoding="utf-8",
        )
        (package/"demo.lua").write_text("return 1\n",encoding="utf-8")
        (package/"BACKPORT_REPORT.md").write_text("Needs review\n",encoding="utf-8")

        payload=analyze(package)
        assert payload["schema"]==2,payload
        assert payload["edges"]==payload["dependencies"],payload
        assert payload["migration_actions"]==payload["actions"],payload
        assert payload["analysis"]["analysis_type"]=="BACKPORT_REPORT",payload
        assert payload["findings"],payload
        assert payload["evidence"],payload

        db=root/"workbench.db"
        import_to_graph(payload,db)
        con=sqlite3.connect(db)
        assert con.execute("SELECT COUNT(*) FROM features WHERE feature_id='feature:test:demo'").fetchone()[0]==1
        assert con.execute("SELECT COUNT(*) FROM artifacts WHERE feature_id='feature:test:demo'").fetchone()[0]>=1
        assert con.execute("SELECT COUNT(*) FROM entity_relationships WHERE relationship='REQUIRES'").fetchone()[0]>=1
        assert con.execute("SELECT COUNT(*) FROM migrations WHERE migration_id='migration:feature:test:demo'").fetchone()[0]==1
        assert con.execute("SELECT COUNT(*) FROM migration_actions WHERE migration_id='migration:feature:test:demo'").fetchone()[0]>=1
        assert con.execute("SELECT COUNT(*) FROM analysis_results WHERE analysis_type='BACKPORT_REPORT'").fetchone()[0]==1
        assert con.execute("SELECT COUNT(*) FROM findings WHERE analysis_id='analysis:backport-report:feature:test:demo'").fetchone()[0]>=1
        assert con.execute("SELECT COUNT(*) FROM evidence WHERE evidence_id='evidence:backport-report:feature:test:demo'").fetchone()[0]==1
        con.close()

    print("feature package canonical graph import self-test: PASS")


if __name__=="__main__":
    main()
