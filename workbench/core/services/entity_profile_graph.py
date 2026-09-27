"""Bridge legacy entity_profile provenance into the canonical Workbench graph."""
from __future__ import annotations

import hashlib
import sqlite3
from collections import defaultdict
from pathlib import Path

from workbench.core import graph
from workbench.core.schema import AnalysisResult, Evidence, Finding


CONFIDENCE_BY_SOURCE={
    "client_dat":"VERIFIED",
    "topaz_sql":"VERIFIED",
    "topaz_lua":"VERIFIED",
    "capture":"VERIFIED",
    "packet_decode":"VERIFIED",
    "wiki":"INFERRED",
    "derived":"INFERRED",
}


def _evidence_type(source: str) -> str:
    return {
        "client_dat":"CLIENT_SOURCE",
        "topaz_sql":"SERVER_SOURCE",
        "topaz_lua":"SERVER_SOURCE",
        "capture":"CAPTURE",
        "packet_decode":"CAPTURE",
        "wiki":"REFERENCE",
        "derived":"DERIVED",
    }.get(source,"OTHER")


def _entity_node(con: sqlite3.Connection, npcid: int) -> str:
    hits=con.execute(
        "SELECT DISTINCT entity_id FROM entity_identifiers "
        "WHERE identifier_type IN ('npcid','entity_id') AND identifier_value=?",
        (str(npcid),),
    ).fetchall()
    if len(hits)==1:
        return hits[0][0]

    node=f"entity:npcid:{npcid}"
    con.execute(
        "INSERT OR IGNORE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
        (node,"NPC",str(npcid),'{"identity_source":"entity_profile"}'),
    )
    con.execute(
        "INSERT OR IGNORE INTO entity_identifiers(entity_id,identifier_type,identifier_value) VALUES(?,?,?)",
        (node,"npcid",str(npcid)),
    )
    return node


def import_entity_profile_provenance(
    profile_db: Path,
    graph_db: Path,
    npcid: int,
) -> dict:
    src=sqlite3.connect(profile_db)
    dst=graph.init_db(graph_db)
    try:
        exists=src.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='field_sources'"
        ).fetchone()
        if not exists:
            return {"status":"NO_FIELD_SOURCES","npcid":npcid,"findings":0,"conflicts":0}

        rows=src.execute(
            "SELECT field_name,source,value,confidence FROM field_sources "
            "WHERE entity_type='npc' AND entity_id=? ORDER BY field_name,source",
            (npcid,),
        ).fetchall()
        node=_entity_node(dst,npcid)
        analysis_id=f"entity-profile:{npcid}"
        finding_ids=[]
        grouped=defaultdict(list)

        for field_name,source,value,legacy_confidence in rows:
            digest=hashlib.sha256(
                f"{npcid}|{field_name}|{source}|{value}".encode("utf-8")
            ).hexdigest()[:16]
            evidence_id=f"evidence:entity-profile:{digest}"
            finding_id=f"finding:entity-profile:{digest}"
            graph.insert_record(dst,Evidence(
                evidence_id,
                _evidence_type(source),
                source,
                location=f"field_sources:npc:{npcid}:{field_name}",
                notes=legacy_confidence,
            ))
            graph.insert_record(dst,Finding(
                finding_id,
                analysis_id,
                node,
                field_name,
                value=value,
                status="DISCOVERED",
                confidence=CONFIDENCE_BY_SOURCE.get(source,"UNKNOWN"),
                evidence_id=evidence_id,
                notes=[f"Imported from entity_profile field_sources source={source}."],
            ))
            finding_ids.append(finding_id)
            grouped[field_name].append((source,value))

        conflict_count=0
        for field_name,values in grouped.items():
            distinct={value for _source,value in values}
            if len(distinct)<=1:
                continue
            conflict_count+=1
            digest=hashlib.sha256(
                f"{npcid}|conflict|{field_name}".encode("utf-8")
            ).hexdigest()[:16]
            finding_id=f"finding:entity-profile-conflict:{digest}"
            graph.insert_record(dst,Finding(
                finding_id,
                analysis_id,
                node,
                field_name,
                value={"sources":[{"source":source,"value":value} for source,value in values]},
                status="CONTRADICTED",
                confidence="VERIFIED",
                notes=["Multiple independent entity_profile sources disagree on this field."],
            ))
            finding_ids.append(finding_id)

        graph.insert_record(dst,AnalysisResult(
            analysis_id,
            "ENTITY_PROFILE_PROVENANCE",
            str(profile_db),
            status="ANALYZED",
            findings=finding_ids,
            notes=["Legacy entity_profile field provenance imported without changing source confidence semantics."],
        ))
        dst.commit()
        return {
            "status":"OK",
            "npcid":npcid,
            "entity_node":node,
            "findings":len(finding_ids),
            "conflicts":conflict_count,
        }
    finally:
        src.close()
        dst.close()
