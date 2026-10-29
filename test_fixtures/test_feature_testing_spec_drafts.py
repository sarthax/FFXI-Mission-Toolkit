import copy
import pytest
from workbench.server_admin.feature_testing.spec_drafts import save_draft,get_drafts
from workbench.server_admin.feature_testing.test_specifications import specification


def draft():
    spec=copy.deepcopy(specification("inventory_observation","INV-OBS-01"))
    spec["case_id"]="INV-OBS-DRAFT-01"
    return spec


def test_draft_create_revision_and_conflict(monkeypatch,tmp_path):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB",str(tmp_path/"drafts.sqlite"))
    first=save_draft(draft(),0)
    assert first["revision"]==1 and first["execution_enabled"] is False
    second=save_draft(draft(),1)
    assert second["revision"]==2
    assert get_drafts()[0]["revision"]==2
    with pytest.raises(ValueError,match="revision conflict"):
        save_draft(draft(),1)


def test_draft_never_overwrites_published_or_binds_runner(monkeypatch,tmp_path):
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_DRAFTS_DB",str(tmp_path/"drafts.sqlite"))
    with pytest.raises(ValueError,match="published"):
        save_draft(copy.deepcopy(specification("inventory_observation","INV-OBS-01")),0)
    item=draft()
    item["runner"]="xiheadless_observation_v1"
    with pytest.raises(ValueError,match="design_only"):
        save_draft(item,0)
    item=draft()
    item["assertions"][0]["operation"]="eval"
    with pytest.raises(ValueError,match="unsupported"):
        save_draft(item,0)


def test_draft_endpoint_requires_separate_operator_auth(monkeypatch):
    from fastapi.testclient import TestClient
    host=pytest.importorskip("workbench.app.host",exc_type=Exception)
    client=TestClient(host.app)
    monkeypatch.setenv("MISSION_TOOLKIT_TEST_OPERATOR_TOKEN","a"*64)
    assert client.get("/feature-testing/builder/drafts").status_code==403
    assert client.post("/feature-testing/builder/drafts",json={"specification":draft(),"expected_revision":0}).status_code==403


def test_draft_editor_not_in_supervisor_schema():
    from pathlib import Path
    from workbench.server_admin.feature_testing.supervisor import supervisor_openapi
    assert "/feature-testing/builder/drafts" not in supervisor_openapi()["paths"]
    assert 'id="ft-draft-editor"' in (Path(__file__).resolve().parents[1]/"gui/templates/feature_testing.html").read_text(encoding="utf-8")
