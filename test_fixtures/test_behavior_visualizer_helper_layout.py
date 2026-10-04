#!/usr/bin/env python3
"""Regression for Behavior Inspector helper layout and branch-preserving presentation."""
from __future__ import annotations

from pathlib import Path
import re

from test_fixtures.test_behavior_branch_flow_projection import main as branch_flow_main
from test_fixtures.test_behavior_stage_transition_projection import main as stage_transition_main


TEMPLATE=Path("gui/templates/behavior_visualizer.html")
WRAPPER=Path("gui/static/behavior_graph_interactions.js")


def main():
    text=TEMPLATE.read_text(encoding="utf-8")
    match=re.search(
        r"function depthFor\(n\)\{(?P<body>.*?)\n \}",
        text,
        flags=re.DOTALL,
    )
    assert match, "depthFor() not found in Behavior Inspector template"
    body=match.group("body")

    assert (
        "if(n.kind==='condition' || n.kind==='helper_input') return 0;"
        in body
    ),body
    assert "if(n.kind==='shared_helper') return 4;" in body,body
    assert (
        "if(n.kind==='helper_effect' || n.kind==='helper_call' || n.kind==='shared_helper_callee') return 5;"
        in body
    ),body
    assert "if(n.kind==='target') return 6;" in body,body

    x_match=re.search(r"const x=\{([^}]+)\}",text)
    assert x_match,"layout x-column map missing"
    pairs=dict(
        (int(k),int(v))
        for k,v in re.findall(r"(\d+):(\d+)",x_match.group(1))
    )
    assert pairs[0] < pairs[4] < pairs[5] < pairs[6],pairs

    wrapper=WRAPPER.read_text(encoding="utf-8")
    assert "branch_tree_v1" in wrapper,wrapper
    assert "plain-branch-tree" in wrapper,wrapper
    assert "Event lifecycle" in wrapper,wrapper
    assert "same literal event identity" in wrapper,wrapper
    assert "UNPROVEN" in wrapper,wrapper
    assert "runtime ordering remains unproven" in wrapper,wrapper

    branch_flow_main()
    stage_transition_main()
    print("Behavior Inspector helper impact layout regression: PASS")


if __name__=="__main__":
    main()
