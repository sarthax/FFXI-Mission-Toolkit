from __future__ import annotations

from pathlib import Path

from workbench.client.models import catalog as canonical

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_root_module_is_retired_and_package_is_canonical():
    assert not (REPO_ROOT / "client_model_catalog.py").exists()
    assert canonical.client_model_resolver.__name__ == "workbench.client.models.resolver"
    assert canonical.look.__name__ == "workbench.client.models.look_decode"
    assert canonical.mob_model_tables.__name__ == "workbench.client.models.mob_model_tables"
    assert canonical.msd.__name__ == "workbench.client.models.schedule_dump"
    assert canonical.zone_plot.__name__.startswith("workbench.devtools.spatial")


def test_build_catalog_uses_package_safe_ffxi_lookup(monkeypatch):
    canonical.clear_cache()
    row = canonical._empty(740)
    monkeypatch.setattr(canonical.zone_plot, "get_server", lambda: "topaz")
    monkeypatch.setattr(canonical, "get_ffxi_install", lambda: "C:/FFXI")
    monkeypatch.setattr(canonical, "_collect_server_models", lambda server: {740: row})
    monkeypatch.setattr(
        canonical.msd,
        "resolve_rom_paths",
        lambda path, ids: {2040: "ROM/7/1.DAT"},
    )

    rows = canonical.build_catalog(refresh=True)

    assert rows[0]["model_id"] == 740
    assert rows[0]["resource_rom_path"] == "ROM/7/1.DAT"
    assert rows[0]["registered"] is True
    assert rows[0]["source_server"] == "topaz"
