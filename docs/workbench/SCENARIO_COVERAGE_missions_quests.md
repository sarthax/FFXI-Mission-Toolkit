# Missions and quests — R5 source-backed scenario coverage

**Issue:** [#1252](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1252) · [epic #1197](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1197) · DSP [`main@86d4467d446569c741d76d296e640c3b844ad844`](https://github.com/sarthax/darkstar-to-valhalla/tree/86d4467d446569c741d76d296e640c3b844ad844), **not confirmed as deployed**.

**Five design-only MQ scenarios.** We chose concrete Bastok NPC handlers to avoid generic assumptions about every quest/mission. In particular, `MQ-01..03` use **Horatius / Breaking Stones**, `MQ-04` uses **Michea / Distant Loyalties**. **MQ-05 is a possible source-backed duplicate-reward weakness**, not a passing safeguard. No live client, commands, mutation or merge.

## Source-specific oracle anchors

- [`Horatius.lua:18–31`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Horatius.lua#L18-L31) trades item **553** (one count) whenever `BREAKING_STONES ~= QUEST_AVAILABLE`; [`33–46`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Horatius.lua#L33-L46) branches on Bastok fame **>=2**, subject to prior Wildcat logic. [`54–74`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Horatius.lua#L54-L74) starts quest on event `0x0064` option **0**; turns in on event `0x0065`, grants `GIL_RATE*400`, and completes the quest. **Do not infer actual Gil amount without verifying live GIL_RATE**.
- Critically, the trade's `~=QUEST_AVAILABLE` test does **not** explicitly exclude `QUEST_COMPLETED`. After an approved already-completed fixture, a repeated trade may trigger another reward in this script. Mark MQ-05 as **possible source defect**, never claim no-duplicate PASS.
- [`Michea.lua:12–57`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Michea.lua#L12-L57) has precise item trade checks; [`104–124`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Michea.lua#L104-L124) changes `DistantLoyaltiesProgress` and adds `MYTHRIL_HEARTS` KI along conditional event branches. **Relog durability remains UNKNOWN**.
- [`checkquest.lua:8–78`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/commands/checkquest.lua#L8-L78) and [`checkmission.lua:7–65`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/commands/checkmission.lua#L7-L65) are permission-1 diagnostics, not independent audit trails. [`addmission.lua:7–66`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/commands/addmission.lua#L7-L66) and [`completequest.lua:7–66`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/commands/completequest.lua#L7-L66) directly mutate and **cannot validate real NPC game progression**.

## Case/readiness matrix

| ID | Scenario | Primary lane | Source and gaps |
|---|---|---|---|
| MQ-01 | Complete eligible NPC progression | `needs-mutation` | Script guards and numeric reward source-pinned, but real client event, fame, Gil rate and server quest/inventory readbacks not yet verified |
| MQ-02 | Missing prerequisite blocks progression | `needs-mutation` | Exact fame readback and WildcatBastok precedence required; normal client event handling UNKNOWN |
| MQ-03 | Wrong dialog choice leaves state unchanged | `needs-mutation` | Source proves handler branch only; other hooks/side effects and event selection capabilities UNKNOWN |
| MQ-04 | Relog retains progression and key items | `needs-mutation` | Michea branch includes zone dependency and GOLDSMITHING_ORDER; missing named exact charvar, persistent KI and client event readback |
| MQ-05 | Repeat reward not duplicated | `needs-mutation` | Repeat reward guard absent in this source; diagnostic might expose a duplicate-Gil vulnerability; reward balances and complete inventory before/after required |

All five full scenarios `needs-mutation`. Initial readbacks `needs-readback` for persisted quest/mission status, Gil, fame and full inventory. Deployed DSP status UNKNOWN so do not falsely classify `needs-deploy` as confirmed. `observe-now` applies only to safe preparatory reads, not a full gameplay verdict.

## BDD with ordered actions and observations

### MQ-01 — Complete eligible NPC progression

**Purpose/rationale:** Verify complete eligible npc progression on a specifically sourced NPC flow. Script guards and numeric reward source-pinned, but real client event, fame, Gil rate and server quest/inventory readbacks not yet verified

**Given:** Owner-approved disposable character and exact NPC/zone source identity; Preconditions and branch precedence verified against pinned DSP files; Independent quest variables, inventory and KI source-backed baselines.

**When:** Use Horatius Breaking Stones in Bastok Markets with source-reviewed fame+quest state, accept and trade one item 553.

**Then:** Horatius script accepts quest after CSID 0x0064 option 0; one item 553 while quest no longer AVAILABLE triggers 0x0065 and completion, reward 400*GIL_RATE; runtime acceptance UNKNOWN.

- **MQ-01-S01 — Read-only setup baseline:** Select authorized character, record exact quest IDs via source, fame, variables, held KI and full inventory/Gil. **Expected:** Complete and pinned baseline; otherwise UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-01-baseline`.
- **MQ-01-S02 — Normal client interaction:** Use Horatius Breaking Stones in Bastok Markets with source-reviewed fame+quest state, accept and trade one item 553. **Expected:** Horatius script accepts quest after CSID 0x0064 option 0; one item 553 while quest no longer AVAILABLE triggers 0x0065 and completion, reward 400*GIL_RATE; runtime acceptance UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-01-transition`.
- **MQ-01-S03 — Independent authoritative comparison:** Capture NPC CSID and choice plus persisted quest/charvar/KI/inventory/Gil before/after. **Expected:** Source-matched independent post-state needed; otherwise UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-01-oracle`.
- **MQ-01-S04 — Cleanup and identity verification:** Only owner-approved restoration or quarantine; verify repeated client attempts and no unrelated changes. **Expected:** Clean complete state or BLOCKED. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-01-cleanup`.

**XIHeadless candidates:** talk_to_npc, event_select, wait_for_event, snapshot, inventory, logout. **Missing:** Validated mapped NPC identity/client event options; Reliable relog and event evidence; Read-only authoritative quest and Gil readback. **Readback:** Fixed read-only per-character quest and mission status endpoint; Read-only per-character Gil/quest fame and event option bindings; Complete untruncated inventory and save boundary, reward attribution. **Cleanup:** Do not use GM command to claim gameplay verdict; restore isolated character by approved process. **Source:** [`scripts/zones/Bastok_Markets/npcs/Horatius.lua:18–31`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Horatius.lua#L18-L31), [`scripts/zones/Bastok_Markets/npcs/Horatius.lua:33–46`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Horatius.lua#L33-L46), [`scripts/zones/Bastok_Markets/npcs/Horatius.lua:54–74`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Horatius.lua#L54-L74), [`scripts/globals/quests.lua:12–27`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/globals/quests.lua#L12-L27). **Verdict:** NOT_RUN.


### MQ-02 — Missing prerequisite blocks progression

**Purpose/rationale:** Verify missing prerequisite blocks progression on a specifically sourced NPC flow. Exact fame readback and WildcatBastok precedence required; normal client event handling UNKNOWN

**Given:** Owner-approved disposable character and exact NPC/zone source identity; Preconditions and branch precedence verified against pinned DSP files; Independent quest variables, inventory and KI source-backed baselines.

**When:** Talk to Horatius with Breaking Stones AVAILABLE but Bastok fame less than 2.

**Then:** Horatius onTrigger uses default CSID 0x006e rather than 0x0064 when fame below 2, assuming no Wildcat branch; no quest acceptance expected until event finished; runtime UNKNOWN.

- **MQ-02-S01 — Read-only setup baseline:** Select authorized character, record exact quest IDs via source, fame, variables, held KI and full inventory/Gil. **Expected:** Complete and pinned baseline; otherwise UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-02-baseline`.
- **MQ-02-S02 — Normal client interaction:** Talk to Horatius with Breaking Stones AVAILABLE but Bastok fame less than 2. **Expected:** Horatius onTrigger uses default CSID 0x006e rather than 0x0064 when fame below 2, assuming no Wildcat branch; no quest acceptance expected until event finished; runtime UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-02-transition`.
- **MQ-02-S03 — Independent authoritative comparison:** Capture NPC CSID and choice plus persisted quest/charvar/KI/inventory/Gil before/after. **Expected:** Source-matched independent post-state needed; otherwise UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-02-oracle`.
- **MQ-02-S04 — Cleanup and identity verification:** Only owner-approved restoration or quarantine; verify repeated client attempts and no unrelated changes. **Expected:** Clean complete state or BLOCKED. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-02-cleanup`.

**XIHeadless candidates:** talk_to_npc, event_select, wait_for_event, snapshot, inventory, logout. **Missing:** Validated mapped NPC identity/client event options; Reliable relog and event evidence; Read-only authoritative quest and Gil readback. **Readback:** Fixed read-only per-character quest and mission status endpoint; Read-only per-character Gil/quest fame and event option bindings; Complete untruncated inventory and save boundary, reward attribution. **Cleanup:** Do not use GM command to claim gameplay verdict; restore isolated character by approved process. **Source:** [`scripts/zones/Bastok_Markets/npcs/Horatius.lua:33–46`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Horatius.lua#L33-L46), [`scripts/zones/Bastok_Markets/npcs/Horatius.lua:54–74`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Horatius.lua#L54-L74). **Verdict:** NOT_RUN.


### MQ-03 — Wrong dialog choice leaves state unchanged

**Purpose/rationale:** Verify wrong dialog choice leaves state unchanged on a specifically sourced NPC flow. Source proves handler branch only; other hooks/side effects and event selection capabilities UNKNOWN

**Given:** Owner-approved disposable character and exact NPC/zone source identity; Preconditions and branch precedence verified against pinned DSP files; Independent quest variables, inventory and KI source-backed baselines.

**When:** On Horatius CSID 0x0064, choose an option other than 0, then inspect quest status.

**Then:** Horatius onEventFinish adds quest only for CSID 0x0064 and option 0; other options have no addQuest branch in this handler; runtime delta UNKNOWN.

- **MQ-03-S01 — Read-only setup baseline:** Select authorized character, record exact quest IDs via source, fame, variables, held KI and full inventory/Gil. **Expected:** Complete and pinned baseline; otherwise UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-03-baseline`.
- **MQ-03-S02 — Normal client interaction:** On Horatius CSID 0x0064, choose an option other than 0, then inspect quest status. **Expected:** Horatius onEventFinish adds quest only for CSID 0x0064 and option 0; other options have no addQuest branch in this handler; runtime delta UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-03-transition`.
- **MQ-03-S03 — Independent authoritative comparison:** Capture NPC CSID and choice plus persisted quest/charvar/KI/inventory/Gil before/after. **Expected:** Source-matched independent post-state needed; otherwise UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-03-oracle`.
- **MQ-03-S04 — Cleanup and identity verification:** Only owner-approved restoration or quarantine; verify repeated client attempts and no unrelated changes. **Expected:** Clean complete state or BLOCKED. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-03-cleanup`.

**XIHeadless candidates:** talk_to_npc, event_select, wait_for_event, snapshot, inventory, logout. **Missing:** Validated mapped NPC identity/client event options; Reliable relog and event evidence; Read-only authoritative quest and Gil readback. **Readback:** Fixed read-only per-character quest and mission status endpoint; Read-only per-character Gil/quest fame and event option bindings; Complete untruncated inventory and save boundary, reward attribution. **Cleanup:** Do not use GM command to claim gameplay verdict; restore isolated character by approved process. **Source:** [`scripts/zones/Bastok_Markets/npcs/Horatius.lua:33–46`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Horatius.lua#L33-L46), [`scripts/zones/Bastok_Markets/npcs/Horatius.lua:54–74`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Horatius.lua#L54-L74). **Verdict:** NOT_RUN.


### MQ-04 — Relog retains progression and key items

**Purpose/rationale:** Verify relog retains progression and key items on a specifically sourced NPC flow. Michea branch includes zone dependency and GOLDSMITHING_ORDER; missing named exact charvar, persistent KI and client event readback

**Given:** Owner-approved disposable character and exact NPC/zone source identity; Preconditions and branch precedence verified against pinned DSP files; Independent quest variables, inventory and KI source-backed baselines.

**When:** Use approved Michea Distant Loyalties event branch with source-reviewed stage/held KI, advance then logout/reconnect.

**Then:** Source advances DistantLoyaltiesProgress 2->3 on CSID 0x013d and 3->4 plus MYTHRIL_HEARTS KI on 0x013e; relog durability UNKNOWN.

- **MQ-04-S01 — Read-only setup baseline:** Select authorized character, record exact quest IDs via source, fame, variables, held KI and full inventory/Gil. **Expected:** Complete and pinned baseline; otherwise UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-04-baseline`.
- **MQ-04-S02 — Normal client interaction:** Use approved Michea Distant Loyalties event branch with source-reviewed stage/held KI, advance then logout/reconnect. **Expected:** Source advances DistantLoyaltiesProgress 2->3 on CSID 0x013d and 3->4 plus MYTHRIL_HEARTS KI on 0x013e; relog durability UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-04-transition`.
- **MQ-04-S03 — Independent authoritative comparison:** Capture NPC CSID and choice plus persisted quest/charvar/KI/inventory/Gil before/after. **Expected:** Source-matched independent post-state needed; otherwise UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-04-oracle`.
- **MQ-04-S04 — Cleanup and identity verification:** Only owner-approved restoration or quarantine; verify repeated client attempts and no unrelated changes. **Expected:** Clean complete state or BLOCKED. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-04-cleanup`.

**XIHeadless candidates:** talk_to_npc, event_select, wait_for_event, snapshot, inventory, logout. **Missing:** Validated mapped NPC identity/client event options; Reliable relog and event evidence; Read-only authoritative quest and Gil readback. **Readback:** Fixed read-only per-character quest and mission status endpoint; Read-only per-character Gil/quest fame and event option bindings; Complete untruncated inventory and save boundary, reward attribution. **Cleanup:** Do not use GM command to claim gameplay verdict; restore isolated character by approved process. **Source:** [`scripts/zones/Bastok_Markets/npcs/Michea.lua:12–57`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Michea.lua#L12-L57), [`scripts/zones/Bastok_Markets/npcs/Michea.lua:104–124`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Michea.lua#L104-L124), [`scripts/commands/checkquest.lua:8–78`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/commands/checkquest.lua#L8-L78). **Verdict:** NOT_RUN.


### MQ-05 — Repeat reward not duplicated

**Purpose/rationale:** Verify repeat reward not duplicated on a specifically sourced NPC flow. Repeat reward guard absent in this source; diagnostic might expose a duplicate-Gil vulnerability; reward balances and complete inventory before/after required

**Given:** Owner-approved disposable character and exact NPC/zone source identity; Preconditions and branch precedence verified against pinned DSP files; Independent quest variables, inventory and KI source-backed baselines.

**When:** Complete Horatius Breaking Stones once; attempt same trade again after verified completed state.

**Then:** Horatius trade accepts item 553 whenever quest is not AVAILABLE, including completed; handler may grant GIL_RATE*400 on repeated CSID 0x0065. No no-duplicate invariant source-backed; treat as possible defect, NOT PASS.

- **MQ-05-S01 — Read-only setup baseline:** Select authorized character, record exact quest IDs via source, fame, variables, held KI and full inventory/Gil. **Expected:** Complete and pinned baseline; otherwise UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-05-baseline`.
- **MQ-05-S02 — Normal client interaction:** Complete Horatius Breaking Stones once; attempt same trade again after verified completed state. **Expected:** Horatius trade accepts item 553 whenever quest is not AVAILABLE, including completed; handler may grant GIL_RATE*400 on repeated CSID 0x0065. No no-duplicate invariant source-backed; treat as possible defect, NOT PASS. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-05-transition`.
- **MQ-05-S03 — Independent authoritative comparison:** Capture NPC CSID and choice plus persisted quest/charvar/KI/inventory/Gil before/after. **Expected:** Source-matched independent post-state needed; otherwise UNKNOWN. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-05-oracle`.
- **MQ-05-S04 — Cleanup and identity verification:** Only owner-approved restoration or quarantine; verify repeated client attempts and no unrelated changes. **Expected:** Clean complete state or BLOCKED. **Client evidence:** talk_to_npc, event_select, wait_for_event, inventory (candidate). **Server evidence:** quest status and exact named char_vars, full server inventory and Gil, keyitem bitsets, source revision and save boundary. **Assertion:** `MQ-05-cleanup`.

**XIHeadless candidates:** talk_to_npc, event_select, wait_for_event, snapshot, inventory, logout. **Missing:** Validated mapped NPC identity/client event options; Reliable relog and event evidence; Read-only authoritative quest and Gil readback. **Readback:** Fixed read-only per-character quest and mission status endpoint; Read-only per-character Gil/quest fame and event option bindings; Complete untruncated inventory and save boundary, reward attribution. **Cleanup:** Do not use GM command to claim gameplay verdict; restore isolated character by approved process. **Source:** [`scripts/zones/Bastok_Markets/npcs/Horatius.lua:18–31`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Horatius.lua#L18-L31), [`scripts/zones/Bastok_Markets/npcs/Horatius.lua:54–74`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Bastok_Markets/npcs/Horatius.lua#L54-L74), [`scripts/commands/checkquest.lua:8–78`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/commands/checkquest.lua#L8-L78). **Verdict:** NOT_RUN.



## Capability matrix and read-only priorities

| Capability | Candidate / available | Gap |
|---|---|---|
| Client NPC/event | XIHeadless `talk_to_npc`, `event_select`, `wait_for_event` | NPC mapping and exact CSID/option evidence accepted per deployed client |
| Quest/mission state | GM `checkquest`, `checkmission` candidate display; Toolkit named-charvar endpoint | Fixed allowlisted SELECT-only quest/mission status + source ID map, independent of GM chat |
| Inventory/KI | Toolkit bounded inventory (100 rows) and KI endpoints | Completeness, reward/Gil/fame, save-boundary alignment |
| Setup | GM add/complete scripts exist | Cannot use direct grants as acceptance; owner-controlled disposable fixtures only |
| Restore/persistence | Approved isolation and generic logout candidate | Reconnect snapshots, persistent quest/KI vars and cleanup proof |

**Ranked read-only substeps:** (1) pin exact NPC source and quest enum and compare to client catalog IDs, (2) inspect approved test character's held KI and named `DistantLoyaltiesProgress` without changing it, (3) inventory baseline + truncation detection, (4) read-only quest status once allowed endpoint is added, (5) historical evidence timeline review. Not enough to advertise ten executable `observe-now` scenarios.

## Schema handoff

The domain JSON is a **non-executable staging artifact**, not accepted strict v1 import. The #1259 schema owner and local integration agent must add typed quest/mission/Gil readbacks, UNKNOWN oracle semantics and step event binding, then reconcile shared JSON serially. All present execution status is design-only and NOT_RUN; no changes to the canonical shared file.
