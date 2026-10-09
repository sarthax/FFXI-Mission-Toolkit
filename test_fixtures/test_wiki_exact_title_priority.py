"""Exact Wiki matches must survive bounded candidate searches."""
import sqlite3
import tempfile
from pathlib import Path
from workbench.devtools.reference import wiki_document, wiki_jobs

def main():
    with tempfile.TemporaryDirectory() as directory:
        with sqlite3.connect(Path(directory)/"wiki.db") as con:
            con.execute(wiki_jobs._PAGES_DDL)
            for i in range(180):
                title=f"Medusa related article {i:03}"
                con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                            ("BGWiki",str(i),title,title.lower(),"1","","body","hash"))
            con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                        ("BGWiki","exact","Medusa","medusa","1","","body","hash"))
            for limit in (1,5,20):
                hits=wiki_document.search_pages(con,"Medusa",limit=limit,source_id="BGWiki")
                assert hits and hits[0]["page_id"]=="exact",(limit,hits)
    print("Wiki exact-title priority: PASS")

if __name__=="__main__":main()
