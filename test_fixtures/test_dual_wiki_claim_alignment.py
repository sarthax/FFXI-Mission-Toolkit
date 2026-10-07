#!/usr/bin/env python3
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.devtools.reference import wiki_evidence
from workbench.devtools.reference import wiki_claim_compare
from workbench.core import graph as workbench_graph
from workbench.core.services import wiki_evidence_graph
from workbench.core.services.feature_trace_providers import provider_tables


def add_claim(con, source, page_id, title, claim_id, claim_type, subject, section, excerpt, rev):
    con.execute(
        """INSERT INTO reference_wiki_claims
        (claim_id,source_id,page_id,page_title,page_url,revision_id,revision_timestamp,
         section_title,claim_type,subject_text,excerpt,source_locator,authority,content_hash)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (claim_id,source,page_id,title,None,rev,"2026-09-28T00:00:00Z",section,claim_type,
         subject,excerpt,f"section:{section}","REFERENCE_ONLY","hash-"+claim_id),
    )


def main():
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        db=root/"db.sqlite"
        graph_db=root/"graph.sqlite"
        con=sqlite3.connect(db)
        wiki_claim_compare.init_db(con)

        # Imported FFXIclopedia page identity; BG page identity can be claim-derived.
        con.execute(
            """INSERT INTO reference_wiki_pages
            (source_id,page_id,title,norm_title,revision_id,revision_timestamp,page_text,page_hash)
            VALUES (?,?,?,?,?,?,?,?)""",
            (wiki_evidence.SOURCE_FFXICLOPEDIA,"fx1","Dual Test","dualtest","900","2026-09-28T00:00:00Z","","fxhash"),
        )

        add_claim(con,wiki_evidence.SOURCE_BG,"bg1","Dual Test","bg-npc","ENTITY_REFERENCE","Test NPC","Walkthrough","Speak with Test NPC.","100")
        add_claim(con,wiki_evidence.SOURCE_FFXICLOPEDIA,"fx1","Dual Test","fx-npc","ENTITY_REFERENCE","Test NPC","Walkthrough","Speak with Test NPC.","900")

        add_claim(con,wiki_evidence.SOURCE_BG,"bg1","Dual Test","bg-num","SECTION_STATEMENT",None,"Walkthrough","Defeat 5 enemies before opening the chest.","101")
        add_claim(con,wiki_evidence.SOURCE_FFXICLOPEDIA,"fx1","Dual Test","fx-num","SECTION_STATEMENT",None,"Walkthrough","Defeat 6 enemies before opening the chest.","901")

        add_claim(con,wiki_evidence.SOURCE_BG,"bg1","Dual Test","bg-neg","SECTION_STATEMENT",None,"Notes","You can trade the item during the mission.","102")
        add_claim(con,wiki_evidence.SOURCE_FFXICLOPEDIA,"fx1","Dual Test","fx-neg","SECTION_STATEMENT",None,"Notes","You cannot trade the item during the mission.","902")

        add_claim(con,wiki_evidence.SOURCE_BG,"bg1","Dual Test","bg-only","ENTITY_REFERENCE","Only BG NPC","Walkthrough","Speak with Only BG NPC.","103")
        add_claim(con,wiki_evidence.SOURCE_FFXICLOPEDIA,"fx1","Dual Test","fx-only","ENTITY_REFERENCE","Only FX NPC","Walkthrough","Speak with Only FX NPC.","903")
        con.commit()

        result=wiki_claim_compare.align_page(con,"Dual Test")
        assert result["status"]=="OK",result
        assert result["page_status"]=="DUAL_SOURCE",result
        assert result["counts"]["AGREEMENT"]>=1,result
        assert result["counts"]["REFERENCE_CONFLICT"]==2,result
        assert result["counts"]["BG_ONLY"]>=1,result
        assert result["counts"]["FFXICLOPEDIA_ONLY"]>=1,result

        report=wiki_claim_compare.alignment_report(con,"Dual Test")
        conflicts=[p for p in report["pairs"] if p["status"]=="REFERENCE_CONFLICT"]
        kinds={p["conflict_kind"] for p in conflicts}
        assert kinds=={"NUMERIC_DISAGREEMENT","NEGATION_DISAGREEMENT"},kinds
        numeric=next(p for p in conflicts if p["conflict_kind"]=="NUMERIC_DISAGREEMENT")
        assert numeric["details"]["bg_numbers"]==["5"] or numeric["details"]["bg_numbers"]==("5",)
        assert numeric["details"]["ffxiclopedia_numbers"]==["6"] or numeric["details"]["ffxiclopedia_numbers"]==("6",)

        imported=wiki_evidence_graph.import_wiki_alignment(db,graph_db,title="Dual Test")
        assert imported["status"]=="OK",imported
        assert imported["conflicts"]==2,imported
        assert imported["agreements"]>=1,imported

        graph=workbench_graph.init_db(graph_db)
        rows=graph.execute(
            """SELECT f.status,f.confidence,f.value_json,e.evidence_type,e.source
               FROM findings f JOIN evidence e ON e.evidence_id=f.evidence_id
               WHERE f.analysis_id LIKE 'analysis:wiki-align:%'"""
        ).fetchall()
        assert rows,rows
        contradicted=[r for r in rows if r[0]=="CONTRADICTED"]
        assert len(contradicted)==2,rows
        for status,confidence,value_json,evidence_type,source in contradicted:
            assert confidence=="INFERRED"
            meta=json.loads(value_json)
            assert meta["authority"]=="REFERENCE_ONLY",meta
            assert source=="BGWiki+FFXIclopedia"
            assert evidence_type=="REFERENCE"
        graph.close()

        tables=provider_tables()
        assert "reference_wiki_page_alignments" in tables
        assert "reference_wiki_claim_alignments" in tables

        template=(Path(__file__).resolve().parents[1]/"gui"/"templates"/"wiki.html").read_text(encoding="utf-8")
        assert "Dual-wiki claim comparison" in template
        assert "REFERENCE_CONFLICT" in template
        assert "does not identify which source is correct" in template

        con.close()

    print("Dual-wiki claim alignment regression: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
