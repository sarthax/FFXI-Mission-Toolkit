"""Service facade for the Development scripted-behavior visualizer.

The canonical extraction/graph implementation lives under ``workbench.devtools.behavior``.
This service adds the evidence-preserving Plain Behavior projection consumed by the GUI so the
browser and backend share one projection contract instead of independently re-implementing it.
"""
from workbench.devtools.behavior.visualizer import *  # noqa: F401,F403
from workbench.devtools.behavior.visualizer import _graph_for_behavior  # noqa: F401
from workbench.devtools.behavior.visualizer import inspect_lsb_behavior as _inspect_lsb_behavior
from workbench.devtools.behavior.plain_view import build_plain_behavior_projection


def inspect_lsb_behavior(root, relative):
    """Inspect behavior and attach the authoritative Plain Behavior projection to the graph."""
    result = _inspect_lsb_behavior(root, relative)
    graph = result.get("graph")
    if isinstance(graph, dict):
        graph["plain_behavior"] = build_plain_behavior_projection(graph)
    return result
