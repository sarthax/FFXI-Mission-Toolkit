from __future__ import annotations

from pathlib import Path

from workbench.validation.packages import item_audit


def test_item_audit_default_paths_use_package_bridge(monkeypatch, tmp_path):
    dsp_root = tmp_path / "dsp"
    monkeypatch.setattr(item_audit, "get_backport_root", lambda: tmp_path / "backport")
    monkeypatch.setattr(item_audit, "get_dsp_root", lambda: dsp_root)

    packages_root, resolved_dsp = item_audit._default_paths()

    assert packages_root == tmp_path / "backport" / "mission-packages"
    assert resolved_dsp == dsp_root


def test_item_audit_source_has_no_root_settings_import():
    source = Path(item_audit.__file__).read_text(encoding="utf-8")
    assert "import settings" not in source
    assert "from workbench.runtime.legacy_settings import get_backport_root, get_dsp_root" in source
