import sqlite3

from workbench.devtools.features.trace_catalog import provider_relationships


def _db():
    con=sqlite3.connect(":memory:")
    con.executescript("""
      CREATE TABLE reference_wiki_pages(
        source_id TEXT,page_id TEXT,title TEXT,norm_title TEXT,revision_id TEXT,revision_timestamp TEXT,
        page_text TEXT,page_hash TEXT,PRIMARY KEY(source_id,page_id));
      CREATE TABLE reference_wiki_blocks(
        source_id TEXT,page_id TEXT,block_id TEXT,ordinal INTEGER,block_type TEXT,heading_level INTEGER,
        section_path TEXT,text TEXT,target TEXT,metadata_json TEXT,source_locator TEXT,
        PRIMARY KEY(source_id,page_id,block_id));
      CREATE TABLE reference_wiki_topics(
        topic_id TEXT PRIMARY KEY,canonical_title TEXT,norm_title TEXT,created_at TEXT);
      CREATE TABLE reference_wiki_topic_pages(
        topic_id TEXT,source_id TEXT,page_id TEXT,link_method TEXT,created_at TEXT,
        PRIMARY KEY(topic_id,source_id,page_id));
      CREATE TABLE reference_wiki_claims(
        claim_id TEXT PRIMARY KEY,source_id TEXT,page_id TEXT,page_title TEXT,page_url TEXT,
        revision_id TEXT,revision_timestamp TEXT,section_title TEXT,claim_type TEXT,subject_text TEXT,
        excerpt TEXT,source_locator TEXT,authority TEXT,content_hash TEXT,created_at TEXT);
      CREATE TABLE reference_wiki_mappings(
        mapping_id TEXT PRIMARY KEY,claim_id TEXT,target_domain TEXT,target_table TEXT,target_key TEXT,
        target_label TEXT,mapping_method TEXT,mapping_status TEXT,confidence TEXT,details_json TEXT,created_at TEXT);
      CREATE TABLE reference_wiki_mapping_reviews(
        mapping_id TEXT PRIMARY KEY,review_status TEXT,notes TEXT,reviewed_at TEXT);
      CREATE TABLE reference_wiki_page_alignments(
        alignment_id TEXT PRIMARY KEY,norm_title TEXT,bg_page_id TEXT,ffxiclopedia_page_id TEXT,status TEXT,updated_at TEXT);
      CREATE TABLE reference_wiki_claim_alignments(
        pair_id TEXT PRIMARY KEY,status TEXT,alignment_id TEXT,bg_claim_id TEXT,ffxiclopedia_claim_id TEXT,
        alignment_type TEXT,similarity REAL,conflict_kind TEXT);
    """)
    con.executemany("INSERT INTO reference_wiki_pages VALUES(?,?,?,?,?,?,?,?)",[
        ("WikiWikiJP","same","JP Page","jp","","","jp","1"),
        ("FFXIclopedia","same","English Page","english","","","en","2"),
    ])
    con.execute("INSERT INTO reference_wiki_blocks VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                ("WikiWikiJP","same","b1",1,"paragraph",None,"攻略","本文",None,"{}","section:攻略"))
    con.execute("INSERT INTO reference_wiki_claims VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("c1","WikiWikiJP","same","JP Page",None,"1",None,"攻略","ENTITY_REFERENCE","対象","対象",
                 "section:攻略","REFERENCE_ONLY","h",None))
    con.execute("INSERT INTO reference_wiki_topics VALUES(?,?,?,?)",
                ("topic:1","Canonical Topic","canonical topic",None))
    con.execute("INSERT INTO reference_wiki_topic_pages VALUES(?,?,?,?,?)",
                ("topic:1","WikiWikiJP","same","MANUAL_REVIEW",None))
    return con


def main():
    con=_db()

    block="catalog:reference_wiki_blocks:source_id=WikiWikiJP&page_id=same&block_id=b1"
    links=provider_relationships(con,block)
    page=next(x for x in links if x["relationship"]=="IN_REFERENCE_PAGE")
    assert page["target_node"]=="catalog:reference_wiki_pages:source_id=WikiWikiJP&page_id=same",links
    assert "FFXIclopedia" not in page["target_node"]

    claim="catalog:reference_wiki_claims:c1"
    links=provider_relationships(con,claim)
    page=next(x for x in links if x["relationship"]=="FROM_REFERENCE_PAGE")
    assert page["target_node"]=="catalog:reference_wiki_pages:source_id=WikiWikiJP&page_id=same",links

    page_node="catalog:reference_wiki_pages:source_id=WikiWikiJP&page_id=same"
    links=provider_relationships(con,page_node)
    membership=next(x for x in links if x["relationship"]=="IN_REFERENCE_TOPIC")
    assert membership["target_node"].startswith("catalog:reference_wiki_topic_pages:"),links

    topic_page=membership["target_node"]
    links=provider_relationships(con,topic_page)
    rels={x["relationship"]:x for x in links}
    assert rels["TOPIC_MEMBER_PAGE"]["target_node"]==page_node,links
    assert rels["IN_REFERENCE_TOPIC"]["target_node"]=="catalog:reference_wiki_topics:topic:1",links

    con.close()
    print("Wiki V2 structured Feature Trace provider regression: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
