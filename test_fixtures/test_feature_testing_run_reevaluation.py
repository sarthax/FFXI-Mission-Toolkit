"""Run inspector reevaluation is bounded, read-only, and transparent."""
from pathlib import Path
import pytest
from fastapi import HTTPException
from workbench.server_admin.feature_testing import router


def _record(run_id="mog-run"):
    from test_feature_testing_normalized_evidence import sample
    from datetime import datetime, timezone
    record=sample()
    record.update(run_id=run_id,stage="key_item",observed_at="2026-10-19T08:18:40Z",
                  dsp_commit="a"*40,headless_commit="b"*40,toolkit_commit="c"*40)
    return record


def test_run_inspector_uses_exact_run_lookup(monkeypatch):
    captured=[]
    monkeypatch.setattr(router,"_results_db",lambda: "/tmp/mock_results.sqlite")
    from workbench.server_admin.feature_testing import results
    def fake_lookup(path, run_id):
        captured.append(run_id)
        return [_record(run_id)] if run_id=="mog-run" else []
    monkeypatch.setattr(results,"results_for_run",fake_lookup)
    class Templates:
        def TemplateResponse(self,**kwargs): return kwargs["context"]
    monkeypatch.setattr(router,"templates",Templates())
    result=router.run_page(None,"mog-run")
    assert captured==["mog-run"]
    assert result["reevaluations"][0]["evaluation"]["verdict"]=="PASS"
    assert result["reevaluations"][0]["recorded_verdict"]=="PASS"
    missing=router.run_page(None,"unknown")  # a readable 404 page (the context is returned by the stub), not bare JSON
    assert missing["missing"] is True and missing["records"]==[] and missing["run_id"]=="unknown"


def test_run_inspector_includes_missing_evidence_and_mismatch(monkeypatch):
    monkeypatch.setattr(router,"_results_db",lambda: "/tmp/mock_results.sqlite")
    from workbench.server_admin.feature_testing import results
    record=_record()
    record["evidence"]["assertions"].pop()
    monkeypatch.setattr(results,"results_for_run",lambda path,run_id:[record])
    class Templates:
        def TemplateResponse(self,**kwargs): return kwargs["context"]
    monkeypatch.setattr(router,"templates",Templates())
    reevaluation=router.run_page(None,"mog-run")["reevaluations"][0]
    assert reevaluation["evaluation"]["verdict"]=="BLOCKED"
    assert reevaluation["recorded_verdict"]=="PASS"
    assert "client_safe" in reevaluation["normalization"]["missing_fields"]


def test_template_displays_dual_verdict_and_provenance():
    html=(Path(__file__).resolve().parents[1]/"gui/templates/feature_testing_run.html").read_text()
    assert "Reevaluate with Specification" in html
    assert "Recorded verdict:" in html
    assert "Recalculated verdict:" in html
    assert "Normalized field provenance" in html
