"""Synthetic tests for exact-root, read-only Feature Trace P0 export.

No actual client DAT, DSP server, capture, production DB or private root is opened.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import export_feature_trace_relevance as exporter
import audit_feature_trace_campaign as campaign
from workbench.core import graph


def _databases(tmp_path: Path):
    graph_path = tmp_path / "workbench.db"
    catalog_path = tmp_path / "synthetic_catalog.db"
    con = graph.init_db(graph_path)
    con.execute("INSERT INTO entities VALUES (?,?,?,?)",
                ("mob:synthetic", "MOB", "Synthetic Mob", "{}"))
    con.execute("INSERT INTO entities VALUES (?,?,?,?)",
                ("mob:other", "MOB", "Synthetic Other", "{}"))
    con.execute(
        "INSERT INTO entity_relationships VALUES (?,?,?,?,?,?,?,?,?)",
        ("relationship:fixture", "mob:synthetic", "mob:other", "SPAWN_USES_GROUP",
         None, "VERIFIED", "DISCOVERED", '{"synthetic":true}', "fixture:snapshot"),
    )
    con.commit()
    con.close()
    sqlite3.connect(catalog_path).close()
    return graph_path, catalog_path


def test_existing_databases_are_strictly_read_only(tmp_path):
    graph_path, catalog_path = _databases(tmp_path)
    graph_con = exporter.open_readonly(graph_path)
    catalog_con = exporter.open_readonly(catalog_path)
    try:
        assert graph_con.execute("SELECT COUNT(*) FROM entities").fetchone()[0] == 2
        with pytest.raises(sqlite3.OperationalError):
            graph_con.execute("DELETE FROM entities")
        with pytest.raises(sqlite3.OperationalError):
            catalog_con.execute("CREATE TABLE synthetic_mutation (id INTEGER)")
    finally:
        catalog_con.close()
        graph_con.close()
    with pytest.raises(FileNotFoundError):
        exporter.open_readonly(tmp_path / "nonexistent.db")


def test_actual_trace_facade_keeps_source_relationship_in_export(tmp_path):
    from workbench.devtools.features import trace
    graph_path, catalog_path = _databases(tmp_path)
    graph_con = exporter.open_readonly(graph_path)
    catalog_con = exporter.open_readonly(catalog_path)
    try:
        out = exporter.collect(
            graph_con, catalog_con, case_id="absolute-virtue",
            root="mob:synthetic", depth=1, service=trace,
        )
    finally:
        graph_con.close()
        catalog_con.close()
    assert out["root"] == "mob:synthetic"  # Synthetic exact ID, NOT a real AV ID.
    assert out["mode"] == "implementation"
    assert out["root_kind"] == "entity"
    assert "relationship:fixture" in out["edge_audit_ids"]
    assert "SPAWN_USES_GROUP" in {edge["relationship"] for edge in out["edges"]}
    assert out["depth"] == 1 and out["max_nodes"] == 500
    assert "initial_edge_ids" not in out
    assert "source_review_required" not in out
    assert out["evidence_boundary"].startswith("Read-only")
    # Campaign scorer must accept the *real exporter format* without weakening
    # identity or evidence checks when either tool evolves independently.
    bound = campaign.validate_export_binding(
        out, case_id="absolute-virtue", root_id="mob:synthetic",
        mode="implementation", root_kind="entity",
    )
    assert bound["export_edge_count"] == len(out["edges"])
    assert bound["export_truncated"] is False


def _synthetic_service(*, kind="entity", identity=True, edges=None, representations=None):
    captured = []
    def node_info(*_args):
        return {
            "known": identity, "node_id": "mob:synthetic",
            "representations": representations if representations is not None
            else [{"node_id": "mob:synthetic", "node_type": "MOB"}],
        }
    def trace(*args, **kwargs):
        captured.append((args, kwargs))
        return {
            "root": "mob:synthetic", "root_kind": kind,
            "trace_mode": {"id": kwargs["mode"]},
            "truncated": False, "edges": edges if edges is not None else [
                {"relationship_id": "synthetic-one",
                 "source_node": "mob:synthetic", "target_node": "mob:other",
                 "relationship": "SPAWN_USES_GROUP"}],
        }
    return SimpleNamespace(node_info=node_info, trace=trace, called=captured)


def test_exact_root_and_multiple_same_root_representations_allowed():
    service = _synthetic_service(representations=[
        {"node_id": "mob:synthetic", "table": "entities"},
        {"node_id": "mob:synthetic", "table": "server_catalog"},
    ])
    out = exporter.collect(None, None, case_id="ordinary-npc",
                           root="mob:synthetic", service=service)
    assert out["edge_audit_ids"] == ["synthetic-one"]
    assert service.called[0][1] == {"max_nodes": 500, "mode": "implementation"}


@pytest.mark.parametrize("root", ["", " ", "@mission synthetic", " mob:synthetic "])
def test_search_queries_do_not_get_promoted_to_exact_roots(root):
    service = _synthetic_service()
    with pytest.raises(ValueError):
        exporter.collect(None, None, case_id="ordinary-npc", root=root, service=service)
    assert not service.called


def test_unknown_or_conflicting_root_fails_closed():
    for service in (
        _synthetic_service(identity=False),
        _synthetic_service(representations=[]),
        _synthetic_service(representations=[{"node_id": "mob:other"}]),
    ):
        with pytest.raises(ValueError):
            exporter.collect(None, None, case_id="ordinary-npc",
                             root="mob:synthetic", service=service)
        assert not service.called


def test_wrong_case_kind_does_not_label_same_name_npc_as_mission():
    service = _synthetic_service(kind="entity")
    with pytest.raises(ValueError, match="kind"):
        exporter.collect(None, None, case_id="wotg-cait-sith",
                         root="mob:synthetic", service=service)
    assert service.called[0][1]["mode"] == "mission"


def test_duplicate_generated_edge_audit_identity_is_refused():
    edge = {"source_node": "mob:synthetic", "target_node": "mob:other",
            "relationship": "SPAWN_USES_GROUP", "generator": "synthetic",
            "evidence": [{"row": "synthetic"}]}
    service = _synthetic_service(edges=[edge, dict(edge)])
    with pytest.raises(ValueError, match="Duplicate edge"):
        exporter.collect(None, None, case_id="absolute-virtue",
                         root="mob:synthetic", service=service)


def test_private_export_is_outside_checkout_and_never_overwritten(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    outside = tmp_path / "reviewed-trace.json"
    exported = {"edges": [{"id": "synthetic"}]}
    with pytest.raises(ValueError, match="outside"):
        exporter.write_new(checkout / "captured.json", exported, repo=checkout)
    exporter.write_new(outside, exported, repo=checkout)
    assert json.loads(outside.read_text()) == exported
    with pytest.raises(FileExistsError):
        exporter.write_new(outside, exported, repo=checkout)


def test_depth_is_explicit_and_bounded():
    service = _synthetic_service()
    for value in (0, 3, -1, True):
        with pytest.raises(ValueError, match="depth"):
            exporter.collect(None, None, case_id="ordinary-npc",
                             root="mob:synthetic", depth=value, service=service)
    assert not service.called
