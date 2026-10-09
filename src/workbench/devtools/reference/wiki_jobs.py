"""Background wiki-page scrape jobs: fetch into a private temp SQLite file, then merge into the main DB.

No LLM involved. The slow network part never touches the main DB; the merge is one short transaction
with a busy timeout, so other tools are not blocked. Page text is stored verbatim (Japanese included);
translation is a display-time step (see translate_cached) and never alters the stored evidence.
"""
from __future__ import annotations
import hashlib, os, sqlite3, subprocess, tempfile, threading, time, urllib.parse, uuid
from datetime import datetime, timezone
from pathlib import Path

from . import wiki_document

SITES = {
    "BGWiki": {"label": "BG Wiki", "home": "https://www.bg-wiki.com/ffxi/Main_Page", "page": "https://www.bg-wiki.com/ffxi/{t}"},
    "FFXIclopedia": {"label": "FFXIclopedia", "home": "https://ffxiclopedia.fandom.com/wiki/Main_Page", "page": "https://ffxiclopedia.fandom.com/wiki/{t}"},
    "WikiWikiJP": {"label": "FFXI Wiki (JP)", "home": "https://wikiwiki.jp/ffxi/", "page": "https://wikiwiki.jp/ffxi/{t}"},
}
JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()

_PAGES_DDL = """CREATE TABLE IF NOT EXISTS reference_wiki_pages(
  source_id TEXT NOT NULL, page_id TEXT NOT NULL, title TEXT NOT NULL, norm_title TEXT NOT NULL,
  revision_id TEXT, revision_timestamp TEXT, page_text TEXT, page_hash TEXT NOT NULL,
  PRIMARY KEY(source_id,page_id))"""


def detect(url: str) -> tuple[str, str] | None:
    """(source_id, page title) from a wiki URL, or None."""
    p = urllib.parse.urlparse((url or "").strip())
    host, path = p.netloc.lower(), urllib.parse.unquote(p.path)
    title = path[6:].strip("/")
    if not title:
        return None
    if "bg-wiki.com" in host and path.startswith("/ffxi/"):
        return "BGWiki", title.replace("_", " ")
    if "ffxiclopedia" in host and path.startswith("/wiki/"):
        return "FFXIclopedia", title.replace("_", " ")
    if host.endswith("wikiwiki.jp") and path.startswith("/ffxi/"):
        return "WikiWikiJP", title
    return None


def page_url(source_id: str, title: str) -> str | None:
    s = SITES.get(source_id)
    if not s or not title:
        return None
    t = title if source_id == "WikiWikiJP" else title.replace(" ", "_")
    return s["page"].format(t=urllib.parse.quote(t, safe="/"))


def _fetch(source_id: str, title: str, log) -> list[dict]:
    """Fetch page rows plus source-preserving structure metadata."""
    now = datetime.now(timezone.utc).isoformat()
    if source_id == "WikiWikiJP":
        from . import scrape_wikiwiki_jp as jp
        log("fetching wikiwiki.jp page")
        raw = jp.get(title)
        text = jp.to_text(raw)
        row = (source_id, title, title, title, "", now, text, hashlib.sha256(text.encode()).hexdigest())
        return [{"row": row, "source_format": "html", "raw_source": raw}]
    if source_id == "FFXIclopedia":
        from . import scrape_ffxiclopedia as fx
        from .ffxiclopedia import norm_title
        log("fetching FFXIclopedia page via API")
        out = []
        for pid, t, rev, ts, text in fx.fetch([title]):
            row = (source_id, str(pid), t, norm_title(t), str(rev), ts, text, hashlib.sha256(text.encode()).hexdigest())
            out.append({"row": row, "source_format": "mediawiki", "raw_source": text})
        return out
    if source_id == "BGWiki":
        from . import scrape_bg_wiki as bg
        from ._wiki_evidence_impl import _norm
        log("fetching BG Wiki page via API")
        out = []
        for r in bg.fetch_pages_by_title([title]):
            text = r["wikitext"]
            row = (source_id, str(r["pageid"]), r["title"], _norm(r["title"]), str(r["revid"]), r["timestamp"],
                   text, hashlib.sha256(text.encode()).hexdigest())
            out.append({"row": row, "source_format": "mediawiki", "raw_source": text})
        return out
    raise ValueError(f"unknown source {source_id}")


def _merge(main_db: str, tmp_db: str, log) -> dict:
    """Merge changed pages only, retaining prior content revisions for audit."""
    for attempt in range(6):
        con = sqlite3.connect(main_db, timeout=30)
        try:
            con.execute("PRAGMA busy_timeout=30000")
            con.execute(_PAGES_DDL)
            con.execute("""CREATE TABLE IF NOT EXISTS reference_wiki_page_history (
              source_id TEXT NOT NULL, page_id TEXT NOT NULL, page_hash TEXT NOT NULL,
              title TEXT NOT NULL, norm_title TEXT NOT NULL, revision_id TEXT,
              revision_timestamp TEXT, page_text TEXT,
              recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY(source_id,page_id,page_hash))""")
            con.execute("ATTACH DATABASE ? AS t", (tmp_db,))
            changes = {"updated": 0, "unchanged": 0, "inserted": 0}
            with con:
                for row in con.execute("""SELECT source_id,page_id,title,norm_title,
                  revision_id,revision_timestamp,page_text,page_hash
                  FROM t.reference_wiki_pages""").fetchall():
                    existing = con.execute("""SELECT source_id,page_id,title,norm_title,
                      revision_id,revision_timestamp,page_text,page_hash
                      FROM reference_wiki_pages WHERE source_id=? AND page_id=?""", row[:2]).fetchone()
                    if existing and existing[2:] == row[2:]:
                        changes["unchanged"] += 1
                        continue
                    if existing:
                        con.execute("""INSERT OR IGNORE INTO reference_wiki_page_history
                          (source_id,page_id,title,norm_title,revision_id,revision_timestamp,page_text,page_hash)
                          VALUES (?,?,?,?,?,?,?,?)""", existing)
                        changes["updated"] += 1
                    else:
                        changes["inserted"] += 1
                    con.execute("""INSERT OR REPLACE INTO reference_wiki_pages
                      (source_id,page_id,title,norm_title,revision_id,revision_timestamp,page_text,page_hash)
                      VALUES (?,?,?,?,?,?,?,?)""", row)
                    con.execute("""INSERT OR IGNORE INTO reference_wiki_page_history
                      (source_id,page_id,title,norm_title,revision_id,revision_timestamp,page_text,page_hash)
                      VALUES (?,?,?,?,?,?,?,?)""", row)
                # Only prune translations whose source page no longer exists.
                # Historical versions can still be inspected, so preserve their cache.
                translation_table = con.execute("""SELECT 1 FROM sqlite_master
                  WHERE type='table' AND name='reference_wiki_translations'""").fetchone()
                if translation_table:
                    con.execute("""DELETE FROM reference_wiki_translations
                      WHERE NOT EXISTS (SELECT 1 FROM reference_wiki_pages p
                        WHERE p.source_id=reference_wiki_translations.source_id
                        AND p.page_id=reference_wiki_translations.page_id)""")
            return changes
        except sqlite3.OperationalError as e:
            # Schema errors, corrupt staging tables, and disk failures will not
            # improve after repeated sleeps. Retry only transient SQLite locks.
            if not any(marker in str(e).lower() for marker in ("database is locked", "database table is locked", "database is busy")):
                raise
            log(f"merge retry {attempt + 1}: {e}")
            if attempt < 5:
                time.sleep(5)
        finally:
            con.close()
    raise RuntimeError("main DB stayed locked; scraped page kept in " + tmp_db)


def _run(job: dict, main_db: str) -> None:
    def log(m):
        job["log"].append(f"{datetime.now():%H:%M:%S} {m}")
    tmp = os.path.join(tempfile.gettempdir(), f"wikiscrape_{job['id']}.db")
    try:
        job["state"] = "fetching"
        fetched = _fetch(job["source"], job["title"], log)
        if not fetched:
            job.update(state="not_found", result=0)
            log("page not found at source")
            return
        rows = [item["row"] for item in fetched]
        t = sqlite3.connect(tmp)
        t.execute(_PAGES_DDL)
        t.executemany("INSERT OR REPLACE INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)", rows)
        t.commit()
        t.close()
        log(f"fetched {len(rows)} page(s) into temp DB; merging")
        job["state"] = "merging"
        job["changes"] = _merge(main_db, tmp, log)
        job["result"] = job["changes"]["updated"] + job["changes"]["inserted"]
        log("page merge: " + ", ".join(f"{k}={v}" for k, v in job["changes"].items()))

        # Persist the structural projection after the short page-row merge. This uses the already
        # fetched source bytes and performs no second network request.
        con = sqlite3.connect(main_db, timeout=30)
        try:
            for item in fetched:
                row = item["row"]
                page = {"page_id": row[1], "title": row[2], "page_text": row[6]}
                page_id, source_format, blocks = wiki_document.build_blocks(
                    page, source_format=item["source_format"], raw_source=item["raw_source"]
                )
                wiki_document.store_document(
                    con, source_id=row[0], page_id=page_id, source_format=source_format,
                    raw_source=item["raw_source"], blocks=blocks,
                )
                wiki_document.ensure_title_alias(con, row[0], page_id, row[2])
        finally:
            con.close()

        # Confirm the imported article is discoverable in the main cache before
        # declaring a successful scrape. The check is read-only and source-scoped.
        con = sqlite3.connect(Path(main_db).resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            missing = []
            for item in fetched:
                row = item["row"]
                if not con.execute(
                    "SELECT 1 FROM reference_wiki_pages WHERE source_id=? AND page_id=? AND title=? LIMIT 1",
                    (row[0], row[1], row[2]),
                ).fetchone():
                    missing.append(f"{row[0]}:{row[2]}")
            job["verified_pages"] = len(fetched) - len(missing)
            job["expected_pages"] = len(fetched)
            # A row in SQLite alone is not sufficient: the user's next action
            # is searching for the title, then opening its Browse view.
            unsearchable = []
            for item in fetched:
                row = item["row"]
                if f"{row[0]}:{row[2]}" in missing:
                    continue
                hits = wiki_document.search_pages(con, row[2], source_id=row[0])
                if not any(str(hit["page_id"]) == str(row[1])
                           and hit["source_id"] == row[0] for hit in hits):
                    unsearchable.append(f"{row[0]}:{row[2]}")
            if missing or unsearchable:
                job["state"] = "partial"
                details = []
                if missing:
                    details.append("not stored: " + ", ".join(missing[:5]))
                if unsearchable:
                    details.append("stored but not searchable: " + ", ".join(unsearchable[:5]))
                job["error"] = "; ".join(details)
                log("post-import verification failed: " + job["error"])
                return
        finally:
            con.close()
        job["state"] = "done"
        log(f"verified {job['verified_pages']} page(s) in main cache; structured document blocks saved")
    except Exception as exc:  # a job must never raise into the server
        job["state"] = "error"
        job["error"] = str(exc)
        log(f"error: {exc}")
    finally:
        if job["state"] != "error" and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def start_job(url: str, main_db) -> dict:
    d = detect(url)
    if d is None:
        raise ValueError("Unrecognised URL: use a bg-wiki.com/ffxi/..., ffxiclopedia.fandom.com/wiki/... or wikiwiki.jp/ffxi/... page link")
    job = {"id": uuid.uuid4().hex[:10], "url": url, "source": d[0], "title": d[1], "state": "queued", "log": [], "result": None, "error": None}
    with _LOCK:
        JOBS[job["id"]] = job
    threading.Thread(target=_run, args=(job, str(main_db)), daemon=True).start()
    return job


def recent_jobs(n: int = 8) -> list[dict]:
    with _LOCK:
        return list(JOBS.values())[-n:][::-1]


def cache_health(main_db) -> dict:
    """Read-only diagnostics: never create a database or change its schema."""
    from pathlib import Path
    path = Path(main_db).resolve()
    if not path.is_file():
        return {"database_exists": False, "database_path": str(path), "sources": {}, "tables": []}
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        tables = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        sources = {}
        if "reference_wiki_pages" in tables:
            sources = {name: count for name, count in con.execute(
                "SELECT source_id, COUNT(*) FROM reference_wiki_pages GROUP BY source_id"
            )}
        if "wiki_pages" in tables:
            sources["BGWiki_dump_index"] = con.execute("SELECT COUNT(*) FROM wiki_pages").fetchone()[0]
        return {
            "database_exists": True, "database_path": str(path),
            "sources": sources,
            "tables": sorted(t for t in tables if t.startswith(("reference_wiki_", "wiki_pages"))),
            "structured_documents": con.execute("SELECT COUNT(*) FROM reference_wiki_documents").fetchone()[0]
                if "reference_wiki_documents" in tables else None,
            "structured_blocks": con.execute("SELECT COUNT(*) FROM reference_wiki_blocks").fetchone()[0]
                if "reference_wiki_blocks" in tables else None,
        }
    finally:
        con.close()


def translate_cached(con: sqlite3.Connection, source_id: str, page_id: str, page_hash: str, text: str) -> dict:
    """Display-time translation. The stored original is never modified; results are cached by page hash and
    are machine-generated. No engine is bundled: set WIKI_TRANSLATE_CMD to a command that reads Japanese on
    stdin and writes English on stdout."""
    con.execute("""CREATE TABLE IF NOT EXISTS reference_wiki_translations(source_id TEXT, page_id TEXT, page_hash TEXT,
      target_lang TEXT, translated TEXT, engine TEXT, created_at TEXT, PRIMARY KEY(source_id,page_id,page_hash,target_lang))""")
    r = con.execute("SELECT translated,engine,created_at FROM reference_wiki_translations WHERE source_id=? AND page_id=? AND page_hash=? AND target_lang='en'",
                    (source_id, page_id, page_hash)).fetchone()
    if r:
        return {"status": "OK", "text": r[0], "engine": r[1], "created_at": r[2]}
    cmd = os.environ.get("WIKI_TRANSLATE_CMD")
    if not cmd:
        return {"status": "NO_ENGINE"}
    out = subprocess.run(cmd, input=text, capture_output=True, text=True, encoding="utf-8", timeout=600, shell=True)
    if out.returncode != 0 or not out.stdout.strip():
        return {"status": "ERROR", "error": (out.stderr or "empty output")[:300]}
    con.execute("INSERT OR REPLACE INTO reference_wiki_translations VALUES(?,?,?,?,?,?,?)",
                (source_id, page_id, page_hash, "en", out.stdout, "cmd:" + cmd[:60], datetime.now(timezone.utc).isoformat()))
    con.commit()
    return {"status": "OK", "text": out.stdout, "engine": "cmd", "created_at": ""}
