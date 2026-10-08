"""Background wiki-page scrape jobs: fetch into a private temp SQLite file, then merge into the main DB.

No LLM involved. The slow network part never touches the main DB; the merge is one short transaction
with a busy timeout, so other tools are not blocked. Page text is stored verbatim (Japanese included);
translation is a display-time step (see translate_cached) and never alters the stored evidence.
"""
from __future__ import annotations
import hashlib, os, sqlite3, subprocess, tempfile, threading, time, urllib.parse, uuid
from datetime import datetime, timezone

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


def _fetch(source_id: str, title: str, log) -> list[tuple]:
    """Rows for reference_wiki_pages."""
    now = datetime.now(timezone.utc).isoformat()
    if source_id == "WikiWikiJP":
        from . import scrape_wikiwiki_jp as jp
        log("fetching wikiwiki.jp page")
        text = jp.to_text(jp.get(title))
        return [(source_id, title, title, title, "", now, text, hashlib.sha256(text.encode()).hexdigest())]
    if source_id == "FFXIclopedia":
        from . import scrape_ffxiclopedia as fx
        from .ffxiclopedia import norm_title
        log("fetching FFXIclopedia page via API")
        return [(source_id, str(pid), t, norm_title(t), str(rev), ts, text, hashlib.sha256(text.encode()).hexdigest())
                for pid, t, rev, ts, text in fx.fetch([title])]
    if source_id == "BGWiki":
        from . import scrape_bg_wiki as bg
        from ._wiki_evidence_impl import _norm
        log("fetching BG Wiki page via API")
        return [(source_id, str(r["pageid"]), r["title"], _norm(r["title"]), str(r["revid"]), r["timestamp"], r["wikitext"],
                 hashlib.sha256(r["wikitext"].encode()).hexdigest()) for r in bg.fetch_pages_by_title([title])]
    raise ValueError(f"unknown source {source_id}")


def _merge(main_db: str, tmp_db: str, log) -> int:
    for attempt in range(6):
        con = sqlite3.connect(main_db, timeout=30)
        try:
            con.execute("PRAGMA busy_timeout=30000")
            con.execute(_PAGES_DDL)
            con.execute("ATTACH DATABASE ? AS t", (tmp_db,))
            n = con.execute("INSERT OR REPLACE INTO reference_wiki_pages SELECT * FROM t.reference_wiki_pages").rowcount
            con.commit()
            return n
        except sqlite3.OperationalError as e:
            log(f"merge retry {attempt + 1}: {e}")
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
        rows = _fetch(job["source"], job["title"], log)
        if not rows:
            job.update(state="not_found", result=0)
            log("page not found at source")
            return
        t = sqlite3.connect(tmp)
        t.execute(_PAGES_DDL)
        t.executemany("INSERT OR REPLACE INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)", rows)
        t.commit()
        t.close()
        log(f"fetched {len(rows)} page(s) into temp DB; merging")
        job["state"] = "merging"
        job["result"] = _merge(main_db, tmp, log)
        job["state"] = "done"
        log("merged into main DB")
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
