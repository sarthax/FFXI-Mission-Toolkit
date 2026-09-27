#!/usr/bin/env python3
"""Regression coverage for the Feature Trace dependency-map adapter and page contract."""
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.reference.absolute_virtue_demo import build_projection
from workbench.reference import seed_runtime_reference_graphs
from workbench.core import graph
from workbench.core.services.obtainability_closure import build_obtainability_closure, resolve_obtainability_root
from workbench.core.services.feature_trace_closure import build_feature_trace_closure


ROOT=Path(__file__).resolve().parents[1]


def main():
    projection=build_projection()
    assert projection["root"]=="entity:av"
    assert projection["demo_name"]=="Absolute Virtue"
    assert any(node["node_type"]=="REQUIREMENT_GATE" for node in projection["nodes"])
    assert any(edge["relationship"]=="SPAWNED_BY" for edge in projection["edges"])
    assert any(edge["relationship"]=="REQUIRES_ACCESS" for edge in projection["edges"])
    assert any(edge["relationship"]=="OBTAINED_FROM" for edge in projection["edges"])
    assert projection["cycles"]
    assert projection["unresolved"]
    organ=next(edge for edge in projection["edges"] if edge.get("edge_id")=="organ-source")
    assert organ["metadata"]["probability"]==0.2
    assert organ["evidence_id"].startswith("evidence:demo:")

    template=(ROOT/"gui"/"templates"/"feature_trace.html").read_text(encoding="utf-8")
    for label in ("Progression","Acquisition","Spawn","Access","Expand visible","Collapse to root"):
        assert label in template,label
    assert "/features/trace/closure.json" in template
    assert "REQUIREMENT_GATE" in template
    assert "Canonical root" in template
    gui_source=(ROOT/"gui_server.py").read_text(encoding="utf-8")
    assert "build_feature_trace_closure(con, root)" in gui_source

    # The running GUI seeds registered reference bundles into its canonical graph and
    # resolves the human selection before traversal.  This guards against falling back
    # to an UNRESOLVED node named after the label.
    with TemporaryDirectory() as tmp:
        con=graph.init_db(Path(tmp)/"runtime.db")
        bundles=seed_runtime_reference_graphs(con)
        root=resolve_obtainability_root(con,"Absolute Virtue")
        assert root=="entity:av"
        closure=build_obtainability_closure(con,root,relationships=bundles[0]["relationships"])
        assert not any(entry["node_id"]==root for entry in closure["unresolved"])
        assert {"entity:jol","item:fourth","item:fifth","item:sixth","mob:justice","mob:hope","mob:prudence","zone:sea","mission:cop"} <= {node["node_id"] for node in closure["nodes"]}
        assert {"SPAWNED_BY","REQUIRES_ITEMS","OBTAINED_FROM","REQUIRES_ACCESS","REQUIRES_MISSION"} <= {edge["relationship"] for edge in closure["edges"]}
        con.close()

    # Exercise the service used directly by the Feature Trace endpoint with the human
    # selection.  It must seed runtime reference data, resolve the label, then traverse.
    with TemporaryDirectory() as tmp:
        runtime_db=Path(tmp)/"gui-runtime.db"
        con=graph.init_db(runtime_db)
        try:
            payload=build_feature_trace_closure(con,"Absolute Virtue")
        finally:
            con.close()
        assert payload["resolved_root"]=="entity:av"
        assert len(payload["nodes"]) > 10
        assert any(edge["relationship"]=="SPAWNED_BY" for edge in payload["edges"])
        assert any(edge["relationship"]=="REQUIRES_MISSION" for edge in payload["edges"])
        assert not any(entry["node_id"]=="entity:av" for entry in payload["unresolved"])
    print("feature dependency map self-test: PASS")


if __name__=="__main__":
    main()
