from pathlib import Path
import struct

from workbench.devtools.spatial import zmesh
from workbench.runtime.paths import GUI_ROOT


def test_packaged_zmesh_uses_canonical_gui_path():
    assert zmesh.DIR == GUI_ROOT / "static" / "zone_visual"
    source = Path("src/workbench/devtools/spatial/zmesh.py").read_text(encoding="utf-8")
    assert "Path(__file__)" not in source


def test_root_zmesh_launcher_is_retired():
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "zmesh.py").exists()


def test_zmesh_conversion_behavior_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(zmesh, "DIR", tmp_path)
    (tmp_path / "1.obj").write_text(
        "v 0 0 0\n"
        "v 1 0 0\n"
        "v 0 1 0\n"
        "f 1 2 3\n",
        encoding="ascii",
    )

    out = zmesh.convert("1", force=True)
    assert out == tmp_path / "1.zmesh"
    blob = out.read_bytes()
    assert blob[:4] == b"ZMS1"
    assert struct.unpack_from("<II", blob, 4) == (3, 1)
