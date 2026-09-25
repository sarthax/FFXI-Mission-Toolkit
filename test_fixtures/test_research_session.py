#!/usr/bin/env python3
import tempfile
from pathlib import Path

from workbench.research import ResearchSessionStore


def main():
    with tempfile.TemporaryDirectory() as td:
        db=Path(td)/"workbench.db"
        store=ResearchSessionStore(db)
        session=store.create(
            research_session_id="research:test",
            question="How is Ancient Vows represented across forks?",
            provider="fixture",
            model="fixture-model",
            source_snapshot_id="lsb:test",
            target_snapshot_id="dsp:test",
            feature_root="feature:cop:ancient_vows",
            budgets={"max_tool_calls":8},
            replay_metadata={"fixture":"research-session"},
        )
        assert session.permission_profile=="READ_ONLY_RESEARCH"

        store.append_tool_call(
            session.research_session_id,
            tool_name="graph.trace",
            args={"root":"feature:cop:ancient_vows"},
            result={"nodes":["feature:cop:ancient_vows"]},
            evidence_ids=["evidence:test:1"],
        )
        try:
            store.add_proposal(
                session.research_session_id,
                proposal_type="FindingProposal",
                payload={"field":"status","value":"implemented"},
            )
        except PermissionError:
            pass
        else:
            raise AssertionError("READ_ONLY_RESEARCH must not create proposals")

        store.finalize(
            session.research_session_id,
            final_report="Draft report",
            verification_state="DRAFT",
            usage={"tool_calls":1},
        )
        loaded=store.get(session.research_session_id)
        assert loaded is not None
        assert loaded["source_snapshot_id"]=="lsb:test",loaded
        assert loaded["target_snapshot_id"]=="dsp:test",loaded
        assert loaded["tool_calls"][0]["tool_name"]=="graph.trace",loaded
        assert loaded["tool_calls"][0]["evidence_ids"]==["evidence:test:1"],loaded
        assert loaded["proposals"]==[],loaded

        propose=store.create(
            research_session_id="research:propose",
            question="Propose a migration action",
            provider="fixture",
            model="fixture-model",
            permission_profile="PROPOSE_CHANGES",
        )
        pid=store.add_proposal(
            propose.research_session_id,
            proposal_type="MigrationActionProposal",
            subject_id="feature:test",
            payload={"action":"MANUAL_REVIEW"},
            supporting_evidence_ids=["evidence:test:2"],
            verification_requirement="Human or deterministic migration verification.",
        )
        loaded=store.get(propose.research_session_id)
        assert loaded["proposals"][0]["proposal_id"]==pid,loaded
        assert loaded["proposals"][0]["status"]=="PROPOSED",loaded

    print("research session persistence self-test: PASS")


if __name__=="__main__":
    main()
