"""Snapshot imports validate hashes before writing any pages."""
import gzip
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from workbench.devtools.reference.wiki_snapshot import import_snapshot


def main():
    with tempfile.TemporaryDirectory() as folder:
        db=Path(folder)/"toolkit.db"
        snapshot=Path(folder)/"wiki.jsonl.gz"
        with sqlite3.connect(db) as con:
            con.execute("CREATE TABLE seed(x INTEGER)")
        page={"source_id":"BGWiki","page_id":"42","title":"Medusa","norm_title":"medusa",
              "revision_id":"1","revision_timestamp":"","page_text":"== Medusa =="}
        page["page_hash"]=hashlib.sha256(page["page_text"].encode()).hexdigest()
        manifest={"type":"manifest","format":"ffxi-wiki-snapshot","version":1,"source":"BGWiki"}
        with gzip.open(snapshot,"wt",encoding="utf-8") as stream:
            stream.write(json.dumps(manifest)+"\n")
            stream.write(json.dumps({"type":"page","data":page})+"\n")
        result=import_snapshot(db,snapshot)
        assert result["pages"]==1 and result["inserted"]==1,result
        with sqlite3.connect(db) as con:
            assert con.execute("SELECT title FROM reference_wiki_pages").fetchone()==("Medusa",)
        assert import_snapshot(db,snapshot)["unchanged"]==1
        page["page_hash"]="0"*64
        with gzip.open(snapshot,"wt",encoding="utf-8") as stream:
            stream.write(json.dumps(manifest)+"\n")
            stream.write(json.dumps({"type":"page","data":page})+"\n")
        try:
            import_snapshot(db,snapshot)
        except ValueError as exc:
            assert "hash mismatch" in str(exc)
        else:
            raise AssertionError("Corrupt snapshot accepted")
        with sqlite3.connect(db) as con:
            assert con.execute("SELECT COUNT(*) FROM reference_wiki_pages").fetchone()[0]==1
    print("Wiki snapshot validated import: PASS")


if __name__=="__main__":
    main()
