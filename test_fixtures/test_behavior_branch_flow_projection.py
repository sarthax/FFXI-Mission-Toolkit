#!/usr/bin/env python3
"""Regression for branch-preserving Plain Behavior mission/event presentation."""
from __future__ import annotations

from test_fixtures.test_scripted_behavior_noncombat_mission_stress import SCRIPT
from workbench.plugins.domain.scripted_behavior_lsb_extract import extract_lsb_scripted_behavior
from workbench.core.services.scripted_behavior_visualizer import _graph_for_behavior
from workbench.devtools.behavior.plain_view import build_plain_behavior_projection
from workbench.devtools.behavior.source_branch_projection import apply_source_branch_evidence


def _flatten(rows):
    out=[]
    stack=list(reversed(rows))
    while stack:
        row=stack.pop()
        out.append(row)
        stack.extend(reversed(row.get("children") or []))
    return out


def _labels(rows):
    return {str(row.get("label")) for row in rows}


def main():
    behavior=extract_lsb_scripted_behavior(
        SCRIPT,
        feature_id="feature:noncombat-mission-branch-flow",
        subject="Mission NPC",
        zone="TEST",
        source_path="scripts/zones/Test/npcs/Mission_NPC.lua",
    )
    graph=_graph_for_behavior(behavior)
    plain=apply_source_branch_evidence(build_plain_behavior_projection(graph),graph,SCRIPT)

    assert plain["presentation"]=="branch_tree_v1",plain
    assert plain["safety"]["branch_nesting_from_guard_containment_only"] is True,plain
    assert plain["safety"]["cross_hook_ordering_inferred"] is False,plain
    assert plain["safety"]["source_literal_branch_overlay"] is True,plain

    groups={row["trigger"]["technical_label"]:row for row in plain["branch_groups"]}
    assert {"onTrigger","onEventFinish","onEventUpdate"} <= set(groups),groups

    trigger_branches=_flatten(groups["onTrigger"]["branches"])
    stage_branches={}
    for branch in trigger_branches:
        reqs=_labels(branch.get("direct_requirements") or [])
        for stage in ("MissionStage = 0","MissionStage = 1","MissionStage = 9"):
            if stage in reqs:
                stage_branches[stage]=branch
    assert set(stage_branches)=={"MissionStage = 0","MissionStage = 1","MissionStage = 9"},stage_branches
    assert any("101" in label for label in _labels(stage_branches["MissionStage = 0"]["effects"])),stage_branches
    assert any("102" in label for label in _labels(stage_branches["MissionStage = 1"]["effects"])),stage_branches
    assert any("103" in label for label in _labels(stage_branches["MissionStage = 9"]["effects"])),stage_branches

    finish_roots=groups["onEventFinish"]["branches"]
    finish_all=_flatten(finish_roots)
    event102=next(
        branch for branch in finish_all
        if "Event / CSID = 102" in _labels(branch.get("direct_requirements") or [])
        and len(branch.get("guard_keys") or [])==1
    )
    option1=next(
        child for child in _flatten(event102.get("children") or [])
        if "option = 1" in _labels(child.get("direct_requirements") or [])
        and len(child.get("guard_keys") or [])==2
    )
    nested=_flatten(option1.get("children") or [])
    assert any("OutcomeGate = 3" in _labels(row.get("direct_requirements") or []) for row in nested),nested
    assert any("OutcomeGate = 4" in _labels(row.get("direct_requirements") or []) for row in nested),nested
    assert any("600" in label for row in nested for label in _labels(row.get("effects") or [])),nested
    assert any("601" in label for row in nested for label in _labels(row.get("effects") or [])),nested

    handoffs={str(row["event_id"]):row for row in plain["event_handoffs"]}
    assert {"101","102"} <= set(handoffs),handoffs
    for event_id in ("101","102"):
        row=handoffs[event_id]
        assert row["ordering"]=="UNPROVEN",row
        assert row["start_branches"],row
        assert row["handler_branches"],row
        assert all(ref["trigger_label"]=="Player interacts with this actor" for ref in row["start_branches"]),row
        assert any("event finishes" in ref["trigger_label"].lower() for ref in row["handler_branches"]),row

    print("behavior branch flow projection self-test: PASS")


if __name__=="__main__":
    main()
