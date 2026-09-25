#!/usr/bin/env python3
import sqlite3
import tempfile
from pathlib import Path

from workbench.core import graph
from workbench.core.schema import Evidence, Feature, ValidationRun
from workbench.research import ResearchSessionStore
from workbench.research.proposal_verifier import ProposalVerifier


def main():
    with tempfile.TemporaryDirectory() as td:
        db=Path(td)/"workbench.db"
        con=graph.init_db(db)
        graph.insert_record(con,Evidence(
            "evidence:support","SERVER_SOURCE","fixture","server.cpp:1","src","support"
        ))
        graph.insert_record(con,Evidence(
            "evidence:contradict","CAPTURE","fixture","capture:1","cap","contradiction"
        ))
        graph.insert_record(con,Feature(
            "feature:test","Test Feature","MISSION","test","src","dst"
        ))
        con.execute(
            "INSERT INTO migrations(migration_id,feature_id,source_snapshot_id,target_snapshot_id,status,metadata_json) "
            "VALUES(?,?,?,?,?,?)",
            ("migration:test","feature:test","src","dst","MANUAL_REQUIRED","{}"),
        )
        graph.insert_record(con,ValidationRun(
            "run:test","test run","src","dst","feature:test","UNKNOWN"
        ))
        con.commit(); con.close()

        store=ResearchSessionStore(db)
        session=store.create(
            research_session_id="research:proposals",
            question="Propose verified changes.",
            provider="fixture",
            model="fixture",
            permission_profile="PROPOSE_CHANGES",
        )

        finding_id=store.add_proposal(
            session.research_session_id,
            proposal_id="proposal:finding",
            proposal_type="FindingProposal",
            subject_id="feature:test",
            payload={"field":"implementation_status","value":"present","confidence":"VERIFIED"},
            supporting_evidence_ids=["evidence:support"],
        )
        verifier=ProposalVerifier(db,store)
        checked=verifier.verify(finding_id)
        assert checked["status"]=="VERIFIED",checked
        assert checked["promotable"] is True,checked
        promoted=verifier.verify(finding_id,promote=True)
        assert promoted["status"]=="PROMOTED",promoted

        con=sqlite3.connect(db)
        assert con.execute(
            "SELECT status,confidence FROM findings WHERE finding_id=?",
            (promoted["promoted_record_id"],),
        ).fetchone()==("VERIFIED","VERIFIED")
        con.close()

        migration_id=store.add_proposal(
            session.research_session_id,
            proposal_id="proposal:migration",
            proposal_type="MigrationActionProposal",
            subject_id="feature:test",
            payload={
                "migration_id":"migration:test",
                "action":"MANUAL_REVIEW",
                "reason":"fixture",
            },
            supporting_evidence_ids=["evidence:support"],
        )
        migration=verifier.verify(migration_id,promote=True)
        assert migration["status"]=="PROMOTED",migration

        validation_id=store.add_proposal(
            session.research_session_id,
            proposal_id="proposal:validation",
            proposal_type="ValidationResultProposal",
            subject_id="feature:test",
            payload={
                "run_id":"run:test",
                "validation_type":"REFERENCE_CHECK",
                "subject_id":"feature:test",
                "status":"VERIFIED",
            },
            supporting_evidence_ids=["evidence:support"],
        )
        validation=verifier.verify(validation_id,promote=True)
        assert validation["status"]=="PROMOTED",validation

        contradicted_id=store.add_proposal(
            session.research_session_id,
            proposal_id="proposal:contradicted",
            proposal_type="FindingProposal",
            subject_id="feature:test",
            payload={"field":"status","value":"present"},
            supporting_evidence_ids=["evidence:support"],
            contradicting_evidence_ids=["evidence:contradict"],
        )
        contradicted=verifier.verify(contradicted_id,promote=True)
        assert contradicted["status"]=="CONTRADICTED",contradicted
        assert contradicted["promoted_record_id"] is None,contradicted

        missing_id=store.add_proposal(
            session.research_session_id,
            proposal_id="proposal:missing-evidence",
            proposal_type="FindingProposal",
            subject_id="feature:test",
            payload={"field":"status","value":"present"},
            supporting_evidence_ids=["evidence:missing"],
        )
        missing=verifier.verify(missing_id,promote=True)
        assert missing["status"]=="FAILED",missing
        assert missing["promoted_record_id"] is None,missing

    print("research proposal verification self-test: PASS")


if __name__=="__main__":
    main()
