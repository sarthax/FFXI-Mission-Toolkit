#!/usr/bin/env python3
"""Regression for the Development scripted-behavior visualizer service facade."""

from workbench.devtools.behavior import visualizer as canonical
from workbench.core.services import scripted_behavior_visualizer as service


def main() -> int:
    # Search/graph helpers remain direct compatibility exports from the canonical package.
    assert service.find_lsb_behavior_sources is canonical.find_lsb_behavior_sources
    assert service.find_behavior_sources_multi is canonical.find_behavior_sources_multi
    assert service._graph_for_behavior is canonical._graph_for_behavior

    # The service intentionally wraps inspection to attach the GUI Plain Behavior contract.
    assert service.inspect_lsb_behavior is not canonical.inspect_lsb_behavior
    assert service._inspect_lsb_behavior is canonical.inspect_lsb_behavior
    assert callable(service.build_plain_behavior_projection)
    assert "/devtools/behavior/visualizer.py" in canonical.__file__.replace("\\", "/")
    print("scripted behavior visualizer service facade self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
