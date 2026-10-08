from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.core import graph as workbench_graph
from workbench.core.services import wiki_evidence_graph
from workbench.devtools.reference import wiki_document, wiki_evidence


def main():
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        db=root/"wiki.sqlite"
        graph_db=root/"graph.sqlite"
        con=sqlite3.connect(db)
        wiki_evidence.init_db(con)
        con.execute("CREATE TABLE npc_names(npcid INTEGER,name TEXT,zoneid INTEGER)")
        con.execute("INSERT INTO npc_names VALUES(1001,'Absolute Virtue',33)")

        # Japanese target page gets a reviewed English canonical topic.
        con.execute("""INSERT INTO reference_wiki_pages
          (source_id,page_id,title,norm_title,revision_id,revision_timestamp,page_text,page_hash)
          VALUES (?,?,?,?,?,?,?,?)""",
          (wiki_evidence.SOURCE_WIKIWIKI_JP,"jp-av","アブソリュートヴァーチュー","アブソリュートヴァーチュー",
           "10","2026-10-08T00:00:00Z","日本語本文","h1"))
        wiki_document.link_topic(
            con,source_id=wiki_evidence.SOURCE_WIKIWIKI_JP,page_id="jp-av",
            canonical_title="Absolute Virtue",method="MANUAL_REVIEW",
        )

        # A second Japanese article explicitly links that Japanese page.
        source_html='''<div id="body"><h2>攻略</h2><p><a href="/ffxi/%E3%82%A2%E3%83%96%E3%82%BD%E3%83%AA%E3%83%A5%E3%83%BC%E3%83%88%E3%83%B4%E3%82%A1%E3%83%BC%E3%83%81%E3%83%A5%E3%83%BC">アブソリュートヴァーチュー</a>を倒す。</p><div id="footer"></div>'''
        page_text="攻略\nアブソリュートヴァーチューを倒す。"
        con.execute("""INSERT INTO reference_wiki_pages
          (source_id,page_id,title,norm_title,revision_id,revision_timestamp,page_text,page_hash)
          VALUES (?,?,?,?,?,?,?,?)""",
          (wiki_evidence.SOURCE_WIKIWIKI_JP,"jp-guide","ルモリア攻略","ルモリア攻略",
           "11","2026-10-08T00:00:00Z",page_text,"h2"))
        _,fmt,blocks=wiki_document.build_blocks(
            {"page_id":"jp-guide","title":"ルモリア攻略","page_text":page_text},
            source_format="html",raw_source=source_html,
        )
        wiki_document.store_document(
            con,source_id=wiki_evidence.SOURCE_WIKIWIKI_JP,page_id="jp-guide",
            source_format=fmt,raw_source=source_html,blocks=blocks,
        )
        con.commit()

        result=wiki_evidence.ingest_page(con,wiki_evidence.SOURCE_WIKIWIKI_JP,"ルモリア攻略")
        assert result["status"]=="OK",result
        assert result["counts"]["entity_references"]>=1,result

        row=con.execute("""SELECT c.subject_text,m.target_table,m.target_key,m.target_label,
                                 m.mapping_method,m.mapping_status,m.confidence,m.details_json
                          FROM reference_wiki_claims c
                          JOIN reference_wiki_mappings m ON m.claim_id=c.claim_id
                          WHERE c.source_id=? AND c.page_id=? AND c.claim_type='ENTITY_REFERENCE'""",
                        (wiki_evidence.SOURCE_WIKIWIKI_JP,"jp-guide")).fetchone()
        assert row,row
        assert row[0]=="アブソリュートヴァーチュー",row
        assert row[1]=="npc_names",row
        assert row[2]=="1001",row
        assert row[3]=="Absolute Virtue",row
        assert row[4]=="MULTILINGUAL_TOPIC_ALIAS",row
        assert row[5]=="MAPPED",row
        assert row[6]=="HIGH",row

        imported=wiki_evidence_graph.import_wiki_evidence(
            db,graph_db,source_id=wiki_evidence.SOURCE_WIKIWIKI_JP,page_id="jp-guide"
        )
        assert imported["status"]=="OK",imported
        assert imported["counts"]["mapped_edges"]>=1,imported

        graph=workbench_graph.init_db(graph_db)
        edges=graph.execute("""SELECT relationship,confidence,metadata_json
                               FROM entity_relationships
                               WHERE relationship_id LIKE 'wiki-reference:%'""").fetchall()
        assert edges,edges
        rel,confidence,metadata=edges[0]
        assert rel=="MENTIONS",edges
        assert confidence=="INFERRED",edges
        assert '"authority": "REFERENCE_ONLY"' in metadata,metadata
        assert '"mapping_method": "MULTILINGUAL_TOPIC_ALIAS"' in metadata,metadata
        graph.close()
        con.close()

    print("Wiki V2 Japanese reference graph regression: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
