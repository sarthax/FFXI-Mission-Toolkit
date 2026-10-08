from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.core import graph as workbench_graph
from workbench.core.services import wiki_evidence_graph
from workbench.devtools.features import trace as feature_trace
from workbench.devtools.reference import wiki_document, wiki_evidence


def _base_db(path: Path):
    con=sqlite3.connect(path)
    wiki_evidence.init_db(con)
    con.execute("CREATE TABLE npc_names(npcid INTEGER,name TEXT,zoneid INTEGER)")
    con.execute("CREATE TABLE items_ours(itemid INTEGER,name TEXT)")
    con.execute("INSERT INTO npc_names VALUES(1001,'Absolute Virtue',33)")
    con.execute("INSERT INTO items_ours VALUES(2001,\"Mars's Ring\")")
    return con


def _relation_row(con, source, page_id):
    return con.execute(
        """SELECT relation_id,relation_type,subject_text,object_text,section_title,authority,extraction_method
           FROM reference_wiki_relations WHERE source_id=? AND page_id=?""",
        (source,page_id),
    ).fetchone()


def test_english_mediawiki_relation_without_network(root: Path):
    db=root/"en.sqlite"; graph_db=root/"en_graph.sqlite"
    con=_base_db(db)
    text="""Lead.
== Drops ==
* [[Mars's Ring]]
== Notes ==
* See [[Kupipi]] for unrelated background.
"""
    con.execute("""INSERT INTO reference_wiki_pages
      (source_id,page_id,title,norm_title,revision_id,revision_timestamp,page_text,page_hash)
      VALUES (?,?,?,?,?,?,?,?)""",
      (wiki_evidence.SOURCE_FFXICLOPEDIA,"fx-av","Absolute Virtue","absolutevirtue","77",
       "2026-10-08T00:00:00Z",text,"hash-en"))
    con.commit()

    result=wiki_evidence.ingest_page(con,wiki_evidence.SOURCE_FFXICLOPEDIA,"Absolute Virtue")
    assert result["status"]=="OK",result
    assert result["counts"]["relations"]==1,result
    assert result["counts"]["mapped_relations"]==1,result
    relation=_relation_row(con,wiki_evidence.SOURCE_FFXICLOPEDIA,"fx-av")
    assert relation[1:] == (
        "REFERENCE_DROPS","Absolute Virtue","Mars's Ring","Drops","REFERENCE_ONLY","STRUCTURED_SECTION_LINK"
    ),relation

    # The unrelated Notes link remains a mention claim, not a typed drop relation.
    objects={r[0] for r in con.execute(
        "SELECT object_text FROM reference_wiki_relations WHERE source_id=? AND page_id=?",
        (wiki_evidence.SOURCE_FFXICLOPEDIA,"fx-av"),
    )}
    assert "Kupipi" not in objects,objects

    imported=wiki_evidence_graph.import_wiki_evidence(
        db,graph_db,source_id=wiki_evidence.SOURCE_FFXICLOPEDIA,page_id="fx-av"
    )
    assert imported["counts"]["relation_edges"]==1,imported
    graph=workbench_graph.init_db(graph_db)
    edge=graph.execute(
        """SELECT source_node,target_node,relationship,confidence,metadata_json
           FROM entity_relationships WHERE relationship LIKE 'REFERENCE_%'"""
    ).fetchone()
    assert edge[0]=="entity:npcid:1001",edge
    assert edge[1]=="entity:itemid:2001",edge
    assert edge[2]=="REFERENCE_DROPS",edge
    assert edge[3]=="INFERRED",edge
    assert '"authority": "REFERENCE_ONLY"' in edge[4],edge

    traced=feature_trace.trace(graph,"entity:itemid:2001",depth=1,direction="both")
    refs=[e for e in traced["edges"] if e["relationship"]=="REFERENCE_DROPS"]
    assert refs and refs[0]["traversed_direction"]=="in",refs
    graph.close(); con.close()


def test_japanese_relation_uses_reviewed_topics(root: Path):
    db=root/"jp.sqlite"; graph_db=root/"jp_graph.sqlite"
    con=_base_db(db)
    con.executemany("""INSERT INTO reference_wiki_pages
      (source_id,page_id,title,norm_title,revision_id,revision_timestamp,page_text,page_hash)
      VALUES (?,?,?,?,?,?,?,?)""",[
        (wiki_evidence.SOURCE_WIKIWIKI_JP,"jp-av","アブソリュートヴァーチュー","アブソリュートヴァーチュー",
         "10","2026-10-08T00:00:00Z","戦利品 マーズリング","h1"),
        (wiki_evidence.SOURCE_WIKIWIKI_JP,"jp-ring","マーズリング","マーズリング",
         "11","2026-10-08T00:00:00Z","指輪","h2"),
    ])
    wiki_document.link_topic(
        con,source_id=wiki_evidence.SOURCE_WIKIWIKI_JP,page_id="jp-av",
        canonical_title="Absolute Virtue",method="MANUAL_REVIEW",
    )
    wiki_document.link_topic(
        con,source_id=wiki_evidence.SOURCE_WIKIWIKI_JP,page_id="jp-ring",
        canonical_title="Mars's Ring",method="MANUAL_REVIEW",
    )
    raw='''<div id="body"><h2>戦利品</h2><ul><li><a href="/ffxi/%E3%83%9E%E3%83%BC%E3%82%BA%E3%83%AA%E3%83%B3%E3%82%B0">マーズリング</a></li></ul><div id="footer"></div>'''
    _,fmt,blocks=wiki_document.build_blocks(
        {"page_id":"jp-av","title":"アブソリュートヴァーチュー","page_text":"戦利品 マーズリング"},
        source_format="html",raw_source=raw,
    )
    wiki_document.store_document(
        con,source_id=wiki_evidence.SOURCE_WIKIWIKI_JP,page_id="jp-av",
        source_format=fmt,raw_source=raw,blocks=blocks,
    )
    con.commit()

    result=wiki_evidence.ingest_page(con,wiki_evidence.SOURCE_WIKIWIKI_JP,"アブソリュートヴァーチュー")
    assert result["counts"]["relations"]==1,result
    assert result["counts"]["mapped_relations"]==1,result
    relation=_relation_row(con,wiki_evidence.SOURCE_WIKIWIKI_JP,"jp-av")
    assert relation[1]=="REFERENCE_DROPS",relation
    assert relation[2]=="Absolute Virtue",relation
    assert relation[3]=="マーズリング",relation
    assert relation[4]=="戦利品",relation

    maps=con.execute(
        """SELECT endpoint,target_label,mapping_method,mapping_status
           FROM reference_wiki_relation_mappings WHERE relation_id=? ORDER BY endpoint""",
        (relation[0],),
    ).fetchall()
    assert maps==[
        ("object","Mars's Ring","MULTILINGUAL_TOPIC_ALIAS","MAPPED"),
        ("subject","Absolute Virtue","DISPLAY_NAME_EXACT","MAPPED"),
    ],maps

    imported=wiki_evidence_graph.import_wiki_evidence(
        db,graph_db,source_id=wiki_evidence.SOURCE_WIKIWIKI_JP,page_id="jp-av"
    )
    assert imported["counts"]["relation_edges"]==1,imported
    graph=workbench_graph.init_db(graph_db)
    edge=graph.execute(
        "SELECT relationship,metadata_json FROM entity_relationships WHERE relationship='REFERENCE_DROPS'"
    ).fetchone()
    assert edge,edge
    assert '"section_title": "\\u6226\\u5229\\u54c1"' in edge[1] or '"section_title": "戦利品"' in edge[1],edge
    assert '"authority": "REFERENCE_ONLY"' in edge[1],edge
    graph.close(); con.close()


def main():
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        test_english_mediawiki_relation_without_network(root)
        test_japanese_relation_uses_reviewed_topics(root)
    template=(Path(__file__).resolve().parents[1]/"gui"/"templates"/"wiki.html").read_text(encoding="utf-8")
    assert "Structured reference relationships" in template
    assert "REFERENCE_ONLY" in template
    print("Wiki V2 typed relation regression: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
