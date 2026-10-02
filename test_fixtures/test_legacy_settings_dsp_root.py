from pathlib import Path

from workbench.runtime import legacy_settings


class _FakeSettings:
    def __init__(self, dsp_root: Path):
        self._dsp_root = dsp_root

    def get_dsp_root(self):
        return self._dsp_root


def test_get_dsp_root_delegates_to_legacy_settings_module(tmp_path, monkeypatch):
    expected = tmp_path / "dsp"
    fake = _FakeSettings(expected)
    monkeypatch.setattr(legacy_settings, "_module", lambda: fake)

    assert legacy_settings.get_dsp_root() == expected
