"""Guarded local Ashita installation: create only, no secrets or overwrites."""
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from workbench.runtime.live_client.ashita_install import preview, install_missing
from workbench.runtime.live_client.bridge_managed import ManagedLiveReceiver
from workbench.runtime.live_client.bridge_management_api import create_bridge_management_router


def test_installer_creates_only_missing_ashita_addon_files(tmp_path):
    (tmp_path / "addons").mkdir()
    report = preview(str(tmp_path))
    assert report["can_install"]
    assert all(row["action"] == "create" for row in report["files"])
    assert not (tmp_path / "addons" / "workbench_live").exists()
    result = install_missing(str(tmp_path), report)
    addon = tmp_path / "addons" / "workbench_live"
    assert len(result["created"]) == 6
    assert (addon / "workbench_live.lua").read_text().startswith("-- Copyright")
    assert "addon.name = 'workbench_live'" in (addon / "workbench_live.lua").read_text()
    assert (addon / "workbench_bridge.lua").is_file()
    assert not (addon / "workbench_bridge_settings.lua").exists()
    again = preview(str(tmp_path))
    assert again["can_install"]
    assert all(row["action"] == "unchanged" for row in again["files"])
    assert install_missing(str(tmp_path), again)["created"] == []


def test_installer_rejects_conflicts_and_stale_preview(tmp_path):
    addons = tmp_path / "addons"
    addons.mkdir()
    report = preview(str(tmp_path))
    (addons / "workbench_live").mkdir()
    (addons / "workbench_live" / "workbench_live.lua").write_text("personal copy")
    new = preview(str(tmp_path))
    assert not new["can_install"]
    assert next(row for row in new["files"] if row["name"] == "workbench_live.lua")["action"] == "blocked_existing"
    with pytest.raises(ValueError):
        install_missing(str(tmp_path), report)
    with pytest.raises(ValueError):
        install_missing(str(tmp_path), new)
    assert (addons / "workbench_live" / "workbench_live.lua").read_text() == "personal copy"


def test_installer_requires_existing_non_symlink_addons(tmp_path):
    with pytest.raises(ValueError):
        preview(str(tmp_path))
    (tmp_path / "addons").mkdir()
    (tmp_path / "addons" / "workbench_live").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        preview(str(tmp_path))


def test_installer_mutation_is_local_same_origin_and_explicit(tmp_path):
    (tmp_path / "addons").mkdir()
    app = FastAPI()
    app.include_router(create_bridge_management_router(ManagedLiveReceiver()))
    http = TestClient(app)
    selection = {"ashita_root":str(tmp_path)}
    assert http.post("/live-client/bridge/installer/preview", json=selection).status_code == 403
    origin = {"origin": "http://testserver"}
    report = http.post("/live-client/bridge/installer/preview", json=selection, headers=origin)
    assert report.status_code == 200
    assert not (tmp_path / "addons" / "workbench_live").exists()
    assert http.post("/live-client/bridge/installer/apply", json={**selection,"expected":report.json()}).status_code == 403
    applied = http.post("/live-client/bridge/installer/apply",json={**selection,"expected":report.json()},headers=origin)
    assert applied.status_code == 200
    assert len(applied.json()["created"]) == 6
