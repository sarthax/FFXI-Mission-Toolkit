"""Bridge claim-level wiki reference evidence into the canonical Workbench graph."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from workbench.core import graph as workbench_graph
import wiki_evidence
import wiki_claim_compare

_TARGET_IDENTIFIERS = {
    "npc_names": ("npcid", "NPC"),
    "zones": ("zoneid", "ZONE"),
    "key_items": ("keyitem_id", "KEY_ITEM"),
    "items_ours": ("itemid", "ITEM"),
    "sql_item_basic": ("itemid", "ITEM"),
    "topaz_item_basic": ("itemid", "ITEM"),
    "lsb_item_basic": ("itemid", "ITEM"),
}


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _target_node(
    con: sqlite3.Connection,
    target_table: str,
    target_key: str,
    target_label: str | None,
) -> str:
    identifier_type, entity_type = _TARGET_IDENTIFIERS.get(
        target_table, (f"{target_table}_id", "REFERENCE_TARGET")
    )
    hits = con.execute(
        """SELECT DISTINCT entity_id FROM entity_identifiers
           WHERE identifier_type=? AND identifier_value=?""",
        (identifier_type, str(target_key)),
    ).fetchall()
    if len(hits) == 1:
        return hits[0][0]
    node = f"entity:{identifier_type}:{target_key}"
    con.execute(
        """INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json)
           VALUES(?,?,?,?)""",
        (
            node,
            entity_type,
            target_label or str(target_key),
            json.dumps({"identity_source": "wiki_reference_mapping", "target_table": target_table}),
        ),
    )
    con.execute(
        """INSERT OR IGNORE INTO entity_identifiers(entity_id,identifier_type,identifier_value)
           VALUES(?,?,?)""",
        (node, identifier_type, str(target_key)),
    )
    return node


def import_wiki_evidence(
    source_db: Path,
    graph_db: Path,
    *,
    source_id: str | None = None,
    page_id: str | None = None,
) -> dict:
    src = sqlite3.connect(source_db)
    wiki_evidence.init_db(src)
    src.row_factory = sqlite3.Row
    dst = workbench_graph.init_db(graph_db)
    counts = {
        "claims": 0, "mapped_edges": 0, "ambiguous_edges": 0, "unmapped_claims": 0,
        "relations": 0, "relation_edges": 0, "unresolved_relations": 0,
    }
    try:
        if not _table_exists(src, "reference_wiki_claims"):
            return {"status": "NO_WIKI_CLAIMS", "counts": counts}

        where = []
        args = []
        if source_id:
            where.append("c.source_id=?")
            args.append(source_id)
        if page_id:
            where.append("c.page_id=?")
            args.append(str(page_id))
        clause = (" WHERE " + " AND ".join(where)) if where else ""

        mapping_ids_query = """
            SELECT m.mapping_id
            FROM reference_wiki_mappings m
            JOIN reference_wiki_claims c ON c.claim_id=m.claim_id
        """
        cleanup_where = []
        cleanup_args = []
        if source_id:
            cleanup_where.append("c.source_id=?")
            cleanup_args.append(source_id)
        if page_id:
            cleanup_where.append("c.page_id=?")
            cleanup_args.append(str(page_id))
        if cleanup_where:
            mapping_ids_query += " WHERE " + " AND ".join(cleanup_where)
        current_mapping_ids = [
            row[0] for row in src.execute(mapping_ids_query, tuple(cleanup_args)).fetchall()
        ]
        for mapping_id in current_mapping_ids:
            dst.execute(
                "DELETE FROM entity_relationships WHERE relationship_id=?",
                (f"wiki-reference:{mapping_id}",),
            )

        query = f"""
            SELECT c.claim_id,c.source_id,c.page_id,c.page_title,c.page_url,c.revision_id,
                   c.revision_timestamp,c.section_title,c.claim_type,c.subject_text,c.excerpt,
                   c.source_locator,c.authority,c.content_hash,
                   m.mapping_id,m.target_domain,m.target_table,m.target_key,m.target_label,
                   m.mapping_method,m.mapping_status,m.confidence,m.details_json,
                   COALESCE(r.review_status,'UNREVIEWED') AS review_status,r.notes AS review_notes
            FROM reference_wiki_claims c
            LEFT JOIN reference_wiki_mappings m ON m.claim_id=c.claim_id
            LEFT JOIN reference_wiki_mapping_reviews r ON r.mapping_id=m.mapping_id
            {clause}
            ORDER BY c.claim_id,m.mapping_id
        """
        seen_claims = set()
        for row in src.execute(query, tuple(args)):
            claim_id = row["claim_id"]
            claim_node = f"reference-claim:{claim_id}"
            if claim_id not in seen_claims:
                seen_claims.add(claim_id)
                counts["claims"] += 1
                metadata = {
                    "source_id": row["source_id"],
                    "page_id": row["page_id"],
                    "page_title": row["page_title"],
                    "page_url": row["page_url"],
                    "revision_id": row["revision_id"],
                    "revision_timestamp": row["revision_timestamp"],
                    "section_title": row["section_title"],
                    "claim_type": row["claim_type"],
                    "subject_text": row["subject_text"],
                    "source_locator": row["source_locator"],
                    "authority": row["authority"],
                    "content_hash": row["content_hash"],
                }
                dst.execute(
                    """INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json)
                       VALUES(?,?,?,?)""",
                    (claim_node, "REFERENCE_CLAIM", row["excerpt"][:180], json.dumps(metadata, sort_keys=True)),
                )
                evidence_id = f"evidence:{claim_id}"
                dst.execute(
                    "INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
                    (
                        evidence_id,
                        "REFERENCE",
                        row["source_id"],
                        f"{row['page_title']}#{row['section_title'] or ''}",
                        row["revision_id"],
                        row["excerpt"],
                    ),
                )

            status = row["mapping_status"]
            review_status = row["review_status"] or "UNREVIEWED"
            if review_status == "REJECTED":
                continue
            if status is None or status in {"UNMAPPED", "UNRESOLVED"}:
                counts["unmapped_claims"] += 1
                continue
            if not row["target_table"] or not row["target_key"]:
                continue
            target = _target_node(dst, row["target_table"], row["target_key"], row["target_label"])
            evidence_id = f"evidence:{claim_id}"
            relationship = "MENTIONS" if status == "MAPPED" else "MAY_MENTION"
            if review_status == "CONFIRMED":
                relationship = "MENTIONS"
                confidence = "VERIFIED"
            else:
                confidence = "INFERRED" if status == "MAPPED" else "UNKNOWN"
            dst.execute(
                """INSERT OR REPLACE INTO entity_relationships
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    f"wiki-reference:{row['mapping_id']}",
                    claim_node,
                    target,
                    relationship,
                    evidence_id,
                    confidence,
                    "DISCOVERED",
                    json.dumps({
                        "mapping_method": row["mapping_method"],
                        "mapping_status": status,
                        "mapping_confidence": row["confidence"],
                        "review_status": review_status,
                        "review_notes": row["review_notes"],
                        "target_table": row["target_table"],
                        "target_key": row["target_key"],
                        "details": json.loads(row["details_json"] or "{}"),
                        "authority": "REFERENCE_ONLY",
                    }, sort_keys=True),
                    None,
                ),
            )
            if status == "MAPPED":
                counts["mapped_edges"] += 1
            else:
                counts["ambiguous_edges"] += 1

        if _table_exists(src, "reference_wiki_relations"):
            rel_where=[]
            rel_args=[]
            if source_id:
                rel_where.append("source_id=?")
                rel_args.append(source_id)
            if page_id:
                rel_where.append("page_id=?")
                rel_args.append(str(page_id))
            rel_clause=(" WHERE "+" AND ".join(rel_where)) if rel_where else ""
            relations=src.execute(
                f"""SELECT relation_id,source_id,page_id,page_title,page_url,revision_id,
                           revision_timestamp,section_title,relation_type,subject_text,object_text,
                           source_locator,authority,extraction_method,content_hash
                    FROM reference_wiki_relations{rel_clause}
                    ORDER BY relation_id""",
                tuple(rel_args),
            ).fetchall()
            for rel in relations:
                relation_id=rel["relation_id"]
                counts["relations"]+=1
                dst.execute(
                    "DELETE FROM entity_relationships WHERE relationship_id=?",
                    (f"wiki-relation:{relation_id}",),
                )
                mappings=src.execute(
                    """SELECT endpoint,target_domain,target_table,target_key,target_label,mapping_method,
                              mapping_status,confidence,details_json
                       FROM reference_wiki_relation_mappings
                       WHERE relation_id=? ORDER BY endpoint,relation_mapping_id""",
                    (relation_id,),
                ).fetchall()
                endpoints={}
                for mapping in mappings:
                    if mapping["mapping_status"]!="MAPPED" or not mapping["target_table"] or not mapping["target_key"]:
                        continue
                    endpoints.setdefault(mapping["endpoint"],[]).append(mapping)
                if len(endpoints.get("subject",[]))!=1 or len(endpoints.get("object",[]))!=1:
                    counts["unresolved_relations"]+=1
                    continue
                subject_map=endpoints["subject"][0]
                object_map=endpoints["object"][0]
                subject_node=_target_node(
                    dst,subject_map["target_table"],subject_map["target_key"],subject_map["target_label"]
                )
                object_node=_target_node(
                    dst,object_map["target_table"],object_map["target_key"],object_map["target_label"]
                )
                evidence_id=f"evidence:{relation_id}"
                excerpt=f"{rel['subject_text']} {rel['relation_type']} {rel['object_text']}"
                dst.execute(
                    "INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
                    (
                        evidence_id,"REFERENCE",rel["source_id"],
                        f"{rel['page_title']}#{rel['section_title'] or ''}",
                        rel["revision_id"],excerpt,
                    ),
                )
                metadata={
                    "authority":"REFERENCE_ONLY",
                    "source_id":rel["source_id"],
                    "page_id":rel["page_id"],
                    "page_title":rel["page_title"],
                    "page_url":rel["page_url"],
                    "revision_id":rel["revision_id"],
                    "revision_timestamp":rel["revision_timestamp"],
                    "section_title":rel["section_title"],
                    "source_locator":rel["source_locator"],
                    "extraction_method":rel["extraction_method"],
                    "subject_text":rel["subject_text"],
                    "object_text":rel["object_text"],
                    "subject_mapping_method":subject_map["mapping_method"],
                    "object_mapping_method":object_map["mapping_method"],
                }
                dst.execute(
                    """INSERT OR REPLACE INTO entity_relationships
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        f"wiki-relation:{relation_id}",subject_node,object_node,rel["relation_type"],
                        evidence_id,"INFERRED","DISCOVERED",json.dumps(metadata,sort_keys=True),None,
                    ),
                )
                counts["relation_edges"]+=1

        dst.commit()
        return {"status": "OK", "counts": counts}
    finally:
        src.close()
        dst.close()


def import_wiki_alignment(
    source_db: Path,
    graph_db: Path,
    *,
    title: str,
) -> dict:
    src = sqlite3.connect(source_db)
    wiki_claim_compare.init_db(src)
    report = wiki_claim_compare.alignment_report(src, title)
    if report.get("status") != "OK":
        src.close()
        return {"status": report.get("status"), "title": title, "findings": 0}

    dst = workbench_graph.init_db(graph_db)
    try:
        alignment_id = report["page"]["alignment_id"]
        analysis_id = f"analysis:{alignment_id}"
        # Reconcile this alignment's prior findings.
        old = dst.execute(
            "SELECT finding_id FROM findings WHERE analysis_id=?", (analysis_id,)
        ).fetchall()
        for row in old:
            dst.execute("DELETE FROM findings WHERE finding_id=?", (row[0],))
        finding_ids = []

        for pair in report["pairs"]:
            status = pair["status"]
            if status == "REFERENCE_CONFLICT":
                finding_status = "CONTRADICTED"
                confidence = "INFERRED"
            elif status == "AGREEMENT":
                finding_status = "SUPPORTED"
                confidence = "INFERRED"
            else:
                finding_status = "UNKNOWN"
                confidence = "UNKNOWN"

            pair_node = f"reference-alignment:{pair['pair_id']}"
            metadata = {
                "alignment_id": alignment_id,
                "alignment_type": pair["alignment_type"],
                "reference_status": status,
                "conflict_kind": pair["conflict_kind"],
                "similarity": pair["similarity"],
                "bg_claim_id": pair["bg_claim_id"],
                "ffxiclopedia_claim_id": pair["ffxiclopedia_claim_id"],
                "bg_excerpt": pair["bg_excerpt"],
                "ffxiclopedia_excerpt": pair["fx_excerpt"],
                "details": pair["details"],
                "authority": "REFERENCE_ONLY",
            }
            dst.execute(
                """INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json)
                   VALUES(?,?,?,?)""",
                (
                    pair_node,
                    "REFERENCE_ALIGNMENT",
                    f"{pair['alignment_type']} {status}",
                    json.dumps(metadata, sort_keys=True),
                ),
            )

            evid = f"evidence:{pair['pair_id']}"
            note = "Dual-wiki reference comparison; neither source is authoritative."
            dst.execute(
                "INSERT OR REPLACE INTO evidence VALUES(?,?,?,?,?,?)",
                (
                    evid,
                    "REFERENCE",
                    "BGWiki+FFXIclopedia",
                    f"wiki-alignment:{title}:{pair['pair_id']}",
                    None,
                    note,
                ),
            )
            finding_id = f"finding:{pair['pair_id']}"
            dst.execute(
                """INSERT OR REPLACE INTO findings
                   (finding_id,analysis_id,subject_id,field,value_json,status,confidence,
                    evidence_id,source_snapshot_id,created_at,updated_at,notes_json)
                   VALUES(?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,?)""",
                (
                    finding_id,
                    analysis_id,
                    pair_node,
                    "reference_claim_alignment",
                    json.dumps(metadata, sort_keys=True),
                    finding_status,
                    confidence,
                    evid,
                    None,
                    json.dumps([note]),
                ),
            )
            finding_ids.append(finding_id)

        dst.execute(
            """INSERT OR REPLACE INTO analysis_results
               (analysis_id,analysis_type,source,target,feature_id,status,created_at,tool_version,
                findings_json,notes_json,source_snapshot_id)
               VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP,?,?,?,?)""",
            (
                analysis_id,
                "REFERENCE_WIKI_ALIGNMENT",
                "BGWiki",
                "FFXIclopedia",
                None,
                "ANALYZED",
                "1",
                json.dumps(finding_ids),
                json.dumps(["Reference-only dual-source comparison; no winner selected."]),
                None,
            ),
        )
        dst.commit()
        return {
            "status": "OK",
            "alignment_id": alignment_id,
            "findings": len(finding_ids),
            "conflicts": sum(1 for p in report["pairs"] if p["status"] == "REFERENCE_CONFLICT"),
            "agreements": sum(1 for p in report["pairs"] if p["status"] == "AGREEMENT"),
        }
    finally:
        src.close()
        dst.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path("ffxi_zone_database.db"))
    ap.add_argument("--graph-db", type=Path, default=Path("workbench.db"))
    ap.add_argument("--source")
    ap.add_argument("--page-id")
    args = ap.parse_args()
    out = import_wiki_evidence(args.db, args.graph_db, source_id=args.source, page_id=args.page_id)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
