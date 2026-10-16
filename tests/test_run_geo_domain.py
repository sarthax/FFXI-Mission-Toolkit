import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from workbench.domains import run_geo  # noqa: E402


def test_overview_counts_and_unique_ids():
    o = run_geo.overview()
    ids = [r["id"] for r in o["items"]]
    assert ids and len(ids) == len(set(ids))
    assert sum(o["counts"].values()) == len(ids)
    assert all(r["status"] in run_geo.STATES for r in o["items"])


def test_save_roundtrip_and_validation(tmp_path, monkeypatch):
    p = tmp_path / "gaps.json"
    p.write_text(Path(run_geo.PATH).read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(run_geo, "PATH", p)
    e = run_geo.save("g04", {"status": "partial", "note": "n"})
    assert e["status"] == "partial"
    assert next(r for r in json.loads(p.read_text(encoding="utf-8")) if r["id"] == "g04")["note"] == "n"
    with pytest.raises(ValueError):
        run_geo.save("g04", {"status": "bogus"})
    with pytest.raises(KeyError):
        run_geo.save("nope", {})
