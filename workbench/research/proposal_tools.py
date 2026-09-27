"""Typed proposal staging/status/verification tools with separated authority."""
from __future__ import annotations

from typing import Any

from .proposal_verifier import ProposalVerifier
from .session import ResearchSessionStore


class ProposalResearchService:
    def __init__(self, store: ResearchSessionStore, verifier: ProposalVerifier):
        self.store=store
        self.verifier=verifier

    def create(
        self,
        research_session_id: str,
        proposal_type: str,
        payload: dict[str,Any],
        *,
        subject_id: str | None = None,
        supporting_evidence_ids: list[str] | None = None,
        contradicting_evidence_ids: list[str] | None = None,
        verification_requirement: str | None = None,
        proposal_id: str | None = None,
    ) -> dict[str,Any]:
        try:
            pid=self.store.add_proposal(
                research_session_id,
                proposal_type=proposal_type,
                payload=payload,
                subject_id=subject_id,
                supporting_evidence_ids=supporting_evidence_ids or [],
                contradicting_evidence_ids=contradicting_evidence_ids or [],
                verification_requirement=verification_requirement,
                proposal_id=proposal_id,
            )
        except (KeyError,PermissionError,ValueError) as exc:
            return {"status":"ERROR","error":str(exc)}
        return {
            "status":"PROPOSED",
            "proposal_id":pid,
            "research_session_id":research_session_id,
            "proposal_type":proposal_type,
        }

    def status(self, proposal_id: str) -> dict[str,Any]:
        return self.verifier.status(proposal_id)

    def verify(self, proposal_id: str) -> dict[str,Any]:
        return self.verifier.verify(proposal_id,promote=False)

    def promote(self, proposal_id: str) -> dict[str,Any]:
        return self.verifier.verify(proposal_id,promote=True)
