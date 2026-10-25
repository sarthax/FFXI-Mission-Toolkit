# Scenario Action / Expectation Crosswalk (DRAFT)

Source: XiHeadless `ScenarioActionSchema`, `ScenarioExpectationSchema`, `ScenarioExpectationOracles`, `ScenarioOperationEvidence` (schema v1) in the read-only b-pr170 checkout.

## Native actions

walk_to, talk_npc, talk_nearest, sweep_npcs, invite, accept_invite, wait_ms, say, kill_all, route, patrol, update, finish, stop, disengage, engage, examine_npc, event_update, event_finish, rest_hp.

## Native expectations (oracle)

GreaterThan: `*_gt` keys. Equals: zone, main_job, main_level, sub_job, hpp, event_id, event_form_34, event_param0-7, x_near/z_near/radius, in_zone, event_active.

## Needs vs availability

| Library need | Native action | Native expectation | MCP readback | Status |
|---|---|---|---|---|
| Be in zone | wait_ms | zone, in_zone | snapshot | supported |
| NPC event opens | talk_npc | event_active, event_id, event_param* | wait_for_event | supported |
| Party forms | invite, accept_invite | party_members_gt | party_status | supported |
| Zone transition | event finish / zone_to | zone | none | partial |
| Item possession | trade_npc / use_item (MCP) | NONE | inventory, container_items | partial (G-01) |
| Key item | none | NONE | key_items | partial (G-01) |
| Quest stage | none | NONE | none found | unsupported (G-02) |
| Mission progress | none | NONE | none found | unsupported |
| Status effect | none | NONE | none found | unknown |
| Combat outcome | kill_all, engage, disengage | hpp | none | unknown |

## Interpretation rule

Dispatch is `accepted`, not verified, unless an echo or close is observed (`ScenarioOperationEvidence`). A dispatch alone is never PASS; absent readback maps to UNKNOWN.
