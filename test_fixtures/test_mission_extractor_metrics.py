#!/usr/bin/env python3
"""Regression for mission extractor coverage/ambiguity metrics."""
from workbench.plugins.domain.mission_lsb_extract import (
    chain_event_transitions,
    correlate_lsb_handlers,
    mission_extraction_metrics,
)

SOURCE=r"""
[xi.zone.TEST_ZONE] =
{
    ['Metric_NPC'] =
    {
        onTrigger = function(player, npc)
            if mission:getVar(player, 'Status') == 0 then
                return mission:progressEvent(10)
            end
        end,

        onTrade = function(player, npc, trade)
            player:getGil()
        end,
    },

    onEventFinish =
    {
        [10] = function(player, csid, option, npc)
            mission:setVar(player, 'Status', 1)
        end,

        [10] = function(player, csid, option, npc)
            mission:setVar(player, 'Status', 2)
        end,
    },
}
"""

def main():
    raw=correlate_lsb_handlers(SOURCE,feature_id="mission:test:metrics")
    metrics=mission_extraction_metrics(raw)
    assert metrics["source_handler_count"]==4,metrics
    assert metrics["modeled_source_handler_count"]==3,metrics
    assert metrics["unmodeled_source_handler_count"]==1,metrics
    assert len(metrics["unmodeled_source_handler_lines"])==1,metrics
    assert metrics["transitions_by_trigger"]["NPC_INTERACT"]==1,metrics
    assert metrics["transitions_by_trigger"]["EVENT_FINISH"]==2,metrics
    assert metrics["event_transition_count"]==3,metrics
    assert metrics["channel_count"]>=1,metrics

    chained=chain_event_transitions(raw)
    chained_metrics=mission_extraction_metrics(chained)
    assert chained_metrics["event_chains"]==2,chained_metrics
    assert chained_metrics["event_chain_ambiguous_groups"]==1,chained_metrics
    assert chained_metrics["event_chain_unmatched_triggers"]==0,chained_metrics

    print("mission extractor stress metrics self-test: PASS")

if __name__=="__main__":
    main()
