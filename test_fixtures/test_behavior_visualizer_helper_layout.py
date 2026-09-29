#!/usr/bin/env python3
"""Regression for Behavior Inspector shared-helper causal column ordering."""
from __future__ import annotations

from pathlib import Path
import re


TEMPLATE=Path("gui/templates/behavior_visualizer.html")


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
        "if(n.kind==='helper_effect' || n.kind==='helper_call') return 5;"
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

    print("Behavior Inspector helper impact layout regression: PASS")


if __name__=="__main__":
    main()
