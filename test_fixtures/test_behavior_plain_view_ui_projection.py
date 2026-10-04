from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "gui" / "static" / "behavior_graph_interactions.js"


def test_plain_view_collapses_rule_scaffolding_and_recovers_guards():
    script = SCRIPT.read_text(encoding="utf-8")

    assert "function recoverRuleRequirements" in script
    assert "edge.kind !== 'GUARDS'" in script
    assert "item.node.kind === 'rule'" in script
    assert "collapsedRules += 1" in script
    assert "addPlainNode(lanes, seen, condition, edge)" in script
    assert "incoming.get(condition.id)" in script


def test_plain_view_keeps_evidence_drilldown_and_summary():
    script = SCRIPT.read_text(encoding="utf-8")

    assert "data-plain-node" in script
    assert "selectPlainNode" in script
    assert "function summarizePlain" in script
    assert "Internal rule scaffolding is collapsed" in script
    assert "internal rule${projection.collapsedRules === 1 ? '' : 's'} collapsed" in script
    assert "Open technical graph" in script


def test_plain_view_preserves_technical_graph_mode():
    script = SCRIPT.read_text(encoding="utf-8")

    assert "behavior-mode-technical" in script
    assert "setMode('technical')" in script
    assert "applyFocus()" in script
    assert "causalPath" in script
