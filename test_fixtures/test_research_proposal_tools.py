#!/usr/bin/env python3
import tempfile
from pathlib import Path

from workbench.core import graph
from workbench.core.schema import Evidence, Feature
from workbench.research import ResearchSessionStore
from workbench.research.proposal_tools import ProposalResearchService
from workbench.research.proposal_verifier import ProposalVerifier
from workbench.research.tools import ResearchToolRegistry, register_proposal_tools


def main():
    with tempfile.TemporaryDirectory() as td:
        db=Path(td)/"workbench.db"
        con=graph.init_db(db)
        graph.insert_record(con,Evidence(
            "evidence:test","SERVER_SOURCE","fixture","server.cpp:1","src","support"
        ))
        graph.insert_record(con,Feature(
            "feature:test","Test Feature","MISSION","test","src","dst"
        ))
        con.commit(); con.close()

        store=ResearchSessionStore(db)
        proposer=store.create(
            research_session_id="research:proposer",
            question="Propose a finding.",
            provider="fixture",
            model="fixture",
            permission_profile="PROPOSE_CHANGES",
        )
        validator=store.create(
            research_session_id="research:validator",
            question="Validate proposals.",
            provider="fixture",
            model="fixture",
            permission_profile="VALIDATION_ORCHESTRATOR",
        )

        service=ProposalResearchService(store,ProposalVerifier(db,store))
        registry=ResearchToolRegistry()
        register_proposal_tools(registry,service)

        created=registry.call(
            "proposal.create",
            {
                "research_session_id":proposer.research_session_id,
                "proposal_id":"proposal:test",
                "proposal_type":"FindingProposal",
                "subject_id":"feature:test",
                "payload":{"field":"status","value":"present","confidence":"VERIFIED"},
                "supporting_evidence_ids":["evidence:test"],
            },
            permission_profile="PROPOSE_CHANGES",
            session_store=store,
            research_session_id=proposer.research_session_id,
        )
        assert created["status"]=="PROPOSED",created

        denied=registry.call(
            "proposal.promote",
            {"proposal_id":"proposal:test"},
            permission_profile="PROPOSE_CHANGES",
            session_store=store,
            research_session_id=proposer.research_session_id,
        )
        assert denied["status"]=="DENIED",denied

        checked=registry.call(
            "proposal.verify",
            {"proposal_id":"proposal:test"},
            permission_profile="VALIDATION_ORCHESTRATOR",
            session_store=store,
            research_session_id=validator.research_session_id,
        )
        assert checked["status"]=="VERIFIED",checked

        promoted=registry.call(
            "proposal.promote",
            {"proposal_id":"proposal:test"},
            permission_profile="VALIDATION_ORCHESTRATOR",
            session_store=store,
            research_session_id=validator.research_session_id,
        )
        assert promoted["status"]=="PROMOTED",promoted

        status=registry.call(
            "proposal.status",
            {"proposal_id":"proposal:test"},
            permission_profile="READ_ONLY_RESEARCH",
        )
        assert status["proposal_status"]=="PROMOTED",status

        specs={row["name"]:row for row in registry.specs()}
        assert specs["proposal.create"]["access"]=="PROPOSE",specs
        assert specs["proposal.verify"]["access"]=="VALIDATE",specs
        assert specs["proposal.promote"]["access"]=="VALIDATE",specs
        assert specs["proposal.status"]["access"]=="READ",specs

    print("proposal research tool permissions self-test: PASS")


if __name__=="__main__":
    main()
