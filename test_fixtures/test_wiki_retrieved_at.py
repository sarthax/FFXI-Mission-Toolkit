"""retrieved_at / source_revision provenance on reference_wiki_documents (offline)."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from workbench.devtools.reference import wiki_document as wd  # noqa: E402

RAW = "<html><body><main><h1>T</h1><p>body</p></main></body></html>"


def _store(con, **kw):
    page = {"page_id": "T", "title": "T", "page_text": "body"}
    pid, fmt, blocks = wd.build_blocks(page, source_format="html", raw_source=RAW)
    wd.store_document(con, source_id="WikiWikiJP", page_id=pid, source_format=fmt,
                      raw_source=RAW, blocks=blocks, **kw)


def _row(con):
    return con.execute("SELECT retrieved_at,source_revision,parsed_at FROM reference_wiki_documents").fetchone()


def main():
    con = sqlite3.connect(":memory:")
    # Legacy table without the new columns is migrated in place.
    con.execute("""CREATE TABLE reference_wiki_documents(source_id TEXT NOT NULL,page_id TEXT NOT NULL,
      source_format TEXT NOT NULL,raw_source TEXT,raw_hash TEXT,parser_version TEXT NOT NULL,
      parsed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(source_id,page_id))""")
    wd.init_db(con)
    cols = {r[1] for r in con.execute("PRAGMA table_info(reference_wiki_documents)")}
    assert {"retrieved_at", "source_revision"} <= cols, cols

    _store(con)  # legacy callers: provenance stays NULL, never invented
    assert _row(con)[:2] == (None, None), _row(con)

    _store(con, retrieved_at="2026-10-18T00:00:00Z")
    r1 = _row(con)
    assert r1[0] == "2026-10-18T00:00:00Z" and r1[1] is None, r1

    _store(con, retrieved_at="2026-10-19T00:00:00Z", source_revision="rev-7")
    r2 = _row(con)
    assert r2[:2] == ("2026-10-19T00:00:00Z", "rev-7"), r2
    assert r2[2] == r1[2], "identical source must not churn parsed_at"

    _store(con, retrieved_at="2026-10-20T00:00:00Z")  # no revision supplied: keep known one
    assert _row(con)[:2] == ("2026-10-20T00:00:00Z", "rev-7"), _row(con)
    print("OK (retrieved_at provenance)")


if __name__ == "__main__":
    main()
