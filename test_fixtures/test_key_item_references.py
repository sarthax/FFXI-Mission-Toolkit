"""Regression coverage for conservative key-item source reference discovery."""
from pathlib import Path

import pytest

from workbench.devtools.features.key_item_references import discover_key_item_references


def test_scoped_key_item_discovery_and_source_lines(tmp_path: Path):
    script = tmp_path / "scripts" / "zones" / "Test" / "npcs" / "Test.lua"
    script.parent.mkdir(parents=True)
    script.write_text(
        "player:hasKeyItem(xi.keyItem.TEST_KEY)\n"
        "player:addKeyItem(xi.keyItem.TEST_KEY)\n"
        "-- player:delKeyItem(xi.keyItem.TEST_KEY)\n"
        "player:delKeyItem(xi.keyItem.OTHER_KEY)\n"
        "npcUtil.giveKeyItem(player, xi.keyItem.TEST_KEY)\n",
        encoding="utf-8",
    )
    result = discover_key_item_references(tmp_path, "TEST_KEY")
    assert [r["operation"] for r in result["references"]] == ["require", "grant", "grant"]
    assert [r["source_line"] for r in result["references"]] == [1, 2, 5]
    assert result["references"][0]["source_path"] == "scripts/zones/Test/npcs/Test.lua"
    assert result["truncated"] is False
    assert result["matched_scripts"] == 1
    assert result["operation_counts"] == {"require": 1, "grant": 2, "remove": 0}


def test_key_item_discovery_limits_and_validation(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "a.lua").write_text("player:addKeyItem(tpz.ki.TEST_KEY)\n"
                                    "player:delKeyItem(tpz.ki.TEST_KEY)\n", encoding="utf-8")
    result = discover_key_item_references(tmp_path, "TEST_KEY", max_matches=1)
    assert len(result["references"]) == 1
    assert result["truncated"] is True
    with pytest.raises(ValueError):
        discover_key_item_references(tmp_path, "../../test")
    with pytest.raises(ValueError):
        discover_key_item_references(tmp_path, "TEST_KEY", max_matches=0)


def test_missing_scripts_directory_is_explicit(tmp_path: Path):
    result = discover_key_item_references(tmp_path, "TEST_KEY")
    assert result["references"] == []
    assert result["limitations"]


def test_key_item_discovery_respects_lineage_namespace(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "mixed.lua").write_text(
        "player:addKeyItem(xi.keyItem.TEST_KEY)\n"
        "player:addKeyItem(tpz.ki.TEST_KEY)\n", encoding="utf-8"
    )
    lsb = discover_key_item_references(tmp_path, "TEST_KEY", lineage="lsb")
    topaz = discover_key_item_references(tmp_path, "TEST_KEY", lineage="topaz")
    assert len(lsb["references"]) == 1
    assert len(topaz["references"]) == 1
    assert "xi.keyItem" in lsb["references"][0]["source_text"]
    assert "tpz.ki" in topaz["references"][0]["source_text"]
    with pytest.raises(ValueError):
        discover_key_item_references(tmp_path, "TEST_KEY", lineage="unverified")


def test_per_call_namespace_and_legacy_constant_form(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "mixed.lua").write_text(
        "player:addKeyItem(xi.keyItem.TEST_KEY); player:delKeyItem(tpz.ki.TEST_KEY)\n"
        "npcUtil.giveKeyItem(player, tpz.keyItem.TEST_KEY)\n"
        "player:addKeyItem(xi.keyItem.TEST_KEY_SUFFIX)\n"
        "-- player:addKeyItem(tpz.ki.TEST_KEY)\n", encoding="utf-8"
    )
    lsb = discover_key_item_references(tmp_path, "TEST_KEY", lineage="lsb")
    topaz = discover_key_item_references(tmp_path, "TEST_KEY", lineage="topaz")
    assert [r["operation"] for r in lsb["references"]] == ["grant"]
    assert [r["operation"] for r in topaz["references"]] == ["remove", "grant"]
    assert [r["namespace"] for r in topaz["references"]] == ["tpz.ki", "tpz.keyItem"]
    assert all(r["source_line"] < 4 for r in topaz["references"])


def test_missing_checkout_has_empty_summary(tmp_path: Path):
    result = discover_key_item_references(tmp_path, "TEST_KEY", lineage="lsb")
    assert result["matched_scripts"] == 0
    assert result["operation_counts"] == {"require": 0, "grant": 0, "remove": 0}


def test_external_symlink_is_not_scanned(tmp_path: Path):
    checkout = tmp_path / "checkout"
    scripts = checkout / "scripts"
    scripts.mkdir(parents=True)
    outside = tmp_path / "outside.lua"
    outside.write_text("player:addKeyItem(xi.keyItem.TEST_KEY)\n", encoding="utf-8")
    try:
        (scripts / "alias.lua").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    result = discover_key_item_references(checkout, "TEST_KEY", lineage="lsb")
    assert result["references"] == []
    assert any("symlink" in limitation for limitation in result["limitations"])


def test_lua_source_cache_invalidation(tmp_path: Path):
    from workbench.devtools.features.key_item_references import _read_lua_lines
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    target = scripts / "changing.lua"
    target.write_text("player:addKeyItem(xi.keyItem.TEST_KEY)\n", encoding="utf-8")
    _read_lua_lines.cache_clear()
    first = discover_key_item_references(tmp_path, "TEST_KEY", lineage="lsb")
    assert [r["operation"] for r in first["references"]] == ["grant"]
    hits_before = _read_lua_lines.cache_info().hits
    second = discover_key_item_references(tmp_path, "TEST_KEY", lineage="lsb")
    assert second["references"] == first["references"]
    assert _read_lua_lines.cache_info().hits > hits_before
    target.write_text("player:delKeyItem(xi.keyItem.TEST_KEY)\n", encoding="utf-8")
    import os
    stat = target.stat()
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000000))
    third = discover_key_item_references(tmp_path, "TEST_KEY", lineage="lsb")
    assert [r["operation"] for r in third["references"]] == ["remove"]


def test_lua_symbol_index_reuses_parsing_and_refreshes_after_edit(tmp_path: Path):
    from workbench.devtools.features.key_item_references import _indexed_lua_lines
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    target = scripts / "many.lua"
    target.write_text(
        "player:addKeyItem(xi.keyItem.TEST_KEY)\n"
        "player:hasKeyItem(xi.keyItem.OTHER_KEY)\n", encoding="utf-8"
    )
    _indexed_lua_lines.cache_clear()
    one = discover_key_item_references(tmp_path, "TEST_KEY", lineage="lsb")
    hits = _indexed_lua_lines.cache_info().hits
    two = discover_key_item_references(tmp_path, "OTHER_KEY", lineage="lsb")
    assert _indexed_lua_lines.cache_info().hits > hits
    assert [r["operation"] for r in one["references"]] == ["grant"]
    assert [r["operation"] for r in two["references"]] == ["require"]
    target.write_text("player:delKeyItem(xi.keyItem.TEST_KEY)\n", encoding="utf-8")
    import os
    stat = target.stat()
    os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000000))
    updated = discover_key_item_references(tmp_path, "TEST_KEY", lineage="lsb")
    assert [r["operation"] for r in updated["references"]] == ["remove"]


def test_dsp_direct_global_key_item_symbols_are_scoped_to_dsp(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "npc.lua").write_text(
        "if player:hasKeyItem(ZERUHN_REPORT) then\n"
        "    player:addKeyItem(ZERUHN_REPORT)\n"
        "    player:delKeyItem(ZERUHN_REPORT)\n"
        "    npcUtil.giveKeyItem(player, ZERUHN_REPORT)\n"
        "    player:addKeyItem(tpz.ki.ZERUHN_REPORT)\n"
        "end\n", encoding="utf-8"
    )
    dsp = discover_key_item_references(tmp_path, "ZERUHN_REPORT", lineage="dsp")
    assert dsp["operation_counts"] == {"require": 1, "grant": 3, "remove": 1}
    assert {r["namespace"] for r in dsp["references"]} == {"dsp.global", "tpz.ki"}
    assert discover_key_item_references(tmp_path, "ZERUHN_REPORT", lineage="lsb")["references"] == []
    topaz = discover_key_item_references(tmp_path, "ZERUHN_REPORT", lineage="topaz")
    assert len(topaz["references"]) == 1


def test_dsp_lua_block_comments_do_not_create_false_dependencies(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "npc.lua").write_text(
        "--[[\n"
        "player:addKeyItem(ZERUHN_REPORT)\n"
        "]]\n"
        "player:hasKeyItem(ZERUHN_REPORT) -- inline comment\n"
        "--[[ player:delKeyItem(ZERUHN_REPORT) ]]\n"
        "player:addKeyItem(ZERUHN_REPORT)\n", encoding="utf-8"
    )
    result = discover_key_item_references(tmp_path, "ZERUHN_REPORT", lineage="dsp")
    assert result["operation_counts"] == {"require": 1, "grant": 1, "remove": 0}
    assert [ref["source_line"] for ref in result["references"]] == [4, 6]


def test_dsp_block_comment_can_end_before_real_source_call(tmp_path: Path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "npc.lua").write_text(
        "--[[ ignored player:addKeyItem(ZERUHN_REPORT) ]] player:delKeyItem(ZERUHN_REPORT)\n",
        encoding="utf-8",
    )
    result = discover_key_item_references(tmp_path, "ZERUHN_REPORT", lineage="dsp")
    assert [r["operation"] for r in result["references"]] == ["remove"]
