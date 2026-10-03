from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_behavior_graph_interaction_layer_is_wired():
    template = (ROOT / "gui" / "templates" / "behavior_visualizer.html").read_text(encoding="utf-8")
    script = (ROOT / "gui" / "static" / "behavior_graph_interactions.js").read_text(encoding="utf-8")

    assert '/static/behavior_graph_interactions.js' in template
    assert "behavior-zoom-in" in script
    assert "behavior-zoom-out" in script
    assert "behavior-fit-view" in script
    assert "behavior-reset-view" in script
    assert "addEventListener('wheel'" in script
    assert "addEventListener('pointerdown'" in script
    assert "addEventListener('pointermove'" in script
    assert "setPointerCapture" in script
    assert "touch-action:none" in script


def test_behavior_graph_uses_directed_causal_path_focus():
    script = (ROOT / "gui" / "static" / "behavior_graph_interactions.js").read_text(encoding="utf-8")

    assert "function causalPath(id)" in script
    assert "walk(id, incoming, edge => edge.source)" in script
    assert "walk(id, outgoing, edge => edge.target)" in script
    assert "path.edgeIds.has(edgeKey(edge))" in script
    assert "path.nodeIds.has(element.dataset.id)" in script
    assert "path-active" in script
    assert "path-dim" in script
    assert "Selected causal chain:" in script
    assert "MutationObserver" in script
    assert "}, true);" in script  # capture node selection before the legacy renderer replaces the SVG subtree
