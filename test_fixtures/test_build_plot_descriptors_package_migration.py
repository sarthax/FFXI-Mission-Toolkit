from __future__ import annotations

import json
from pathlib import Path

from workbench.devtools.spatial import build_plot_descriptors as canonical
from workbench.runtime.paths import PLOT_DESCRIPTORS_ROOT


def test_root_launcher_is_retired_and_package_path_is_canonical():
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "build_plot_descriptors.py").exists()
    assert canonical.OUT == PLOT_DESCRIPTORS_ROOT


def test_zone_root_uses_package_safe_dsp_bridge(tmp_path, monkeypatch):
    dsp_root = tmp_path / "dsp"
    monkeypatch.setattr(canonical, "get_dsp_root", lambda: dsp_root)

    assert canonical._zone_root() == dsp_root / "scripts/zones"


def test_missing_dsp_root_preserves_existing_error(monkeypatch):
    monkeypatch.setattr(canonical, "get_dsp_root", lambda: None)

    try:
        canonical._zone_root()
    except SystemExit as exc:
        assert "DSP server path isn't configured yet" in str(exc)
    else:
        raise AssertionError("missing DSP path must still stop descriptor generation")


def test_generate_writes_descriptors_to_configured_output(tmp_path, monkeypatch):
    out = tmp_path / "plot_descriptors"
    golden = {"id": "golden_salvage", "zone": 55, "ops": []}
    arrapago = {"id": "arrapago_remnants", "zone": 56, "ops": []}

    monkeypatch.setattr(canonical, "OUT", out)
    monkeypatch.setattr(canonical, "golden_salvage", lambda: golden)
    monkeypatch.setattr(canonical, "arrapago", lambda: arrapago)

    descriptors = canonical.generate()

    assert descriptors == [golden, arrapago]
    assert json.loads((out / "golden_salvage.json").read_text()) == golden
    assert json.loads((out / "arrapago_remnants.json").read_text()) == arrapago
