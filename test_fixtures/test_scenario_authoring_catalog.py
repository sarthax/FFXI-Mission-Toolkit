"""Synthetic, offline tests for read-only scenario catalog candidate discovery.

These synthetic Lua/SQL rows are not retail/client/server evidence.
"""
from pathlib import Path

import pytest

from workbench.server_admin.scenario_authoring import catalog_adapter as adapter


@pytest.fixture
def fake_dsp(tmp_path: Path) -> Path:
    (tmp_path / "sql").mkdir()
    (tmp_path / "scripts" / "globals").mkdir(parents=True)
    (tmp_path / "scripts" / "commands").mkdir()
    (tmp_path / "sql" / "item_basic.sql").write_text(
        "INSERT INTO `item_basic` VALUES (420,0,'synthetic_item');\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "globals" / "keyitems.lua").write_text(
        "SYNTHETIC_KEY = 70;\nSYNTHETIC_ALT_KEY = 70;\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "commands" / "getmobaction.lua").write_text(
        "-- desc: synthetic diagnostic sample\n"
        "cmdprops = { permission = 2, parameters = \"i\" }\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "commands" / "additem.lua").write_text(
        "-- desc: synthetic mutating sample\n"
        "cmdprops = { permission = 2, parameters = \"i\" }\n",
        encoding="utf-8",
    )
    return tmp_path


def test_id_candidate_is_source_only_and_never_executable(fake_dsp: Path):
    result = adapter.search_catalog(fake_dsp, "item", "420")
    assert result["binding_verified"] is False
    assert result["execution_enabled"] is False
    assert result["source_revision"] is None
    assert result["source_lineage"] == "configured_local_dsp"
    assert len(result["choices"]) == 1
    candidate = result["choices"][0]
    assert candidate["id"] == 420  # from synthetic SQL, not fabricated by adapter
    assert candidate["name"] == "synthetic item"
    assert candidate["source_path"] == "sql/item_basic.sql"
    assert candidate["identity_status"] == "unreconciled_source_candidate"
    assert candidate["operator_review_required"] is True
    assert str(fake_dsp) not in str(result)


def test_duplicate_source_ids_remain_visible_as_ambiguous(fake_dsp: Path):
    result = adapter.search_catalog(fake_dsp, "keyitem", "synthetic")
    assert len(result["choices"]) == 2
    assert [x["id"] for x in result["choices"]] == [70, 70]
    assert all(x["duplicate_id_in_results"] for x in result["choices"])
    assert all(not x["binding_verified"] for x in result["choices"])


def test_gm_diagnostic_label_never_grants_permission(fake_dsp: Path):
    result = adapter.search_catalog(fake_dsp, "gm", "getmobaction")
    assert len(result["choices"]) == 1
    candidate = result["choices"][0]
    assert candidate["catalog_classification"] == "diagnostic_candidate"
    assert candidate["permission_declared"] == 2
    assert candidate["execution_enabled"] is False
    assert candidate["operator_review_required"] is True
    assert candidate["source_path"] == "scripts/commands/getmobaction.lua"
    assert not any(k in candidate for k in ("command", "usage", "params", "preview", "dispatch"))


def test_mutating_gm_catalog_record_cannot_create_action(fake_dsp: Path):
    result = adapter.search_catalog(fake_dsp, "gm", "additem")
    assert len(result["choices"]) == 1
    assert result["choices"][0]["catalog_classification"] == "unreviewed"
    assert result["choices"][0]["execution_enabled"] is False
    assert "!" not in str(result)


@pytest.mark.parametrize("kind", ["quest", "mission", "csid", "event", "trace", "../etc"])
def test_unscoped_or_unsupported_identity_kind_is_rejected(fake_dsp: Path, kind: str):
    with pytest.raises(ValueError, match="unsupported"):
        adapter.search_catalog(fake_dsp, kind, "example")


@pytest.mark.parametrize("query,limit", [
    ("", 20), (" \t ", 20), ("valid\ninvalid", 20),
    ("x" * 65, 20), ("valid", 0), ("valid", True), ("valid", 51),
])
def test_invalid_search_input_fails_closed(fake_dsp: Path, query: str, limit: int):
    with pytest.raises(ValueError):
        adapter.search_catalog(fake_dsp, "item", query, limit=limit)


def test_unavailable_server_source_is_not_reported_as_empty_catalog(tmp_path: Path):
    with pytest.raises(adapter.CatalogUnavailable, match="unavailable"):
        adapter.search_catalog(tmp_path / "not-configured", "item", "anything")
    with pytest.raises(adapter.CatalogUnavailable, match="unavailable"):
        adapter.search_catalog(tmp_path / "not-configured", "gm", "anything")


def test_bad_provider_row_is_not_accepted(monkeypatch, fake_dsp: Path):
    monkeypatch.setattr(adapter, "lookup", lambda *a, **kw: [{"id": True, "name": "bogus"}])
    with pytest.raises(adapter.CatalogUnavailable, match="invalid identifier"):
        adapter.search_catalog(fake_dsp, "item", "bogus")


def test_absent_match_returns_only_an_explicit_unverified_empty_query(fake_dsp: Path):
    result = adapter.search_catalog(fake_dsp, "keyitem", "not-in-fixture")
    assert result["choices"] == []
    assert result["completeness"] == "bounded_catalog_query_not_full_inventory"
    assert result["binding_verified"] is False
