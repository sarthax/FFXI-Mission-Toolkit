#!/usr/bin/env python3
"""Regression coverage for the Feature Trace dependency-map adapter and page contract."""
from pathlib import Path
from tempfile import TemporaryDirectory

from workbench.reference.absolute_virtue_demo import build_projection
from workbench.reference import seed_runtime_reference_graphs
from workbench.core import graph
from workbench.core.services.obtainability_closure import build_obtainability_closure, resolve_obtainability_root
from workbench.core.services.feature_trace_closure import build_feature_trace_closure
from workbench.core.services.dependency_map_presentation import direct_dependencies, path_from_root, visible_nodes


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
    for label in ("Progression","Acquisition","Spawn","Access","Expand all","Expand selected branch","Collapse selected branch","Collapse to root","Toggle selected branch","Reset node positions"):
        assert label in template,label
    assert "/features/trace/closure.json" in template
    assert "REQUIREMENT_GATE" in template
    assert "Canonical root" in template
    assert "closure-scene" in template  # pan/zoom scene, not a static grid
    assert "marker-end:url(#closure-arrow)" in template
    assert "e.preventDefault()" in template
    assert "select(el.dataset.node)" in template
    assert "presentation?.initial_expanded" in template
    assert "data-branch" in template  # explicit per-node expand/collapse affordance
    assert "path-edge" in template and "cross-edge" in template
    assert "normalizeProjection" in template
    assert "e.source_node===id" in template  # normalized closure direction drives expansion
    assert "shown.has(e.source_node)" in template  # normalized fields also drive SVG edge rendering
    assert "pos[e.source_node]" in template
    assert "graph.edges.filter(e=>e.target_node===id)" in template  # selection follows dependent links as well as prerequisites
    assert "prerequisites=walk" in template and "dependents=walk" in template
    assert "manualPositions" in template  # user adjustments are presentation state
    assert "nodeDragging" in template
    assert "getBBox()" in template  # drag begins from the rendered node position
    assert "entity:av" not in template  # no fixture-specific renderer behavior
    gui_source=(ROOT/"src"/"workbench"/"app"/"_host_impl.py").read_text(encoding="utf-8")
    assert "build_feature_trace_closure(con, root)" in gui_source

    # The running GUI seeds registered reference bundles into its canonical graph and
    # resolves the human selection before traversal.  This guards against falling back
    # to an UNRESOLVED node named after the label.
    with TemporaryDirectory() as tmp:
        con=graph.init_db(Path(tmp)/"runtime.db")
        bundles=seed_runtime_reference_graphs(con)
        # A raw observed entity may share a human label with the dependency root.
        # The generic resolver must choose the only candidate with prerequisites.
        con.execute("INSERT INTO entities VALUES (?,?,?,?)",("npc:fixture-av","NPC","Absolute Virtue","{}"))
        con.commit()
        root=resolve_obtainability_root(con,"Absolute Virtue")
        assert root=="entity:av"
        closure=build_obtainability_closure(con,root,relationships=bundles[0]["relationships"])
        assert not any(entry["node_id"]==root for entry in closure["unresolved"])
        assert {"entity:jol","item:fourth","item:fifth","item:sixth","mob:justice","mob:hope","mob:prudence","zone:sea","mission:cop"} <= {node["node_id"] for node in closure["nodes"]}
        assert {"SPAWNED_BY","REQUIRES_ITEMS","OBTAINED_FROM","REQUIRES_ACCESS","REQUIRES_MISSION"} <= {edge["relationship"] for edge in closure["edges"]}
        assert any(edge["source_node"]=="entity:av" and edge["target_node"]=="entity:jol" and edge["relationship"]=="SPAWNED_BY" for edge in closure["edges"])
        assert any(edge["source_node"]=="entity:jol" and edge["target_node"]=="item:fifth" and edge["relationship"]=="REQUIRES_ITEMS" for edge in closure["edges"])
        assert not any(edge["source_node"]=="entity:jol" and edge["target_node"]=="entity:av" for edge in closure["edges"])
        assert closure["cycles"]  # the explicitly declared reference cycle still survives traversal
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
        # Progressive disclosure is presentation-only: root expansion shows JoL but not
        # the whole closure; expanding JoL fans out its three sibling Virtues.
        initial=set(payload["presentation"]["initial_visible_nodes"])
        assert {"entity:av","entity:jol"} <= initial
        assert "item:fifth" not in initial
        assert "entity:jol" in direct_dependencies(payload,"entity:av")
        expanded={payload["root"],"entity:jol"}
        branched=visible_nodes(payload,expanded)
        assert {"item:fourth","item:fifth","item:sixth"} <= branched
        assert "mob:hope" not in branched
        collapsed=visible_nodes(payload,{payload["root"]})
        assert "entity:jol" in collapsed and "item:fifth" not in collapsed
        path_nodes,path_edges=path_from_root(payload,"mob:hope")
        assert {"entity:av","entity:jol","item:fifth","mob:hope"} <= path_nodes
        assert path_edges
    print("feature dependency map self-test: PASS")


if __name__=="__main__":
    main()
