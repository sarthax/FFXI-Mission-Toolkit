#!/usr/bin/env python3
"""Import an offline MediaWiki XML export as a separate FFXIclopedia reference source.

The adapter deliberately does not scrape or merge the wiki into BG Wiki. Each source retains
its own page/revision/content hash so later comparison can expose disagreements instead of
silently choosing one reference.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3
from pathlib import Path
from xml.etree import ElementTree as ET
from datetime import datetime, timezone

SOURCE_ID="FFXIclopedia"
SOURCE_URL="https://ffxiclopedia.fandom.com/wiki/Main_Page"

def norm_title(title):
    return re.sub(r"[^a-z0-9]+","",(title or "").replace("_"," ").lower())

def iter_pages(path):
    for _,elem in ET.iterparse(path,events=("end",)):
        if elem.tag.rsplit("}",1)[-1] != "page": continue
        title=elem.findtext(".//{*}title") or ""
        pageid=elem.findtext(".//{*}id") or ""
        rev=elem.find(".//{*}revision")
        text=(rev.findtext(".//{*}text") if rev is not None else "") or ""
        revid=(rev.findtext(".//{*}id") if rev is not None else "") or ""
        ts=(rev.findtext(".//{*}timestamp") if rev is not None else "") or ""
        yield title,pageid,revid,ts,text
        elem.clear()

def init_db(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS reference_wiki_sources(
      source_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, base_url TEXT NOT NULL,
      snapshot_id TEXT, imported_at TEXT, notes TEXT
    );
    CREATE TABLE IF NOT EXISTS reference_wiki_pages(
      source_id TEXT NOT NULL, page_id TEXT NOT NULL, title TEXT NOT NULL, norm_title TEXT NOT NULL,
      revision_id TEXT, revision_timestamp TEXT, page_text TEXT, page_hash TEXT NOT NULL,
      PRIMARY KEY(source_id,page_id)
    );
    CREATE INDEX IF NOT EXISTS idx_reference_wiki_norm ON reference_wiki_pages(source_id,norm_title);
    """)

def import_xml(xml_path,db):
    con=sqlite3.connect(db); init_db(con)
    snapshot="sha256:"+hashlib.sha256(xml_path.read_bytes()).hexdigest()
    count=0
    for title,pageid,revid,ts,text in iter_pages(xml_path):
        ph=hashlib.sha256(text.encode("utf-8")).hexdigest()
        con.execute("INSERT OR REPLACE INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                    (SOURCE_ID,pageid,title,norm_title(title),revid,ts,text,ph))
        count+=1
    con.execute("INSERT OR REPLACE INTO reference_wiki_sources VALUES(?,?,?,?,?,?)",
                (SOURCE_ID,"FFXIclopedia",SOURCE_URL,snapshot,
                 datetime.now(timezone.utc).isoformat(),
                 "Offline MediaWiki XML import; reference-only evidence."))
    con.commit(); con.close()
    return {"schema":1,"source":SOURCE_ID,"snapshot_id":snapshot,"pages":count,"database":str(db)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("xml",type=Path)
    ap.add_argument("--db",type=Path,default=Path("ffxi_zone_database.db"))
    ap.add_argument("--json",type=Path)
    a=ap.parse_args()
    out=json.dumps(import_xml(a.xml,a.db),indent=2,sort_keys=True)
    if a.json:
        a.json.parent.mkdir(parents=True,exist_ok=True); a.json.write_text(out+"\n",encoding="utf-8")
    else: print(out)
if __name__=="__main__": main()
