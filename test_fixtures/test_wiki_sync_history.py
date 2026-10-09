"""Persisted Wiki sync history differentiates completed runs from incomplete runs."""
import sqlite3
import tempfile
from pathlib import Path
from workbench.devtools.reference import wiki_bulk_jobs as jobs

def main():
    with tempfile.TemporaryDirectory() as folder:
        db=Path(folder)/"cache.db"
        with jobs._connect(db) as con:
            con.execute("""INSERT INTO wiki_bulk_jobs
                (id,source,state,mode,page_limit,started_at,completed_at)
                VALUES (?,?,?,?,?,?,?)""",
                ("complete","FFXIclopedia","completed","changed",50,
                 "2026-10-09 08:00:00","2026-10-09 09:00:00"))
            con.execute("""INSERT INTO wiki_bulk_jobs
                (id,source,state,mode,page_limit,started_at)
                VALUES (?,?,?,?,?,?)""",
                ("failure","FFXIclopedia","error","changed",50,"2026-10-09 10:00:00"))
        summary=jobs.sync_summary(db)
        assert summary["last_success"]["changed"]["at"]=="2026-10-09 09:00:00"
        assert summary["last_success"]["changed"]["runs"]==1
        assert "missing" not in summary["last_success"]
        assert summary["latest"]["state"]=="error"
    print("Wiki synchronization history: PASS")

if __name__ == "__main__":
    main()
