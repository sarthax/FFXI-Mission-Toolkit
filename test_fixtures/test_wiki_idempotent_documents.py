"""Regression: unchanged Wiki V2 documents do not churn preserved evidence."""
from __future__ import annotations
import sqlite3
from workbench.devtools.reference import wiki_document as doc


def main():
    con = sqlite3.connect(":memory:")
    params = dict(source_id="WikiWikiJP", page_id="same-page", source_format="html")
    blocks = [{"block_id":"block-1","ordinal":1,"block_type":"paragraph","text":"日本語本文","metadata":{}}]
    doc.store_document(con, **params, raw_source="<p>日本語本文</p>", blocks=blocks)
    con.execute("UPDATE reference_wiki_documents SET parsed_at='2000-01-01' WHERE source_id=? AND page_id=?", ("WikiWikiJP","same-page"))
    doc.store_document(con, **params, raw_source="<p>日本語本文</p>", blocks=[])
    assert con.execute("SELECT parsed_at FROM reference_wiki_documents").fetchone()[0] == "2000-01-01"
    assert con.execute("SELECT COUNT(*) FROM reference_wiki_blocks").fetchone()[0] == 1
    doc.store_document(con, **params, raw_source="<p>updated</p>", blocks=[dict(blocks[0], text="updated")])
    assert con.execute("SELECT text FROM reference_wiki_blocks").fetchone()[0] == "updated"
    con.execute("UPDATE reference_wiki_documents SET parser_version='old' ")
    doc.store_document(con, **params, raw_source="<p>updated</p>", blocks=[dict(blocks[0], text="reparsed")])
    assert con.execute("SELECT text FROM reference_wiki_blocks").fetchone()[0] == "reparsed"
    con.close()
    print("Wiki V2 idempotent document regression: PASS")


if __name__ == "__main__":
    main()
