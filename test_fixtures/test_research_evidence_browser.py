#!/usr/bin/env python3
"""Regression coverage for research contradiction filtering and evidence drill-down."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from workbench.core import graph
from workbench.core.schema import Evidence, Finding
from workbench.gui_shell import build_shell_context, route_owner
from workbench.research.evidence_browser import evidence_record, list_contradictions
from workbench.research.session import ResearchSessionStore


ROOT=Path(__file__).resolve().parents[1]
TEMPLATES=ROOT/"gui"/"templates"


def request(path: str):
    return SimpleNamespace(url=SimpleNamespace(path=path),method="GET")


def shell(path: str):
    return build_shell_context(
        path=path,method="GET",settings={},
        default_topaz_root="C:/missing-topaz",
        default_backport_root="C:/missing-workspace",
        path_exists=lambda _path: False,
    )


def render(name: str,path: str,**values) -> str:
    env=Environment(loader=FileSystemLoader(str(TEMPLATES)),autoescape=select_autoescape(("html",)))
    env.globals.update(
        current_theme=lambda:"light",
        backport_enabled=lambda:False,
        shell_context=lambda _request:shell(path),
    )
    return env.get_template(name).render(request=request(path),**values)


def main() -> int:
    assert route_owner("/research/contradictions")["section"]=="Research: Contradictions"
    assert route_owner("/research/evidence")["section"]=="Research: Contradictions"

    with TemporaryDirectory() as td:
        db=Path(td)/"workbench.db"
        con=graph.init_db(db)
        graph.insert_record(con,Evidence("evidence:server","SERVER","LSB","scripts/a.lua","lsb:test","server evidence"))
        graph.insert_record(con,Evidence("evidence:client","CLIENT","FFXI DAT","ROM/1/2.DAT","client:test","client evidence"))
        graph.insert_record(con,Evidence("evidence:capture","CAPTURE","packet capture","capture:7","runtime:test","capture evidence"))
        graph.insert_record(con,Evidence("evidence:other-a","SERVER","Other A","scripts/other_a.lua","other:a","other evidence a"))
        graph.insert_record(con,Evidence("evidence:other-b","CLIENT","Other B","ROM/other.DAT","other:b","other evidence b"))
        graph.insert_record(con,Evidence(
            "evidence:wiki-claim:test","REFERENCE","bg-wiki","Test Page#Walkthrough","revision:42",
            "Reference-only claim excerpt",
        ))
        graph.insert_record(con,Finding(
            "finding:a","analysis:a","feature:test","implementation_state","IMPLEMENTED",
            "VERIFIED","HIGH","evidence:server","lsb:test"
        ))
        graph.insert_record(con,Finding(
            "finding:b","analysis:b","feature:test","implementation_state","MISSING",
            "VERIFIED","HIGH","evidence:client","client:test"
        ))
        graph.insert_record(con,Finding(
            "finding:explicit","analysis:c","feature:other","notes","conflict",
            "CONTRADICTED","HIGH","evidence:capture","runtime:test"
        ))
        graph.insert_record(con,Finding(
            "finding:unrelated-a","analysis:u1","feature:unrelated","implementation_state","IMPLEMENTED",
            "VERIFIED","HIGH","evidence:other-a","other:a"
        ))
        graph.insert_record(con,Finding(
            "finding:unrelated-b","analysis:u2","feature:unrelated","implementation_state","MISSING",
            "VERIFIED","HIGH","evidence:other-b","other:b"
        ))
        con.execute(
            "INSERT INTO capability_observations VALUES (?,?,?,?,?,?,?)",
            ("obs:src","capability:test","lsb:test","VERIFIED",'{"value":true}',"evidence:server","[]"),
        )
        con.execute(
            "INSERT INTO capability_observations VALUES (?,?,?,?,?,?,?)",
            ("obs:dst","capability:test","client:test","MISSING",'{"value":false}',"evidence:client","[]"),
        )
        con.execute(
            "INSERT INTO entity_relationships VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "wiki-reference:wiki-map:test","reference-claim:wiki-claim:test","item:2413","MENTIONS",
                "evidence:wiki-claim:test","INFERRED","DISCOVERED",'{"mapping_status":"MAPPED"}',None,
            ),
        )
        con.commit()
        con.close()

        store=ResearchSessionStore(db)
        session=store.create(
            research_session_id="research:evidence",
            question="Why do the sources disagree?",
            provider="fixture",
            model="fixture",
            permission_profile="PROPOSE_CHANGES",
        )
        store.append_tool_call(
            session.research_session_id,
            tool_name="graph.search",
            args={"query":"feature:test"},
            result={"status":"OK"},
            evidence_ids=["evidence:server","evidence:client"],
        )
        store.add_proposal(
            session.research_session_id,
            proposal_type="FindingProposal",
            subject_id="feature:test",
            payload={"subject_id":"feature:test","field":"implementation_state","value":"IMPLEMENTED"},
            supporting_evidence_ids=["evidence:server"],
            contradicting_evidence_ids=["evidence:client"],
            verification_requirement="Resolve server/client disagreement.",
        )

        report=list_contradictions(db)
        kinds={item["kind"] for item in report["items"]}
        assert "FINDING_VALUE_CONFLICT" in kinds,report
        assert "EXPLICIT_FINDING_CONTRADICTION" in kinds,report
        assert "CAPABILITY_OBSERVATION_CONFLICT" in kinds,report
        assert "RESEARCH_PROPOSAL_CONTRADICTION" in kinds,report
        assert report["state_counts"],report
        assert any(item["subject_id"]=="feature:unrelated" for item in report["items"]),report

        finding_conflict=next(item for item in report["items"] if item["kind"]=="FINDING_VALUE_CONFLICT" and item["subject_id"]=="feature:test")
        assert finding_conflict["comparison_state"]=="EVIDENCE_BACKED_SIDES",finding_conflict
        assert len(finding_conflict["sides"])==2,finding_conflict
        assert {side["value"] for side in finding_conflict["sides"]}=={"IMPLEMENTED","MISSING"},finding_conflict
        assert {snapshot for side in finding_conflict["sides"] for snapshot in side["source_snapshots"]}=={"lsb:test","client:test"},finding_conflict
        assert all(side["evidence"] for side in finding_conflict["sides"]),finding_conflict

        explicit=next(item for item in report["items"] if item["kind"]=="EXPLICIT_FINDING_CONTRADICTION")
        assert explicit["comparison_state"]=="FLAGGED_ONLY",explicit
        assert len(explicit["sides"])==1,explicit

        proposal=next(item for item in report["items"] if item["kind"]=="RESEARCH_PROPOSAL_CONTRADICTION")
        assert proposal["comparison_state"]=="EVIDENCE_BACKED_SIDES",proposal
        assert [side["label"] for side in proposal["sides"]]==["Supporting evidence","Contradicting evidence"],proposal
        assert set(proposal["evidence_ids"])=={"evidence:server","evidence:client"},proposal
        assert proposal["sides"][0]["evidence_ids"]==["evidence:server"],proposal
        assert proposal["sides"][1]["evidence_ids"]==["evidence:client"],proposal

        session_report=list_contradictions(db,research_session_id="research:evidence")
        assert any(item["kind"]=="RESEARCH_PROPOSAL_CONTRADICTION" for item in session_report["items"]),session_report
        assert any(item["kind"]=="FINDING_VALUE_CONFLICT" for item in session_report["items"]),session_report
        assert all(item["subject_id"]!="feature:unrelated" for item in session_report["items"]),session_report

        client_only=list_contradictions(db,evidence_type="CLIENT")
        assert client_only["items"],client_only
        assert all("CLIENT" in item["evidence_types"] for item in client_only["items"]),client_only

        limited=list_contradictions(db,limit=1)
        assert limited["total"]==1,limited
        assert limited["matched_total"]>limited["total"],limited
        assert limited["truncated"] is True,limited
        assert limited["limit"]==1,limited

        detail=evidence_record(db,"evidence:client")
        assert detail is not None
        assert detail["evidence_type"]=="CLIENT",detail
        kinds={ref["kind"] for ref in detail["references"]}
        assert "findings" in kinds,detail
        assert "capability_observations" in kinds,detail
        assert "research_tool_call" in kinds,detail
        assert "research_proposal" in kinds,detail
        finding_ref=next(ref for ref in detail["references"] if ref["kind"]=="findings")
        assert finding_ref["field"]=="implementation_state",finding_ref
        assert finding_ref["value"]=="MISSING",finding_ref
        assert finding_ref["source_snapshot_id"]=="client:test",finding_ref
        capability_ref=next(ref for ref in detail["references"] if ref["kind"]=="capability_observations")
        assert capability_ref["value"]=={"value":False},capability_ref
        assert capability_ref["source_snapshot_id"]=="client:test",capability_ref
        proposal_ref=next(ref for ref in detail["references"] if ref["kind"]=="research_proposal")
        assert "CONTRADICTING" in proposal_ref["evidence_roles"],proposal_ref
        assert "client:test" in detail["referenced_snapshots"],detail
        assert "feature:test" in detail["referenced_subjects"],detail

        wiki_detail=evidence_record(db,"evidence:wiki-claim:test")
        assert wiki_detail is not None
        assert wiki_detail["evidence_type"]=="REFERENCE",wiki_detail
        wiki_relationship=next(ref for ref in wiki_detail["references"] if ref["kind"]=="entity_relationships")
        assert wiki_relationship["record_id"]=="wiki-reference:wiki-map:test",wiki_relationship
        assert wiki_relationship["subject_id"]=="reference-claim:wiki-claim:test",wiki_relationship

        contradictions_html=render(
            "research_contradictions.html","/research/contradictions",
            report=report,session_id="",subject_id="",evidence_type="",
        )
        assert "Research Contradictions" in contradictions_html
        assert "FINDING_VALUE_CONFLICT" in contradictions_html
        assert "EVIDENCE_BACKED_SIDES" in contradictions_html
        assert "Recorded value 1" in contradictions_html
        assert "Supporting evidence" in contradictions_html
        assert "Contradicting evidence" in contradictions_html
        assert "evidence%3Aclient" in contradictions_html
        # Canonical subjects use the existing exact Feature Trace query route.
        assert "/features/trace?q=feature%3Atest" in contradictions_html

        limited_html=render(
            "research_contradictions.html","/research/contradictions",
            report=limited,session_id="",subject_id="",evidence_type="",
        )
        assert "Truncated at 1" in limited_html
        assert "Showing 1 /" in limited_html

        evidence_html=render(
            "research_evidence.html","/research/evidence",
            evidence=detail,
        )
        assert "Evidence Detail" in evidence_html
        assert "FFXI DAT" in evidence_html
        assert "implementation_state" in evidence_html
        assert "client:test" in evidence_html
        assert "CONTRADICTING" in evidence_html
        assert "graph.search" in evidence_html
        assert "/features/trace?q=feature%3Atest" in evidence_html
        # ResearchSession references keep their dedicated session route instead of being rewritten as traces.
        assert "/research/research%3Aevidence" in evidence_html

        wiki_html=render(
            "research_evidence.html","/research/evidence",
            evidence=wiki_detail,
        )
        assert "Reference Claim Provenance" in wiki_html
        assert "wiki-claim:test" in wiki_html
        assert "Test Page#Walkthrough" in wiki_html
        assert "revision:42" in wiki_html
        assert "Reference-only claim excerpt" in wiki_html
        assert "/features/trace?q=wiki-claim%3Atest" in wiki_html
        assert "wiki-map:test" in wiki_html
        assert "/features/trace?q=wiki-map%3Atest" in wiki_html
        assert "Feature Trace remains authoritative" in wiki_html

        session_data=store.get("research:evidence")
        session_html=render(
            "research_session_detail.html","/research/research:evidence",
            session=session_data,
            created="",run_status="",run_error="",replayed_from="",
            run_defaults={
                "provider":"fixture","model":"fixture","max_tool_calls":8,
                "max_provider_calls":12,"timeout":120.0,"temperature":0.1,
                "provider_base_url":"",
            },
            has_run=True,
        )
        assert "/research/contradictions?session_id=research%3Aevidence" in session_html
        assert "/research/evidence?evidence_id=evidence%3Aclient" in session_html

    source=(ROOT/"gui_server.py").read_text(encoding="utf-8")
    assert '@app.get("/research/contradictions"' in source
    assert '@app.get("/research/evidence"' in source

    print("research evidence drill-down regression: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
