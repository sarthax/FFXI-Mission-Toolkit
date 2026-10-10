from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI

from workbench.editors.items import client_asset_cache as cache
from workbench.editors.character.gui import router


def test_lazy_item_cache_and_source_invalidation(tmp_path, monkeypatch):
    client = tmp_path / "client"
    dat_path = client / "ROM" / "1.DAT"
    dat_path.parent.mkdir(parents=True)
    dat_path.write_bytes(b"first")

    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path / "cache")
    monkeypatch.setattr(cache.dat_tools, "ffxi_dir", lambda: str(client))
    monkeypatch.setattr(cache.dat_tools, "ITEM_DATS", [("Test", 100, 0, "ROM/1.DAT", "ROM/JP.DAT")])
    monkeypatch.setattr(cache.dat_tools, "record_count", lambda _path: 2)

    reads: list[int] = []
    def fake_read(item_id: int):
        reads.append(int(item_id))
        if int(item_id) == 101:
            return None
        return SimpleNamespace(id=int(item_id), icon_data=b"icon")

    monkeypatch.setattr(cache.dat_tools, "read_client_item", fake_read)
    monkeypatch.setattr(cache.dat_tools, "item_to_dict", lambda row: {"id": row.id, "name": "Cached Item"})
    monkeypatch.setattr(cache.dat_tools, "bitmap_a_to_png", lambda raw: b"PNG" + bytes(raw))

    first = cache.ensure_item(100)
    assert first is not None and first.available is True and first.cache_hit is False
    assert first.metadata == {"id": 100, "name": "Cached Item"}
    assert first.icon_path is not None and first.icon_path.read_bytes() == b"PNGicon"
    assert reads == [100]

    second = cache.ensure_item(100)
    assert second is not None and second.cache_hit is True
    assert reads == [100]

    dat_path.write_bytes(b"changed-source")
    third = cache.ensure_item(100)
    assert third is not None and third.cache_hit is False
    assert reads == [100, 100]

    built = cache.build_source("Test")
    assert built["record_count"] == 2
    assert built["available"] == 1
    assert built["empty"] == 1
    assert built["failed"] == 0

    status = cache.cache_status()
    assert status["cached_rows"] == 2
    assert status["total_records"] == 2
    assert status["complete"] is True
    assert status["fresh_rows"] == 2
    assert status["stale_rows"] == 0
    assert status["missing_rows"] == 0
    assert status["total_bytes"] > 0

    cleared = cache.clear_cache()
    assert cleared["bytes_removed"] > 0
    assert not (cache.CACHE_ROOT / status["client_key"]).exists()


def test_client_cache_routes_and_inventory_lazy_contract():
    app = FastAPI()
    app.include_router(router)
    paths = set(app.openapi()["paths"])
    assert "/character-editor/client-cache/status.json" in paths
    assert "/character-editor/client-cache/build-source" in paths
    assert "/character-editor/client-cache/clear" in paths
    assert "/character-editor/client-cache/items/{item_id}.json" in paths
    assert "/character-editor/client-cache/icons/{item_id}.png" in paths

    root = Path(__file__).resolve().parents[1]
    dense = (root / "gui" / "static" / "character_editor_dense_ux.js").read_text(encoding="utf-8")
    settings = (root / "gui" / "static" / "settings_server_profiles.js").read_text(encoding="utf-8")
    ignore = (root / ".gitignore").read_text(encoding="utf-8")

    assert "/character-editor/client-cache/icons/${id}.png" in dense
    assert "data-src=" in dense
    assert "hydrateInventoryIcons" in dense
    assert "openedFirstPopulated" in dense
    assert "loading=\"lazy\"" in dense
    assert "Build all item DAT cache" in settings
    assert "/character-editor/client-cache" in settings
    assert "build-source" in settings
    assert "data/client_asset_cache/" in ignore


def test_cache_status_detects_changed_dat_missing_icon_and_orphan(tmp_path, monkeypatch):
    client = tmp_path / "client"
    dat_path = client / "ROM" / "1.DAT"
    dat_path.parent.mkdir(parents=True)
    dat_path.write_bytes(b"source")
    monkeypatch.setattr(cache, "CACHE_ROOT", tmp_path / "cache")
    monkeypatch.setattr(cache.dat_tools, "ffxi_dir", lambda: str(client))
    monkeypatch.setattr(cache.dat_tools, "ITEM_DATS", [("Test", 100, 0, "ROM/1.DAT", "")])
    monkeypatch.setattr(cache.dat_tools, "record_count", lambda path: 2)
    monkeypatch.setattr(cache.dat_tools, "read_client_item", lambda item_id: SimpleNamespace(id=item_id, icon_data=b"icon"))
    monkeypatch.setattr(cache.dat_tools, "item_to_dict", lambda item: {"id": item.id})
    monkeypatch.setattr(cache.dat_tools, "bitmap_a_to_png", lambda _: b"PNG")

    entry = cache.ensure_item(100)
    initial = cache.cache_status()
    assert (initial["fresh_rows"], initial["missing_rows"]) == (1, 1)
    assert initial["complete"] is False
    entry.icon_path.unlink()
    missing_icon = cache.cache_status()
    assert missing_icon["stale_rows"] == 1
    assert missing_icon["fresh_rows"] == 0
    cache.ensure_item(100)
    dat_path.write_bytes(b"modified-source")
    changed = cache.cache_status()
    assert changed["stale_rows"] == 1
    assert changed["sources"][0]["fresh_count"] == 0
    cache.build_source("Test")
    assert cache.cache_status()["complete"] is True
    dat_path.unlink()
    orphaned = cache.cache_status()
    assert orphaned["orphaned_rows"] == 2
    assert orphaned["complete"] is False
