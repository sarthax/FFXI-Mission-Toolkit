"""Regression for idempotent wiki scrape merge, revision history and cache retention."""
import hashlib
import os
import sqlite3
import tempfile

from workbench.devtools.reference import wiki_jobs


def main():
    with tempfile.TemporaryDirectory() as root:
        db = os.path.join(root, "main.db")
        temp = os.path.join(root, "scrape.db")
        with sqlite3.connect(temp) as con:
            con.execute(wiki_jobs._PAGES_DDL)
        def stage(body):
            with sqlite3.connect(temp) as con:
                con.execute("DELETE FROM reference_wiki_pages")
                con.execute("INSERT INTO reference_wiki_pages VALUES (?,?,?,?,?,?,?,?)",
                            ("WikiWikiJP", "p1", "題名", "題名", "", "2026-10-08", body,
                             hashlib.sha256(body.encode()).hexdigest()))
        stage("元の内容")
        assert wiki_jobs._merge(db, temp, lambda _: None) == {
            "updated":0, "unchanged":0, "inserted":1}
        with sqlite3.connect(db) as con:
            con.execute("""CREATE TABLE reference_wiki_translations(
              source_id TEXT,page_id TEXT,page_hash TEXT,target_lang TEXT,
              translated TEXT,engine TEXT,created_at TEXT)""")
            con.execute("INSERT INTO reference_wiki_translations VALUES (?,?,?,?,?,?,?)",
                        ("WikiWikiJP","p1","old","en","saved","test","now"))
            con.execute("INSERT INTO reference_wiki_translations VALUES (?,?,?,?,?,?,?)",
                        ("WikiWikiJP","deleted","gone","en","orphan","test","now"))
        assert wiki_jobs._merge(db, temp, lambda _: None)["unchanged"] == 1
        stage("更新内容")
        assert wiki_jobs._merge(db, temp, lambda _: None)["updated"] == 1
        assert wiki_jobs._merge(db, temp, lambda _: None)["unchanged"] == 1
        with sqlite3.connect(db) as con:
            history = con.execute("""SELECT page_text FROM reference_wiki_page_history
              WHERE source_id='WikiWikiJP' AND page_id='p1' ORDER BY page_text""").fetchall()
            assert {x[0] for x in history} == {"元の内容", "更新内容"}
            assert con.execute("SELECT page_text FROM reference_wiki_pages").fetchone()[0] == "更新内容"
            assert con.execute("SELECT translated FROM reference_wiki_translations").fetchall() == [("saved",)]
    print("Wiki V2 revision history regression: PASS")


if __name__ == "__main__":
    main()
