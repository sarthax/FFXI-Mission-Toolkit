"""Conservative JP→EN terminology derived only from explicitly reviewed Wiki topic links."""
from __future__ import annotations

import sqlite3


def reviewed_glossary(con: sqlite3.Connection, *, limit: int = 300) -> dict[str, str]:
    """Return unambiguous Japanese titles tied to an explicitly reviewed English topic.

    SOURCE_TITLE alone is not verification. Translation-generated aliases are excluded.
    """
    if limit < 1 or limit > 1000:
        raise ValueError("Invalid glossary limit")
    required = {"reference_wiki_topic_pages", "reference_wiki_topics", "reference_wiki_pages"}
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required.issubset(tables):
        return {}
    rows = con.execute("""
        SELECT jp.title, t.canonical_title, p.link_method
        FROM reference_wiki_topic_pages p
        JOIN reference_wiki_pages jp ON jp.source_id=p.source_id AND jp.page_id=p.page_id
        JOIN reference_wiki_topics t ON t.topic_id=p.topic_id
        WHERE p.source_id='WikiWikiJP'
        ORDER BY jp.title, t.canonical_title
    """).fetchall()
    possible = {}
    for ja, en, method in rows:
        if not ja or not en or method not in {"MANUAL", "REVIEWED"}:
            continue
        ja, en = str(ja).strip(), str(en).strip()
        if not any("\u3040" <= c <= "\u9fff" for c in ja):
            continue
        possible.setdefault(ja, set()).add(en)
    accepted = [(ja, next(iter(values))) for ja, values in sorted(possible.items()) if len(values) == 1]
    return dict(accepted[:limit])
