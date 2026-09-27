#!/usr/bin/env python3
import tempfile
from pathlib import Path

from workbench.research import BoundedSourceCrawler, CrawlPolicy, ResearchSessionStore
from workbench.research.tools import (
    ACCESS_PROPOSE,
    ACCESS_READ,
    ResearchTool,
    ResearchToolRegistry,
    register_source_tools,
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

        source_root=Path(td)/"source"
        source_root.mkdir()
        (source_root/"example.lua").write_text("player:getID()\n",encoding="utf-8")
        crawler=BoundedSourceCrawler(CrawlPolicy(roots=(source_root,)))

        registry=ResearchToolRegistry()
        register_source_tools(registry,crawler)
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

        source_result=registry.call(
            "source.search",
            {"query":"getID"},
            permission_profile="READ_ONLY_RESEARCH",
            session_store=store,
            research_session_id=session.research_session_id,
        )
        assert source_result["status"]=="OK",source_result
        assert source_result["matches"][0]["path"]=="example.lua",source_result

        loaded=store.get(session.research_session_id)
        assert len(loaded["tool_calls"])==3,loaded
        assert loaded["tool_calls"][0]["evidence_ids"]==["evidence:trace:1"],loaded
        assert loaded["tool_calls"][1]["status"]=="DENIED",loaded
        assert loaded["tool_calls"][2]["tool_name"]=="source.search",loaded

        specs={row["name"]:row for row in registry.specs()}
        assert specs["graph.trace"]["access"]=="READ",specs
        assert specs["migration.propose"]["access"]=="PROPOSE",specs
        assert specs["source.search"]["access"]=="READ",specs
        assert specs["source.read"]["access"]=="READ",specs

    print("typed research tool registry self-test: PASS")


if __name__=="__main__":
    main()
