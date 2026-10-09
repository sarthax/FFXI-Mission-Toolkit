"""A Wiki title rename must be searchable even if page body stays identical."""
import hashlib
import sqlite3
import tempfile
from pathlib import Path
from workbench.devtools.reference import wiki_jobs, wiki_document

def main():
    with tempfile.TemporaryDirectory() as directory:
        db=Path(directory)/"main.db"
        incoming=Path(directory)/"incoming.db"
        text="Same article content"
        digest=hashlib.sha256(text.encode()).hexdigest()
        with sqlite3.connect(db) as con:
            con.execute(wiki_jobs._PAGES_DDL)
            con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                        ("BGWiki","123","Former Name","formername","1","",text,digest))
        with sqlite3.connect(incoming) as con:
            con.execute(wiki_jobs._PAGES_DDL)
            con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                        ("BGWiki","123","Medusa","medusa","2","",text,digest))
        changes=wiki_jobs._merge(str(db),str(incoming),lambda msg:None)
        assert changes["updated"]==1,changes
        with sqlite3.connect(db) as con:
            assert con.execute("SELECT title,norm_title,revision_id FROM reference_wiki_pages").fetchone()==("Medusa","medusa","2")
            hits=wiki_document.search_pages(con,"Medusa",source_id="BGWiki")
            assert any(r["page_id"]=="123" for r in hits),hits
        assert wiki_jobs._merge(str(db),str(incoming),lambda msg:None)["unchanged"]==1
    print("Wiki title rename merge: PASS")

if __name__=="__main__":
    main()
