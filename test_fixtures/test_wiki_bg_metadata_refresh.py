"""BG compressed snapshots must update title metadata even if text hash is unchanged."""
import gzip, json, sqlite3, tempfile, hashlib
from pathlib import Path
from workbench.devtools.reference import wiki_bg_dump_jobs as bg, wiki_jobs

def main():
    with tempfile.TemporaryDirectory() as directory:
        db=Path(directory)/"wiki.db"
        archive=Path(directory)/"bg.jsonl.gz"
        body="Unchanged body"
        digest=hashlib.sha256(body.encode()).hexdigest()
        with sqlite3.connect(db) as con:
            con.execute(wiki_jobs._PAGES_DDL)
            con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                        ("BGWiki","123","Old Medusa","oldmedusa","1","2026-01-01",body,digest))
        with gzip.open(archive,"wt",encoding="utf-8") as out:
            out.write(json.dumps({"pageid":123,"title":"Medusa","revid":2,
                         "timestamp":"2026-02-01","wikitext":body})+"\n")
        with bg._db(db) as con:
            con.execute("""INSERT INTO wiki_bg_dump_jobs
                (id,state,dump_path,dump_signature,page_limit) VALUES (?,?,?,?,?)""",
                ("demo","queued",str(archive),bg._signature(archive),50))
        bg._worker(str(db),"demo")
        with bg._db(db) as con:
            result=con.execute("SELECT title,norm_title,revision_id FROM reference_wiki_pages WHERE page_id='123'").fetchone()
            job=con.execute("SELECT state,imported,skipped FROM wiki_bg_dump_jobs WHERE id='demo'").fetchone()
        assert result==("Medusa","medusa","2"),result
        assert job==("completed",1,0),job
    print("BG metadata-only snapshot refresh: PASS")
if __name__=="__main__": main()
