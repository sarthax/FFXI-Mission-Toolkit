from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "gui" / "static" / "behavior_graph_interactions.js"
CORE = ROOT / "gui" / "static" / "behavior_graph_interactions_core.js"


def test_plain_view_core_still_builds_evidence_drilldown_and_technical_graph():
    core = CORE.read_text(encoding="utf-8")

    assert "function recoverRuleRequirements" in core
    assert "edge.kind !== 'GUARDS'" in core
    assert "item.node.kind === 'rule'" in core
    assert "collapsedRules += 1" in core
    assert "addPlainNode(lanes, seen, condition, edge)" in core
    assert "incoming.get(condition.id)" in core
    assert "data-plain-node" in core
    assert "selectPlainNode" in core
    assert "behavior-mode-technical" in core
    assert "setMode('technical')" in core
    assert "applyFocus()" in core
    assert "causalPath" in core


def test_plain_view_wrapper_consumes_backend_projection_contract():
    wrapper = WRAPPER.read_text(encoding="utf-8")

    assert "graph.plain_behavior" in wrapper
    assert "expected.trigger?.node_id" in wrapper
    assert "expected.requirements" in wrapper
    assert "expected.actions" in wrapper
    assert "expected.results" in wrapper
    assert "expected.collapsed_count" in wrapper
    assert "expected.summary" in wrapper
    assert "card.hidden = !visible.has(card.dataset.plainNode)" in wrapper
    assert "behavior_graph_interactions_core.js" in wrapper


def test_plain_view_wrapper_does_not_reimplement_helper_or_summary_semantics():
    wrapper = WRAPPER.read_text(encoding="utf-8")

    assert "COLLAPSED_HELPER_KINDS" not in wrapper
    assert "function plainSummary" not in wrapper
    assert "helper_call" not in wrapper
    assert "shared_helper_callee" not in wrapper
