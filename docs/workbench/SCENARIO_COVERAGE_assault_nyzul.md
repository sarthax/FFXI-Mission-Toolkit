# Assault / Nyzul R5 — source-backed domain scenario coverage

**Issue:** [#1251](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1251) · [Epic #1197](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1197). **DSP source pin:** [`feature/assault-gm-debug-tools@2b71b4425d20ce47941c140b57fac886f28bea73`](https://github.com/sarthax/darkstar-to-valhalla/tree/2b71b4425d20ce47941c140b57fac886f28bea73); **deployed server revision UNKNOWN**. No live execution or merge.

## Safety/semantic source findings

- [`warpassault.lua:1–27`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/commands/warpassault.lua#L1-L27) **bypasses officer/portal eligibility** and has zone-then-second-invocation behavior; it is setup only. [`warpassault.lua:134–190`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/commands/warpassault.lua#L134-L190) leaves/fails an instance rather than naturally expiring it, so it is not a time-expiry oracle.
- [`nyzuldebug.lua:53–94`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/commands/nyzuldebug.lua#L53-L94) permission 1, requires a live instance ID 51, and `complete` forces `instance:setProgress(15)`; `floor <N>` (1–100) primes `N-1` for the next Rune transfer. None proves natural objective completion.
- [`nyzuldebug.lua:95–120`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/commands/nyzuldebug.lua#L95-L120) pinning layout/leader persists until `clear`; cleanup must verify both pins reset. Invalid layout values outside 1–16 and invalid floor outside 1–100 are guarded **in the debug tool**; that does not prove normal client Rune behavior.
- [`nyzul.lua:53–88`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/globals/nyzul.lua#L53-L88) contains six objective categories, but its inline objective names are placeholder text and **not verified client message IDs**. [`Rune_of_Transfer.lua:14–32`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/zones/Nyzul_Isle/npcs/Rune_of_Transfer.lua#L14-L32) documents captured Rune CSID 201 and specifically says the separate exit choice is not wired. Do not invent missing options/packets.
- [`nyzul_isle_investigation.lua:1–19`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/zones/Nyzul_Isle/instances/nyzul_isle_investigation.lua#L1-L19) says entry gating lives in another NPC. This draft does not infer a permit predicate or reward/expiry effect from a debug helper.

## Scenario lanes and oracle gaps

| Case | Scenario | Primary lane | Expected outcome confidence |
|---|---|---|---|
| ASLT-01 | Enter eligible instance and complete objective | `needs-mutation` | UNKNOWN — GM warpassault bypasses standard eligibility and cannot validate gameplay progression |
| ASLT-02 | Missing permit or eligibility rejects entry | `needs-mutation` | UNKNOWN — blocked normal entry and invariant no live instance/reward |
| ASLT-03 | Expired timer fails without reward | `needs-mutation` | UNKNOWN — timer/failure callback and non-reward persistence not independently pinned |
| ASLT-04 | Repeat completion cannot duplicate rewards | `needs-mutation` | UNKNOWN — reward duplication prevention requires per-instance source and full count readback |
| NYZ-01 | Floor layout and objective completion | `needs-mutation` | UNKNOWN — local debug complete forces progress=15 and is not natural proof; layout random unless approved pin |
| NYZ-02 | Invalid floor transitions rejected | `needs-mutation` | Source debug floor arguments outside 1..100 rejected before mutation; gameplay Rune transition rejection UNKNOWN |

All full gameplay tests are `needs-mutation`. Their initial read-only setup is `needs-readback` because current bounded supervisor queries have no instance ID/objective/progress/timer/claim state. A deployed-branch check is still UNKNOWN, not proof of `needs-deploy`. Zero complete cases qualify as `observe-now`.

## Ordered scenario definitions

### ASLT-01 — Enter eligible instance and complete objective

**Purpose/rationale:** Verify enter eligible instance and complete objective using source-backed normal gameplay semantics, not GM setup acknowledgements. Normal Assault entry, objective/reward oracle and client packet evidence not pinned

**Given:** Approved disposable character and controlled instance profile; Exact permit/floor/objective fixture source and server revision pinned or UNKNOWN; Before-state includes actual instance and per-character rewards.

**When:** Player uses normal entrance requirements; completes reviewed naturally bounded objective.

**Then:** UNKNOWN — GM warpassault bypasses standard eligibility and cannot validate gameplay progression.

- **ASLT-01-S01 — Authorize and snapshot:** Check disposable character, configured server SHA and detailed instance state. **Expected:** Complete before-state with exact instance/zone/permit/reward; UNKNOWN if missing. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-01-pre_state`.
- **ASLT-01-S02 — Execute only when approved:** Player uses normal entrance requirements; completes reviewed naturally bounded objective. **Expected:** UNKNOWN — GM warpassault bypasses standard eligibility and cannot validate gameplay progression. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-01-transition`.
- **ASLT-01-S03 — Independent outcome comparison:** Compare actual client event, instance local vars, time and full reward mutations. **Expected:** PASS only after independent oracle and full state; otherwise UNKNOWN. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-01-oracle`.
- **ASLT-01-S04 — Remove debug pins and verify cleanup:** Use operator-approved isolation/teardown, clear any layout/leader pins and verify no stale instance. **Expected:** Restored profile and confirmed instance removal or quarantine as BLOCKED. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-01-cleanup`.

**XIHeadless candidates:** move_to, engage, party, zone_to, wait_for_event, snapshot, inventory; acceptance UNKNOWN. **Missing readback:** Read-only instance ID,status,timeRemaining,objective/progress,localvar snapshot; Approved per-character reward/assault points baseline and change; Per-instance entity and Rune client event binding/decoder. **Mutation and cleanup:** Debug complete/floor/warpassault are fixture/bypass, not oracle; Exit/expire, clear Nyzul_Debug_ForceLayout and Nyzul_Debug_ForceLeader if ever set, verify no stale instance. **Source:** [`scripts/commands/warpassault.lua:193–259`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/commands/warpassault.lua#L193-L259), [`scripts/zones/Leujaoam_Sanctum/instances/leujaoam_cleansing.lua:1–25`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/zones/Leujaoam_Sanctum/instances/leujaoam_cleansing.lua#L1-L25). No executed verdict.


### ASLT-02 — Missing permit or eligibility rejects entry

**Purpose/rationale:** Verify missing permit or eligibility rejects entry using source-backed normal gameplay semantics, not GM setup acknowledgements. Exact permit source and entry guard not verified; GM warpassault cannot be used

**Given:** Approved disposable character and controlled instance profile; Exact permit/floor/objective fixture source and server revision pinned or UNKNOWN; Before-state includes actual instance and per-character rewards.

**When:** Attempt normal entrance without one independently documented prerequisite.

**Then:** UNKNOWN — blocked normal entry and invariant no live instance/reward.

- **ASLT-02-S01 — Authorize and snapshot:** Check disposable character, configured server SHA and detailed instance state. **Expected:** Complete before-state with exact instance/zone/permit/reward; UNKNOWN if missing. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-02-pre_state`.
- **ASLT-02-S02 — Execute only when approved:** Attempt normal entrance without one independently documented prerequisite. **Expected:** UNKNOWN — blocked normal entry and invariant no live instance/reward. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-02-transition`.
- **ASLT-02-S03 — Independent outcome comparison:** Compare actual client event, instance local vars, time and full reward mutations. **Expected:** PASS only after independent oracle and full state; otherwise UNKNOWN. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-02-oracle`.
- **ASLT-02-S04 — Remove debug pins and verify cleanup:** Use operator-approved isolation/teardown, clear any layout/leader pins and verify no stale instance. **Expected:** Restored profile and confirmed instance removal or quarantine as BLOCKED. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-02-cleanup`.

**XIHeadless candidates:** move_to, engage, party, zone_to, wait_for_event, snapshot, inventory; acceptance UNKNOWN. **Missing readback:** Read-only instance ID,status,timeRemaining,objective/progress,localvar snapshot; Approved per-character reward/assault points baseline and change; Per-instance entity and Rune client event binding/decoder. **Mutation and cleanup:** Debug complete/floor/warpassault are fixture/bypass, not oracle; Exit/expire, clear Nyzul_Debug_ForceLayout and Nyzul_Debug_ForceLeader if ever set, verify no stale instance. **Source:** [`scripts/commands/warpassault.lua:31–112`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/commands/warpassault.lua#L31-L112), [`scripts/zones/Nyzul_Isle/instances/nyzul_isle_investigation.lua:1–19`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/zones/Nyzul_Isle/instances/nyzul_isle_investigation.lua#L1-L19). No executed verdict.


### ASLT-03 — Expired timer fails without reward

**Purpose/rationale:** Verify expired timer fails without reward using source-backed normal gameplay semantics, not GM setup acknowledgements. Timer-expiry and cleanup authoritative queries absent; GM leave forcibly fails not equivalent to natural expiry

**Given:** Approved disposable character and controlled instance profile; Exact permit/floor/objective fixture source and server revision pinned or UNKNOWN; Before-state includes actual instance and per-character rewards.

**When:** Run an owner-approved isolated instance until independently confirmed expiry.

**Then:** UNKNOWN — timer/failure callback and non-reward persistence not independently pinned.

- **ASLT-03-S01 — Authorize and snapshot:** Check disposable character, configured server SHA and detailed instance state. **Expected:** Complete before-state with exact instance/zone/permit/reward; UNKNOWN if missing. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-03-pre_state`.
- **ASLT-03-S02 — Execute only when approved:** Run an owner-approved isolated instance until independently confirmed expiry. **Expected:** UNKNOWN — timer/failure callback and non-reward persistence not independently pinned. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-03-transition`.
- **ASLT-03-S03 — Independent outcome comparison:** Compare actual client event, instance local vars, time and full reward mutations. **Expected:** PASS only after independent oracle and full state; otherwise UNKNOWN. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-03-oracle`.
- **ASLT-03-S04 — Remove debug pins and verify cleanup:** Use operator-approved isolation/teardown, clear any layout/leader pins and verify no stale instance. **Expected:** Restored profile and confirmed instance removal or quarantine as BLOCKED. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-03-cleanup`.

**XIHeadless candidates:** move_to, engage, party, zone_to, wait_for_event, snapshot, inventory; acceptance UNKNOWN. **Missing readback:** Read-only instance ID,status,timeRemaining,objective/progress,localvar snapshot; Approved per-character reward/assault points baseline and change; Per-instance entity and Rune client event binding/decoder. **Mutation and cleanup:** Debug complete/floor/warpassault are fixture/bypass, not oracle; Exit/expire, clear Nyzul_Debug_ForceLayout and Nyzul_Debug_ForceLeader if ever set, verify no stale instance. **Source:** [`scripts/commands/warpassault.lua:134–190`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/commands/warpassault.lua#L134-L190), [`scripts/zones/Leujaoam_Sanctum/instances/leujaoam_cleansing.lua:1–25`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/zones/Leujaoam_Sanctum/instances/leujaoam_cleansing.lua#L1-L25). No executed verdict.


### ASLT-04 — Repeat completion cannot duplicate rewards

**Purpose/rationale:** Verify repeat completion cannot duplicate rewards using source-backed normal gameplay semantics, not GM setup acknowledgements. Reward choice script and duplicate-claim predicate not source-pinned

**Given:** Approved disposable character and controlled instance profile; Exact permit/floor/objective fixture source and server revision pinned or UNKNOWN; Before-state includes actual instance and per-character rewards.

**When:** After verified natural completion attempt same claim/turn-in again on disposable profile.

**Then:** UNKNOWN — reward duplication prevention requires per-instance source and full count readback.

- **ASLT-04-S01 — Authorize and snapshot:** Check disposable character, configured server SHA and detailed instance state. **Expected:** Complete before-state with exact instance/zone/permit/reward; UNKNOWN if missing. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-04-pre_state`.
- **ASLT-04-S02 — Execute only when approved:** After verified natural completion attempt same claim/turn-in again on disposable profile. **Expected:** UNKNOWN — reward duplication prevention requires per-instance source and full count readback. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-04-transition`.
- **ASLT-04-S03 — Independent outcome comparison:** Compare actual client event, instance local vars, time and full reward mutations. **Expected:** PASS only after independent oracle and full state; otherwise UNKNOWN. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-04-oracle`.
- **ASLT-04-S04 — Remove debug pins and verify cleanup:** Use operator-approved isolation/teardown, clear any layout/leader pins and verify no stale instance. **Expected:** Restored profile and confirmed instance removal or quarantine as BLOCKED. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `ASLT-04-cleanup`.

**XIHeadless candidates:** move_to, engage, party, zone_to, wait_for_event, snapshot, inventory; acceptance UNKNOWN. **Missing readback:** Read-only instance ID,status,timeRemaining,objective/progress,localvar snapshot; Approved per-character reward/assault points baseline and change; Per-instance entity and Rune client event binding/decoder. **Mutation and cleanup:** Debug complete/floor/warpassault are fixture/bypass, not oracle; Exit/expire, clear Nyzul_Debug_ForceLayout and Nyzul_Debug_ForceLeader if ever set, verify no stale instance. **Source:** [`scripts/zones/Leujaoam_Sanctum/instances/leujaoam_cleansing.lua:1–25`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/zones/Leujaoam_Sanctum/instances/leujaoam_cleansing.lua#L1-L25), [`scripts/commands/warpassault.lua:193–259`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/commands/warpassault.lua#L193-L259). No executed verdict.


### NYZ-01 — Floor layout and objective completion

**Purpose/rationale:** Verify floor layout and objective completion using source-backed normal gameplay semantics, not GM setup acknowledgements. Normal objective branch, instance state, selection/layout readback and accepted Rune events missing

**Given:** Approved disposable character and controlled instance profile; Exact permit/floor/objective fixture source and server revision pinned or UNKNOWN; Before-state includes actual instance and per-character rewards.

**When:** With approved live Nyzul instance, play natural objective and use Rune transfer.

**Then:** UNKNOWN — local debug complete forces progress=15 and is not natural proof; layout random unless approved pin.

- **NYZ-01-S01 — Authorize and snapshot:** Check disposable character, configured server SHA and detailed instance state. **Expected:** Complete before-state with exact instance/zone/permit/reward; UNKNOWN if missing. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `NYZ-01-pre_state`.
- **NYZ-01-S02 — Execute only when approved:** With approved live Nyzul instance, play natural objective and use Rune transfer. **Expected:** UNKNOWN — local debug complete forces progress=15 and is not natural proof; layout random unless approved pin. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `NYZ-01-transition`.
- **NYZ-01-S03 — Independent outcome comparison:** Compare actual client event, instance local vars, time and full reward mutations. **Expected:** PASS only after independent oracle and full state; otherwise UNKNOWN. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `NYZ-01-oracle`.
- **NYZ-01-S04 — Remove debug pins and verify cleanup:** Use operator-approved isolation/teardown, clear any layout/leader pins and verify no stale instance. **Expected:** Restored profile and confirmed instance removal or quarantine as BLOCKED. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `NYZ-01-cleanup`.

**XIHeadless candidates:** move_to, engage, party, zone_to, wait_for_event, snapshot, inventory; acceptance UNKNOWN. **Missing readback:** Read-only instance ID,status,timeRemaining,objective/progress,localvar snapshot; Approved per-character reward/assault points baseline and change; Per-instance entity and Rune client event binding/decoder. **Mutation and cleanup:** Debug complete/floor/warpassault are fixture/bypass, not oracle; Exit/expire, clear Nyzul_Debug_ForceLayout and Nyzul_Debug_ForceLeader if ever set, verify no stale instance. **Source:** [`scripts/commands/nyzuldebug.lua:50–121`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/commands/nyzuldebug.lua#L50-L121), [`scripts/globals/nyzul.lua:53–88`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/globals/nyzul.lua#L53-L88), [`scripts/zones/Nyzul_Isle/npcs/Rune_of_Transfer.lua:14–32`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/zones/Nyzul_Isle/npcs/Rune_of_Transfer.lua#L14-L32). No executed verdict.


### NYZ-02 — Invalid floor transitions rejected

**Purpose/rationale:** Verify invalid floor transitions rejected using source-backed normal gameplay semantics, not GM setup acknowledgements. No trusted instance local-vars readback; source diagnostic rejection != normal game event result

**Given:** Approved disposable character and controlled instance profile; Exact permit/floor/objective fixture source and server revision pinned or UNKNOWN; Before-state includes actual instance and per-character rewards.

**When:** Evaluate invalid debug floor command only as manual diagnostic design; separate normal Rune invalid choice test.

**Then:** Source debug floor arguments outside 1..100 rejected before mutation; gameplay Rune transition rejection UNKNOWN.

- **NYZ-02-S01 — Authorize and snapshot:** Check disposable character, configured server SHA and detailed instance state. **Expected:** Complete before-state with exact instance/zone/permit/reward; UNKNOWN if missing. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `NYZ-02-pre_state`.
- **NYZ-02-S02 — Execute only when approved:** Evaluate invalid debug floor command only as manual diagnostic design; separate normal Rune invalid choice test. **Expected:** Source debug floor arguments outside 1..100 rejected before mutation; gameplay Rune transition rejection UNKNOWN. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `NYZ-02-transition`.
- **NYZ-02-S03 — Independent outcome comparison:** Compare actual client event, instance local vars, time and full reward mutations. **Expected:** PASS only after independent oracle and full state; otherwise UNKNOWN. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `NYZ-02-oracle`.
- **NYZ-02-S04 — Remove debug pins and verify cleanup:** Use operator-approved isolation/teardown, clear any layout/leader pins and verify no stale instance. **Expected:** Restored profile and confirmed instance removal or quarantine as BLOCKED. **Client:** Client event/rune/action timeline, zone and inventory. **Authoritative:** Authoritative instance ID, status, timer, objective/progress and local vars, Reward/point inventory deltas before and after. **Assertion:** `NYZ-02-cleanup`.

**XIHeadless candidates:** move_to, engage, party, zone_to, wait_for_event, snapshot, inventory; acceptance UNKNOWN. **Missing readback:** Read-only instance ID,status,timeRemaining,objective/progress,localvar snapshot; Approved per-character reward/assault points baseline and change; Per-instance entity and Rune client event binding/decoder. **Mutation and cleanup:** Debug complete/floor/warpassault are fixture/bypass, not oracle; Exit/expire, clear Nyzul_Debug_ForceLayout and Nyzul_Debug_ForceLeader if ever set, verify no stale instance. **Source:** [`scripts/commands/nyzuldebug.lua:72–95`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/commands/nyzuldebug.lua#L72-L95), [`scripts/zones/Nyzul_Isle/npcs/Rune_of_Transfer.lua:14–32`](https://github.com/sarthax/darkstar-to-valhalla/blob/2b71b4425d20ce47941c140b57fac886f28bea73/scripts/zones/Nyzul_Isle/npcs/Rune_of_Transfer.lua#L14-L32). No executed verdict.



## Capability matrix and ranked observation opportunities

| Capability | Source/candidate | Blocking gap |
|---|---|---|
| Instance admission | GM bypass `warpassault` exists; normal NPC entry source separate | Exact normal permit and eligibility oracle, source linked NPC path |
| Objective/progress | `nyzuldebug complete` and `nyzul.lua` objective enums | Read-only runtime instance local vars and naturally observed objective completion |
| Floor/Rune | Rune-of-Transfer client capture comments and debug floor command | Verified client options/packet bindings, timer and floor readback |
| Reward/repeat | Candidate XIHeadless `inventory`/session | Approved reward/point oracle with full before/after and persistence |
| Cleanup | GM `leave`, layout/leader `clear` source | Owner-controlled teardown and independent instance disappearance confirmation |

**Ranked read-only *substeps*, not complete cases:** (1) Compare deployed instance table/config and current DSP SHA (without entry), (2) static audit of requested Nyzul floor 1–100 and layout 1–16 bounds, (3) source-backed static mapping of objective names to enumerations, (4) review approved-character inventory/keyitem baseline, (5) read-only instance state/timer once a bounded endpoint is accepted. Do not fabricate ten cross-domain `observe-now` executions.

## Canonical compatibility / open dependencies

Companion `data/testing/domain_drafts/assault_nyzul.json` is staged design only. No shared JSON changed. The strict v1 canonical loader cannot yet represent instance local-var snapshots, step-specific runtime capabilities, source-cited UNKNOWN expectations or approvals. #1259 schema owner and local agent must map the draft through the accepted extension *before* manual import. No execution, GM command dispatch, or account usage authorized by this PR; source availability ≠ live server deployment or gameplay verification.

## Source-pin versus current DSP main — 2026-10-21 readiness erratum

The staged scenarios reference `feature/assault-gm-debug-tools@2b71b4425d20ce47941c140b57fac886f28bea73`. The pinned `scripts/commands/nyzuldebug.lua:62–67` permits only a live instance ID **51**, and its leader lookup at line 108 hardcodes the `mobs[51]` table. **Current** DSP `main@86d4467d446569c741d76d296e640c3b844ad844` permits **51 or 52** at line 64 and looks up `mobs[instance:getID()]` at line 108. These implementations must not be treated as interchangeable when an oracle is rebound; exact live server commit remains UNKNOWN.

Both checked revisions use `complete` and `floor` as **force-progression diagnostics**, not independent proof of natural Rune objective completion, entry eligibility or reward attribution. Preserve NYZ-01/02 as `needs-mutation` with prior instance-state readback and explicit owner permission. See the [R5 readiness audit PR #1292](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1292) for GAP-06/GAP-11 and proposed tests. **No actual scenario steps or runner policies changed here.**
