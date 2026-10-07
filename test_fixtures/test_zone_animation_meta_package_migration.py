from pathlib import Path

from workbench.client.models import zone_animation_meta
from workbench.devtools.indexing import build_lsb_index


def test_zone_animation_meta_uses_packaged_lsb_index():
    assert zone_animation_meta.LSB_ROOT == build_lsb_index.LSB_ROOT
    source = Path("src/workbench/client/models/zone_animation_meta.py").read_text(encoding="utf-8")
    assert "import build_lsb_index" not in source
    assert "from workbench.devtools.indexing import build_lsb_index" in source


def test_root_zone_animation_meta_launcher_is_retired():
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "zone_animation_meta.py").exists()


def test_fallback_animation_contract_remains_available(monkeypatch):
    monkeypatch.setattr(zone_animation_meta, "ANIMATION_YAML", Path("missing-animation.yaml"))
    values = zone_animation_meta.animation_values()
    by_value = {row["value"]: row for row in values}
    assert by_value[0]["name"] == "none"
    assert by_value[4]["name"] == "event"
    assert by_value[85]["name"] == "mount"
