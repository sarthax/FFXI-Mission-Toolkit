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


def import_snapshot(database, snapshot):
    """Validate the entire portable snapshot before merging any page.

    Preserves existing revisions through the shared history-aware Wiki merge.
    This importer does not contact remote Wikis.
    """
    from . import wiki_jobs, wiki_document
    path=Path(snapshot).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Wiki snapshot not found: {path}")
    target=Path(database).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Toolkit database not found: {target}")
    temp=None
    count=0
    try:
        with tempfile.NamedTemporaryFile(prefix="wiki_snapshot_stage_",suffix=".db",delete=False) as output:
            temp=Path(output.name)
        with sqlite3.connect(temp) as staging:
            staging.execute(wiki_jobs._PAGES_DDL)
            with gzip.open(path,"rt",encoding="utf-8") as stream:
                header=json.loads(next(stream))
                if (header.get("type")!="manifest" or
                    header.get("format")!="ffxi-wiki-snapshot" or
                    header.get("version")!=VERSION or
                    header.get("source") not in (*SOURCES,"all")):
                    raise ValueError("Unrecognized Wiki snapshot manifest/version")
                for line in stream:
                    item=json.loads(line)
                    if item.get("type")!="page" or not isinstance(item.get("data"),dict):
                        raise ValueError("Invalid Wiki snapshot record")
                    page=item["data"]
                    columns=("source_id","page_id","title","norm_title","revision_id",
                             "revision_timestamp","page_text","page_hash")
                    if any(k not in page for k in columns) or page["source_id"] not in SOURCES:
                        raise ValueError("Invalid Wiki page fields or source")
                    if header["source"]!="all" and page["source_id"]!=header["source"]:
                        raise ValueError("Snapshot page source does not match manifest")
                    if not all(isinstance(page[k],str) for k in ("source_id","page_id","title","norm_title","page_text","page_hash")):
                        raise ValueError("Wiki snapshot text fields must be strings")
                    if hashlib.sha256(page["page_text"].encode("utf-8")).hexdigest()!=page["page_hash"]:
                        raise ValueError("Wiki snapshot page hash mismatch")
                    staging.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                                    tuple(page[k] for k in columns))
                    count+=1
        if not count:
            return {"pages":0,"inserted":0,"updated":0,"unchanged":0}
        changes=wiki_jobs._merge(str(target),str(temp),lambda _:None)
        # Project retained raw text into structured documents, without refetching.
        with sqlite3.connect(str(target),timeout=30) as con, sqlite3.connect(temp) as staging:
            for source,page_id,title,text in staging.execute(
                "SELECT source_id,page_id,title,page_text FROM reference_wiki_pages"
            ):
                page={"page_id":page_id,"title":title,"page_text":text}
                projected_id,fmt,blocks=wiki_document.build_blocks(
                    page,source_format="mediawiki" if source!="WikiWikiJP" else "text",
                    raw_source=text)
                wiki_document.store_document(con,source_id=source,page_id=projected_id,
                                            source_format=fmt,raw_source=text,blocks=blocks)
                wiki_document.ensure_title_alias(con,source,projected_id,title)
        return {"pages":count,**changes}
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
