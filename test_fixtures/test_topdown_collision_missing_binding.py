"""A xi_tinkerer build without parse_zone_collision_obj must give an actionable message, not an AttributeError."""
import sqlite3
from types import SimpleNamespace

from workbench.devtools.spatial import build_topdown


def test_missing_collision_binding_reports_rebuild_hint(monkeypatch, tmp_path, capsys):
    dat = tmp_path / "rom" / "z.dat"
    dat.parent.mkdir()
    dat.write_bytes(b"x")
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE zones (zoneid INTEGER, name TEXT, geometry_rom_path TEXT)")
    con.execute("INSERT INTO zones VALUES (1,'Z','rom/z.dat')")
    monkeypatch.setattr(build_topdown, "xi_tinkerer", SimpleNamespace())
    assert build_topdown.build_one(con, 1, str(tmp_path), collision=True, visual=False) is False
    out = capsys.readouterr().out
    assert "rebuild the xi-tinkerer Python extension" in out and "AttributeError" not in out
