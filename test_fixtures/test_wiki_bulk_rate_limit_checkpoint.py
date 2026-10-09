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
    # Non-rate-limit failures must also retain the page and block completion.
    with tempfile.TemporaryDirectory() as root:
        db=Path(root)/"wiki.db"
        with batch._connect(db) as con:
            con.execute("""INSERT INTO wiki_bulk_jobs
                (id,source,state,mode,page_limit,discovered,pending_json)
                VALUES (?,?,?,?,?,?,?)""",
                ("j2","FFXIclopedia","queued","missing",50,2,json.dumps(["Broken","Other"])))
        def fail_other(job, db_path):
            job["state"]="error"
            job["error"]="Article format could not be parsed"
        with patch.object(batch.wiki_jobs,"_run",side_effect=fail_other):
            batch._worker(str(db),"j2")
        with batch._connect(db) as con:
            state,pending,processed,failed=con.execute(
                "SELECT state,pending_json,processed,failed FROM wiki_bulk_jobs WHERE id='j2'"
            ).fetchone()
        assert state=="error" and json.loads(pending)==["Broken","Other"]
        assert processed==0 and failed==1
        with patch.object(batch.threading.Thread,"start"):
            batch.resume(db,"j2")
        def succeed(job, db_path):
            job["state"]="done"
        with patch.object(batch.wiki_jobs,"_run",side_effect=succeed), patch.object(batch.time,"sleep"):
            batch._worker(str(db),"j2")
        with batch._connect(db) as con:
            state,pending,processed,imported=con.execute(
                "SELECT state,pending_json,processed,imported FROM wiki_bulk_jobs WHERE id='j2'"
            ).fetchone()
        assert state=="completed" and json.loads(pending)==[]
        assert processed==2 and imported==2
    print("Wiki rate-limit checkpoint: PASS")

if __name__=="__main__":
    main()
