from __future__ import annotations

import sqlite3

from workbench.devtools.reference import wiki_document


def _con():
    con=sqlite3.connect(":memory:")
    con.execute("""CREATE TABLE reference_wiki_pages(
      source_id TEXT NOT NULL,page_id TEXT NOT NULL,title TEXT NOT NULL,norm_title TEXT NOT NULL,
      revision_id TEXT,revision_timestamp TEXT,page_text TEXT,page_hash TEXT NOT NULL,
      PRIMARY KEY(source_id,page_id))""")
    con.execute("""CREATE TABLE wiki_pages(norm_title TEXT PRIMARY KEY,title TEXT,url TEXT)""")
    wiki_document.init_db(con)
    return con


def test_mediawiki_structure_preserves_headings_lists_tables_and_links():
    text="""Lead paragraph.

== Walkthrough ==
* Speak with [[Kupipi]].
* Trade [[Test Item]].
{| class="wikitable"
! Item !! Count
|-
| Test Item || 2
|}
"""
    blocks=wiki_document.mediawiki_blocks("p1",text)
    kinds=[b["block_type"] for b in blocks]
    assert "heading" in kinds
    assert kinds.count("list_item")==2
    assert "table_start" in kinds
    assert "table_header_cell" in kinds
    assert "table_cell" in kinds
    links={b["target"] for b in blocks if b["block_type"]=="link"}
    assert {"Kupipi","Test Item"} <= links
    groups=wiki_document.presentation_groups([b for b in blocks if not b["metadata"].get("hidden")])
    walkthrough=next(g for g in groups if g["title"]=="Walkthrough")
    assert any(x["type"]=="list" for x in walkthrough["content"])
    assert any(x["type"]=="table" for x in walkthrough["content"])


def test_html_structure_preserves_japanese_headings_lists_tables_and_links():
    raw="""<div id="body"><h2>攻略</h2><p>テスト説明。</p>
    <ul><li><a href="/ffxi/Absolute%20Virtue">Absolute Virtue</a>を倒す。</li></ul>
    <table><tr><th>項目</th><th>値</th></tr><tr><td>場所</td><td>アル・タユ</td></tr></table></div>"""
    blocks=wiki_document.html_blocks("jp1",raw)
    assert any(b["block_type"]=="heading" and b["text"]=="攻略" for b in blocks)
    assert any(b["block_type"]=="list_item" for b in blocks)
    assert any(b["block_type"]=="table_header_cell" and b["text"]=="項目" for b in blocks)
    assert any(b["block_type"]=="table_cell" and b["text"]=="アル・タユ" for b in blocks)
    assert any(b["block_type"]=="link" and "Absolute" in (b["target"] or "") for b in blocks)


def test_legacy_text_fallback_is_explicitly_degraded():
    blocks=wiki_document.legacy_text_blocks("old","one flattened line\nsecond flattened line")
    assert blocks
    assert all(b["block_type"]=="legacy_text" for b in blocks)
    assert all(b["metadata"]["degraded"] is True for b in blocks)


def test_canonical_topic_makes_japanese_page_searchable_in_english():
    con=_con()
    con.execute("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",
                ("WikiWikiJP","AV","アブソリュートヴァーチュー","アブソリュートヴァーチュー","","","日本語本文","h"))
    wiki_document.link_topic(con,source_id="WikiWikiJP",page_id="AV",canonical_title="Absolute Virtue",method="TEST")
    rows=wiki_document.search_pages(con,"Absolute Virtue")
    assert rows
    assert rows[0]["source_id"]=="WikiWikiJP"
    assert "canonical topic" in rows[0]["reasons"] or "alias" in rows[0]["reasons"]
    topic=wiki_document.page_topic(con,"WikiWikiJP","AV")
    assert topic["canonical_title"]=="Absolute Virtue"


def test_cross_source_topic_membership_keeps_sources_distinct():
    con=_con()
    con.executemany("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",[
        ("WikiWikiJP","jp","絶対回避","絶対回避","","","jp","1"),
        ("FFXIclopedia","fx","Perfect Dodge","perfectdodge","","","en","2"),
    ])
    wiki_document.link_topic(con,source_id="WikiWikiJP",page_id="jp",canonical_title="Perfect Dodge",method="TEST")
    wiki_document.link_topic(con,source_id="FFXIclopedia",page_id="fx",canonical_title="Perfect Dodge",method="TEST")
    topic=wiki_document.page_topic(con,"WikiWikiJP","jp")
    assert {(m["source_id"],m["page_id"]) for m in topic["members"]}=={
        ("WikiWikiJP","jp"),("FFXIclopedia","fx")
    }


def test_bg_reverse_index_stays_searchable_without_page_import():
    con=_con()
    con.execute("INSERT INTO wiki_pages VALUES(?,?,?)",
                ("absolutevirtue","Absolute Virtue","https://www.bg-wiki.com/ffxi/Absolute_Virtue"))
    rows=wiki_document.search_pages(con,"Absolute Virtue")
    assert any(r["source_id"]=="BGWiki" and r["title"]=="Absolute Virtue" for r in rows)
