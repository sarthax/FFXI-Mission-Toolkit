#!/usr/bin/env python3
"""Regression coverage for bounded ResearchSession run/replay orchestration."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.core import graph
from workbench.core.schema import Feature
from workbench.research.providers.base import ProviderResponse
from workbench.research.runtime import ResearchExecutionError, execute_session
from workbench.research.session import ResearchSessionStore


class FixtureProvider:
    provider_id="fixture"

    def __init__(self):
        self.calls=0

    def chat(self,messages,*,model,temperature=0.1,timeout=120.0):
        self.calls+=1
        if self.calls==1:
            return ProviderResponse(
                '{"tool":"graph.search","args":{"query":"Fixture feature"}}',
                {"prompt_tokens":5},
                {"model":model},
            )
        return ProviderResponse(
            "Draft replay-safe report citing the typed graph result.",
            {"completion_tokens":8},
            {"model":model},
        )


def main() -> int:
    with TemporaryDirectory() as td:
        db=Path(td)/"workbench.db"
        con=graph.init_db(db)
        graph.insert_record(con,Feature(
            "feature:fixture","Fixture feature","MISSION","fixture","src","dst"
        ))
        con.commit()
        con.close()

        store=ResearchSessionStore(db)
        session=store.create(
            research_session_id="research:runtime",
            question="Find the fixture feature.",
            provider="openwebui",
            model="original-model",
            budgets={"max_tool_calls":3},
            replay_metadata={"created_from":"fixture"},
        )

        first=execute_session(
            db,
            session.research_session_id,
            provider_id="ollama",
            model="run-model",
            max_tool_calls=2,
            max_provider_calls=4,
            timeout=45.0,
            temperature=0.2,
            provider_base_url="http://fixture-ollama",
            provider_override=FixtureProvider(),
        )
        assert first["replay"] is False,first
        assert first["research_session_id"]=="research:runtime",first
        assert first["provider_calls"]==2,first
        assert first["tool_calls"]==1,first

        loaded=store.get("research:runtime")
        assert loaded["provider"]=="ollama",loaded
        assert loaded["model"]=="run-model",loaded
        assert loaded["budgets"]["max_tool_calls"]==2,loaded
        assert loaded["replay_metadata"]["run_controls"]["timeout"]==45.0,loaded
        assert loaded["replay_metadata"]["run_controls"]["max_provider_calls"]==4,loaded
        assert len(loaded["tool_calls"])==1,loaded
        assert loaded["tool_calls"][0]["tool_name"]=="graph.search",loaded
        assert "Draft replay-safe report" in loaded["final_report"],loaded

        try:
            execute_session(
                db,
                "research:runtime",
                provider_id="ollama",
                model="run-model",
                max_tool_calls=2,
                max_provider_calls=4,
                timeout=45.0,
                temperature=0.2,
                provider_override=FixtureProvider(),
            )
        except ResearchExecutionError as ex:
            assert "already run" in str(ex),ex
        else:
            raise AssertionError("already-run session must require Replay")

        replay=execute_session(
            db,
            "research:runtime",
            provider_id="openwebui",
            model="replay-model",
            max_tool_calls=1,
            max_provider_calls=3,
            timeout=30.0,
            temperature=0.0,
            provider_base_url="http://fixture-webui",
            replay=True,
            provider_override=FixtureProvider(),
        )
        assert replay["replay"] is True,replay
        assert replay["research_session_id"]!="research:runtime",replay
        child=store.get(replay["research_session_id"])
        assert child["replay_metadata"]["replay_of"]=="research:runtime",child
        assert child["provider"]=="openwebui",child
        assert child["model"]=="replay-model",child
        assert child["budgets"]["max_tool_calls"]==1,child
        assert len(child["tool_calls"])==1,child

        original=store.get("research:runtime")
        assert len(original["tool_calls"])==1,original
        assert original["model"]=="run-model",original

        try:
            execute_session(
                db,
                "research:runtime",
                provider_id="ollama",
                model="x",
                max_tool_calls=101,
                max_provider_calls=1,
                timeout=1.0,
                temperature=0.0,
                replay=True,
                provider_override=FixtureProvider(),
            )
        except ResearchExecutionError as ex:
            assert "Max tool calls" in str(ex),ex
        else:
            raise AssertionError("invalid run controls must fail before replay")

    print("research session runtime self-test: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
