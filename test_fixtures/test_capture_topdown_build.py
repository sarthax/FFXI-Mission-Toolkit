"""Capture path plots offer to build a missing top-down cache. Offline: the real builder is faked."""
import pytest
from fastapi.testclient import TestClient

host = pytest.importorskip("workbench.app.host", exc_type=Exception)


def test_build_endpoint_returns_builder_log_and_variants(monkeypatch):
    from workbench.devtools.spatial import build_topdown as bt
    monkeypatch.setattr(host.settings_mod, "get_ffxi_install", lambda: "C:/fake")
    monkeypatch.setattr(bt, "build_one", lambda con, zid, ffxi: print(f"built {zid}") or True)
    monkeypatch.setattr(host, "topdown_variants", lambda z: {"collision": False, "detailed": True})
    body = TestClient(host.app).post("/captures/topdown/74/build").json()
    assert body == {"ok": True, "log": "built 74", "collision": False, "detailed": True}


def test_build_endpoint_explains_missing_install(monkeypatch):
    monkeypatch.setattr(host.settings_mod, "get_ffxi_install", lambda: "")
    r = TestClient(host.app).post("/captures/topdown/74/build")
    assert r.status_code == 400 and "FFXI install" in r.json()["log"]


def test_missing_cache_page_shows_build_button(monkeypatch):
    con = host.get_con()
    if not con.execute("SELECT 1 FROM captures WHERE capture_id=1").fetchone():
        pytest.skip("needs ingested capture 1 in the local captures database")
    con.close()
    monkeypatch.setattr(host, "topdown_variants", lambda z: {"collision": False, "detailed": False})
    html = TestClient(host.app).get("/captures/plot_all", params={"capture_id": 1, "zone_db": "Arrapago Remnants"}).text
    assert "td-build-btn" in html and "/captures/topdown/74/build" in html
