from pathlib import Path
from workbench.devtools.features.key_item_persistent_index import query_index


def test_persistent_index_reuses_and_refreshes_source(tmp_path: Path):
    root = tmp_path / "dsp"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    source = scripts / "npc.lua"
    cache = tmp_path / "cache" / "refs.sqlite"
    source.write_text("player:addKeyItem(ZERUHN_REPORT)\n", encoding="utf-8")
    one = query_index(root, cache, "ZERUHN_REPORT")
    assert one["operation_counts"]["grant"] == 1
    assert one["reindexed_files"] == 1
    assert cache.exists()
    two = query_index(root, cache, "ZERUHN_REPORT")
    assert two["reindexed_files"] == 0
    source.write_text("player:delKeyItem(ZERUHN_REPORT)\n", encoding="utf-8")
    import os
    st = source.stat()
    os.utime(source, ns=(st.st_atime_ns, st.st_mtime_ns + 1000000000))
    three = query_index(root, cache, "ZERUHN_REPORT")
    assert three["operation_counts"] == {"require": 0, "grant": 0, "remove": 1}
    assert three["reindexed_files"] == 1
    source.unlink()
    four = query_index(root, cache, "ZERUHN_REPORT")
    assert four["references"] == []


def test_persistent_index_isolates_roots_and_lineages(tmp_path: Path):
    cache = tmp_path / "refs.sqlite"
    first, second = tmp_path / "first", tmp_path / "second"
    for root in (first, second):
        (root / "scripts").mkdir(parents=True)
    (first / "scripts" / "a.lua").write_text(
        "player:addKeyItem(ZERUHN_REPORT)\n", encoding="utf-8")
    (second / "scripts" / "b.lua").write_text(
        "player:hasKeyItem(xi.keyItem.ZERUHN_REPORT)\n", encoding="utf-8")
    assert len(query_index(first, cache, "ZERUHN_REPORT", lineage="dsp")["references"]) == 1
    assert query_index(first, cache, "ZERUHN_REPORT", lineage="lsb")["references"] == []
    assert len(query_index(second, cache, "ZERUHN_REPORT", lineage="lsb")["references"]) == 1
    assert query_index(second, cache, "ZERUHN_REPORT", lineage="dsp")["references"] == []


def test_persistent_index_never_writes_into_source_root(tmp_path: Path):
    root = tmp_path / "dsp"
    (root / "scripts").mkdir(parents=True)
    import pytest
    with pytest.raises(ValueError):
        query_index(root, root / "index.sqlite", "ZERUHN_REPORT")


def test_dsp_lookup_uses_persistent_index():
    host = Path("src/workbench/app/_host_impl.py").read_text(encoding="utf-8")
    lookup = host.split("def keyitems_lua_references(", 1)[1].split("ZONE_BROWSE_PAGE_SIZE", 1)[0]
    assert 'key_item_persistent_index import query_index' in lookup
    assert 'key_item_lua_refs.sqlite' in lookup
