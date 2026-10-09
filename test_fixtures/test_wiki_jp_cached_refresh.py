"""JP refresh rechecks cached subtree without discovering new links."""
import json,sqlite3,tempfile
from pathlib import Path
from unittest.mock import patch
from workbench.devtools.reference import wiki_jp_crawl_jobs as jp
from workbench.devtools.reference import wiki_jobs

def main():
    with tempfile.TemporaryDirectory() as root:
        db=Path(root)/"wiki.db"
        with sqlite3.connect(db) as con:
            con.execute(wiki_jobs._PAGES_DDL)
            for title in ("クエスト","クエスト/一","クエスト/二","別のページ"):
                con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                    ("WikiWikiJP",title,title,title,"","","text","hash"))
        with patch.object(jp.threading.Thread,"start"):
            job=jp.start(db,"クエスト",50,mode="refresh")
        with jp._db(db) as con:
            mode,pending=con.execute("SELECT mode,queue_json FROM wiki_jp_crawl_jobs WHERE id=?",(job,)).fetchone()
        assert mode=="refresh" and len(json.loads(pending))==3,(mode,pending)
        visited=[]
        with patch.object(jp.jp,"get",side_effect=lambda title:visited.append(title) or "test"),patch.object(
            jp,"_save_page"),patch.object(jp.jp,"links",side_effect=AssertionError("Refresh must not traverse links")),patch.object(jp.time,"sleep"):
            jp._worker(str(db),job)
        assert len(visited)==3,visited
        with jp._db(db) as con:
            assert con.execute("SELECT state FROM wiki_jp_crawl_jobs WHERE id=?",(job,)).fetchone()[0]=="completed"
    print("JP bounded cached refresh: PASS")
if __name__=="__main__":main()
