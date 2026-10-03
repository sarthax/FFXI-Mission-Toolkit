from __future__ import annotations

from workbench.client.models import catalog
from workbench.devtools.spatial import active_zone_plot
from workbench.editors.items import editor as item_editor


def test_item_editor_uses_active_environment_zone_backend():
    assert item_editor.zone_plot is active_zone_plot
    assert hasattr(item_editor.zone_plot, "get_environment_key")


def test_model_catalog_cache_isolated_by_named_environment(monkeypatch):
    catalog.clear_cache()
    state = {
        "key": "profile:1",
        "environment": {
            "profile_id": 1,
            "name": "Live",
            "environment": "live",
            "family": "lsb",
        },
    }
    calls = []

    monkeypatch.setattr(catalog.zone_plot, "get_environment_key", lambda: state["key"])
    monkeypatch.setattr(catalog.zone_plot, "get_environment", lambda: state["environment"])
    monkeypatch.setattr(catalog, "get_ffxi_install", lambda: None)
    monkeypatch.setattr(catalog, "_collect_server_models", lambda server=None: calls.append(state["key"]) or {})

    assert catalog.build_catalog() == []
    assert catalog.build_catalog() == []
    assert calls == ["profile:1"]

    state["key"] = "profile:2"
    state["environment"] = {
        "profile_id": 2,
        "name": "Test",
        "environment": "test",
        "family": "lsb",
    }
    assert catalog.build_catalog() == []
    assert calls == ["profile:1", "profile:2"]
