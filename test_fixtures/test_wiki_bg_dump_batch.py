"""Offline BG dump batch import persists checkpoints and preserves source snapshot."""
import gzip
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from workbench.devtools.reference import wiki_bg_dump_jobs as jobs


def main():
    with tempfile.TemporaryDirectory() as directory:
        dump=Path(directory)/"bg-wiki.jsonl.gz"
        db=Path(directory)/"toolkit.db"
        records=[{"title":"Medusa","pageid":101,"wikitext":"== Medusa ==\nTest","revid":4,
                  "timestamp":"2026-10-09T00:00:00Z"}]
        with gzip.open(dump,"wt",encoding="utf-8") as file:
            for row in records:file.write(json.dumps(row)+"\n")
        original=dump.read_bytes()
        with patch.object(jobs.threading.Thread,"start"):
            job=jobs.start(db,dump,limit=50)
        jobs._RUNNING.clear()
        assert jobs.status(db)[0]["state"]=="interrupted"
        with patch.object(jobs.threading.Thread,"start"):
            jobs.resume(db,job)
        jobs._worker(str(db),job)
        result=jobs.status(db)[0]
        assert result["state"]=="completed",result
        assert result["processed"]==1,result
        assert result["imported"]==1,result
        assert dump.read_bytes()==original
        with sqlite3.connect(db) as con:
            assert con.execute("SELECT title FROM reference_wiki_pages WHERE source_id='BGWiki'").fetchone()==("Medusa",)
            assert con.execute("SELECT COUNT(*) FROM reference_wiki_documents").fetchone()[0]==1
        with patch.object(jobs.threading.Thread,"start"):
            second=jobs.start(db,dump,limit=50)
        jobs._worker(str(db),second)
        result=jobs.status(db)[0]
        assert result["skipped"]==1,result
        assert result["imported"]==0,result
    # A corrupt source record must not disappear from a checkpoint or allow
    # a partial import to report successful completion.
    with tempfile.TemporaryDirectory() as directory:
        dump=Path(directory)/"mixed.jsonl.gz"
        db=Path(directory)/"mixed.db"
        with gzip.open(dump,"wt",encoding="utf-8") as file:
            file.write(json.dumps({"title":"Medusa","pageid":101,"wikitext":"valid"})+"\n")
            file.write(json.dumps({"title":"Broken","pageid":102})+"\n")
            file.write(json.dumps({"title":"Following","pageid":103,"wikitext":"valid"})+"\n")
        with patch.object(jobs.threading.Thread,"start"):
            job=jobs.start(db,dump,limit=50)
        jobs._worker(str(db),job)
        result=jobs.status(db)[0]
        assert result["state"]=="error",result
        assert result["cursor"]==1,result
        assert result["processed"]==1,result
        assert result["imported"]==1,result
        assert result["failed"]==1,result
        assert "Record 2" in result["last_error"],result
        with sqlite3.connect(db) as con:
            assert con.execute("SELECT COUNT(*) FROM reference_wiki_pages").fetchone()[0]==1
        with patch.object(jobs.threading.Thread,"start"):
            jobs.resume(db,job)
        jobs._worker(str(db),job)
        repeated=jobs.status(db)[0]
        assert repeated["state"]=="error",repeated
        assert repeated["cursor"]==1,repeated
        assert repeated["processed"]==1,repeated

    print("BG Wiki dump batch importer: PASS")


if __name__=="__main__":
    main()
