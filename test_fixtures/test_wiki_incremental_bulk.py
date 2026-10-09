"""FFXIclopedia incremental batch refreshes cached titles and persists mode."""
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
from workbench.devtools.reference import wiki_bulk_jobs as bulk
from workbench.devtools.reference import wiki_jobs

def main():
    with tempfile.TemporaryDirectory() as root:
        db=Path(root)/"wiki.db"
        with sqlite3.connect(db) as con:
            con.execute(wiki_jobs._PAGES_DDL)
            con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                        ("FFXIclopedia","7","Medusa","medusa","1","2026-01-01T00:00:00Z","old","hash"))
        with patch.object(bulk.threading.Thread,"start"):
            job=bulk.start(db,50,mode="changed")
        def changed(con):
            yield "Medusa"
        def run(j,db_path):
            j["state"]="done"
        with patch("workbench.devtools.reference.scrape_ffxiclopedia.changed_titles",side_effect=changed),patch.object(bulk.wiki_jobs,"_run",side_effect=run):
            bulk._worker(str(db),job)
        with sqlite3.connect(db) as con:
            row=con.execute("SELECT mode,discovered,processed,imported,state FROM wiki_bulk_jobs WHERE id=?",(job,)).fetchone()
        assert row==("changed",1,1,1,"completed"),row
        with patch.object(bulk.threading.Thread,"start"):
            try:
                bulk.start(db,50,mode="invalid")
            except ValueError: pass
            else: raise AssertionError("Invalid mode accepted")
    print("FFXIclopedia incremental refresh: PASS")

if __name__=="__main__":
    main()
