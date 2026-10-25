"""Builds the DRAFT scenario catalog from recorded research facts. Non-executing; reads only a local JSON extract."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ex = json.load(open(os.path.join(HERE, "dsp_source_extract.json"), encoding="utf-8"))
ZONES = {"Bastok_Markets": 235, "Port_Bastok": 236, "Bastok_Mines": 234, "Southern_San_dOria": 230,
         "Windurst_Waters": 238, "Port_Windurst": 240, "Windurst_Woods": 241}


def zone_of(npc_id):
    return ((npc_id - 0x1000000) >> 12) & 0xFFF if npc_id >= 0x1000000 else None


SRC = "dsp-branches@main:febdc00209"


def quest(key):
    v = ex[key]
    zdir = v["zone_dir"]
    flags = []
    npc = None
    for r in v["sql_rows"]:
        if zone_of(r[0]) == ZONES.get(zdir):
            npc = r
            break
    if npc is None:
        flags.append("npc_list id does not resolve to the script's zone: do not execute until re-verified")
    elif float(npc[1]) == 0 and float(npc[2]) == 0 and float(npc[3]) == 0:
        flags.append("npc_list position is (0,0,0) (dynamic/hidden per project rule)")
    return v, npc, flags


def interp(desc):
    return {"PASS": "All expectations observed by readback: " + desc,
            "FAIL": "A readback was obtained and contradicts an expectation",
            "BLOCKED": "Setup requirement unmet (character not in zone, NPC absent, server not seeded)",
            "UNKNOWN": "Dispatch accepted but no readback/echo observed; a dispatch alone is never PASS"}


def cand(sid, domain, title, given, when, then, prov, conf, ev, support, action=None, tier="candidate", extra=None):
    d = {"id": sid, "schema_version": "scenario-library-draft/1", "status": "draft", "tier": tier,
         "domain": domain, "title": title, "readable": {"given": given, "when": when, "then": then},
         "provenance": prov, "confidence": conf, "evidence_class": ev, "support_status": support,
         "owner": "unassigned (discovery draft)", "execution_validated": False,
         "safety": "read-only observation; no execution performed in discovery"}
    if action:
        d["xiheadless"] = action
    if extra:
        d.update(extra)
    return d


C = []
C.append(cand("SL-PARTY-001", "parties", "Leader invites member; party forms (Bastok Markets)",
  "Two headless characters in Bastok Markets (zone 235).", "Leader invites the member id; member accepts.",
  "Leader and member each report party_members_gt 0.",
  ["headless b-pr170 scenarios/scenario_party_leader.json",
   "docs/evidence/pr7-acceptance-2026-10-19/A11-1-leader-member-{leader,member}/results.json"],
  "high", ["previously-executed", "source-supported"], "supported", tier="characterized",
  action={"native_action": "invite / accept_invite", "params": {"invite": 21830},
          "typed_ids": {"invite": "character id taken verbatim from scenario file"},
          "expected_state": {"zone": 235, "in_zone": True, "party_members_gt": 0},
          "readback_collector": "scenario expectation party_members_gt (party_status MCP tool as cross-check)",
          "oracle_rule": "GreaterThan(party_members_gt, 0)",
          "setup": ["two seeded characters in zone 235", "leader and member run concurrently"],
          "interpretation": interp("party_members_gt > 0 on both sides")},
  extra={"recorded_outcome": "A11-1 leader results passed=2 failed=0; member results passed=2 failed=0 (pr7 evidence 2026-10-19). Server build provenance not re-verified here."}))
C.append(cand("SL-NPC-001", "npc-interaction", "Talk to Argus starts an event (Port Bastok)",
  "Character in zone 236 with NPCs visible.", "Character talks to NPC 17743873.", "An event becomes active.",
  ["headless scenarios/scenario_npc_event.json"], "medium", ["source-supported"], "supported", tier="characterized",
  action={"native_action": "talk_npc", "params": {"talk_npc": 17743873},
          "typed_ids": {"talk_npc": "npc entity id from scenario file"},
          "expected_state": {"in_zone": True, "zone": 236, "entities_gt": 3, "event_active": True},
          "readback_collector": "scenario expectation event_active", "oracle_rule": "Equals(event_active, true)",
          "setup": ["character in zone 236"], "interpretation": interp("event_active true after talk_npc")},
  extra={"recorded_outcome": "scenario file exists; no recorded results.json located in this pass",
         "note": "id resolves to zone %s by the id>>12 rule" % zone_of(17743873)}))
C.append(cand("SL-ASLT-001", "instanced-content", "Leujaoam Sanctum entry via Runic Seal (Caedarva Mire)",
  "Character in zone 79 (Caedarva Mire).", "Talk to Runic Seal 17101270, update(0), finish(4).",
  "Event 0x8C fires with captured parameters, then character is in zone 69.",
  ["headless scenarios/scenario_leujaoam_entry.json (expectation values labelled capture-derived in the file)"],
  "medium", ["capture-observed", "source-supported"], "partial", tier="characterized",
  action={"native_action": "talk_npc + walk_to + update + finish",
          "params": {"talk_npc": 17101270, "update": 0, "finish": 4},
          "typed_ids": {"talk_npc": "npc entity id", "event_id": 140, "zone_in": 79, "zone_out": 69},
          "expected_state": {"event_id": 140, "event_form_34": 1, "event_param0": 1, "event_param1": 4294967292,
                             "event_param2": 0, "event_param3": 50, "zone": 69},
          "readback_collector": "scenario expectations event_id/event_param*/zone",
          "oracle_rule": "Equals on each field",
          "setup": ["Assault rank/imprimatur prerequisites NOT characterized in discovery", "instance capacity free"],
          "interpretation": interp("event fields then zone == 69")},
  extra={"recorded_outcome": "no recorded result located; sibling files leujaoam_dbg/leujaoam_full not triaged for outcome"}))
C.append(cand("SL-ZONE-001", "zone-transitions", "Character settles in a zone and sees entities",
  "Logged-in character.", "Wait for settle.", "in_zone true, max_hp_gt 0, entities_gt N.",
  ["pr7 evidence 'settle' step (passes in most A06 runs)", "scenarios/scenario_idle235.json"], "high",
  ["previously-executed"], "supported", tier="characterized",
  action={"native_action": "wait_ms (+ expectation only)", "params": {"wait_ms": 3000},
          "typed_ids": {"zone": "zone id"}, "expected_state": {"in_zone": True, "max_hp_gt": 0, "entities_gt": 0},
          "readback_collector": "scenario expectations", "oracle_rule": "Equals/GreaterThan",
          "setup": ["character online"], "interpretation": interp("in_zone true and entities visible")},
  extra={"recorded_outcome": "'settle' step pass=true across A06 probe runs"}))
C.append(cand("SL-ZONE-002", "zone-transitions", "Zone-to command changes zone",
  "Character in zone A.", "MCP zone_to targets zone B.", "zone == B and in_zone.",
  ["MCP tool zone_to (name only; parameters not read in discovery)", "docs/evidence/pr67-stop-logout-zone-20261019/"],
  "low", ["unverified"], "unknown", extra={"note": "design-only; zone_to is an MCP tool, not a scenario action"}))
C.append(cand("SL-COMBAT-001", "combat", "kill_all clears nearby mobs", "Character near mobs.", "kill_all action.",
  "Nearby mob count falls; hpp expectation observable.", ["ScenarioActionSchema.Known includes kill_all"], "low",
  ["source-supported"], "unknown", extra={"note": "design-only; no recorded scenario using kill_all located"}))
C.append(cand("SL-COMBAT-002", "combat", "rest_hp restores hpp", "Damaged character.", "rest_hp action.", "hpp rises.",
  ["ScenarioActionSchema.Known includes rest_hp; expectation key hpp exists"], "low", ["source-supported"],
  "unknown", extra={"note": "design-only"}))
C.append(cand("SL-DIAG-001", "dialog-csid", "sweep_npcs enumerates NPC events in a zone", "Character in zone 235.",
  "sweep_npcs.", "Each NPC either starts an event or none.", ["headless scenarios/scenario_sweep.json"], "medium",
  ["source-supported"], "partial", extra={"note": "outcome not located; sweep is exploratory, not a pass/fail oracle"}))
C.append(cand("SL-MOG-009", "inventory", "MOG-09 Toolkit catalog scenario", "Per Toolkit catalog entry.",
  "Per Toolkit runner.", "Per Toolkit oracle.",
  ["data/testing/test_specifications.json (MOG-09)", "execution_preflight.SUPPORTED"], "high",
  ["previously-executed", "locally-validated"], "supported", tier="characterized",
  action={"native_action": "Toolkit built-in runner (not XIHeadless scenario schema)", "params": {}, "typed_ids": {},
          "expected_state": "see catalog entry",
          "readback_collector": "Toolkit observation operations (equals/nonempty/same_rows/all_zero)",
          "oracle_rule": "Toolkit assertion ids", "setup": ["see MOG-09 catalog entry"],
          "interpretation": interp("catalog assertions")},
  extra={"note": "spec contents not duplicated here; reference only"}))
C.append(cand("SL-INV-001", "inventory", "INV-OBS-01 inventory observation spec", "Per catalog.",
  "Observe inventory.", "Per catalog.", ["data/testing/test_specifications.json (INV-OBS-01)"], "medium",
  ["source-supported"], "partial", extra={"note": "not runnable (execution_preflight.SUPPORTED lists only MOG-09)"}))
C.append(cand("SL-ITEM-001", "inventory", "Item possession after trade or quest reward", "Character with empty slot.",
  "Complete a reward step.", "container_items shows the item id.",
  ["MCP tools inventory, container_items, trade_npc, use_item (names only)",
   "no item expectation exists in ScenarioExpectationSchema"], "medium", ["source-supported"], "partial",
  tier="characterized",
  action={"native_action": "MCP inventory / container_items (outside scenario schema)",
          "params": {"item_id": "from addItem in the NPC script, e.g. 16387 for Zon-Fobun"},
          "typed_ids": {"item_id": "item id from the DSP script"}, "expected_state": {"item_present": True},
          "readback_collector": "container_items tool", "oracle_rule": "none in ScenarioOracle (gap G-01)",
          "setup": ["empty slot"], "interpretation": interp("item id present in container")}))
C.append(cand("SL-KI-001", "key-items", "Key item granted by NPC", "Character without key item.",
  "Complete the NPC step.", "key_items lists the key item.",
  ["MCP tool key_items", "DSP scripts use addKeyItem(tpz.ki.NAME)",
   "memory note: key item ids drift ~90% LSB vs Topaz; resolve via id_bridge"], "medium", ["source-supported"],
  "partial", tier="characterized",
  action={"native_action": "MCP key_items (outside scenario schema)", "params": {"key_item": "name only"},
          "typed_ids": {"key_item_id": "NOT asserted: resolve with id_bridge.py in an execution session"},
          "expected_state": {"key_item_present": True}, "readback_collector": "key_items tool",
          "oracle_rule": "none in ScenarioOracle (gap G-01)", "setup": ["character lacks key item"],
          "interpretation": interp("key item listed")}))

CHAR = {"Bastok_Markets/Ardea", "Bastok_Markets/Zon-Fobun", "Bastok_Markets/Degenhard",
        "Windurst_Waters/Angelica", "Southern_San_dOria/Paouala"}
for key in ex:
    v, npc, flags = quest(key)
    name, zdir = v["npc"], v["zone_dir"]
    zid = ZONES[zdir]
    sid = "SL-QUEST-" + name.upper().replace("-", "").replace("_", "")[:10]
    qs = v["quests"] or v["addQuest"]
    tier = "characterized" if key in CHAR and not flags else "candidate"
    action = None
    if tier == "characterized":
        action = {"native_action": "talk_npc", "params": {"talk_npc": npc[0]},
                  "typed_ids": {"talk_npc": "npc_list id (zone check passed)", "zone": zid,
                                "csids_in_script": v["startEvent"]},
                  "expected_state": {"zone": zid, "event_active": True},
                  "readback_collector": "scenario expectation event_active; quest stage NOT readable (gap G-02)",
                  "oracle_rule": "Equals(event_active, true)",
                  "setup": ["character in zone %d near NPC at (%s,%s,%s)" % (zid, npc[1], npc[2], npc[3]),
                            "quest prerequisites per script (not characterized)",
                            "npc_list id vs client id offset unverified (verify with dat-extractor)"],
                  "interpretation": interp("event_active true after talk_npc; quest state change is unobservable today, so at most partial")}
    C.append(cand(sid, "missions-quests", "%s: %s" % (name.replace("_", " "), "/".join(qs[:2]) or "dialog"),
      "Character in %s with quest %s in a start-eligible state." % (zdir.replace("_", " "), "/".join(qs[:2]) or "n/a"),
      "Character talks to %s." % name,
      "NPC event fires (script csids %s); quest/key item/reward effects per script." % ", ".join(v["startEvent"][:4]),
      ["%s: scripts/zones/%s/npcs/%s.lua" % (SRC, zdir, name), "%s: sql/npc_list.sql" % SRC],
      "medium" if not flags else "low", ["source-supported"],
      "partial" if tier == "characterized" else "unknown", tier=tier, action=action,
      extra={"source_facts": {"quests": qs, "keyitems": v["keyitems"], "addItem": v["addItem"], "vars": v["vars"],
                              "npc_list": npc and {"id": npc[0], "pos": npc[1:]}},
             "verification_flags": flags}))

PROBES = [
    {"id": "SL-PROBE-A06", "kind": "failure-injection",
     "source": "pr7 A06-* (probe, probe2/3, bind, stalled, jitter, temp-block, cancel x5, wrong-floor)",
     "note": "route/walk robustness probes; failures there are injected or exploratory, NOT expected-fail library scenarios",
     "recorded": "mixed pass/fail; one run failed at scenario load (walk_to shape)"},
    {"id": "SL-PROBE-A11-2", "kind": "failure-injection",
     "source": "pr7 A11-2-invite-absent-{leader,member}", "note": "invite with absent counterpart; each side 1 pass 1 fail"}]
cat = {"catalog_schema_version": "scenario-library-draft/1", "status": "DRAFT", "execution_validated": False,
       "generated_from": {"dsp": SRC, "headless": "FFXI-Tools/headless-research/b-pr170 (read-only)",
                          "toolkit": "origin/main 7bb970af"},
       "scenarios": C, "failure_injection_probes": PROBES}
json.dump(cat, open(os.path.join(HERE, "scenario_catalog_draft.json"), "w", encoding="utf-8"), indent=1)
print(len(C), "scenarios;", sum(1 for c in C if c["tier"] == "characterized"), "characterized;",
      sum(1 for c in C if c.get("verification_flags")), "flagged")
