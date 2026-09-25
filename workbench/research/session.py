"""Persistent, replay-oriented research sessions for the evidence-aware Workbench layer."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import uuid
from typing import Any


PERMISSION_PROFILES = {
    "READ_ONLY_RESEARCH",
    "PROPOSE_CHANGES",
    "VALIDATION_ORCHESTRATOR",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ResearchSession:
    research_session_id: str
    question: str
    provider: str
    model: str
    permission_profile: str = "READ_ONLY_RESEARCH"
    source_snapshot_id: str | None = None
    target_snapshot_id: str | None = None
    feature_root: str | None = None
    entity_root: str | None = None
    verification_state: str = "DRAFT"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    final_report: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    budgets: dict[str, Any] = field(default_factory=dict)
    replay_metadata: dict[str, Any] = field(default_factory=dict)


class ResearchSessionStore:
    def __init__(self, db_path: Path):
        self.db_path=Path(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        con=sqlite3.connect(self.db_path)
        con.row_factory=sqlite3.Row
        return con

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True,exist_ok=True)
        con=self._connect()
        try:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS research_sessions (
                    research_session_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    permission_profile TEXT NOT NULL,
                    source_snapshot_id TEXT,
                    target_snapshot_id TEXT,
                    feature_root TEXT,
                    entity_root TEXT,
                    verification_state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    final_report TEXT,
                    usage_json TEXT NOT NULL,
                    budgets_json TEXT NOT NULL,
                    replay_metadata_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    research_session_id TEXT NOT NULL,
                    sequence_no INTEGER NOT NULL,
                    tool_name TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(research_session_id) REFERENCES research_sessions(research_session_id),
                    UNIQUE(research_session_id, sequence_no)
                );
                CREATE TABLE IF NOT EXISTS research_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    research_session_id TEXT NOT NULL,
                    proposal_type TEXT NOT NULL,
                    subject_id TEXT,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    supporting_evidence_ids_json TEXT NOT NULL,
                    contradicting_evidence_ids_json TEXT NOT NULL,
                    verification_requirement TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(research_session_id) REFERENCES research_sessions(research_session_id)
                );
                CREATE INDEX IF NOT EXISTS idx_research_tool_calls_session
                    ON research_tool_calls(research_session_id, sequence_no);
                CREATE INDEX IF NOT EXISTS idx_research_proposals_session
                    ON research_proposals(research_session_id, proposal_type, status);
            """)
            con.commit()
        finally:
            con.close()

    def create(
        self,
        *,
        question: str,
        provider: str,
        model: str,
        permission_profile: str = "READ_ONLY_RESEARCH",
        source_snapshot_id: str | None = None,
        target_snapshot_id: str | None = None,
        feature_root: str | None = None,
        entity_root: str | None = None,
        budgets: dict[str, Any] | None = None,
        replay_metadata: dict[str, Any] | None = None,
        research_session_id: str | None = None,
    ) -> ResearchSession:
        if permission_profile not in PERMISSION_PROFILES:
            raise ValueError(f"Unsupported research permission profile: {permission_profile}")
        session=ResearchSession(
            research_session_id=research_session_id or f"research:{uuid.uuid4()}",
            question=question,
            provider=provider,
            model=model,
            permission_profile=permission_profile,
            source_snapshot_id=source_snapshot_id,
            target_snapshot_id=target_snapshot_id,
            feature_root=feature_root,
            entity_root=entity_root,
            budgets=dict(budgets or {}),
            replay_metadata=dict(replay_metadata or {}),
        )
        con=self._connect()
        try:
            con.execute(
                "INSERT INTO research_sessions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    session.research_session_id,session.question,session.provider,session.model,
                    session.permission_profile,session.source_snapshot_id,session.target_snapshot_id,
                    session.feature_root,session.entity_root,session.verification_state,
                    session.created_at,session.updated_at,session.final_report,
                    json.dumps(session.usage,sort_keys=True),
                    json.dumps(session.budgets,sort_keys=True),
                    json.dumps(session.replay_metadata,sort_keys=True),
                ),
            )
            con.commit()
        finally:
            con.close()
        return session

    def append_tool_call(
        self,
        research_session_id: str,
        *,
        tool_name: str,
        args: dict[str, Any],
        result: Any,
        status: str = "OK",
        evidence_ids: list[str] | tuple[str, ...] = (),
    ) -> int:
        con=self._connect()
        try:
            exists=con.execute(
                "SELECT 1 FROM research_sessions WHERE research_session_id=?",
                (research_session_id,),
            ).fetchone()
            if not exists:
                raise KeyError(research_session_id)
            next_no=con.execute(
                "SELECT COALESCE(MAX(sequence_no),0)+1 FROM research_tool_calls WHERE research_session_id=?",
                (research_session_id,),
            ).fetchone()[0]
            cur=con.execute(
                "INSERT INTO research_tool_calls "
                "(research_session_id,sequence_no,tool_name,args_json,result_json,status,evidence_ids_json,created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    research_session_id,next_no,tool_name,
                    json.dumps(args,sort_keys=True,default=str),
                    json.dumps(result,sort_keys=True,default=str),
                    status,
                    json.dumps(list(evidence_ids),sort_keys=True),
                    _now(),
                ),
            )
            con.execute(
                "UPDATE research_sessions SET updated_at=? WHERE research_session_id=?",
                (_now(),research_session_id),
            )
            con.commit()
            return int(cur.lastrowid)
        finally:
            con.close()

    def add_proposal(
        self,
        research_session_id: str,
        *,
        proposal_type: str,
        payload: dict[str, Any],
        subject_id: str | None = None,
        supporting_evidence_ids: list[str] | tuple[str, ...] = (),
        contradicting_evidence_ids: list[str] | tuple[str, ...] = (),
        verification_requirement: str | None = None,
        proposal_id: str | None = None,
    ) -> str:
        proposal_id=proposal_id or f"proposal:{uuid.uuid4()}"
        con=self._connect()
        try:
            session=con.execute(
                "SELECT permission_profile FROM research_sessions WHERE research_session_id=?",
                (research_session_id,),
            ).fetchone()
            if not session:
                raise KeyError(research_session_id)
            if session["permission_profile"]=="READ_ONLY_RESEARCH":
                raise PermissionError("READ_ONLY_RESEARCH sessions cannot create change/finding proposals.")
            con.execute(
                "INSERT INTO research_proposals "
                "(proposal_id,research_session_id,proposal_type,subject_id,status,payload_json,"
                "supporting_evidence_ids_json,contradicting_evidence_ids_json,verification_requirement,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    proposal_id,research_session_id,proposal_type,subject_id,"PROPOSED",
                    json.dumps(payload,sort_keys=True,default=str),
                    json.dumps(list(supporting_evidence_ids),sort_keys=True),
                    json.dumps(list(contradicting_evidence_ids),sort_keys=True),
                    verification_requirement,_now(),
                ),
            )
            con.execute(
                "UPDATE research_sessions SET updated_at=? WHERE research_session_id=?",
                (_now(),research_session_id),
            )
            con.commit()
            return proposal_id
        finally:
            con.close()

    def finalize(
        self,
        research_session_id: str,
        *,
        final_report: str,
        verification_state: str = "DRAFT",
        usage: dict[str, Any] | None = None,
    ) -> None:
        con=self._connect()
        try:
            cur=con.execute(
                "UPDATE research_sessions SET final_report=?, verification_state=?, usage_json=?, updated_at=? "
                "WHERE research_session_id=?",
                (
                    final_report,verification_state,json.dumps(dict(usage or {}),sort_keys=True),
                    _now(),research_session_id,
                ),
            )
            if cur.rowcount != 1:
                raise KeyError(research_session_id)
            con.commit()
        finally:
            con.close()

    def get(self, research_session_id: str) -> dict[str, Any] | None:
        con=self._connect()
        try:
            row=con.execute(
                "SELECT * FROM research_sessions WHERE research_session_id=?",
                (research_session_id,),
            ).fetchone()
            if row is None:
                return None
            session=dict(row)
            for key in ("usage_json","budgets_json","replay_metadata_json"):
                session[key.removesuffix("_json")]=json.loads(session.pop(key) or "{}")
            session["tool_calls"]=[
                {
                    **dict(call),
                    "args":json.loads(call["args_json"]),
                    "result":json.loads(call["result_json"]),
                    "evidence_ids":json.loads(call["evidence_ids_json"]),
                }
                for call in con.execute(
                    "SELECT * FROM research_tool_calls WHERE research_session_id=? ORDER BY sequence_no",
                    (research_session_id,),
                ).fetchall()
            ]
            for call in session["tool_calls"]:
                call.pop("args_json",None); call.pop("result_json",None); call.pop("evidence_ids_json",None)
            session["proposals"]=[]
            for proposal in con.execute(
                "SELECT * FROM research_proposals WHERE research_session_id=? ORDER BY created_at,proposal_id",
                (research_session_id,),
            ).fetchall():
                item=dict(proposal)
                item["payload"]=json.loads(item.pop("payload_json"))
                item["supporting_evidence_ids"]=json.loads(item.pop("supporting_evidence_ids_json"))
                item["contradicting_evidence_ids"]=json.loads(item.pop("contradicting_evidence_ids_json"))
                session["proposals"].append(item)
            return session
        finally:
            con.close()
