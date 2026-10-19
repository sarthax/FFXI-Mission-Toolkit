"""Read-only investigation makes no causal claims without independent evidence."""
import pytest
from fastapi import HTTPException
from workbench.server_admin.feature_testing import supervisor
from workbench.server_admin.feature_testing.investigation_dossier import investigation_dossier
from workbench.server_admin.feature_testing.results import append_result


def row(evidence, verdict="FAIL"):
    return {"run_id": "run-42", "case_id": "MOG-09", "feature_id": "moghancement",
            "stage": "key_item", "verdict": verdict, "observed_at": "2026-10-19T00:00:00Z",
            "dsp_commit": "d" * 40, "headless_commit": "h" * 40,
            "toolkit_commit": "t" * 40, "evidence": evidence}


def test_assertion_scoped_search_and_unverified_label(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "logic.lua").write_text("function auraMismatch() end\n", encoding="utf-8")
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_DSP_SOURCE_ROOT", str(root))
    dossier = investigation_dossier([row({"assertions": [{"id": "auraMismatch", "ok": False}]})])
    assert dossier["searches"][0]["matches"][0]["path"] == "logic.lua"
    assert dossier["hypotheses"] == []
    assert "No causal conclusion" in dossier["conclusion"]
    assert dossier["execution_enabled"] is False


def test_unverified_or_unsearchable_does_not_fabricate_sources(monkeypatch):
    monkeypatch.delenv("MISSION_TOOLKIT_SUPERVISOR_DSP_SOURCE_ROOT", raising=False)
    dossier = investigation_dossier([row({"evaluation": {"reason": "mismatch"}})])
    assert dossier["searches"] == []
    assert dossier["problem_records"][0]["verdict"] == "FAIL"


def test_repository_and_mixed_run_ids_fail_closed():
    with pytest.raises(ValueError):
        investigation_dossier([row({"evaluation": {}})], repository="../../etc")
    other = {**row({"evaluation": {}}), "run_id": "other"}
    with pytest.raises(ValueError):
        investigation_dossier([row({"evaluation": {}}), other])


def test_endpoint_requires_auth_and_exact_run(tmp_path, monkeypatch):
    db = tmp_path / "runs.db"
    append_result(db, row({"assertions": [{"id": "auraMismatch", "ok": False}]}))
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_RESULTS_DB", str(db))
    monkeypatch.setenv("MISSION_TOOLKIT_SUPERVISOR_TOKEN", "a" * 64)
    with pytest.raises(HTTPException) as error:
        supervisor.supervisor_investigation_dossier("run-42", authorization=None)
    assert error.value.status_code == 403
    response = supervisor.supervisor_investigation_dossier("run-42", authorization="Bearer " + "a" * 64)
    assert response["run_id"] == "run-42"
    with pytest.raises(HTTPException) as error:
        supervisor.supervisor_investigation_dossier("missing", authorization="Bearer " + "a" * 64)
    assert error.value.status_code == 404
