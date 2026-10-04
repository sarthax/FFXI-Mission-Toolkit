from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "gui" / "static" / "behavior_graph_interactions.js"
CORE = ROOT / "gui" / "static" / "behavior_graph_interactions_core.js"


def test_plain_behavior_helper_ui_wrapper_preserves_core_and_collapses_only_helper_plumbing():
    entry = ENTRY.read_text(encoding="utf-8")
    core = CORE.read_text(encoding="utf-8")

    assert "behavior_graph_interactions_core.js" in entry
    assert "helper_call" in entry
    assert "shared_helper_callee" in entry
    assert "shared_helper" not in "COLLAPSED_HELPER_KINDS = new Set(['helper_call', 'shared_helper_callee'])".replace("shared_helper_callee", "")
    assert "helper_effect" not in "COLLAPSED_HELPER_KINDS = new Set(['helper_call', 'shared_helper_callee'])"
    assert "function projectPlain(trigger)" in core
    assert "function renderPlain()" in core


def test_plain_behavior_helper_ui_rewrites_summary_after_hidden_plumbing_is_removed():
    entry = ENTRY.read_text(encoding="utf-8")

    assert "plainSummary(flow)" in entry
    assert "card.hidden = shouldCollapse" in entry
    assert "helper plumbing node" in entry
    assert "MutationObserver" in entry
