"""Automatic BG dump continuation is opt-in, persisted, and completes the file."""
import gzip
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
from workbench.devtools.reference import wiki_bg_dump_jobs as jobs


def main():
    with tempfile.TemporaryDirectory() as dirname:
        dump=Path(dirname)/"dump.jsonl.gz"
        db=Path(dirname)/"toolkit.db"
        with gzip.open(dump,"wt",encoding="utf-8") as out:
            for i in range(55):
                out.write(json.dumps({"title":f"Example {i}","pageid":i+1,
                    "wikitext":f"== Example {i} ==","revid":1})+"\n")
        with patch.object(jobs.threading.Thread,"start"):
            job_id=jobs.start(db,dump,limit=50,auto_continue=True)
        with sqlite3.connect(db) as con:
            assert con.execute("SELECT auto_continue FROM wiki_bg_dump_jobs WHERE id=?",(job_id,)).fetchone()==(1,)
        jobs._worker(str(db),job_id)
        result=next(x for x in jobs.status(db) if x["id"]==job_id)
        assert result["state"]=="completed",result
        assert result["processed"]==55,result
        assert result["imported"]==55,result
        with sqlite3.connect(db) as con:
            assert con.execute("SELECT COUNT(*) FROM reference_wiki_pages").fetchone()[0]==55
    print("BG Wiki auto continuation: PASS")


if __name__ == "__main__":
    main()
