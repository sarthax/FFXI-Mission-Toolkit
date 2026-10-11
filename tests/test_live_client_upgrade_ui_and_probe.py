"""The main Windows addon install flow supports explicit backup-and-replace."""
from pathlib import Path

from workbench.runtime.live_client.ashita_install import preview_upgrade, upgrade_with_backup

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "gui/templates/live_client_bridge.html"


def test_install_ui_defaults_to_safe_backup_upgrade_and_has_command_probe():
    page = TEMPLATE.read_text(encoding="utf-8")
    assert 'id="ashita-install-preview"' in page
    assert "addEventListener('click',previewSafeUpgrade)" in page
    assert "request('installer/upgrade-preview'" in page
    assert "request('installer/upgrade-apply'" in page
    assert "Install / update with backup" in page
    assert 'id="bridge-test-command"' in page
    assert "request('control/probe',{client_id:id})" in page
    assert "control/probe/'+encodeURIComponent(id)" in page
    assert "run /wblive bridge ping" in page


def test_upgrade_replaces_all_differing_addon_files_and_retains_private_settings(tmp_path):
    addon = tmp_path / "addons" / "workbench_live"
    addon.mkdir(parents=True)
    targets = ("workbench_live.lua", "workbench_bridge.lua", "workbench_live_direct.lua")
    for name in targets:
        (addon / name).write_text("old:" + name, encoding="utf-8")
    private = addon / "workbench_bridge_settings.lua"
    private.write_text("SECRET", encoding="utf-8")
    plan = preview_upgrade(str(tmp_path))
    assert sum(row["action"] == "replace_with_backup" for row in plan["files"]) == 3
    outcome = upgrade_with_backup(str(tmp_path), plan)
    backup = Path(outcome["backup_directory"])
    for name in targets:
        assert (backup / name).read_text(encoding="utf-8") == "old:" + name
        assert (addon / name).read_text(encoding="utf-8") != "old:" + name
    assert private.read_text(encoding="utf-8") == "SECRET"
    assert all(row["action"] == "unchanged" for row in preview_upgrade(str(tmp_path))["files"])
