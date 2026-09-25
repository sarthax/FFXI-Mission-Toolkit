#!/usr/bin/env python3
import tempfile
from pathlib import Path

from workbench.research import ResearchSessionStore
from workbench.research.tools import (
    ACCESS_PROPOSE,
    ACCESS_READ,
    ResearchTool,
    ResearchToolRegistry,
)


def main():
    with tempfile.TemporaryDirectory() as td:
        store=ResearchSessionStore(Path(td)/"workbench.db")
        session=store.create(
            research_session_id="research:tools",
            question="Trace evidence",
            provider="fixture",
            model="fixture",
        )

        registry=ResearchToolRegistry()
        registry.register(ResearchTool(
            "graph.trace",
            "Trace canonical graph evidence.",
            lambda root:{
                "status":"OK",
                "root":root,
                "nodes":[{"id":root,"evidence_id":"evidence:trace:1"}],
            },
            ACCESS_READ,
        ))
        registry.register(ResearchTool(
            "migration.propose",
            "Stage a migration proposal.",
            lambda subject:{"status":"PROPOSED","subject":subject},
            ACCESS_PROPOSE,
        ))

        result=registry.call(
            "graph.trace",
            {"root":"feature:test"},
            permission_profile="READ_ONLY_RESEARCH",
            session_store=store,
            research_session_id=session.research_session_id,
        )
        assert result["status"]=="OK",result

        denied=registry.call(
            "migration.propose",
            {"subject":"feature:test"},
            permission_profile="READ_ONLY_RESEARCH",
            session_store=store,
            research_session_id=session.research_session_id,
        )
        assert denied["status"]=="DENIED",denied

        loaded=store.get(session.research_session_id)
        assert len(loaded["tool_calls"])==2,loaded
        assert loaded["tool_calls"][0]["evidence_ids"]==["evidence:trace:1"],loaded
        assert loaded["tool_calls"][1]["status"]=="DENIED",loaded

        specs={row["name"]:row for row in registry.specs()}
        assert specs["graph.trace"]["access"]=="READ",specs
        assert specs["migration.propose"]["access"]=="PROPOSE",specs

    print("typed research tool registry self-test: PASS")


if __name__=="__main__":
    main()
