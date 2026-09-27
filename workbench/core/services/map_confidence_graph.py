"""Import namespace-map confidence results into the canonical Workbench graph."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterable

from workbench.core import graph
from workbench.core.schema import AnalysisResult, Evidence, Finding


def import_map_confidence_results(
    results: Iterable[dict],
    graph_db: Path,
    *,
    source: str,
    target: str,
    source_snapshot_id: str | None = None,
    target_snapshot_id: str | None = None,
) -> dict:
    con=graph.init_db(graph_db)
    analysis_key=hashlib.sha256(
        f"{source}|{target}|{source_snapshot_id}|{target_snapshot_id}".encode("utf-8")
    ).hexdigest()[:16]
    analysis_id=f"map-confidence:{analysis_key}"
    finding_ids=[]
    confirmed_count=0
    missing_count=0
    try:
        for result in results:
            family=str(result.get("family") or "")
            for state,rows in (("confirmed",result.get("confirmed",[])),("missing",result.get("missing",[]))):
                for key,target_name in rows:
                    source_name=f"tpz.{family}.{key}"
                    node=f"namespace-map:{family}:{key}"
                    con.execute(
                        "INSERT OR REPLACE INTO entities(entity_id,entity_type,display_name,metadata_json) VALUES(?,?,?,?)",
                        (
                            node,
                            "NAMESPACE_MAPPING",
                            source_name,
                            json.dumps({
                                "family":family,
                                "source_identifier":source_name,
                                "target_identifier":target_name,
                                "target_snapshot_id":target_snapshot_id,
                            },sort_keys=True),
                        ),
                    )
                    digest=hashlib.sha256(
                        f"{analysis_id}|{family}|{key}|{target_name}".encode("utf-8")
                    ).hexdigest()[:16]
                    evidence_id=f"evidence:map-confidence:{digest}"
                    finding_id=f"finding:map-confidence:{digest}"
                    is_confirmed=state=="confirmed"
                    graph.insert_record(con,Evidence(
                        evidence_id,
                        "SERVER_SOURCE",
                        "backport_map_confidence_check",
                        location=f"{family}:{key}->{target_name}",
                        snapshot=target_snapshot_id,
                        notes=(
                            "Mapped target identifier exists in indexed DSP source."
                            if is_confirmed else
                            "Mapped target identifier was not found in indexed DSP source."
                        ),
                    ))
                    graph.insert_record(con,Finding(
                        finding_id,
                        analysis_id,
                        node,
                        "target_identifier_presence",
                        value={
                            "source_identifier":source_name,
                            "target_identifier":target_name,
                            "target_snapshot_id":target_snapshot_id,
                        },
                        status="VERIFIED" if is_confirmed else "CONTRADICTED",
                        confidence="INFERRED",
                        evidence_id=evidence_id,
                        source_snapshot_id=source_snapshot_id,
                        notes=[
                            "Identifier-presence evidence only; value/behavior equivalence is not proven.",
                        ],
                    ))
                    finding_ids.append(finding_id)
                    if is_confirmed:
                        confirmed_count+=1
                    else:
                        missing_count+=1

        graph.insert_record(con,AnalysisResult(
            analysis_id,
            "NAMESPACE_MAP_CONFIDENCE",
            source,
            target=target,
            status="ANALYZED",
            findings=finding_ids,
            notes=[
                "Imported namespace-map member presence checks.",
                "Target identifier presence does not prove semantic or numeric-value equivalence.",
            ],
            source_snapshot_id=source_snapshot_id,
        ))
        con.commit()
        return {
            "status":"OK",
            "analysis_id":analysis_id,
            "confirmed":confirmed_count,
            "missing":missing_count,
            "findings":len(finding_ids),
        }
    finally:
        con.close()
