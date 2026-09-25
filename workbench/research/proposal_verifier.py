"""Deterministic verification and canonical promotion for staged research proposals."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from typing import Any

from workbench.core import graph
from workbench.core.schema import Finding, MigrationAction, ValidationResult
from .session import ResearchSessionStore


ALLOWED_FINDING_CONFIDENCE={"VERIFIED","INFERRED","UNKNOWN"}
ALLOWED_MIGRATION_ACTIONS={
    "COPY","CONVERT","RENUMBER","RESHAPE","GENERATE","MANUAL_REVIEW","NOT_REQUIRED","BLOCK",
}
ALLOWED_VALIDATION_STATUS={"VERIFIED","FAILED","UNKNOWN","MANUAL_REQUIRED","BLOCKED"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ProposalVerification:
    proposal_id: str
    status: str
    promotable: bool
    checks: tuple[dict[str,Any], ...]
    promoted_record_id: str | None = None


class ProposalVerifier:
    """Separate deterministic authority from the model-facing research runner."""

    def __init__(self, db_path: Path, session_store: ResearchSessionStore | None = None):
        self.db_path=Path(db_path)
        self.session_store=session_store or ResearchSessionStore(self.db_path)
        self._ensure_columns()

    def _connect(self) -> sqlite3.Connection:
        con=sqlite3.connect(self.db_path)
        con.row_factory=sqlite3.Row
        return con

    def _ensure_columns(self) -> None:
        con=self._connect()
        try:
            cols={row["name"] for row in con.execute("PRAGMA table_info(research_proposals)")}
            for name,decl in (
                ("verified_at","TEXT"),
                ("verification_json","TEXT"),
                ("promoted_record_id","TEXT"),
            ):
                if name not in cols:
                    con.execute(f"ALTER TABLE research_proposals ADD COLUMN {name} {decl}")
            con.commit()
        finally:
            con.close()

    def _proposal(self, con: sqlite3.Connection, proposal_id: str) -> dict[str,Any] | None:
        row=con.execute(
            "SELECT * FROM research_proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            return None
        item=dict(row)
        item["payload"]=json.loads(item.pop("payload_json"))
        item["supporting_evidence_ids"]=json.loads(item.pop("supporting_evidence_ids_json"))
        item["contradicting_evidence_ids"]=json.loads(item.pop("contradicting_evidence_ids_json"))
        return item

    def _evidence_checks(self, con, proposal) -> tuple[list[dict[str,Any]], bool]:
        checks=[]
        support=list(proposal["supporting_evidence_ids"])
        contradict=list(proposal["contradicting_evidence_ids"])
        all_ids=sorted(set(support+contradict))
        existing=set()
        if all_ids:
            placeholders=",".join("?" for _ in all_ids)
            existing={
                row[0]
                for row in con.execute(
                    f"SELECT evidence_id FROM evidence WHERE evidence_id IN ({placeholders})",
                    tuple(all_ids),
                ).fetchall()
            }
        missing=[eid for eid in all_ids if eid not in existing]
        checks.append({
            "check":"evidence_exists",
            "status":"VERIFIED" if not missing else "FAILED",
            "missing_evidence_ids":missing,
        })
        checks.append({
            "check":"contradicting_evidence",
            "status":"VERIFIED" if not contradict else "CONTRADICTED",
            "contradicting_evidence_ids":contradict,
        })
        checks.append({
            "check":"supporting_evidence",
            "status":"VERIFIED" if support else "FAILED",
            "supporting_evidence_ids":support,
        })
        return checks, (not missing and not contradict and bool(support))

    def verify(self, proposal_id: str, *, promote: bool = False) -> dict[str,Any]:
        con=self._connect()
        try:
            proposal=self._proposal(con,proposal_id)
            if proposal is None:
                return {"status":"ERROR","error":f"Unknown proposal: {proposal_id}"}
            if proposal["status"]=="PROMOTED":
                return {
                    "status":"PROMOTED",
                    "proposal_id":proposal_id,
                    "promoted_record_id":proposal.get("promoted_record_id"),
                    "verification":json.loads(proposal.get("verification_json") or "{}"),
                }

            checks,evidence_ok=self._evidence_checks(con,proposal)
            ptype=proposal["proposal_type"]
            payload=proposal["payload"]
            type_ok=False
            canonical_record=None

            if ptype=="FindingProposal":
                required=("subject_id","field")
                missing=[key for key in required if not (payload.get(key) or proposal.get(key))]
                confidence=str(payload.get("confidence","INFERRED")).upper()
                valid_confidence=confidence in ALLOWED_FINDING_CONFIDENCE
                checks.append({
                    "check":"finding_shape",
                    "status":"VERIFIED" if not missing and valid_confidence else "FAILED",
                    "missing_fields":missing,
                    "confidence":confidence,
                })
                type_ok=not missing and valid_confidence
                if type_ok:
                    canonical_record=Finding(
                        finding_id=str(payload.get("finding_id") or f"finding:{proposal_id}"),
                        analysis_id=str(payload.get("analysis_id") or f"research-analysis:{proposal['research_session_id']}"),
                        subject_id=str(payload.get("subject_id") or proposal.get("subject_id")),
                        field=str(payload["field"]),
                        value=payload.get("value"),
                        status="VERIFIED",
                        confidence=confidence,
                        evidence_id=proposal["supporting_evidence_ids"][0] if len(proposal["supporting_evidence_ids"])==1 else None,
                        source_snapshot_id=payload.get("source_snapshot_id"),
                        notes=list(payload.get("notes",[]))+[
                            "Promoted from deterministic research proposal verification.",
                            "supporting_evidence_ids="+json.dumps(proposal["supporting_evidence_ids"]),
                        ],
                    )

            elif ptype=="MigrationActionProposal":
                migration_id=payload.get("migration_id")
                action=str(payload.get("action") or "").upper()
                parent=con.execute(
                    "SELECT 1 FROM migrations WHERE migration_id=?",
                    (migration_id,),
                ).fetchone() if migration_id else None
                valid_action=action in ALLOWED_MIGRATION_ACTIONS
                checks.append({
                    "check":"migration_action_shape",
                    "status":"VERIFIED" if migration_id and parent and valid_action else "FAILED",
                    "migration_exists":bool(parent),
                    "action":action,
                })
                type_ok=bool(migration_id and parent and valid_action)
                if type_ok:
                    canonical_record=MigrationAction(
                        action_id=str(payload.get("action_id") or f"action:{proposal_id}"),
                        migration_id=str(migration_id),
                        action=action,
                        artifact_id=payload.get("artifact_id"),
                        status=str(payload.get("status") or "MANUAL_REQUIRED"),
                        reason=str(payload.get("reason") or "Verified research proposal"),
                        metadata={
                            **dict(payload.get("metadata") or {}),
                            "proposal_id":proposal_id,
                            "research_session_id":proposal["research_session_id"],
                            "supporting_evidence_ids":proposal["supporting_evidence_ids"],
                        },
                    )

            elif ptype=="ValidationResultProposal":
                run_id=payload.get("run_id")
                validation_type=payload.get("validation_type")
                subject_id=payload.get("subject_id") or proposal.get("subject_id")
                result_status=str(payload.get("status") or "").upper()
                parent=con.execute(
                    "SELECT 1 FROM validation_runs WHERE run_id=?",
                    (run_id,),
                ).fetchone() if run_id else None
                valid_status=result_status in ALLOWED_VALIDATION_STATUS
                checks.append({
                    "check":"validation_result_shape",
                    "status":"VERIFIED" if run_id and parent and validation_type and subject_id and valid_status else "FAILED",
                    "run_exists":bool(parent),
                    "validation_status":result_status,
                })
                type_ok=bool(run_id and parent and validation_type and subject_id and valid_status)
                if type_ok:
                    canonical_record=ValidationResult(
                        validation_id=str(payload.get("validation_id") or f"validation:{proposal_id}"),
                        validation_type=str(validation_type),
                        subject_id=str(subject_id),
                        status=result_status,
                        evidence_id=proposal["supporting_evidence_ids"][0] if len(proposal["supporting_evidence_ids"])==1 else None,
                        source=payload.get("source"),
                        target=payload.get("target"),
                        notes=list(payload.get("notes",[]))+[
                            "Promoted from deterministic research proposal verification.",
                            "supporting_evidence_ids="+json.dumps(proposal["supporting_evidence_ids"]),
                        ],
                        run_id=str(run_id),
                    )
            else:
                checks.append({
                    "check":"proposal_type",
                    "status":"FAILED",
                    "proposal_type":ptype,
                    "error":"Unsupported proposal type",
                })

            promotable=evidence_ok and type_ok
            verify_status=(
                "CONTRADICTED"
                if any(c["status"]=="CONTRADICTED" for c in checks)
                else ("VERIFIED" if promotable else "FAILED")
            )
            promoted_record_id=None

            if promote and promotable and canonical_record is not None:
                graph.insert_record(con,canonical_record)
                if isinstance(canonical_record,Finding):
                    promoted_record_id=canonical_record.finding_id
                elif isinstance(canonical_record,MigrationAction):
                    promoted_record_id=canonical_record.action_id
                else:
                    promoted_record_id=canonical_record.validation_id
                proposal_status="PROMOTED"
            else:
                proposal_status=verify_status

            verification={
                "status":verify_status,
                "promotable":promotable,
                "checks":checks,
                "promote_requested":bool(promote),
            }
            con.execute(
                "UPDATE research_proposals SET status=?,verified_at=?,verification_json=?,promoted_record_id=? "
                "WHERE proposal_id=?",
                (
                    proposal_status,_now(),json.dumps(verification,sort_keys=True),
                    promoted_record_id,proposal_id,
                ),
            )
            con.commit()
            return {
                "status":proposal_status,
                "proposal_id":proposal_id,
                "promotable":promotable,
                "checks":checks,
                "promoted_record_id":promoted_record_id,
            }
        finally:
            con.close()

    def status(self, proposal_id: str) -> dict[str,Any]:
        con=self._connect()
        try:
            proposal=self._proposal(con,proposal_id)
            if proposal is None:
                return {"status":"ERROR","error":f"Unknown proposal: {proposal_id}"}
            return {
                "status":"OK",
                "proposal_id":proposal_id,
                "proposal_status":proposal["status"],
                "proposal_type":proposal["proposal_type"],
                "subject_id":proposal.get("subject_id"),
                "supporting_evidence_ids":proposal["supporting_evidence_ids"],
                "contradicting_evidence_ids":proposal["contradicting_evidence_ids"],
                "verified_at":proposal.get("verified_at"),
                "verification":json.loads(proposal.get("verification_json") or "{}"),
                "promoted_record_id":proposal.get("promoted_record_id"),
            }
        finally:
            con.close()
