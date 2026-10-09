"""Portable snapshot export leaves source database untouched."""
import gzip
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from workbench.devtools.reference.wiki_snapshot import export_snapshot

def main():
    with tempfile.TemporaryDirectory() as folder:
        db=Path(folder)/"toolkit.db"
        out=Path(folder)/"cache.jsonl.gz"
        content="== Medusa ==\nA test page"
        with sqlite3.connect(db) as con:
            con.execute("""CREATE TABLE reference_wiki_pages(
              source_id TEXT,page_id TEXT,title TEXT,norm_title TEXT,
              revision_id TEXT,revision_timestamp TEXT,page_text TEXT,page_hash TEXT)""")
            con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                        ("BGWiki","42","Medusa","medusa","8","",""+content,hashlib.sha256(content.encode()).hexdigest()))
        original=db.read_bytes()
        result=export_snapshot(db,out,source="BGWiki")
        assert result["pages"]==1
        with gzip.open(out,"rt",encoding="utf-8") as stream:
            records=[json.loads(line) for line in stream]
        assert records[0]["type"]=="manifest" and records[0]["version"]==1
        assert records[1]["data"]["title"]=="Medusa"
        assert db.read_bytes()==original
        try:
            export_snapshot(db,Path(folder)/"invalid.zip")
        except ValueError:
            pass
        else:
            raise AssertionError("Non-JSONL destination accepted")
    print("Wiki snapshot export: PASS")

if __name__=="__main__":
    main()
