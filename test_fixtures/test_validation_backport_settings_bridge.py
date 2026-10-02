from __future__ import annotations

from pathlib import Path

from workbench.runtime import legacy_settings
from workbench.validation.packages import lua_sanity


def test_backport_root_bridge_delegates_to_legacy_settings(monkeypatch, tmp_path):
    class FakeSettings:
        @staticmethod
        def get_backport_root():
            return tmp_path

    monkeypatch.setattr(legacy_settings, "_module", lambda: FakeSettings)
    assert legacy_settings.get_backport_root() == tmp_path


def test_lua_sanity_default_packages_root_uses_package_bridge(monkeypatch, tmp_path):
    monkeypatch.setattr(lua_sanity, "get_backport_root", lambda: tmp_path)
    assert lua_sanity._default_packages_root() == tmp_path / "mission-packages"


def test_lua_sanity_source_has_no_root_settings_import():
    source = Path(lua_sanity.__file__).read_text(encoding="utf-8")
    assert "import settings" not in source
    assert "from workbench.runtime.legacy_settings import get_backport_root" in source
