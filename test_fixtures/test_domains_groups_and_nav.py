"""Domains overview grouping and the toolbar workspace dropdowns (presentation only)."""
from pathlib import Path

from workbench.domains.groups import GROUPS, STATIC_ENTRIES, group_rows
from workbench.gui_shell import WORKSPACES

ROOT = Path(__file__).resolve().parents[1]


def _rows(*keys):
    return [{"key": k, "label": k.title(), "archetype": "x"} for k in keys]


def test_every_row_appears_exactly_once_and_unknown_keys_fall_back():
    groups = group_rows(_rows("abyssea", "brand_new_domain", "trust"))
    seen = [e["key"] for g in groups for e in g["entries"]]
    assert sorted(seen) == sorted(set(seen))
    assert {"abyssea", "trust", "brand_new_domain"} <= set(seen)
    other = next(g for g in groups if g["id"] == "other")
    assert [e["key"] for e in other["entries"]] == ["brand_new_domain"]


def test_static_tools_are_grouped_and_never_duplicated():
    groups = group_rows(_rows("assault", "nyzul"))
    keys = [e["key"] for g in groups for e in g["entries"]]
    assert keys.count("assault") == 1 and keys.count("nyzul") == 1
    calc = next(g for g in groups if g["id"] == "calculators")
    assert {e["href"] for e in calc["entries"]} == {
        "/tools/ws-calc", "/tools/magic-calc", "/tools/heal-calc", "/tools/pet-calc", "/tools/melee-calc"}


def test_group_ids_are_unique_and_keys_not_shared():
    ids = [g[0] for g in GROUPS]
    assert len(ids) == len(set(ids))
    keys = [k for g in GROUPS for k in g[3]]
    assert len(keys) == len(set(keys))


def test_domains_page_renders_groups_and_favorites_and_base_has_dropdowns():
    from fastapi.testclient import TestClient
    from workbench.app import host
    client = TestClient(host.app, client=("127.0.0.1", 50000))
    html = client.get("/domains").text
    assert 'id="dm-favorites"' in html and "data-group" in html and 'id="dm-filter"' in html
    assert html.count('class="ws-caret"') >= len([w for w in WORKSPACES if w.get("sections")])
    assert 'id="shell-nav-data"' in html and "/static/shell_nav.js" in html


def test_nav_and_favorites_scripts_guard_storage_and_wheel():
    fav = (ROOT / "gui/static/shell_favorites.js").read_text(encoding="utf-8")
    nav = (ROOT / "gui/static/shell_nav.js").read_text(encoding="utf-8")
    assert fav.count("try {") >= 2 and "localStorage" in fav
    assert '"wheel"' in nav and "passive: false" in nav
