"""Offline tests for Japanese Wiki crawl queue, resume, and safe failure."""
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
from workbench.devtools.reference import wiki_jp_crawl_jobs as crawler


def main():
    with tempfile.TemporaryDirectory() as folder:
        db=Path(folder)/"test.db"
        with patch.object(crawler.threading.Thread,"start"):
            job=crawler.start(db,"ヴォイドウォッチ",50)
        crawler._RUNNING.clear()
        assert crawler.status(db)[0]["state"]=="interrupted"
        with patch.object(crawler.threading.Thread,"start"):
            crawler.resume(db,job)
        page='<html><body><div id="body"><h2>情報</h2>日本語本文</div></body></html>'
        with patch.object(crawler.jp,"get",return_value=page), patch.object(crawler,"time") as timing:
            crawler._worker(str(db),job)
        result=crawler.status(db)[0]
        assert result["state"]=="completed",result
        assert result["imported"]==1,result
        with sqlite3.connect(db) as con:
            assert con.execute("SELECT COUNT(*) FROM reference_wiki_pages").fetchone()[0]==1
        with patch.object(crawler.threading.Thread,"start"):
            second=crawler.start(db,"別のページ",50)
        crawler._RUNNING.clear()
        with patch.object(crawler.jp,"get",side_effect=RuntimeError("challenge required")):
            crawler._worker(str(db),second)
        assert crawler.status(db)[0]["state"]=="error"
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def read(self): return b"<html><body>valid Wiki article</body></html>"
    with patch.object(crawler.jp.urllib.request,"urlopen",return_value=Response()):
        assert "valid Wiki article" in crawler.jp.get("Medusa")
    # Exact subtree boundaries: prefix siblings must never be traversed.
    assert crawler._in_subtree("Medusa", "Medusa")
    assert crawler._in_subtree("Medusa/Abilities", "Medusa")
    assert not crawler._in_subtree("MedusaExtra", "Medusa")
    assert not crawler._in_subtree("Medusa_Extra", "Medusa")

    # SQLite LIKE metacharacters in a seed must remain literal, not wildcards.
    with tempfile.TemporaryDirectory() as folder:
        db=Path(folder)/"refresh.db"
        with sqlite3.connect(db) as con:
            con.execute("""CREATE TABLE reference_wiki_pages (
                source_id TEXT,page_id TEXT,title TEXT,norm_title TEXT,
                revision_id TEXT,revision_timestamp TEXT,page_text TEXT,page_hash TEXT)""")
            for title in ("Test_100%", "Test_100%/Child", "TestX100%",
                          "Test_1000/Child", "Test_100%Extra"):
                con.execute("INSERT INTO reference_wiki_pages VALUES (?,?,?,?,?,?,?,?)",
                            ("WikiWikiJP",title,title,title,"","","text","digest"))
        with patch.object(crawler.threading.Thread,"start"):
            job=crawler.start(db,"Test_100%",50,mode="refresh")
        with sqlite3.connect(db) as con:
            selected=__import__("json").loads(con.execute(
                "SELECT queue_json FROM wiki_jp_crawl_jobs WHERE id=?",(job,)
            ).fetchone()[0])
        assert selected==["Test_100%", "Test_100%/Child"],selected
        crawler._RUNNING.clear()

    print("Japanese Wiki checkpointed crawl: PASS")


if __name__ == "__main__":
    main()
