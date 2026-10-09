"""Read-only Wiki snapshot preview produces per-source new/updated/unchanged counts."""
import sqlite3,hashlib,tempfile
from pathlib import Path
from workbench.devtools.reference.wiki_snapshot import export_snapshot,preview_snapshot

def main():
    with tempfile.TemporaryDirectory() as d:
        a,b,s=[Path(d)/x for x in ("a.db","b.db","s.jsonl.gz")]
        ddl="CREATE TABLE reference_wiki_pages(source_id TEXT,page_id TEXT,title TEXT,norm_title TEXT,revision_id TEXT,revision_timestamp TEXT,page_text TEXT,page_hash TEXT)"
        for db in (a,b):
            with sqlite3.connect(db) as c:c.execute(ddl)
        def put(db,source,ident,body):
            with sqlite3.connect(db) as c:
                c.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                    (source,ident,"Medusa","medusa","1","",body,hashlib.sha256(body.encode()).hexdigest()))
        put(a,"BGWiki","1","new version")
        put(a,"WikiWikiJP","jp","日本語")
        put(b,"BGWiki","1","old version")
        before=b.read_bytes()
        export_snapshot(a,s)
        result=preview_snapshot(b,s)
        assert result["totals"]=={"new":1,"updated":1,"unchanged":0},result
        assert result["sources"]["WikiWikiJP"]["new"]==1
        assert b.read_bytes()==before
    print("Wiki snapshot preview: PASS")

if __name__=="__main__":main()
