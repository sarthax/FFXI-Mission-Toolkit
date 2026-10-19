"""Offline Feature Trace contract: wiki document provenance is source-native, not graph evidence.

Run: PYTHONPATH=src:. python test_fixtures/test_feature_trace_wiki_documents.py
"""
import sqlite3

from workbench.devtools.features import trace
from workbench.devtools.features.trace_catalog import provider_relationships


def main():
    con = sqlite3.connect(":memory:")
    con.execute("""CREATE TABLE reference_wiki_documents (
        source_id TEXT NOT NULL, page_id TEXT NOT NULL, source_format TEXT NOT NULL,
        raw_source TEXT, raw_hash TEXT, parser_version TEXT NOT NULL,
        parsed_at TEXT, retrieved_at TEXT, source_revision TEXT,
        PRIMARY KEY(source_id,page_id))""")
    con.executemany("""INSERT INTO reference_wiki_documents
        (source_id,page_id,source_format,raw_source,raw_hash,parser_version,
         parsed_at,retrieved_at,source_revision) VALUES (?,?,?,?,?,?,?,?,?)""", [
        ("BGWiki","42","mediawiki","private-source","digest-bg","wiki-doc-v6-html-table-spans",
         "2026-10-18","2026-10-17","2048"),
        ("WikiWikiJP","42","html","別の原文","digest-jp","wiki-doc-v6-html-table-spans",
         "2026-10-18","2026-10-17",None),
    ])
    con.execute("""CREATE TABLE reference_wiki_pages (
        source_id TEXT, page_id TEXT, title TEXT,
        PRIMARY KEY(source_id,page_id))""")
    con.executemany("INSERT INTO reference_wiki_pages VALUES (?,?,?)", [
        ("BGWiki","42","Shared ID BG"),("WikiWikiJP","42","Shared ID JP")])
    for source in ("BGWiki","WikiWikiJP"):
        node_id = f"catalog:reference_wiki_documents:source_id={source}&page_id=42"
        node = trace.node_info(con,node_id)
        assert node["known"], (source,node)
        rep = node["representations"][0]
        assert rep["metadata"]["provider"] == "reference-wiki", rep
        assert rep["metadata"]["identity"] == {"source_id":source,"page_id":"42"}
        details = rep["metadata"]["details"]
        assert details["source_format"] == ("html" if source=="WikiWikiJP" else "mediawiki")
        assert details["raw_hash"].startswith("digest-")
        assert details["parser_version"] == "wiki-doc-v6-html-table-spans"
        assert details["retrieved_at"] == "2026-10-17"
        assert "raw_source" not in details, "raw wiki pages must not enter trace metadata"
        assert "source_revision" in details
        document_links = provider_relationships(con,node_id)
        expected_page = f"catalog:reference_wiki_pages:source_id={source}&page_id=42"
        assert any(link["relationship"] == "DOCUMENT_FOR_REFERENCE_PAGE"
                   and link["target_node"] == expected_page
                   and link["provider_native"] is True
                   for link in document_links), document_links
        page_links = provider_relationships(con,expected_page)
        assert any(link["relationship"] == "HAS_SOURCE_DOCUMENT"
                   and link["target_node"] == node_id
                   and link["provider_native"] is True
                   for link in page_links), page_links
        assert all(other not in str(document_links) + str(page_links)
                   for other in (("WikiWikiJP" if source=="BGWiki" else "BGWiki"),))
    assert not trace.node_info(con,"catalog:reference_wiki_documents:42")["known"]
    assert not trace.node_info(con,"catalog:reference_wiki_documents:source_id=FFXIclopedia&page_id=42")["known"]
    rows=[r for r in trace.search_nodes(con,"wiki-doc-v6-html-table-spans")
          if r.get("table")=="reference_wiki_documents"]
    assert len(rows)==2 and len({r["node_id"] for r in rows})==2,rows
    con.close()
    print("Feature Trace Wiki source document contract: PASS")


if __name__=="__main__":
    main()
