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
    assert "path.nodeIds.has(el.dataset.id)" in script
    assert "path-active" in script
    assert "path-dim" in script
    assert "Selected causal chain:" in script
    assert "MutationObserver" in script


def test_behavior_node_inspector_stays_visible_beside_graph():
    script = (ROOT / "gui" / "static" / "behavior_graph_interactions.js").read_text(encoding="utf-8")

    assert "behavior-workspace" in script
    assert "grid-template-columns:minmax(0,1fr) minmax(320px,380px)" in script
    assert "behavior-inspector-pane" in script
    assert "Selected behavior inspector" in script
    assert "pane.appendChild(detail)" in script
    assert "overflow:auto;flex:1" in script
    assert "behavior-inspector-toggle" in script
    assert "inspector-collapsed" in script
    assert "@media(max-width:1000px)" in script


def test_plain_behavior_is_default_and_preserves_technical_graph():
    script = (ROOT / "gui" / "static" / "behavior_graph_interactions.js").read_text(encoding="utf-8")

    assert "let mode = 'plain'" in script
    assert "Plain Behavior" in script
    assert "Technical Graph" in script
    assert "setMode('plain')" in script
    assert "function renderPlain()" in script
    assert "function humanHook(node)" in script
    assert "function humanNode(node)" in script
    assert "function laneFor(node, edge = null)" in script
    for label in ("Trigger", "Requirements", "Actions / Events", "Results / State Changes"):
        assert label in script
    assert "Player interacts with this actor" in script
    assert "Play cutscene / event" in script
    assert "Update character progress" in script
    assert "Open technical graph" in script
    assert "data-plain-node" in script
