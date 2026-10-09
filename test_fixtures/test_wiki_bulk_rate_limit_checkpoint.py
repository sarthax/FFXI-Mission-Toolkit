"""Wiki batch retains the current page on remote rate-limit errors."""
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
from workbench.devtools.reference import wiki_bulk_jobs as batch

def main():
    with tempfile.TemporaryDirectory() as root:
        db=Path(root)/"wiki.db"
        with batch._connect(db) as con:
            con.execute("""INSERT INTO wiki_bulk_jobs
                (id,source,state,mode,page_limit,discovered,pending_json)
                VALUES (?,?,?,?,?,?,?)""",
                ("j1","FFXIclopedia","queued","missing",50,2,json.dumps(["Medusa","Other"])))
        def fail(job,db_path):
            job["state"]="error"
            job["error"]="HTTP 429 Too Many Requests"
        with patch.object(batch.wiki_jobs,"_run",side_effect=fail):
            batch._worker(str(db),"j1")
        with batch._connect(db) as con:
            state,pending,processed=con.execute(
                "SELECT state,pending_json,processed FROM wiki_bulk_jobs WHERE id='j1'"
            ).fetchone()
        assert state=="error" and json.loads(pending)==["Medusa","Other"] and processed==0
    print("Wiki rate-limit checkpoint: PASS")

if __name__=="__main__":
    main()
