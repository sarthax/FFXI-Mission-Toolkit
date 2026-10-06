from __future__ import annotations

from pathlib import Path

from workbench.client.models import viewer as canonical


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_root_module_is_retired_and_package_is_canonical():
    assert not (REPO_ROOT / "model_viewer.py").exists()
    assert canonical.look.__name__ == "workbench.client.models.look_decode"
    assert canonical.msd.__name__ == "workbench.client.models.schedule_dump"
    assert canonical.client_model_resolver.__name__ == "workbench.client.models.resolver"
    assert canonical.mob_model_tables.__name__ == "workbench.client.models.mob_model_tables"
    assert canonical.zone_plot.__name__ == "workbench.devtools.spatial.zone_plot"


def test_resolve_uses_package_safe_ffxi_lookup(monkeypatch):
    monkeypatch.setattr(canonical, "_db_row", lambda kind, eid, server=None: (bytes(20), "Fixture", None))
    monkeypatch.setattr(
        canonical.look,
        "decode_look_data",
        lambda blob, familyid=None: {"kind": "flat", "modelid": 740},
    )
    monkeypatch.setattr(canonical, "get_ffxi_install", lambda: "C:/FFXI")
    monkeypatch.setattr(
        canonical.client_model_resolver,
        "resolve_model_id",
        lambda model_id, ffxi_path: {
            "file_id": 2040,
            "mapping_source": "fixture",
            "mapping_rule": "fixture",
            "rom_path": "ROM/7/1.DAT",
            "registered": True,
        },
    )

    result = canonical.resolve("m", 1)
    assert result["ffxi_path"] == "C:/FFXI"
    assert result["resource_file_id"] == 2040
    assert result["resource_rom_path"] == "ROM/7/1.DAT"


def test_client_dat_path_stays_inside_configured_root(tmp_path):
    root = tmp_path / "ffxi"
    root.mkdir()
    inside = canonical._client_dat_path(str(root), "ROM/0/1.DAT")
    assert root.resolve() in inside.parents

    try:
        canonical._client_dat_path(str(root), "../outside.DAT")
    except ValueError as exc:
        assert "inside the configured FFXI client install" in str(exc)
    else:
        raise AssertionError("path traversal must be rejected")


def test_resolve_dat_preserves_missing_client_error(monkeypatch):
    monkeypatch.setattr(canonical, "get_ffxi_install", lambda: None)
    result = canonical.resolve_dat(file_id=1)
    assert "no FFXI client install path configured" in result["error"]
