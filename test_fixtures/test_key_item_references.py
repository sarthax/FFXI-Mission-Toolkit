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
