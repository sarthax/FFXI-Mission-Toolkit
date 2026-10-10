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


def test_upgrade_backs_up_existing_files_and_keeps_private_settings(tmp_path):
    from workbench.runtime.live_client.ashita_install import preview_upgrade, upgrade_with_backup
    (tmp_path / "addons" / "workbench_live").mkdir(parents=True)
    addon = tmp_path / "addons" / "workbench_live"
    (addon / "workbench_live.lua").write_text("old-addon", encoding="utf-8")
    (addon / "workbench_bridge_settings.lua").write_text("PRIVATE", encoding="utf-8")
    plan = preview_upgrade(str(tmp_path))
    assert plan["mode"] == "backup_upgrade"
    assert next(x for x in plan["files"] if x["name"] == "workbench_live.lua")["action"] == "replace_with_backup"
    result = upgrade_with_backup(str(tmp_path), plan)
    backup = Path(result["backup_directory"])
    assert backup.parent == addon.parent
    assert (backup / "workbench_live.lua").read_text() == "old-addon"
    assert "addon.name = 'workbench_live'" in (addon / "workbench_live.lua").read_text()
    assert (addon / "workbench_bridge_settings.lua").read_text() == "PRIVATE"


def test_upgrade_rejects_stale_preview_without_touching_existing_files(tmp_path):
    from workbench.runtime.live_client.ashita_install import preview_upgrade, upgrade_with_backup
    addon = tmp_path / "addons" / "workbench_live"
    addon.mkdir(parents=True)
    entry = addon / "workbench_live.lua"
    entry.write_text("old")
    plan = preview_upgrade(str(tmp_path))
    entry.write_text("changed")
    with pytest.raises(ValueError, match="preview changed"):
        upgrade_with_backup(str(tmp_path), plan)
    assert entry.read_text() == "changed"
    assert not list(addon.parent.glob("workbench_live_backup_*"))


def test_upgrade_routes_require_same_origin(tmp_path):
    (tmp_path / "addons").mkdir()
    app = FastAPI()
    app.include_router(create_bridge_management_router(ManagedLiveReceiver()))
    http = TestClient(app)
    selection = {"ashita_root": str(tmp_path)}
    assert http.post("/live-client/bridge/installer/upgrade-preview", json=selection).status_code == 403
    origin = {"origin": "http://testserver"}
    plan = http.post("/live-client/bridge/installer/upgrade-preview", json=selection, headers=origin)
    assert plan.status_code == 200
    assert http.post("/live-client/bridge/installer/upgrade-apply", json={**selection,"expected":plan.json()}).status_code == 403
    assert http.post("/live-client/bridge/installer/upgrade-apply",json={**selection,"expected":plan.json()},headers=origin).status_code == 200


def test_failed_upgrade_keeps_verified_original_backup_and_reports_location(tmp_path, monkeypatch):
    import workbench.runtime.live_client.ashita_install as installer
    addon = tmp_path / "addons" / "workbench_live"
    addon.mkdir(parents=True)
    entry = addon / "workbench_live.lua"
    entry.write_text("known-old")
    plan = installer.preview_upgrade(str(tmp_path))
    original_replace = installer.os.replace

    def fail_replace(*args):
        raise OSError("synthetic disk error")
    monkeypatch.setattr(installer.os, "replace", fail_replace)
    with pytest.raises(RuntimeError, match="backup directory:"):
        installer.upgrade_with_backup(str(tmp_path), plan)
    monkeypatch.setattr(installer.os, "replace", original_replace)
    assert entry.read_text() == "known-old"
    backups = list((tmp_path / "addons").glob("workbench_live_backup_*"))
    assert len(backups) == 1
    assert (backups[0] / "workbench_live.lua").read_text() == "known-old"
    assert not list(addon.glob("*.tmp"))


def test_upgrade_does_not_replace_with_symlink_target(tmp_path, monkeypatch):
    import workbench.runtime.live_client.ashita_install as installer
    addon = tmp_path / "addons" / "workbench_live"
    addon.mkdir(parents=True)
    entry = addon / "workbench_live.lua"
    entry.write_text("old")
    outside = tmp_path / "outside.lua"
    outside.write_text("safe")
    plan = installer.preview_upgrade(str(tmp_path))
    actual_open = installer.Path.open

    def redirect_on_staging(path, mode="r", *args, **kwargs):
        if path.parent == addon and path.suffix == ".tmp" and mode == "xb":
            entry.unlink()
            entry.symlink_to(outside)
        return actual_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(installer.Path, "open", redirect_on_staging)
    with pytest.raises(RuntimeError, match="backup directory"):
        installer.upgrade_with_backup(str(tmp_path), plan)
    assert outside.read_text() == "safe"
