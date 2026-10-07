#!/usr/bin/env python3
"""Regression coverage for the searchable client model catalog."""

from pathlib import Path
from types import SimpleNamespace

from workbench.client.models import catalog
from workbench.client.models import schedule_dump as msd

ROOT = Path(__file__).resolve().parents[1]


def main():
    assert catalog._bytes(bytes(range(20))) == bytes(range(20))
    assert catalog._bytes("0x" + "00" * 20) == bytes(20)
    assert catalog._bytes("not-a-look") is None

    row = catalog._empty(740)
    assert row["model_id"] == 740
    assert row["resource_file_id"] == 2040
    assert row["mapping_rule"] == "<1500 +1300"

    sample = {
        **row,
        "primary_name": "Abyssal Demon",
        "names": ["Abyssal Demon", "Demon"],
        "mob_names": ["Abyssal Demon"],
        "npc_names": [],
        "family_ids": [169],
        "pool_ids": [123],
        "source_kinds": ["mob_pool"],
        "reference_count": 4,
        "resource_rom_path": r"ROM\7\1.DAT",
        "render_file_id": 2017,
        "render_rom_path": r"ROM\7\64.DAT",
        "render_source": "legacy hand-verified family visual DAT",
        "visual_hints": [{
            "family_id": 169,
            "family_name": "Demon",
            "file_id": 2017,
            "rom_path": r"ROM\7\64.DAT",
            "verified": "fixture",
        }],
    }

    original = catalog.build_catalog
    try:
        catalog.build_catalog = lambda server=None, refresh=False: [sample]
        result = catalog.search_catalog("abyssal", server="topaz")
        assert result["matched"] == 1
        assert result["rows"][0]["model_id"] == 740

        assert catalog.search_catalog("2017", server="topaz")["matched"] == 1
        assert catalog.search_catalog("ROM/7/64.DAT", server="topaz")["matched"] == 1
        assert catalog.search_catalog("family-does-not-exist", server="topaz")["matched"] == 0

        assert catalog.correlate(model_id=740, server="topaz")[0]["primary_name"] == "Abyssal Demon"
        assert catalog.correlate(file_id=2017, server="topaz")[0]["model_id"] == 740
        assert catalog.correlate(rom_path=r"ROM\7\64.DAT", server="topaz")[0]["model_id"] == 740
        assert catalog.correlate(file_id=999999, server="topaz") == []
    finally:
        catalog.build_catalog = original

    original_run = msd.subprocess.run
    calls = []
    try:
        def fake_run(args, capture_output=True, text=True):
            ids = [int(x) for x in args[5:]]
            calls.append(ids)
            return SimpleNamespace(stdout="".join(f"{x}\tROM/0/{x}.DAT\n" for x in ids))
        msd.subprocess.run = fake_run
        got = msd.resolve_rom_paths("C:/FFXI", range(5), batch_size=2)
        assert len(calls) == 3
        assert got[4] == "ROM/0/4.DAT"
    finally:
        msd.subprocess.run = original_run

    server = (ROOT / "src" / "workbench" / "app" / "_host_impl.py").read_text(encoding="utf-8")
    viewer = (ROOT / "gui" / "templates" / "model_viewer.html").read_text(encoding="utf-8")
    zone = (ROOT / "gui" / "templates" / "zone_plot.html").read_text(encoding="utf-8")
    route_map = (ROOT / "docs" / "workbench" / "GUI_ROUTE_MAP.json").read_text(encoding="utf-8")

    for route in (
        "/modelviewer/catalog.json",
        "/modelviewer/catalog/correlate.json",
        "/modelviewer/dat-info.json",
    ):
        assert route in server
        assert route in route_map

    assert 'id="catalog-search"' in viewer
    assert 'id="catalog-results"' in viewer
    assert 'id="datref"' in viewer
    assert "async function searchCatalog()" in viewer
    assert "async function loadDirectDat()" in viewer
    assert "catalog aliases:" in viewer
    assert 'id="modelCandidateSearch"' in zone
    assert 'id="modelCandidateResults"' in zone
    assert "function previewCandidateModel(mid,name)" in zone
    assert "CANDIDATE PREVIEW ONLY" in zone
    assert "function modelCatalogEsc(v)" in zone

    print("Client model catalog regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
