#!/usr/bin/env python3
"""Regression coverage for the Research Sessions audit-first GUI."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from workbench.gui_shell import build_shell_context, route_owner
from workbench.research.session import ResearchSessionStore


ROOT=Path(__file__).resolve().parents[1]
TEMPLATES=ROOT/"gui"/"templates"


def request(path: str):
    return SimpleNamespace(url=SimpleNamespace(path=path),method="GET")


def shell(path: str):
    return build_shell_context(
        path=path,
        method="GET",
        settings={},
        default_topaz_root="C:/missing-topaz",
        default_backport_root="C:/missing-workspace",
        path_exists=lambda _path: False,
    )


def render(name: str,path: str,**values) -> str:
    env=Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(("html",)),
    )
    env.globals.update(
        current_theme=lambda: "light",
        backport_enabled=lambda: False,
        shell_context=lambda _request: shell(path),
    )
    return env.get_template(name).render(request=request(path),**values)


def main():
    assert route_owner("/research")["home"]=="Tools"
    assert route_owner("/research")["section"]=="Research: Sessions"
    assert route_owner("/research","POST")["section"]=="Research: Sessions"
    assert route_owner("/research/research:test")["section"]=="Research: Sessions"
    assert route_owner("/research/run","POST")["section"]=="Research: Sessions"
    assert route_owner("/research/replay","POST")["section"]=="Research: Sessions"

    with TemporaryDirectory() as td:
        db=Path(td)/"workbench.db"
        store=ResearchSessionStore(db)
        first=store.create(
            research_session_id="research:first",
            question="Trace one feature with evidence",
            provider="fixture",
            model="fixture-model",
            source_snapshot_id="lsb:test",
            target_snapshot_id="dsp:test",
            budgets={"max_tool_calls":4},
        )
        store.append_tool_call(
            first.research_session_id,
            tool_name="graph.trace",
            args={"root":"feature:test"},
            result={"status":"OK","evidence_ids":["evidence:one"]},
            evidence_ids=["evidence:one"],
        )
        store.finalize(
            first.research_session_id,
            final_report="Draft evidence report.",
            verification_state="DRAFT",
            usage={"provider_calls":1,"tool_calls":1},
        )

        second=store.create(
            research_session_id="research:second",
            question="Stage a proposal",
            provider="fixture",
            model="fixture-model",
            permission_profile="PROPOSE_CHANGES",
        )
        store.add_proposal(
            second.research_session_id,
            proposal_type="FindingProposal",
            subject_id="feature:test",
            payload={"status":"MISSING"},
            supporting_evidence_ids=["evidence:two"],
            contradicting_evidence_ids=["evidence:three"],
            verification_requirement="Deterministic verification required.",
        )

        rows=store.list()
        assert len(rows)==2,rows
        by_id={row["research_session_id"]:row for row in rows}
        assert by_id["research:first"]["tool_call_count"]==1,by_id
        assert by_id["research:first"]["proposal_count"]==0,by_id
        assert by_id["research:second"]["proposal_count"]==1,by_id

        list_html=render(
            "research_sessions.html",
            "/research",
            sessions=rows,
            created="",
            permission_profiles=(
                "READ_ONLY_RESEARCH",
                "PROPOSE_CHANGES",
                "VALIDATION_ORCHESTRATOR",
            ),
        )
        assert "Research Sessions" in list_html
        assert 'wb-archetype-browser' in list_html
        assert 'class="wb-page-title">Research Sessions</span>' in list_html
        assert "Trace one feature with evidence" in list_html
        assert "PROPOSE_CHANGES" in list_html
        assert "No provider has been run" not in list_html

        detail=store.get("research:first")
        detail_html=render(
            "research_session_detail.html",
            "/research/research:first",
            session=detail,
            created="1",
            run_status="",
            run_error="",
            replayed_from="",
            run_defaults={
                "provider":"openwebui","model":"fixture-model","max_tool_calls":4,
                "max_provider_calls":12,"timeout":120.0,"temperature":0.1,
                "provider_base_url":"",
            },
            has_run=True,
        )
        assert "graph.trace" in detail_html
        assert "evidence:one" in detail_html
        assert "Draft evidence report." in detail_html
        assert "No provider has been run by this page." in detail_html
        assert '<body class="shell-dense">' in detail_html
        assert 'wb-archetype-workbench' in detail_html
        assert 'class="wb-page-title">Research Session</span>' in detail_html
        assert 'class="research-meta"' in detail_html
        assert 'class="research-section" open' in detail_html
        assert "Typed Tool Transcript" in detail_html
        assert "Final Report" in detail_html

        proposal=store.get("research:second")
        proposal_html=render(
            "research_session_detail.html",
            "/research/research:second",
            session=proposal,
            created="",
            run_status="",
            run_error="",
            replayed_from="",
            run_defaults={
                "provider":"openwebui","model":"fixture-model","max_tool_calls":8,
                "max_provider_calls":12,"timeout":120.0,"temperature":0.1,
                "provider_base_url":"",
            },
            has_run=False,
        )
        assert "FindingProposal" in proposal_html
        assert "evidence:two" in proposal_html
        assert "evidence:three" in proposal_html
        assert "Deterministic verification required." in proposal_html
        assert "Run / Replay" in proposal_html
        assert "Run session" in proposal_html
        assert "Replay as new session" in proposal_html
        assert "Max provider calls" in proposal_html
        assert "Timeout / call" in proposal_html
        assert "research-run-grid" in proposal_html
        assert "Research Proposals" in proposal_html

    source=(ROOT/"src"/"workbench"/"app"/"_host_impl.py").read_text(encoding="utf-8")
    assert '@app.get("/research"' in source
    assert '@app.post("/research"' in source
    assert '@app.get("/research/{research_session_id:path}"' in source
    assert '@app.post("/research/run")' in source
    assert '@app.post("/research/replay")' in source
    assert "_research_execute_from_form" in source
    assert "ResearchSessionStore(WORKBENCH_DB)" in source

    print("research session GUI regression: PASS")


if __name__=="__main__":
    main()
