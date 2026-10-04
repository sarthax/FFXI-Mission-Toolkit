"""Service facade for the Development scripted-behavior visualizer.

The canonical extraction/graph implementation lives under ``workbench.devtools.behavior``.
This service adds the evidence-preserving Plain Behavior projection consumed by the GUI so the
browser and backend share one projection contract instead of independently re-implementing it.
"""
from pathlib import Path

from workbench.devtools.behavior.visualizer import *  # noqa: F401,F403
from workbench.devtools.behavior.visualizer import _graph_for_behavior  # noqa: F401
from workbench.devtools.behavior.visualizer import inspect_lsb_behavior as _inspect_lsb_behavior
from workbench.devtools.behavior.plain_view import build_plain_behavior_projection
from workbench.devtools.behavior.source_branch_projection import apply_source_branch_evidence
from workbench.devtools.behavior.stage_transition_projection import apply_stage_transition_evidence


def inspect_lsb_behavior(root, relative):
    """Inspect behavior and attach the authoritative Plain Behavior projection to the graph."""
    result = _inspect_lsb_behavior(root, relative)
    graph = result.get("graph")
    if isinstance(graph, dict):
        projection = build_plain_behavior_projection(graph)
        # _inspect_lsb_behavior has already validated that ``relative`` resolves inside ``root``.
        # Re-read that exact selected source only to recover bounded literal guard -> event pairs
        # that the generic technical extractor intentionally keeps at hook scope.
        source_path = (Path(root).resolve() / str(relative).replace("\\", "/")).resolve()
        try:
            source_path.relative_to(Path(root).resolve())
            lua = source_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            lua = ""
        if lua:
            projection = apply_source_branch_evidence(projection, graph, lua)
            projection = apply_stage_transition_evidence(projection, lua)
        graph["plain_behavior"] = projection
    return result
