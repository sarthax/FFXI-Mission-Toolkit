"""Client-term lookup and page matching over the bilingual client text DB.

Read-only. Items and auto-translate phrases come from exact same-install EN/JA DAT
pairs (see ``workbench.client.dat.text_db``). Matches are candidates for reading
Japanese Wiki pages, not verified translations of the surrounding prose.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from .wiki_translation_client_terms import MIN_TERM_CHARS, default_db_path

_KIND_ITEM, _KIND_AUTO, _KIND_ZONE = "item", "auto-translate", "zone"


def _connect() -> sqlite3.Connection | None:
    path = default_db_path()
    if not path.exists():
        return None
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def _like(text: str) -> str:
    return "%" + text.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


def search(query: str, limit: int = 50) -> dict:
    """Substring search of EN, JA or kana over items, auto-translate phrases and zone names."""
    query = (query or "").strip()
    if not query:
        return {"status": "OK", "results": [], "truncated": False}
    con = _connect()
    if con is None:
        return {"status": "NO_DB", "results": [], "truncated": False}
    like, results = _like(query), []
    with closing(con):
        for cat, entry, en, ja, kana, category in con.execute(
                "SELECT cat_id, entry_id, en, ja, ja_kana, category_en FROM auto_translate "
                "WHERE en LIKE ? ESCAPE '!' OR ja LIKE ? ESCAPE '!' OR ja_kana LIKE ? ESCAPE '!' "
                "ORDER BY cat_id, entry_id LIMIT ?", (like, like, like, limit + 1)):
            results.append({"kind": _KIND_AUTO, "en": en, "ja": ja, "kana": kana or "",
                            "category": category or "", "ref": f"{cat}:{entry}"})
        for item_id, en, ja, category in con.execute(
                "SELECT item_id, name_en, name_ja, category FROM items "
                "WHERE name_en LIKE ? ESCAPE '!' OR name_ja LIKE ? ESCAPE '!' "
                "ORDER BY item_id LIMIT ?", (like, like, limit + 1)):
            results.append({"kind": _KIND_ITEM, "en": en, "ja": ja, "kana": "",
                            "category": category or "", "ref": str(item_id)})
        for zone_id, name in con.execute(
                "SELECT zone_id, name FROM zones WHERE name LIKE ? ESCAPE '!' ORDER BY zone_id LIMIT ?",
                (like, limit + 1)):
            results.append({"kind": _KIND_ZONE, "en": name, "ja": "", "kana": "",
                            "category": "", "ref": str(zone_id)})
    q = query.casefold()
    results.sort(key=lambda r: not (r["en"].casefold() == q or r["ja"] == query or r["kana"] == query))
    truncated = len(results) > limit
    return {"status": "OK", "results": results[:limit], "truncated": truncated}


_index: dict | None = None
_index_path = None


def _load() -> dict[str, list[dict]]:
    """JA text -> distinct client entries (items + auto-translate), cached per DB path."""
    global _index, _index_path
    path = default_db_path()
    if _index is not None and _index_path == path:
        return _index
    index: dict[str, list[dict]] = {}
    con = _connect()
    if con is not None:
        with closing(con):
            for cat, entry, en, ja, category in con.execute(
                    "SELECT cat_id, entry_id, en, ja, category_en FROM auto_translate"):
                _add(index, ja, en, _KIND_AUTO, category, f"{cat}:{entry}")
            for item_id, en, ja, category in con.execute(
                    "SELECT item_id, name_en, name_ja, category FROM items"):
                _add(index, ja, en, _KIND_ITEM, category, str(item_id))
    _index, _index_path = index, path
    return index


def _add(index: dict, ja, en, kind: str, category, ref: str) -> None:
    ja, en = (ja or "").strip(), (en or "").strip()
    if len(ja) < MIN_TERM_CHARS or not en or "${" in ja or "${" in en:
        return
    entries = index.setdefault(ja, [])
    if not any(e["en"] == en and e["kind"] == kind for e in entries):
        entries.append({"kind": kind, "en": en, "category": category or "", "ref": ref})


def match(text: str, limit: int = 300) -> dict:
    """Client terms occurring in a page; the longest term wins over terms it contains."""
    index = _load()
    if not index:
        return {"status": "NO_DB", "terms": []}
    found = sorted((t for t in index if t in text), key=len, reverse=True)
    kept: list[str] = []
    for term in found:
        if not any(term in longer for longer in kept):
            kept.append(term)
        if len(kept) >= limit:
            break
    terms = [{"ja": t, "count": text.count(t), "entries": index[t]} for t in kept]
    terms.sort(key=lambda r: (-r["count"], r["ja"]))
    return {"status": "OK", "terms": terms}
