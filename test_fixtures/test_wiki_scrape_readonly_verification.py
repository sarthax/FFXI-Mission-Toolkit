"""Verify cached wiki search works without schema writes on a read-only database."""
import sqlite3
import tempfile
from pathlib import Path
from workbench.devtools.reference import wiki_document


def main():
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "wiki.db"
        with sqlite3.connect(path) as con:
            wiki_document.init_db(con)
            con.execute("""CREATE TABLE reference_wiki_pages(
                source_id TEXT, page_id TEXT, title TEXT, norm_title TEXT,
                revision_id TEXT, revision_timestamp TEXT, page_text TEXT, page_hash TEXT,
                PRIMARY KEY(source_id,page_id))""")
            con.execute("INSERT INTO reference_wiki_pages VALUES (?,?,?,?,?,?,?,?)",
                        ("BGWiki","101","Medusa","medusa","12","", "Medusa article", "hash"))
            con.commit()
        with sqlite3.connect(path.as_uri()+"?mode=ro", uri=True) as con:
            hits = wiki_document.search_pages(con, "Medusa", source_id="BGWiki", initialize=False)
            assert any(h["page_id"] == "101" and h["source_id"] == "BGWiki" for h in hits)
    print("Wiki read-only scrape verification: PASS")


if __name__ == "__main__":
    main()
