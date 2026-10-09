"""Read-only portable snapshot export of imported Wiki pages (not main DB)."""
from __future__ import annotations
import gzip
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

VERSION=1
SOURCES=("BGWiki","FFXIclopedia","WikiWikiJP")

def export_snapshot(database, destination, source="all"):
    if source not in (*SOURCES,"all"):
        raise ValueError("Unknown Wiki source")
    db=Path(database).resolve()
    if not db.is_file():
        raise FileNotFoundError(f"Toolkit database not found: {db}")
    target=Path(destination).resolve()
    if target.suffixes[-2:]!=[".jsonl",".gz"]:
        raise ValueError("Snapshot destination must end in .jsonl.gz")
    if target == db:
        raise ValueError("Cannot export over toolkit database")
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=None
    con=sqlite3.connect(db.as_uri()+"?mode=ro",uri=True,timeout=10)
    try:
        table=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reference_wiki_pages'").fetchone()
        if not table:
            raise ValueError("No imported Wiki pages table exists")
        with tempfile.NamedTemporaryFile(dir=target.parent,prefix=".wiki_snapshot_",suffix=".tmp",delete=False) as handle:
            tmp=Path(handle.name)
        count=0
        with gzip.open(tmp,"wt",encoding="utf-8") as out:
            out.write(json.dumps({"type":"manifest","format":"ffxi-wiki-snapshot","version":VERSION,
                                  "source":source,"created_at":datetime.now(timezone.utc).isoformat()},ensure_ascii=False)+"\n")
            cursor=con.execute("""SELECT source_id,page_id,title,norm_title,revision_id,revision_timestamp,page_text,page_hash
                                   FROM reference_wiki_pages WHERE (?='all' OR source_id=?)
                                   ORDER BY source_id,page_id""",(source,source))
            for row in cursor:
                fields=("source_id","page_id","title","norm_title","revision_id","revision_timestamp","page_text","page_hash")
                page=dict(zip(fields,row))
                text=page["page_text"] or ""
                if hashlib.sha256(text.encode("utf-8")).hexdigest()!=page["page_hash"]:
                    raise ValueError(f"Hash mismatch in cached page {page['source_id']}:{page['page_id']}")
                out.write(json.dumps({"type":"page","data":page},ensure_ascii=False)+"\n")
                count+=1
        os.replace(tmp,target)
        tmp=None
        return {"path":str(target),"pages":count,"source":source}
    finally:
        con.close()
        if tmp is not None:
            tmp.unlink(missing_ok=True)
