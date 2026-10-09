"""Transfer Wiki snapshots across two databases without losing existing pages."""
import sqlite3, hashlib, tempfile
from pathlib import Path
from workbench.devtools.reference.wiki_snapshot import export_snapshot, import_snapshot

DDL = """CREATE TABLE reference_wiki_pages(source_id TEXT,page_id TEXT,title TEXT,
norm_title TEXT,revision_id TEXT,revision_timestamp TEXT,page_text TEXT,page_hash TEXT,
PRIMARY KEY(source_id,page_id))"""

def seed(path, rows):
    with sqlite3.connect(path) as con:
        con.execute(DDL)
        for source, pid, title, body in rows:
            con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                        (source,pid,title,title,"1","",body,hashlib.sha256(body.encode()).hexdigest()))

def main():
    with tempfile.TemporaryDirectory() as folder:
        src, dst, archive = (Path(folder)/name for name in ("source.db","destination.db","wiki.jsonl.gz"))
        seed(src,[("BGWiki","42","Medusa","New article"),
                  ("FFXIclopedia","57","Nyzul Isle","Quest info"),
                  ("WikiWikiJP","jp1","ヴォイドウォッチ","日本語の原文")])
        seed(dst,[("BGWiki","42","Medusa","Old article"),
                  ("BGWiki","99","Existing","Preserved article")])
        assert export_snapshot(src,archive)["pages"] == 3
        first=import_snapshot(dst,archive)
        assert (first["inserted"],first["updated"]) == (2,1),first
        with sqlite3.connect(dst) as con:
            assert con.execute("SELECT COUNT(*) FROM reference_wiki_pages").fetchone()[0] == 4
            assert con.execute("SELECT page_text FROM reference_wiki_pages WHERE page_id='jp1'").fetchone()[0] == "日本語の原文"
            assert con.execute("SELECT page_text FROM reference_wiki_pages WHERE page_id='99'").fetchone()[0] == "Preserved article"
            assert con.execute("SELECT COUNT(*) FROM reference_wiki_page_history WHERE page_id='42'").fetchone()[0] >= 2
        assert import_snapshot(dst,archive)["unchanged"] == 3
    print("Wiki snapshot cross-database roundtrip: PASS")

if __name__ == "__main__":
    main()
