"""No-execution observation preview regression checks."""
import pytest
from fastapi.testclient import TestClient
from workbench.server_admin.feature_testing.evaluation_preview import preview

def test_inventory_preview_pass_and_block():
    observations={"client_bag":[[1,42,1]],"db_bag":[[1,42,1]],"client_safe":[],"db_safe":[]}
    result=preview("inventory_observation","INV-OBS-01",observations)
    assert result["verdict"]=="PASS"
    assert result["preview_only"] is True
    assert result["persisted"] is False
    assert result["execution_enabled"] is False
    assert result["evidence_authenticated"] is False
    observations.pop("db_safe")
    assert preview("inventory_observation","INV-OBS-01",observations)["verdict"]=="BLOCKED"

def test_preview_unknown_and_restricted_context():
    with pytest.raises(ValueError,match="unknown"):
        preview("moghancement","MOG-999",{})
    with pytest.raises(ValueError,match="unsupported"):
        preview("inventory_observation","INV-OBS-01",{},{"exec":"not_allowed"})

def test_preview_endpoint_is_not_supervisor_tool(monkeypatch):
    from workbench.server_admin.feature_testing.supervisor import supervisor_openapi
    assert "/feature-testing/builder/evaluate" not in supervisor_openapi()["paths"]
    host=pytest.importorskip("workbench.app.host",exc_type=Exception)
    client=TestClient(host.app, client=("127.0.0.1", 50000))
    response=client.post("/feature-testing/builder/evaluate",json={
        "feature_id":"inventory_observation","case_id":"INV-OBS-01",
        "observations":{"client_bag":[],"db_bag":[],"client_safe":[],"db_safe":[]}})
    assert response.status_code==200
    assert response.json()["preview_only"] is True

def test_gui_preview_visible():
    from pathlib import Path
    html=(Path(__file__).resolve().parents[1]/"gui/templates/feature_testing.html").read_text(encoding="utf-8")
    assert 'id="ft-evaluation-form"' in html
    assert "/feature-testing/builder/evaluate" in html
