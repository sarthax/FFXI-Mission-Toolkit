#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.devtools.reference import wiki_evidence
from workbench.core import graph as workbench_graph
from workbench.core.services import wiki_evidence_graph
from workbench.core.services.feature_trace_providers import provider_tables


def main():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        db = root / "ffxi_zone_database.db"
        graph_db = root / "workbench.db"

        con = sqlite3.connect(db)
        con.executescript("""
            CREATE TABLE zones(zoneid INTEGER PRIMARY KEY,name TEXT);
            CREATE TABLE npc_names(npcid INTEGER,name TEXT,zoneid INTEGER);
            CREATE TABLE key_items(keyitem_id INTEGER,name TEXT);
            CREATE TABLE items_ours(itemid INTEGER,name TEXT);
        """)
        con.execute("INSERT INTO zones VALUES(77,'TEST_ZONE')")
        con.execute("INSERT INTO npc_names VALUES(17000001,'Test NPC',77)")
        con.execute("INSERT INTO key_items VALUES(900,'Shared Token')")
        con.execute("INSERT INTO items_ours VALUES(1234,'shared_token')")
        con.commit()

        page = {
            "title": "Evidence Quest",
            "pageid": 101,
            "revid": 202,
            "timestamp": "2026-09-28T12:00:00Z",
            "url": "https://example.invalid/Evidence_Quest",
            "wikitext": """== Walkthrough ==
* Speak with [[Test NPC]] in [[Test Zone]].
* Bring [[Shared Token]] to the NPC.
* Examine [[Missing Object]] after the cutscene.
== Notes ==
* This is reference prose that should remain a claim even without a mapped entity.
""",
        }

        original_find = wiki_evidence.find_reference_page
        wiki_evidence.find_reference_page = lambda _con, source_id, title: page if source_id == wiki_evidence.SOURCE_BG else None
        try:
            result = wiki_evidence.ingest_page(con, wiki_evidence.SOURCE_BG, "Evidence Quest")
        finally:
            wiki_evidence.find_reference_page = original_find

        assert result["status"] == "OK", result
        assert result["counts"]["entity_references"] == 4, result
        assert result["counts"]["section_statements"] >= 4, result
        assert result["counts"]["mapped"] >= 2, result
        assert result["counts"]["ambiguous"] >= 2, result
        assert result["counts"]["unresolved"] >= 1, result

        con.row_factory = sqlite3.Row
        npc_mapping = con.execute(
            """SELECT m.mapping_id,m.claim_id FROM reference_wiki_mappings m
               JOIN reference_wiki_claims c ON c.claim_id=m.claim_id
               WHERE c.subject_text='Test NPC' AND m.mapping_status='MAPPED'"""
        ).fetchone()
        assert npc_mapping is not None

        shared = con.execute(
            """SELECT COUNT(*) FROM reference_wiki_mappings m
               JOIN reference_wiki_claims c ON c.claim_id=m.claim_id
               WHERE c.subject_text='Shared Token' AND m.mapping_status='AMBIGUOUS'"""
        ).fetchone()[0]
        assert shared == 2, shared

        missing = con.execute(
            """SELECT m.mapping_status FROM reference_wiki_mappings m
               JOIN reference_wiki_claims c ON c.claim_id=m.claim_id
               WHERE c.subject_text='Missing Object'"""
        ).fetchone()
        assert missing[0] == "UNRESOLVED", missing

        wiki_evidence.review_mapping(con, npc_mapping["mapping_id"], "CONFIRMED", "Verified intended NPC identity.")
        # Read the persisted review directly; the synthetic page resolver was intentionally restored.
        review = con.execute(
            "SELECT review_status,notes FROM reference_wiki_mapping_reviews WHERE mapping_id=?",
            (npc_mapping["mapping_id"],),
        ).fetchone()
        assert review[0] == "CONFIRMED", review
        con.close()

        imported = wiki_evidence_graph.import_wiki_evidence(
            db, graph_db, source_id=wiki_evidence.SOURCE_BG, page_id="101"
        )
        assert imported["status"] == "OK", imported
        assert imported["counts"]["claims"] >= 8, imported
        assert imported["counts"]["mapped_edges"] >= 2, imported

        graph = workbench_graph.init_db(graph_db)
        edge = graph.execute(
            """SELECT relationship,confidence,metadata_json
               FROM entity_relationships
               WHERE relationship_id=?""",
            (f"wiki-reference:{npc_mapping['mapping_id']}",),
        ).fetchone()
        assert edge is not None
        assert edge[0] == "MENTIONS" and edge[1] == "VERIFIED", edge
        metadata = json.loads(edge[2])
        assert metadata["authority"] == "REFERENCE_ONLY", metadata
        assert metadata["review_status"] == "CONFIRMED", metadata

        evidence = graph.execute(
            "SELECT evidence_type,source,notes FROM evidence WHERE evidence_id=?",
            (f"evidence:{npc_mapping['claim_id']}",),
        ).fetchone()
        assert evidence[0] == "REFERENCE" and evidence[1] == wiki_evidence.SOURCE_BG, evidence
        graph.close()

        con = sqlite3.connect(db)
        wiki_evidence.review_mapping(con, npc_mapping["mapping_id"], "REJECTED", "Wrong identity on review.")
        con.close()
        wiki_evidence_graph.import_wiki_evidence(
            db, graph_db, source_id=wiki_evidence.SOURCE_BG, page_id="101"
        )
        graph = workbench_graph.init_db(graph_db)
        stale = graph.execute(
            "SELECT 1 FROM entity_relationships WHERE relationship_id=?",
            (f"wiki-reference:{npc_mapping['mapping_id']}",),
        ).fetchone()
        assert stale is None, stale
        graph.close()

        tables = provider_tables()
        assert "reference_wiki_claims" in tables
        assert "reference_wiki_mappings" in tables
        assert "reference_wiki_mapping_reviews" in tables

        template = (Path(__file__).resolve().parents[1] / "gui" / "templates" / "wiki.html").read_text(encoding="utf-8")
        assert "Evidence mapping ledger" in template
        assert "Build / refresh evidence map" in template
        assert "confirm identity" in template
        assert "{% block shell_mode %}dense{% endblock %}" in template
        assert "wiki-section" in template
        assert "wiki-kpis" in template
        assert "Export handoff packet" in template

    print("Wiki evidence mapping regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
