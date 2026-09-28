"""Bridge claim-level wiki reference evidence into the canonical Workbench graph."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from workbench.core import graph as workbench_graph

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
    src.row_factory = sqlite3.Row
    dst = workbench_graph.init_db(graph_db)
    counts = {"claims": 0, "mapped_edges": 0, "ambiguous_edges": 0, "unmapped_claims": 0}
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

        query = f"""
            SELECT c.claim_id,c.source_id,c.page_id,c.page_title,c.page_url,c.revision_id,
                   c.revision_timestamp,c.section_title,c.claim_type,c.subject_text,c.excerpt,
                   c.source_locator,c.authority,c.content_hash,
                   m.mapping_id,m.target_domain,m.target_table,m.target_key,m.target_label,
                   m.mapping_method,m.mapping_status,m.confidence,m.details_json
            FROM reference_wiki_claims c
            LEFT JOIN reference_wiki_mappings m ON m.claim_id=c.claim_id
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
            if status is None or status in {"UNMAPPED", "UNRESOLVED"}:
                counts["unmapped_claims"] += 1
                continue
            if not row["target_table"] or not row["target_key"]:
                continue
            target = _target_node(dst, row["target_table"], row["target_key"], row["target_label"])
            evidence_id = f"evidence:{claim_id}"
            relationship = "MENTIONS" if status == "MAPPED" else "MAY_MENTION"
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

        dst.commit()
        return {"status": "OK", "counts": counts}
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
