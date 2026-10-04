from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "gui" / "static" / "behavior_graph_interactions.js"
CORE = ROOT / "gui" / "static" / "behavior_graph_interactions_core.js"


def test_plain_view_core_preserves_evidence_drilldown_and_technical_graph():
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


def test_clarified_flow_wrapper_renders_backend_branch_projection_without_replacing_plain():
    wrapper = WRAPPER.read_text(encoding="utf-8")

    assert "graph.plain_behavior" in wrapper
    assert "contract.branch_groups" in wrapper
    assert "contract.event_handoffs" in wrapper
    assert "behavior-clarified-view" in wrapper
    assert "behavior-mode-clarified" in wrapper
    assert "Clarified Flow" in wrapper
    assert "workspace.insertBefore(clarified, plain)" in wrapper
    assert "plainButton.parentElement.insertBefore(clarifiedButton, plainButton)" in wrapper
    assert "data-contract-node" in wrapper
    assert "originalButtons.get(String(nodeId))" in wrapper
    assert "behavior_graph_interactions_core.js" in wrapper


def test_clarified_flow_is_default_and_node_selection_keeps_it_active():
    wrapper = WRAPPER.read_text(encoding="utf-8")

    assert "activateClarified();" in wrapper
    assert "sourceButton.click();" in wrapper
    assert "queueMicrotask(activateClarified);" in wrapper
    assert "clarified.hidden = false" in wrapper
    assert "plain.hidden = true" in wrapper
    assert "canvasWrap.hidden = true" in wrapper
    assert "plainButton.addEventListener('click'" in wrapper
    assert "technicalButton.addEventListener('click'" in wrapper


def test_clarified_event_handoffs_jump_to_clarified_branches_not_technical_nodes():
    wrapper = WRAPPER.read_text(encoding="utf-8")

    assert "data-contract-branch" in wrapper
    assert "focusBranch" in wrapper
    assert "button.dataset.contractBranch" in wrapper
    assert "branch.dataset.branchId === String(branchId)" in wrapper
    assert "scrollIntoView({behavior: 'smooth', block: 'center'})" in wrapper
    assert "handoff-focus" in wrapper
    assert "data-contract-node=\"${esc(ref.branch_id)}\"" not in wrapper


def test_clarified_flow_groups_stage_event_handler_overview_from_existing_evidence():
    wrapper = WRAPPER.read_text(encoding="utf-8")

    assert "contract.source_branch_evidence" in wrapper
    assert "handoffsByEvent" in wrapper
    assert "handoffsByEvent.has(String(row.event_id))" in wrapper
    assert "Stage → event overview" in wrapper
    assert "Verified stage guard" in wrapper
    assert "starts under this guard" in wrapper
    assert "Matching handlers" in wrapper
    assert "same event identity" in wrapper
    assert "handoff.ordering || 'UNPROVEN'" in wrapper
    assert "not runtime ordering" in wrapper
    assert "${stageHtml}${lifecycleHtml}${groupsHtml}" in wrapper


def test_clarified_flow_groups_event_lifecycle_without_claiming_runtime_order():
    wrapper = WRAPPER.read_text(encoding="utf-8")

    assert "Event lifecycle" in wrapper
    assert "Starts event" in wrapper
    assert "Handled by" in wrapper
    assert "same literal event identity" in wrapper
    assert "row.ordering || 'UNPROVEN'" in wrapper
    assert "runtime ordering remains unproven" in wrapper
    assert "${stageHtml}${lifecycleHtml}${groupsHtml}" in wrapper


def test_clarified_flow_wrapper_contract_render_is_idempotent():
    wrapper = WRAPPER.read_text(encoding="utf-8")

    assert "CONTRACT_VERSION" in wrapper
    assert "clarified.dataset.plainContractVersion === CONTRACT_VERSION" in wrapper
    assert "clarified.dataset.plainContractVersion = CONTRACT_VERSION" in wrapper


def test_clarified_flow_wrapper_does_not_reimplement_projection_semantics():
    wrapper = WRAPPER.read_text(encoding="utf-8")

    assert "COLLAPSED_HELPER_KINDS" not in wrapper
    assert "function plainSummary" not in wrapper
    assert "helper_call" not in wrapper
    assert "shared_helper_callee" not in wrapper
    assert "recoverRuleRequirements" not in wrapper
