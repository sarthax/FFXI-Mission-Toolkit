"""Generates the four markdown deliverables from scenario_catalog_draft.json. Non-executing."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
c = json.load(open(os.path.join(HERE, "scenario_catalog_draft.json"), encoding="utf-8"))
S = c["scenarios"]


def w(name, lines):
    open(os.path.join(HERE, name), "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")


n_char = sum(s["tier"] == "characterized" for s in S)
L = ["# Scenario Library Inventory (DRAFT, not execution-validated)", "",
     "Coordinator: #1348. Machine-readable source of truth: `scenario_catalog_draft.json` (schema `scenario-library-draft/1`).",
     "Evidence labels: source-supported, capture-observed, previously-executed, locally-validated, unverified.", "",
     "Totals: %d candidates, %d characterized, %d failure-injection probe groups (kept separate)." % (
         len(S), n_char, len(c["failure_injection_probes"])), "",
     "| ID | Domain | Tier | Support | Confidence | Evidence | Title |", "|---|---|---|---|---|---|---|"]
for s in S:
    L.append("| %s | %s | %s | %s | %s | %s | %s |" % (s["id"], s["domain"], s["tier"], s["support_status"],
             s["confidence"], ", ".join(s["evidence_class"]), s["title"].replace("|", "/")))
L += ["", "## Headless asset revalidation", "",
      "Scanned `scenarios/*.json` (10 files) and `docs/evidence/**/scenario*.json` in the read-only headless checkout b-pr170. "
      "The earlier 28-file / ~12-14 distinct figure is NOT re-asserted: this pass found 10 top-level scenario files plus the pr7 "
      "acceptance scenario.json files, many of which are failure-injection probes (A06 route/cancel, A11-2 absent invite). "
      "Only the A11-1 party pair is recorded as passing end to end (passed=2, failed=0 on each side). Distinct reusable behaviours "
      "found: party formation, NPC talk, Leujaoam entry, idle/settle, sweep, patrol. No exact dedup count is claimed beyond that.", "",
      "## Domains not researched in this pass", "",
      "Missions (getCurrentMission), status effects, doors/switches/teleports, Feature Trace and Behavior Inspector outputs, "
      "packet captures. These have no candidates; see the gap report.", "",
      "## Provenance notes", "",
      "Mission facts (WoTG 1-10 and nation rank 1-2 starters, 82 mission files extracted) come from LandSandBoat `landsandboat-latest@5f77448970` via `_extract_missions.py` -> `lsb_mission_extract.json`. DSP main has no WoTG mission scripts, so those are LSB-sourced and design-only for DSP/Valhalla. Nation-quest starters are the 19 DSP NPC scripts above. LSB csids are LSB client generation: verify before execution.", "",
      "DSP quest facts come from `dsp-branches` main `febdc00209` scripts and `sql/npc_list.sql` (19 NPC scripts, "
      "`dsp_source_extract.json`). npc_list ids were checked against the script zone with the id>>12 rule only; the client-id "
      "offset is NOT verified (project caveat)."]
w("SCENARIO_LIBRARY_INVENTORY.md", L)

w("SCENARIO_ACTION_EXPECTATION_CROSSWALK.md", [
    "# Scenario Action / Expectation Crosswalk (DRAFT)", "",
    "Source: XiHeadless `ScenarioActionSchema`, `ScenarioExpectationSchema`, `ScenarioExpectationOracles`, "
    "`ScenarioOperationEvidence` (schema v1) in the read-only b-pr170 checkout.", "",
    "## Native actions", "",
    "walk_to, talk_npc, talk_nearest, sweep_npcs, invite, accept_invite, wait_ms, say, kill_all, route, patrol, update, "
    "finish, stop, disengage, engage, examine_npc, event_update, event_finish, rest_hp.", "",
    "## Native expectations (oracle)", "",
    "GreaterThan: `*_gt` keys. Equals: zone, main_job, main_level, sub_job, hpp, event_id, event_form_34, event_param0-7, "
    "x_near/z_near/radius, in_zone, event_active.", "",
    "## Needs vs availability", "",
    "| Library need | Native action | Native expectation | MCP readback | Status |", "|---|---|---|---|---|",
    "| Be in zone | wait_ms | zone, in_zone | snapshot | supported |",
    "| NPC event opens | talk_npc | event_active, event_id, event_param* | wait_for_event | supported |",
    "| Party forms | invite, accept_invite | party_members_gt | party_status | supported |",
    "| Zone transition | event finish / zone_to | zone | none | partial |",
    "| Item possession | trade_npc / use_item (MCP) | NONE | inventory, container_items | partial (G-01) |",
    "| Key item | none | NONE | key_items | partial (G-01) |",
    "| Quest stage | none | NONE | none found | unsupported (G-02) |",
    "| Mission progress | none | NONE | none found | unsupported |",
    "| Status effect | none | NONE | none found | unknown |",
    "| Combat outcome | kill_all, engage, disengage | hpp | none | unknown |", "",
    "## Interpretation rule", "",
    "Dispatch is `accepted`, not verified, unless an echo or close is observed (`ScenarioOperationEvidence`). "
    "A dispatch alone is never PASS; absent readback maps to UNKNOWN."])

w("SCENARIO_LIBRARY_GAP_REPORT.md", [
    "# Scenario Library Gap Report (DRAFT)", "",
    "- **G-01** No item or key-item expectation/oracle in `ScenarioExpectationSchema`; readback exists only as MCP tools (inventory, container_items, key_items).",
    "- **G-02** No quest/mission state readback tool found; quest scenarios can only assert that an event opened.",
    "- **G-03** Client-vs-server ID offset: npc_list ids and csids come from server source; every quest candidate needs dat-extractor verification before execution.",
    "- **G-04** Prerequisites (levels, rank, prior quests, imprimatur) are not characterized for any quest or Assault scenario.",
    "- **G-05** Toolkit execution_preflight supports only MOG-09; no publish path or categories (see the #1348 proposal).",
    "- **G-06** Domains not researched: missions, status effects, doors/switches, captures, Feature Trace, Behavior Inspector.",
    "- **G-07** No recorded results for the Argus, Leujaoam, sweep and patrol scenario files; they are source-supported only.",
    "- **G-08** Duplicate NPC names across zones (e.g. Brygid, Babenn, Kopuro-Popuro) need a zone-qualified npc_list query; the extract used the first row whose id resolves to the script zone.",
    "- **G-09** Combat and status-effect entries are design-only (no recorded runs).", "",
    "Historical failures are not treated as expected failures."])

w("SCENARIO_LIBRARY_IMPORT_PLAN.md", [
    "# Scenario Library Import Plan (DRAFT)", "",
    "Draft-only. Never auto-publish; owner approval is required per scenario.", "",
    "1. **Fixture shape**: each catalog entry keeps the `xiheadless` native payload verbatim plus `provenance`, `evidence_class`, `confidence`; Toolkit fields are derived, not substituted.",
    "2. **Stage A**: import entries with `support_status: supported` as drafts into the drafts DB (#1410).",
    "3. **Stage B**: add item/key-item expectations (G-01), then import partial entries.",
    "4. **Stage C**: quest/mission readback (G-02), then promote quest candidates after dat-extractor verification (G-03).", "",
    "## Top 10 recommended first slices", "",
    "1. SL-MOG-009 (already runnable)", "2. SL-NPC-001 Argus event", "3. SL-ZONE-001 settle",
    "4. SL-PARTY-001 party formation (recorded pass)", "5. SL-ASLT-001 Leujaoam entry",
    "6. SL-ITEM-001 item possession (needs G-01)", "7. SL-KI-001 key item (needs G-01)",
    "8. SL-MSN-WOTG-01..05 (WoTG missions 1-5 sample; replaces the earlier Zon-Fobun slot per owner direction)", "9. SL-MSN-WOTG-06..10 (WoTG missions 6-10 sample; replaces the earlier Ardea slot)",
    "10. SL-ZONE-002 zone_to", "",
    "## Proposed next issues", "",
    "- Item/key-item expectation and oracle in XiHeadless",
    "- Quest state readback tool",
    "- Zone-qualified NPC id verifier",
    "- Toolkit draft import for `scenario-library-draft/1`"])
print("docs written")
