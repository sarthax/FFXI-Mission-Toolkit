from pathlib import Path
from jinja2 import Environment

SOURCE = (Path(__file__).resolve().parents[1] / "gui/templates/zone_view3d.html").read_text(encoding="utf-8")


def test_scenery_evidence_and_isolation_controls():
    Environment().parse(SOURCE)
    for element in ("zone3d-isolate-prefab", "zone3d-copy-material-evidence",
                    "zone3d-scenery-evidence"):
        assert f'id="{element}"' in SOURCE
    assert "function applyPrefabIsolation()" in SOURCE
    assert "mesh.userData.prefabIndex === selectedSceneryPrefab" in SOURCE
    assert "camera_distance: Number(hit.distance.toFixed(3))" in SOURCE
    assert "lod_switching: 'not established" in SOURCE
    assert "navigator.clipboard.writeText(JSON.stringify(selectedSceneryEvidence, null, 2))" in SOURCE
    assert "prefabIsolationToggle.checked = false" in SOURCE
