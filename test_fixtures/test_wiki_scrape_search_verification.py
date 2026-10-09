"""A persisted page must also be discoverable before scrape reports done."""
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
from workbench.devtools.reference import wiki_jobs

def main():
    with tempfile.TemporaryDirectory() as folder:
        db=Path(folder)/"test.db"
        with sqlite3.connect(db) as con:
            con.execute(wiki_jobs._PAGES_DDL)
        row=("BGWiki","123","Medusa","medusa","1","","Page body","hash")
        item={"row":row,"source_format":"mediawiki","raw_source":"Page body"}
        job={"id":"unsearchablecase","source":"BGWiki","title":"Medusa",
             "state":"queued","log":[],"error":None}
        with patch.object(wiki_jobs,"_fetch",return_value=[item]),patch.object(
            wiki_jobs.wiki_document,"build_blocks",return_value=("123","mediawiki",[])
        ),patch.object(wiki_jobs.wiki_document,"store_document"),patch.object(
            wiki_jobs.wiki_document,"ensure_title_alias"
        ),patch.object(wiki_jobs.wiki_document,"search_pages",return_value=[]):
            wiki_jobs._run(job,str(db))
        assert job["state"]=="partial",job
        assert "stored but not searchable" in job["error"],job
    print("Wiki search verification: PASS")

if __name__=="__main__":
    main()
