import sqlite3, tempfile, hashlib
from pathlib import Path
from workbench.devtools.reference import wiki_document, wiki_jobs

def main():
    with tempfile.TemporaryDirectory() as d:
        with sqlite3.connect(Path(d)/"wiki.db") as con:
            con.execute(wiki_jobs._PAGES_DDL)
            body="Medusa is an NM"
            con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                        ("BGWiki","123","Medusa","medusa","1","",body,
                         hashlib.sha256(body.encode()).hexdigest()))
            report=wiki_document.diagnose_title(con,"Medusa")
            item=report["sources"][0]
            assert item["cached"]==1 and item["pages"][0]["searchable"],report
            assert report["sources"][2]["cached"]==0
    print("Wiki Medusa diagnostic: PASS")

if __name__=="__main__":
    main()
