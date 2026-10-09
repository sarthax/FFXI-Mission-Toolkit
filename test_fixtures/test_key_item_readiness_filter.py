"""Key Items full-catalog readiness browsing contracts."""
from pathlib import Path


def test_key_items_readiness_filter_precedes_pagination():
    host = Path("src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    route = host.split('def keyitems(request: Request, q:', 1)[1].split('@app.get("/keyitems/lua-references.json")', 1)[0]
    assert 'readiness: str = "all"' in route
    assert 'if readiness != "all":' in route
    assert 'resolve_keyitem_readiness(' in route
    assert 'candidates[offset:offset + KEYITEMS_PAGE_SIZE]' in route
    assert 'page = min(page, total_pages)' in route
    assert '"readiness_filter": readiness' in route
    assert '"readiness": item_readiness' in route


def test_key_items_search_and_pagination_preserve_global_filter():
    page = Path("gui/templates/keyitems.html").read_text(encoding="utf-8")
    assert 'name="readiness" id="ki-global-readiness"' in page
    assert 'name="readiness" value="{{ readiness_filter }}"' in page
    assert page.count("readiness={{ readiness_filter|urlencode }}") == 2
    assert "filters all matching records before pagination" in page


def test_key_items_search_supports_exact_numeric_ids():
    host = Path("src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    section = host.split('def keyitems(request: Request, q:', 1)[1].split('@app.get("/keyitems/lua-references.json")', 1)[0]
    assert "q.isascii() and q.isdecimal()" in section
    assert '(name LIKE ? OR keyitem_id = ?)' in section
    assert '(*args, KEYITEMS_PAGE_SIZE, offset)' in section
    assert 'predicate + " ORDER BY name"' in section
