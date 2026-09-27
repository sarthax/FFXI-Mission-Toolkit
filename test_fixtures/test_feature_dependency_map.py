#!/usr/bin/env python3
"""Regression coverage for the Feature Trace dependency-map adapter and page contract."""
from pathlib import Path

from workbench.reference.absolute_virtue_demo import build_projection


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
    print("feature dependency map self-test: PASS")


if __name__=="__main__":
    main()
