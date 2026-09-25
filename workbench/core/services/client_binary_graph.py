"""Canonical graph ingestion for client binary indexes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from workbench.core import graph
from workbench.core.schema import AnalysisResult, Artifact, Evidence, Finding


def _safe_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def ingest_client_binary_index(
    payload: dict[str,Any],
    graph_db: Path,
    *,
    source_snapshot_id: str | None = None,
) -> dict[str,Any]:
    binary=dict(payload.get("binary") or {})
    sha256=str(binary.get("sha256") or "")
    if not sha256:
        raise ValueError("client binary index is missing binary.sha256")

    artifact_id=f"artifact:client-binary:{sha256[:24]}"
    analysis_id=f"analysis:client-binary:{sha256[:24]}"
    snapshot=source_snapshot_id or binary.get("client_build") or f"client-binary:{sha256[:16]}"
    evidence_ids=[]
    finding_ids=[]

    con=graph.init_db(Path(graph_db))
    try:
        graph.insert_record(con,Artifact(
            artifact_id=artifact_id,
            artifact_type="CLIENT_BINARY",
            path=binary.get("path"),
            source_snapshot_id=snapshot,
            metadata={
                "filename":binary.get("filename"),
                "label":binary.get("label"),
                "client_build":binary.get("client_build"),
                "sha256":sha256,
                "file_size":binary.get("file_size"),
                "pe_kind":binary.get("pe_kind"),
                "machine":binary.get("machine"),
                "image_base":binary.get("image_base"),
                "entry_point_rva":binary.get("entry_point_rva"),
            },
        ))

        header_evidence=f"evidence:client-binary:{sha256[:24]}:pe"
        graph.insert_record(con,Evidence(
            header_evidence,
            "CLIENT_SOURCE",
            binary.get("filename") or "client-binary",
            location=binary.get("path"),
            snapshot=snapshot,
            notes="Static PE/COFF header and hash evidence.",
        ))
        evidence_ids.append(header_evidence)

        for field in (
            "sha256","file_size","client_build","pe_kind","machine","timestamp",
            "subsystem","image_base","entry_point_rva","size_of_image",
        ):
            finding_id=f"finding:client-binary:{sha256[:16]}:{field}"
            graph.insert_record(con,Finding(
                finding_id,
                analysis_id,
                artifact_id,
                field,
                binary.get(field),
                "VERIFIED",
                "VERIFIED",
                header_evidence,
                snapshot,
                notes=["Deterministically extracted from the indexed binary or caller-supplied snapshot label."],
            ))
            finding_ids.append(finding_id)

        for section in payload.get("sections",[]):
            token=_safe_id(json.dumps(section,sort_keys=True))
            eid=f"evidence:client-binary-section:{token}"
            fid=f"finding:client-binary-section:{token}"
            graph.insert_record(con,Evidence(
                eid,"CLIENT_SOURCE",binary.get("filename") or "client-binary",
                location=f"section:{section.get('name')}",snapshot=snapshot,
                notes="PE section table evidence.",
            ))
            graph.insert_record(con,Finding(
                fid,analysis_id,artifact_id,"section",section,
                "VERIFIED","VERIFIED",eid,snapshot,
            ))
            evidence_ids.append(eid); finding_ids.append(fid)

        for category in ("imports","exports"):
            for row in payload.get(category,[]):
                token=_safe_id(category+json.dumps(row,sort_keys=True))
                eid=f"evidence:client-binary-{category[:-1]}:{token}"
                fid=f"finding:client-binary-{category[:-1]}:{token}"
                graph.insert_record(con,Evidence(
                    eid,"CLIENT_SOURCE",binary.get("filename") or "client-binary",
                    location=f"{category}:{row.get('dll') or row.get('name') or row.get('ordinal')}",
                    snapshot=snapshot,
                    notes=f"Static PE {category[:-1]} table evidence.",
                ))
                graph.insert_record(con,Finding(
                    fid,analysis_id,artifact_id,category[:-1],row,
                    "VERIFIED","VERIFIED",eid,snapshot,
                ))
                evidence_ids.append(eid); finding_ids.append(fid)

        graph.insert_record(con,AnalysisResult(
            analysis_id,
            "CLIENT_BINARY_STATIC_INDEX",
            binary.get("path") or binary.get("filename") or "client-binary",
            status="ANALYZED",
            findings=finding_ids,
            notes=[
                "Static PE metadata/import/export index ingested into canonical Workbench evidence.",
                f"String corpus remains in the binary index file for bounded search; strings are not bulk-promoted to canonical findings.",
            ],
            source_snapshot_id=snapshot,
        ))
        con.commit()
        return {
            "status":"OK",
            "artifact_id":artifact_id,
            "analysis_id":analysis_id,
            "source_snapshot_id":snapshot,
            "evidence_ids":sorted(set(evidence_ids)),
            "finding_count":len(finding_ids),
        }
    finally:
        con.close()
