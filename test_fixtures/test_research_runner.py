#!/usr/bin/env python3
import tempfile
from pathlib import Path

from workbench.research import ResearchSessionStore
from workbench.research.providers.base import ProviderResponse
from workbench.research.runner import ResearchRunner
from workbench.research.tools import ResearchTool, ResearchToolRegistry


class FixtureProvider:
    provider_id="fixture"

    def __init__(self):
        self.calls=0

    def chat(self,messages,*,model,temperature=0.1,timeout=120.0):
        self.calls+=1
        if self.calls==1:
            return ProviderResponse(
                '{"tool":"graph.trace","args":{"root":"feature:test"}}',
                {"prompt_tokens":10},
            )
        return ProviderResponse(
            "Draft report citing evidence:test:1 and preserving INFERRED state.",
            {"completion_tokens":12},
        )


def main():
    with tempfile.TemporaryDirectory() as td:
        store=ResearchSessionStore(Path(td)/"workbench.db")
        session=store.create(
            research_session_id="research:runner",
            question="Trace this feature.",
            provider="fixture",
            model="fixture-model",
            budgets={"max_tool_calls":2},
        )
        registry=ResearchToolRegistry()
        registry.register(ResearchTool(
            "graph.trace",
            "Trace graph.",
            lambda root:{
                "status":"OK",
                "root":root,
                "edges":[{"confidence":"INFERRED","evidence_id":"evidence:test:1"}],
                "evidence_ids":["evidence:test:1"],
            },
        ))

        out=ResearchRunner(
            provider=FixtureProvider(),
            registry=registry,
            session_store=store,
        ).run(session.research_session_id)

        assert out["status"]=="OK",out
        assert out["tool_calls"]==1,out
        assert "evidence:test:1" in out["final_report"],out

        loaded=store.get(session.research_session_id)
        assert loaded["verification_state"]=="DRAFT",loaded
        assert loaded["usage"]["provider_calls"]==2,loaded
        assert loaded["tool_calls"][0]["evidence_ids"]==["evidence:test:1"],loaded

        exhausted=store.create(
            research_session_id="research:budget",
            question="Try a tool with no budget.",
            provider="fixture",
            model="fixture-model",
            budgets={"max_tool_calls":0},
        )
        provider=FixtureProvider()
        result=ResearchRunner(
            provider=provider,
            registry=registry,
            session_store=store,
        ).run(exhausted.research_session_id)
        assert result["verification_state"]=="INCOMPLETE",result
        assert result["tool_calls"]==0,result

    print("bounded research runner self-test: PASS")


if __name__=="__main__":
    main()
