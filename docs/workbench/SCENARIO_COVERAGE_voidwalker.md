# Voidwalker — R5 domain scenario and capability matrix

**Issue:** [#1250](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1250) · **Epic:** [#1197](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1197) · **DSP:** [`sarthax/darkstar-to-valhalla` `feature/voidwalker` at `5fac778004364e2991df779845d7403e64a8dc23`](https://github.com/sarthax/darkstar-to-valhalla/tree/5fac778004364e2991df779845d7403e64a8dc23) · **Toolkit base:** `7835d5019f1939f3d20a402240c649b17aea6ec6`.

**Status: seven human-readable source-informed design specifications; zero authorized/runnable cases and zero independently verified gameplay verdicts.** No commands, clients, or server changes were executed. The deployed DSP branch/revision and `ENABLE_VOIDWALKER` are **UNKNOWN**.

## Source-backed rules, with boundaries

- In [`voidwalker.lua:293–334`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L293-L334), `/heal` returns when Voidwalker is disabled, the current zone is unsupported, or no eligible abyssite is held. A nearest eligible unclaimed NM within **four yalms** is exposed; >= **300 yalms** emits a too-far message; otherwise a hint is emitted. These are *conditional source rules*, not runtime observations.
- [`voidwalker.lua:101–116`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L101-L116) filters zone-mapped mobs by eligible KI, mob HP and unset `[VoidWalker]PopedBy` local var. The guard prevents reuse of a currently tracked mob; it **does not establish a blanket single-NM/no-cooldown invariant**, since other eligible mobs might remain.
- [`voidwalker.lua:153–177`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L153-L177) only upgrades abyssite on `math.random(1,10)==5`, so one kill **must not** assert a deterministic upgrade. [`voidwalker.lua:262–288`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L262-L288) shows participation/death conditions. Do not infer a drop oracle from this upgrade function.
- [`voidwalker.lua:180–192`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L180-L192), [`238–259`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L238-L259) explicitly reset encounter local variables on disengage/despawn, but **do not independently prove zoning cleanup**. The 7,200-second or 25-distance checks apply to the shown fight logic only.
- [`voidwalker_data.lua:1–48`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker_data.lua#L1-L48) provides generated IDs, zones, positions and dialog IDs; its header says positions require navmesh validation. Do not invent or assume a valid navigation route. [`mobskilldiag.lua:8–25`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/commands/mobskilldiag.lua#L8-L25) reports mob diagnostics, not independently verified skill outcomes.
- Toolkit's [`data/voidwalker/validation.json`](https://github.com/sarthax/FFXI-Mission-Toolkit/blob/7835d5019f1939f3d20a402240c649b17aea6ec6/data/voidwalker/validation.json) records historical manually labeled observations; they do not establish newly authenticated runtime PASS. [`data/voidwalker/backlog.json`](https://github.com/sarthax/FFXI-Mission-Toolkit/blob/7835d5019f1939f3d20a402240c649b17aea6ec6/data/voidwalker/backlog.json) flags unported/guessed skills, drops, and second-zone/navmesh gaps.

## Lane and oracle matrix

| Case | Behavior | Primary lane | Top gap |
|---|---|---|---|
| VWK-01 | Clear abyssite: hint, pop, fight, tier transition | `needs-mutation` | Keyitem readback exists but no fixed-query mob pop/owner state readback; /heal and combat capability not accepted |
| VWK-02 | Colorful/black progression in a second zone | `needs-mutation` | Second-zone navmesh spots and tier readiness unverified, no automatic keyitem grant allowed |
| VWK-03 | No abyssite prevents pop | `needs-mutation` | Server mob readback absent; no-abyssite fixture and /heal action not accepted |
| VWK-04 | Wrong zone or tier does not trigger target NM | `needs-mutation` | Requires zone-specific authoritative mob/claim/visibility readback and verified mapping |
| VWK-05 | Repeat pop cannot duplicate the same NM | `needs-mutation` | No local-var readback; no source-backed global cooldown guarantee |
| VWK-06 | Death, disengage and zoning clear encounter state | `needs-mutation` | Zoning cleanup and death path not equivalent to disengage; authoritative mob readback missing |
| VWK-07 | Skill effects and rewards match server definitions | `needs-mutation` | Backlog records unported/guessed skill effects and drops; do not promote prior manual OK statuses to verified oracle |

All seven are `needs-mutation` because a complete gameplay scenario requires live client interaction or combat; server-side readback is a separate `needs-readback` dependency. No complete `observe-now` scenario has been established. `needs-deploy` is **UNKNOWN**, not an asserted deployment fact.

## Capabilities, provenance, and readback

| Capability | Source/current candidate | Missing for authoritative verification |
|---|---|---|
| Held/persisted abyssites | Guarded Toolkit `/api/supervisor/test-character-keyitems`; candidate XiHeadless client observations | Independently comparable client/DB KI snapshots at a confirmed save boundary |
| NPC/dialog and heal | XIHeadless `talk_to_npc`, `move_to`, `snapshot` candidate commands | Accepted `/heal` and dialog event capture, with verified source ID mapping and full timeline |
| NM spawn/claim | `nearby_entities` and source `POPPED_BY` flag | Fixed read-only server mob state, `POPPED_BY/WITH/AT` and claim/HP/status, exact zone/mob identity |
| Combat and rewards | XIHeadless `engage` and event capture candidates | Reviewed skill/damage/drop source definitions, authoritative item/reward readback and no inferred PASS |
| Location/nav | Generated `voidwalker_data.lua` positions | Navmesh qualification; avoid treating generated coordinates as accepted paths |
| Deployed system | DSP source branch commit pinned above | Running server SHA, `ENABLE_VOIDWALKER`, KI data and configuration snapshot |

The missing `POPPED_*` fields are **mob runtime local variables**, not `char_vars`; querying `char_vars` would be a false surrogate. A proposed read-only observation capability must be fixed-query, owner-authorized, bounded by exact approved character/zone and mob IDs, and return completeness and timestamps.

## Readable Given/When/Then scenarios and ordered steps

### VWK-01 — Clear abyssite: hint, pop, fight, tier transition

**Purpose:** Verify clear abyssite: hint, pop, fight, tier transition without inferring results from a command being accepted. **Rationale:** Keyitem readback exists but no fixed-query mob pop/owner state readback; /heal and combat capability not accepted

**Given:** Authorized disposable character and known zone/keyitem fixture; Active server DSP revision and enabled flag established or UNKNOWN; Pre-state mob/claim and complete key-item readback.

**When:** Use approved clear-abyssite fixture, rest near source-defined candidate, then defeat popped NM.

**Then:** Source: eligible nearest mob within four yalms is made targetable; upgrade occurs only on RNG 1/10 branch, so observed upgrade is UNKNOWN.

- **VWK-01-S01 — Baseline:** Capture approved character, zone, held/persisted keyitems, and matching mobs. **Expected:** Complete named fixture and before-state; else UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-01-baseline_complete`.
- **VWK-01-S02 — Action:** Use approved clear-abyssite fixture, rest near source-defined candidate, then defeat popped NM. **Expected:** Source: eligible nearest mob within four yalms is made targetable; upgrade occurs only on RNG 1/10 branch, so observed upgrade is UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-01-action_oracle`.
- **VWK-01-S03 — Independent comparison:** Capture client event/monster state plus authoritative KI and spawn/local-var readback. **Expected:** Compare to documented conditions; VWK keyitem before/after plus mob local vars, spawn/claim and kill evidence; absent authoritative capture => UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-01-server_oracle`.
- **VWK-01-S04 — Cleanup:** Approved operator verifies no unintended live mob, claim or KI change; quarantine incomplete runs. **Expected:** Verified restoration or BLOCKED; no remote execution here. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-01-cleanup_verified`.

**Capabilities:** snapshot, nearby_entities, move_to, engage, wait_for_event, inventory, key_items observation candidate (unverified), missing Accepted rest/heal interaction and hint capture; Runtime authoritative mob local vars; Per-combat effect/drop structured evidence. **Readback:** VWK keyitem before/after plus mob local vars, spawn/claim and kill evidence. **Cleanup:** verify despawn and keyitem baseline; isolate spawned mob; quarantine if incomplete. **Gaps:** Keyitem readback exists but no fixed-query mob pop/owner state readback; /heal and combat capability not accepted; Deployment revision and ENABLE_VOIDWALKER runtime setting UNKNOWN; Mob local-vars/claim authoritative readback not available. **Mutation:** explicitly disabled pending per-case owner approval; lane `needs-mutation`.

**Source-backed assertions:** [`scripts/globals/voidwalker.lua:35–65`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L35-L65), [`scripts/globals/voidwalker.lua:100–130`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L100-L130), [`scripts/globals/voidwalker.lua:292–334`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L292-L334), [`scripts/globals/voidwalker.lua:261–288`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L261-L288), [`scripts/globals/voidwalker.lua:153–177`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L153-L177). No observed PASS is asserted.

### VWK-02 — Colorful/black progression in a second zone

**Purpose:** Verify colorful/black progression in a second zone without inferring results from a command being accepted. **Rationale:** Second-zone navmesh spots and tier readiness unverified, no automatic keyitem grant allowed

**Given:** Authorized disposable character and known zone/keyitem fixture; Active server DSP revision and enabled flag established or UNKNOWN; Pre-state mob/claim and complete key-item readback.

**When:** Use separately approved colorful/black keyitem and zone fixture; invoke actual /heal and fight.

**Then:** Source uses zone-specific mob mapping; black/colored KI may be consumed on pop. Specific second-zone outcome UNKNOWN without deployed data/config.

- **VWK-02-S01 — Baseline:** Capture approved character, zone, held/persisted keyitems, and matching mobs. **Expected:** Complete named fixture and before-state; else UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-02-baseline_complete`.
- **VWK-02-S02 — Action:** Use separately approved colorful/black keyitem and zone fixture; invoke actual /heal and fight. **Expected:** Source uses zone-specific mob mapping; black/colored KI may be consumed on pop. Specific second-zone outcome UNKNOWN without deployed data/config. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-02-action_oracle`.
- **VWK-02-S03 — Independent comparison:** Capture client event/monster state plus authoritative KI and spawn/local-var readback. **Expected:** Compare to documented conditions; Zone-aware KI set, targeted mob identity, mutation before/after; absent authoritative capture => UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-02-server_oracle`.
- **VWK-02-S04 — Cleanup:** Approved operator verifies no unintended live mob, claim or KI change; quarantine incomplete runs. **Expected:** Verified restoration or BLOCKED; no remote execution here. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-02-cleanup_verified`.

**Capabilities:** snapshot, nearby_entities, move_to, engage, wait_for_event, inventory, key_items observation candidate (unverified), missing Accepted rest/heal interaction and hint capture; Runtime authoritative mob local vars; Per-combat effect/drop structured evidence. **Readback:** Zone-aware KI set, targeted mob identity, mutation before/after. **Cleanup:** verify despawn and keyitem baseline; isolate spawned mob; quarantine if incomplete. **Gaps:** Second-zone navmesh spots and tier readiness unverified, no automatic keyitem grant allowed; Deployment revision and ENABLE_VOIDWALKER runtime setting UNKNOWN; Mob local-vars/claim authoritative readback not available. **Mutation:** explicitly disabled pending per-case owner approval; lane `needs-mutation`.

**Source-backed assertions:** [`scripts/globals/voidwalker.lua:100–130`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L100-L130), [`scripts/globals/voidwalker.lua:292–334`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L292-L334), [`scripts/globals/voidwalker_data.lua:1–48`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker_data.lua#L1-L48), [`scripts/globals/voidwalker.lua:153–177`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L153-L177). No observed PASS is asserted.

### VWK-03 — No abyssite prevents pop

**Purpose:** Verify no abyssite prevents pop without inferring results from a command being accepted. **Rationale:** Server mob readback absent; no-abyssite fixture and /heal action not accepted

**Given:** Authorized disposable character and known zone/keyitem fixture; Active server DSP revision and enabled flag established or UNKNOWN; Pre-state mob/claim and complete key-item readback.

**When:** Confirm no eligible abyssite in persisted and held KI set, then /heal in a reviewed zone.

**Then:** Source: onHealing returns immediately when eligible abyssites array empty; no target NM may be attributed to this action.

- **VWK-03-S01 — Baseline:** Capture approved character, zone, held/persisted keyitems, and matching mobs. **Expected:** Complete named fixture and before-state; else UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-03-baseline_complete`.
- **VWK-03-S02 — Action:** Confirm no eligible abyssite in persisted and held KI set, then /heal in a reviewed zone. **Expected:** Source: onHealing returns immediately when eligible abyssites array empty; no target NM may be attributed to this action. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-03-action_oracle`.
- **VWK-03-S03 — Independent comparison:** Capture client event/monster state plus authoritative KI and spawn/local-var readback. **Expected:** Compare to documented conditions; Held/persisted KI before/after, per-mob spawned/claimed state; absent authoritative capture => UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-03-server_oracle`.
- **VWK-03-S04 — Cleanup:** Approved operator verifies no unintended live mob, claim or KI change; quarantine incomplete runs. **Expected:** Verified restoration or BLOCKED; no remote execution here. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-03-cleanup_verified`.

**Capabilities:** snapshot, nearby_entities, move_to, engage, wait_for_event, inventory, key_items observation candidate (unverified), missing Accepted rest/heal interaction and hint capture; Runtime authoritative mob local vars; Per-combat effect/drop structured evidence. **Readback:** Held/persisted KI before/after, per-mob spawned/claimed state. **Cleanup:** verify despawn and keyitem baseline; isolate spawned mob; quarantine if incomplete. **Gaps:** Server mob readback absent; no-abyssite fixture and /heal action not accepted; Deployment revision and ENABLE_VOIDWALKER runtime setting UNKNOWN; Mob local-vars/claim authoritative readback not available. **Mutation:** explicitly disabled pending per-case owner approval; lane `needs-mutation`.

**Source-backed assertions:** [`scripts/globals/voidwalker.lua:35–65`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L35-L65), [`scripts/globals/voidwalker.lua:292–334`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L292-L334). No observed PASS is asserted.

### VWK-04 — Wrong zone or tier does not trigger target NM

**Purpose:** Verify wrong zone or tier does not trigger target nm without inferring results from a command being accepted. **Rationale:** Requires zone-specific authoritative mob/claim/visibility readback and verified mapping

**Given:** Authorized disposable character and known zone/keyitem fixture; Active server DSP revision and enabled flag established or UNKNOWN; Pre-state mob/claim and complete key-item readback.

**When:** Choose a source-mapped zone and a keyitem not mapped to the target in that zone.

**Then:** Source filters candidate mobs by zone and keyitem mapping; specific no-pop observed state UNKNOWN.

- **VWK-04-S01 — Baseline:** Capture approved character, zone, held/persisted keyitems, and matching mobs. **Expected:** Complete named fixture and before-state; else UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-04-baseline_complete`.
- **VWK-04-S02 — Action:** Choose a source-mapped zone and a keyitem not mapped to the target in that zone. **Expected:** Source filters candidate mobs by zone and keyitem mapping; specific no-pop observed state UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-04-action_oracle`.
- **VWK-04-S03 — Independent comparison:** Capture client event/monster state plus authoritative KI and spawn/local-var readback. **Expected:** Compare to documented conditions; Zone, eligible KI mapping, mob identity/status before/after; absent authoritative capture => UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-04-server_oracle`.
- **VWK-04-S04 — Cleanup:** Approved operator verifies no unintended live mob, claim or KI change; quarantine incomplete runs. **Expected:** Verified restoration or BLOCKED; no remote execution here. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-04-cleanup_verified`.

**Capabilities:** snapshot, nearby_entities, move_to, engage, wait_for_event, inventory, key_items observation candidate (unverified), missing Accepted rest/heal interaction and hint capture; Runtime authoritative mob local vars; Per-combat effect/drop structured evidence. **Readback:** Zone, eligible KI mapping, mob identity/status before/after. **Cleanup:** verify despawn and keyitem baseline; isolate spawned mob; quarantine if incomplete. **Gaps:** Requires zone-specific authoritative mob/claim/visibility readback and verified mapping; Deployment revision and ENABLE_VOIDWALKER runtime setting UNKNOWN; Mob local-vars/claim authoritative readback not available. **Mutation:** explicitly disabled pending per-case owner approval; lane `needs-mutation`.

**Source-backed assertions:** [`scripts/globals/voidwalker.lua:100–130`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L100-L130), [`scripts/globals/voidwalker.lua:292–334`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L292-L334), [`scripts/globals/voidwalker_data.lua:1–48`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker_data.lua#L1-L48). No observed PASS is asserted.

### VWK-05 — Repeat pop cannot duplicate the same NM

**Purpose:** Verify repeat pop cannot duplicate the same nm without inferring results from a command being accepted. **Rationale:** No local-var readback; no source-backed global cooldown guarantee

**Given:** Authorized disposable character and known zone/keyitem fixture; Active server DSP revision and enabled flag established or UNKNOWN; Pre-state mob/claim and complete key-item readback.

**When:** Use a monitored already-popped NM; /heal again without resetting it.

**Then:** Source skips candidates where POPPED_BY is nonzero; another candidate can still pop, so blanket no-NM or cooldown claims are UNKNOWN.

- **VWK-05-S01 — Baseline:** Capture approved character, zone, held/persisted keyitems, and matching mobs. **Expected:** Complete named fixture and before-state; else UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-05-baseline_complete`.
- **VWK-05-S02 — Action:** Use a monitored already-popped NM; /heal again without resetting it. **Expected:** Source skips candidates where POPPED_BY is nonzero; another candidate can still pop, so blanket no-NM or cooldown claims are UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-05-action_oracle`.
- **VWK-05-S03 — Independent comparison:** Capture client event/monster state plus authoritative KI and spawn/local-var readback. **Expected:** Compare to documented conditions; POPPED_BY/POPPED_AT local vars and distinct mob counts before/after; absent authoritative capture => UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-05-server_oracle`.
- **VWK-05-S04 — Cleanup:** Approved operator verifies no unintended live mob, claim or KI change; quarantine incomplete runs. **Expected:** Verified restoration or BLOCKED; no remote execution here. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-05-cleanup_verified`.

**Capabilities:** snapshot, nearby_entities, move_to, engage, wait_for_event, inventory, key_items observation candidate (unverified), missing Accepted rest/heal interaction and hint capture; Runtime authoritative mob local vars; Per-combat effect/drop structured evidence. **Readback:** POPPED_BY/POPPED_AT local vars and distinct mob counts before/after. **Cleanup:** verify despawn and keyitem baseline; isolate spawned mob; quarantine if incomplete. **Gaps:** No local-var readback; no source-backed global cooldown guarantee; Deployment revision and ENABLE_VOIDWALKER runtime setting UNKNOWN; Mob local-vars/claim authoritative readback not available. **Mutation:** explicitly disabled pending per-case owner approval; lane `needs-mutation`.

**Source-backed assertions:** [`scripts/globals/voidwalker.lua:100–130`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L100-L130), [`scripts/globals/voidwalker.lua:292–334`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L292-L334), [`scripts/globals/voidwalker.lua:180–192`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L180-L192). No observed PASS is asserted.

### VWK-06 — Death, disengage and zoning clear encounter state

**Purpose:** Verify death, disengage and zoning clear encounter state without inferring results from a command being accepted. **Rationale:** Zoning cleanup and death path not equivalent to disengage; authoritative mob readback missing

**Given:** Authorized disposable character and known zone/keyitem fixture; Active server DSP revision and enabled flag established or UNKNOWN; Pre-state mob/claim and complete key-item readback.

**When:** Observe authorized encounter teardown via individual death/disengage/despawn paths and separately zone.

**Then:** Source explicitly resets mob local vars on disengage/despawn and may reposition on despawn; zoning cleanup remains UNKNOWN.

- **VWK-06-S01 — Baseline:** Capture approved character, zone, held/persisted keyitems, and matching mobs. **Expected:** Complete named fixture and before-state; else UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-06-baseline_complete`.
- **VWK-06-S02 — Action:** Observe authorized encounter teardown via individual death/disengage/despawn paths and separately zone. **Expected:** Source explicitly resets mob local vars on disengage/despawn and may reposition on despawn; zoning cleanup remains UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-06-action_oracle`.
- **VWK-06-S03 — Independent comparison:** Capture client event/monster state plus authoritative KI and spawn/local-var readback. **Expected:** Compare to documented conditions; Server local vars, status, zone and mob spawn slot before/after; absent authoritative capture => UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-06-server_oracle`.
- **VWK-06-S04 — Cleanup:** Approved operator verifies no unintended live mob, claim or KI change; quarantine incomplete runs. **Expected:** Verified restoration or BLOCKED; no remote execution here. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-06-cleanup_verified`.

**Capabilities:** snapshot, nearby_entities, move_to, engage, wait_for_event, inventory, key_items observation candidate (unverified), missing Accepted rest/heal interaction and hint capture; Runtime authoritative mob local vars; Per-combat effect/drop structured evidence. **Readback:** Server local vars, status, zone and mob spawn slot before/after. **Cleanup:** verify despawn and keyitem baseline; isolate spawned mob; quarantine if incomplete. **Gaps:** Zoning cleanup and death path not equivalent to disengage; authoritative mob readback missing; Deployment revision and ENABLE_VOIDWALKER runtime setting UNKNOWN; Mob local-vars/claim authoritative readback not available. **Mutation:** explicitly disabled pending per-case owner approval; lane `needs-mutation`.

**Source-backed assertions:** [`scripts/globals/voidwalker.lua:238–259`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L238-L259), [`scripts/globals/voidwalker.lua:180–192`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L180-L192), [`scripts/globals/voidwalker.lua:261–288`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L261-L288). No observed PASS is asserted.

### VWK-07 — Skill effects and rewards match server definitions

**Purpose:** Verify skill effects and rewards match server definitions without inferring results from a command being accepted. **Rationale:** Backlog records unported/guessed skill effects and drops; do not promote prior manual OK statuses to verified oracle

**Given:** Authorized disposable character and known zone/keyitem fixture; Active server DSP revision and enabled flag established or UNKNOWN; Pre-state mob/claim and complete key-item readback.

**When:** Inspect source-linked mob skill list and drop row for an explicitly chosen supported NM before combat.

**Then:** UNKNOWN: generic mobskilldiag only exposes diagnostics; per-skill effects and rewards lack fully reviewed oracle.

- **VWK-07-S01 — Baseline:** Capture approved character, zone, held/persisted keyitems, and matching mobs. **Expected:** Complete named fixture and before-state; else UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-07-baseline_complete`.
- **VWK-07-S02 — Action:** Inspect source-linked mob skill list and drop row for an explicitly chosen supported NM before combat. **Expected:** UNKNOWN: generic mobskilldiag only exposes diagnostics; per-skill effects and rewards lack fully reviewed oracle. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-07-action_oracle`.
- **VWK-07-S03 — Independent comparison:** Capture client event/monster state plus authoritative KI and spawn/local-var readback. **Expected:** Compare to documented conditions; Mob skill events, actual effect/TP/HP, full drop rows and server item changes; absent authoritative capture => UNKNOWN. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-07-server_oracle`.
- **VWK-07-S04 — Cleanup:** Approved operator verifies no unintended live mob, claim or KI change; quarantine incomplete runs. **Expected:** Verified restoration or BLOCKED; no remote execution here. **Client:** session, key_items, zone, client_event_timeline, nearby_entities. **Server:** chars.keyitems, mob local vars POPPED_BY, POPPED_WITH, POPPED_AT, spawn/claim/status from approved fixed readback. **Assertion:** `VWK-07-cleanup_verified`.

**Capabilities:** snapshot, nearby_entities, move_to, engage, wait_for_event, inventory, key_items observation candidate (unverified), missing Accepted rest/heal interaction and hint capture; Runtime authoritative mob local vars; Per-combat effect/drop structured evidence. **Readback:** Mob skill events, actual effect/TP/HP, full drop rows and server item changes. **Cleanup:** verify despawn and keyitem baseline; isolate spawned mob; quarantine if incomplete. **Gaps:** Backlog records unported/guessed skill effects and drops; do not promote prior manual OK statuses to verified oracle; Deployment revision and ENABLE_VOIDWALKER runtime setting UNKNOWN; Mob local-vars/claim authoritative readback not available. **Mutation:** explicitly disabled pending per-case owner approval; lane `needs-mutation`.

**Source-backed assertions:** [`scripts/commands/mobskilldiag.lua:8–25`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/commands/mobskilldiag.lua#L8-L25), [`scripts/globals/voidwalker_data.lua:1–48`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker_data.lua#L1-L48), [`scripts/globals/voidwalker.lua:261–288`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L261-L288). No observed PASS is asserted.

## Ranked read-only observation opportunities

1. **Keyitem-only baseline:** safely compare approved-character held/persisted abyssite state and revision metadata before initiating a pop; KI completeness must be verified.
2. **Static zone/tier mapping audit:** check exact supported zone+abyssite paths from the pinned `voidwalker_data.lua` without entering a fight or inventing navigation acceptance.
3. **Historical validation provenance review:** categorize Toolkit's prior pop/hint/model/fight notes as *operator-annotated*, not independently verified.
4. **No-eligible-abyssite preflight:** combine static `playerAbyssites` source rule with a complete read-only KI snapshot; without a /heal observation this is **not** an executed VWK-03.
5. **Runtime gate inspection after readback acceptance:** inspect server revision/feature enablement without requesting a spawn.

These are **substeps**, not fully executable `observe-now` gameplay scenarios. Cross-domain first-ten prioritization remains pending #1251–#1254 source reviews; recording ten artificial candidates would misstate capability.

## Canonical schema, orchestration and cleanup handoff

The companion `data/testing/domain_drafts/voidwalker.json` is a staged, **non-executable** artifact with stable IDs, step actions, assertion links, source+commit, UNKNOWN flags, independent readback and cleanup gates. It is not loaded by the strict `test_specifications.py` v1 validator because the latter lacks typed mob local-var/status observations and draft-only source-bound oracle semantics. The owner of #1259 and the local integration agent must review this contract and reconcile shared JSON sequentially; this PR does not edit either shared catalog. Do not implement a second XIHeadless runner.

For any eventual supervised execution, require per-case explicit operator approval, exact disposable profile/zone/character, validated deployed server and capabilities, complete pre/post state, redacted evidence, and independent cleanup or quarantine. Source references are normative only for conditions they actually express; source-presumed outcomes remain UNKNOWN until proven.

## Pinned source index

- Eligibility, KI flags: [`scripts/globals/voidwalker.lua#L35-L65`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L35-L65)
- Mob selection: [`scripts/globals/voidwalker.lua#L100-L130`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L100-L130)
- Heal/hint/pop: [`scripts/globals/voidwalker.lua#L292-L334`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L292-L334)
- Probabilistic upgrade: [`scripts/globals/voidwalker.lua#L153-L177`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L153-L177)
- Death/participation: [`scripts/globals/voidwalker.lua#L261-L288`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L261-L288)
- Mob reset: [`scripts/globals/voidwalker.lua#L180-L192`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L180-L192)
- Mob disengage/despawn: [`scripts/globals/voidwalker.lua#L238-L259`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L238-L259)
- NPC/abyssite interaction: [`scripts/globals/voidwalker.lua#L336-L385`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker.lua#L336-L385)
- Generated zone data: [`scripts/globals/voidwalker_data.lua#L1-L48`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/globals/voidwalker_data.lua#L1-L48)
- Mob skill diagnostic: [`scripts/commands/mobskilldiag.lua#L8-L25`](https://github.com/sarthax/darkstar-to-valhalla/blob/5fac778004364e2991df779845d7403e64a8dc23/scripts/commands/mobskilldiag.lua#L8-L25)
