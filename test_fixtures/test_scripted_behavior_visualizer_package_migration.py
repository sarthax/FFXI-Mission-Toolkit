#!/usr/bin/env python3
"""Regression for the Development scripted-behavior visualizer move."""

from workbench.devtools.behavior import visualizer as canonical
from workbench.core.services import scripted_behavior_visualizer as legacy


def main() -> int:
    assert legacy.inspect_lsb_behavior is canonical.inspect_lsb_behavior
    assert legacy.find_lsb_behavior_sources is canonical.find_lsb_behavior_sources
    assert legacy.find_behavior_sources_multi is canonical.find_behavior_sources_multi
    assert legacy._graph_for_behavior is canonical._graph_for_behavior
    assert "/devtools/behavior/visualizer.py" in canonical.__file__.replace("\\", "/")
    print("scripted behavior visualizer package migration self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
