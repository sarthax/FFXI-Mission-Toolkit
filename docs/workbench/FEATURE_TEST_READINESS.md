# Feature acceptance test readiness — cross-repository bridge

This is the **initial planning catalog**, not a record of passing tests or proof that named GM commands support particular arguments. Machine-readable catalog: `data/testing/feature_test_readiness.json`.

## Three-repository responsibilities
- **Mission Toolkit** owns scenario definitions, GM catalog metadata, feature/command mapping, preflight, evidence ingest, verdicts and stale-result detection.
- **XiHeadless-DSP** performs actions and records client-observed state through its existing MCP tools, ScenarioBrain, character pool and watchdog. Do not duplicate its movement/combat implementations.
- **DSP/Valhalla** owns GM Lua command semantics, actual authoritative state and test-server fixtures. Pin server checkout, branch and commit at run time.

## Implementation gates
1. Scan the **active configured local** DSP `scripts/commands/*.lua`, join names to this catalog, and extract signatures/permissions. Resolve each candidate to VERIFIED, NOT_FOUND, or NEEDS_REVIEW. The catalog's hardcoded categories are **not** an exhaustive inventory; include unclassified commands. Capture command SHA and scope/side effects after source review.
2. Classify each GM utility as `setup`, `accelerate`, `diagnostic`, `cleanup`, or mixed; separately label whether its effects are character, zone, instance, or global. Default to **manual only**, with stronger approval for destructive/global actions. Capture requested command, actor, target, time, before/after server state, and execution result.
3. Every scenario needs prerequisites, a staged baseline, positive/negative case, independent assertions, cleanup, and durable evidence. A command acknowledgement alone never passes a test.
4. Add a *missing utility request* record only for a proved coverage gap, including required API, suggested safe scope, planned permission and tests. New GM commands belong in DSP through isolated reviewed changes; no new command is assumed necessary until existing commands and client tools are exhausted.
5. Use safe, disposable test characters and isolated test profiles. Never alter global clock or a production DB to accelerate gardening. Preserve logout cooldown and failure recovery behavior documented in XiHeadless-DSP.
6. Output `PASS`, `FAIL`, `BLOCKED`, `SKIPPED` or `NOT_RUN` per case. Distinguish source-defined expectation from observed client/server effect; never infer success from the presence of Lua/SQL or Toolkit UI.

## Pilot priorities
**Gardening**: inspect `!garden` and confirm exactly how day advancement, growth stages, and crystal feeding work, then test invalid feeding timing, full-bag harvest, repeat-harvest, and relog persistence.

**Voidwalker**: link cases to the Toolkit Voidwalker domain validation dimensions (pop, hint, fight, model, drops, upgrade), beginning with the previously user-observed Batallia Downs flow. Validate other abyssite tiers, zones, and negative pop conditions individually. Server feature deployment is not yet confirmed.

**Assault/Nyzul**: use existing floor/layout diagnostics to stage only isolated test instances; verify entry denial, expiry and duplicate-reward protections.

**Missions/quests**: use mission/quest/KI setup and readback commands, but assert actual state changes from NPC interactions, not from GM grants.

## Integration contracts
Suggested future execution record: `{run_id, test_id, toolkit_commit, headless_commit, dsp_commit, server_profile, character_alias, gm_commands:[{name,arguments_redacted,scope,permission,source_sha,approved}], actions, assertions, evidence, cleanup, verdict}`.

Avoid storing account passwords, full connection credentials or unredacted secrets in test evidence. A prerequisite not implemented should mark the case `BLOCKED` with a specific work item, rather than FAIL. Negative cases pass only when prohibited transitions are demonstrably rejected and state remains unchanged.

## Immediate next engineering slice
Implement a **read-only GM command resolution report** joining the JSON candidates to the local catalog parser's `catalog_commands(server_root)`; add tests using synthetic Lua fixtures. Then expose test planning in the Toolkit UI; execution remains disabled until scope, privileges, side effects and cleanup are reviewed.

## Headless refresh from GitHub (2026-10-18)

Reviewed `sarthax/xiheadless-dsp` main at commit `c51e0f80`. The live suite now selects named, unclaimed mobs with `nearby_entities.isMob` rather than relying on a short hard-coded name set. It still excludes certain flying mobs from the dedicated fight test because melee reach can be misleading. This **improves selection robustness**, but does not validate arbitrary mob mechanics or close the known unreachable/stuck edge cases.

The checked-in headless project already provides an MCP brain, `snapshot`, `nearby_entities`, `inventory`, `talk_to_npc`, `trade_npc`, `event_select`, `wait_for_event`, `move_to`, `engage`, `capabilities`, persistent goal/checkpoint tools, and the live scenario client `tools/mcp_client.py`. Reuse these; don't create a second protocol client in Toolkit. The documented `McpBot.gm()` test helper can submit GM chat commands, **but that is not evidence of a safe, authorized command**.

For the Toolkit bridge, record exact headless commit and `capabilities` output in readiness results, and explicitly verify the `isMob` field before depending on it. Client-side `ok` confirms an accepted request at most, never an authoritative server effect.

## Outstanding GM source verification

Toolkit's `src/workbench/server_admin/gm_commands/catalog.py` currently categorizes `garden`, `moghancement`, `nyzuldebug`, `mobskilldiag` and other names, but the category table is **only a display map**. The connected `sarthax/darkstar-to-valhalla` GitHub repository did not expose the expected `scripts/commands/garden.lua` on its default `master` branch. Therefore the exact gardening command arguments, scope, and crystal-feeding semantics remain **unverified here**; they must be extracted from the authoritative *local* DSP checkout and its actual runtime branch.

Do not introduce replacement gardening or Voidwalker GM commands simply because the public-facing GitHub path was missing. First run `resolve_test_utilities(server_root, plan_path)` against the configured local checkout and inspect the concrete files; add utility requests only when a verified gap remains.

## Negative-test fixture discipline

All negative tests must snapshot the pre-state and assert both the refused player action and **no forbidden post-state mutation**. Cover repeated calls, wrong stage/tier, missing prerequisites, full inventory, relog, zoning during events, and attempts by non-GM accounts where appropriate. GM setup commands should be run in disposable test contexts, not by the normal gameplay actor; store explicit fixtures and cleanup/rollback requirements. Treat aborted or interrupted tests as `BLOCKED` or `FAIL` with a clear reason, never as a positive verdict.

## Source-backed GM command review (feature branches, 2026-10-18)

**Provenance:** `sarthax/darkstar-to-valhalla`, **feature branches**, not verified deployed to the running test server. Recheck these exact files against the local checkout before executing.

### Gardening: `feature/mog-house-gardening:scripts/commands/garden.lua`

- `permission=1`; `parameters="sii"`; syntax `!garden <action> {value} {slot}`; omitted slot uses `-1` (all pots), meaning **tests must specify a slot** when isolation matters.
- Preconditions: inside **Mog House**; command delegates to `player:gardenDebug(action, value or 0, slot or -1)`. Inspect the C++ `gardenDebug` implementation before asserting which side effects persist.
- Diagnostic actions: `info` (plant, stage, crystals, strength, dried/examined state, remaining time), `results` (a **random-roll preview**, not a deterministic expected reward).
- Acceleration/setup actions: `plant 1..8` (directly sows), `stage 1..11` (10 mature, 11 wilted), `grow [n]` (normal growth path), `mature`, `wilt`, `ready` (next tick due), `crystal1 0..8`, `crystal2 0..8`, `strength 0..31`, `dry 0|1`, `examined 0|1`, `clean`.
- **Critical positive/negative split:** `!garden crystal1` directly **sets** a crystal value and cannot validate player-facing crystal feeding constraints. To test feeding, execute the actual client operation through the headless client and assert inventory consumption + plant state; use `!garden info` only as postcondition evidence. `!garden plant` bypasses normal pot/seed interaction and is suitable for fixture setup, not planting acceptance. `!garden grow` is appropriate for acceleration when it follows normal growth logic, but verify stage effects in C++.
- Focused test plan: (1) pot+seed via normal game operation; (2) `info` before state; (3) valid/invalid normal crystal feeding; (4) `grow` with exact slot, stage observation, harvest; (5) negative mature/wilted feeding and duplicate harvest; (6) logoff/relogin persistence and a second untouched slot. Existing `GARD-01..08` IDs track these scenarios.

### Nyzul: `feature/assault-gm-debug-tools:scripts/commands/nyzuldebug.lua`

- `permission=1`, `parameters="ss"`; requires a **live instance with ID 51**.
- `complete` directly forces the floor objective: **fixture/acceleration only**, not proof that the objective was solved by gameplay.
- `floor N` for `1..100` primes floor `N-1` and lights the current transfer rune; player must actually use the rune to reach the target floor.
- `reroll` regenerates objective/spawns. `layout N` for `1..16`, or `layout clear`, pins/unpins layouts; `leader <name>` and `leader clear` pin/unpin leader spawns. **Always clear test pins during cleanup.**
- Negative cases: invalid floor `0`/`101`, invalid layout `0`/`17`, unknown leader, invocation outside instance 51; verify no state mutation. Test an objective naturally before using `complete` to exercise win conditions.
- `!warpassault` is also available on the feature branch and bypasses standard entry; it may first warp the character to the required zone and **require a second invocation** after zoning. Do not count a GM-assisted entry as proof of ordinary Assault entry eligibility.

### Voidwalker: `feature/voidwalker:scripts/commands/mobskilldiag.lua`

- `permission=1`, no args; reports targeted mob's ID, pool, job, HP%, TP and skill list / TP-use mods. Requires the player to **target a mob**; not a generic spawn/abyssite progression query.
- `!checknav x y z` on the reviewed Assault diagnostics branch is a diagnostic for valid nav position and path from the player; does not validate Voidwalker hint logic.
- Neither operation by itself proves a tier upgrade, specific skill effect, or drop. Treat missing abyssite state readback as a **candidate** for a scoped read-only utility after checking the current Voidwalker Lua and any existing `!checkvar` / `!haskeyitem` commands.

## Gardening C++ implementation audit (source verified)

Reviewed `sarthax/darkstar-to-valhalla:feature/mog-house-gardening:src/map/utils/gardenutils.cpp`, specifically `gardenutils::DebugCommand` called by `CLuaBaseEntity::gardenDebug`.

- **Container collision:** the loop visits **both** `LOC_MOGSAFE` and `LOC_MOGSAFE2`; `slotFilter` compares only the numeric slot ID within each container. Thus **`!garden grow 1 5` could affect two pots** if both safes contain a flowerpot in slot 5. The operator should treat all state-changing `!garden` actions as *potentially multi-container*. A slot is NOT a unique per-pot identifier. Automated state-changing calls must be blocked until either (a) a unique matching pot is verified across both containers, or (b) DSP receives a reviewed container-scoped command argument. Verify this via read-only `!garden info` before/after.
- **State persistence:** each successful state-changing debug action calls `SavePot(PChar, PPot, containerID, slotID)`, followed by `CFurnitureInteractPacket` and `CInventoryFinishPacket`. This supports same-session persistence, but relog durability remains a runtime assertion.
- **`grow` path:** loops through `GrowToNextStage(PPot)`, using `max(1, value)` so a value of 0 or negative does not mean no-op. Add a negative test preventing accidental stage advance from zero count and make the harness reject count less than 1.
- **`results` action:** directly invokes `CalculateResults`, which includes random choice and configuration-dependent influences (weekday, pot element, moon phase, furnishing auras). Do not treat consecutive `!garden results` outputs as deterministic expected yields.
- **`ready` action:** sets the stage due timestamp to now but does not itself move to the next stage. Normal tick may wait for a feeding requirement.
- **`stage`/`mature`/`wilt` and `crystal1/2`** directly manipulate state, not gameplay checks. Test normal crystal feeding and harvesting through the client, with these actions reserved for explicit fixture or acceleration stages.

### Missing GM utility requirement GARD-GM-01 (candidate; no implementation yet)

A scoped `gardenstate` or extension to `garden` should address **one pot by both container ID and slot ID**, with a read-only structured state output. For mutating operations, require explicit container ID, slot, and a unique flowerpot lookup; reject nonexistent pots, out-of-range values, and non-Mog-House calls with **no side effects**. Keep permission at or above the existing level 1 and provide structured confirmation including affected container+slot, action, before/after stage and update result. Review existing `gardenDebug` signature and client update packets before introducing the new command. Avoid global-clock manipulation.

**Until this is addressed, tests requiring an isolated pot must preflight both safe containers and abort if the slot has more than one matching pot.** This is now a concrete, source-proven GM command improvement candidate rather than speculative test infrastructure.

## Initial executable preflight (planning only)

Added `workbench.server_admin.gm_commands.garden_preflight` and synthetic tests. It parses the actual `[c<container> s<slot>] pot <item>: plant=... stage=...` lines emitted by DSP `gardenutils::Describe`, and refuses to produce an allowed preview if more than one pot shares the requested numeric slot, if none match, if the expected item/container differs, or if `grow` uses zero/negative count. This avoids a concrete hazard in the existing debug command.

The preflight **does not transmit or execute** commands. `allow=true` indicates only that a supplied diagnostic snapshot is consistent with one observed pot. The caller must independently ensure `!garden info` is complete, fresh, from the correct character and server, and that permissions/side effects are approved. Chat response truncation, races between preflight and execution, or other concurrent bot actions are not solved; therefore the safe long-term fix is the container-scoped GARD-GM-01 utility, with server-side atomic validation.

If the runtime is unable to capture a complete pot list from both safes, the operator must treat the preflight as unavailable and **not automate a mutation**.

## Updated user requirement: high-throughput batch gardening

**Preferred acceptance mode is a Mog House-wide batch campaign**, not individually addressed pots. Arrange mixed or uniform pots, iterate seed families (1..8), crystal elements (0..8), and tree second-crystal combinations where applicable, accelerate stages with the existing `!garden grow` command, harvest through the client, record the yields and state transitions, then reset and repeat. Run subsets by input filters when investigating a regression.

The `!garden` omission of a slot applies to **all placed flowerpots**, which is **desired in batch mode**. The existing per-pot collision preflight remains useful only in `focused_single_pot` mode, and **GARD-GM-01 is not a blocker for batch campaigns**. Do not build a container-scoped GM command merely to enable bulk tests. Batch preflight instead verifies the complete pot inventory, intended pot types and starting stage, active disposable character, and that all placed pots are legitimately part of the campaign.

The plan lives at `data/testing/gardening_batch_plan.json`. Pairwise coverage is the initial default; exhaustive seed × crystal × pot × repeat combinations should be opt-in and bounded by the run budget. A mixed-pot batch lets different pot types be sampled per harvest; uniform batches offer easier isolation and comparison. Capture per-container/slot identity **for evidence** even though actions operate on all pots. A shared GM mutation must not count as a pass for planting or crystal-feeding interactions: **headless must perform those player-facing actions** when testing them.

For each iteration: snapshot baseline → provision/reset → choose input combination → plant/feed through client (or mark fixture-only subtest) → accelerate via `!garden grow` → verify mature → harvest via client → inventory diff, outcomes, and pot-state check → cleanup. Add separate negative campaigns for invalid crystal timing, multiple feeds, premature harvest, full inventory, and duplicate harvest. No global time adjustments.

Goal: hundreds of independent iterations in roughly an hour **subject to actual client interaction speed and session stability**, not a claimed measured throughput. Avoid relog between every case; sample persistence with dedicated relog cases. Existing GM debug `results` is random, so validate rewards against authoritative allowed outcome tables rather than treating its prediction as deterministic.

## Offline gardening campaign generator implemented

`workbench.server_admin.gm_commands.garden_campaign.generate_campaign(plan)` generates bounded, deterministic cases from `data/testing/gardening_batch_plan.json`. Pairwise coverage spans pot type, seed family, first crystal and tree-only second crystal; non-tree cases have second crystal 0. Optional field filters isolate exact failures; full-cartesian mode requires explicit opt-in and respects max run count. Repetitions get distinct case IDs and remain `NOT_RUN`.

This is *test planning*, not a client/server runner. It intentionally does not send GM commands, invent a harvest result, change the clock, or certify a client operation. Underlying DSP random yields and config effects require runtime-aware expected-outcome validation.

### Headless protocol gap reviewed

`sarthax/xiheadless-dsp` main `Interfaces/IInventory.cs` exposes container-item use, move, count and related bag actions. This is **not proof of gardening furniture menu support**. Before promoting the campaign to live execution, inspect client 0x? furniture interaction packets, Mog House eligibility and the corresponding DSP handlers for normal pot placement, sowing, feeding and harvesting; then add a narrow capability implementation and explicit observations/rewards. Maintain separate `fixture_mechanics` and `gameplay_acceptance` verdicts.

Do not assume hundreds of trials/hour until a timed disposable-server pilot measures setup, tick advancement, harvest, inventory cleanup and login overhead. Keep one login per batch where possible and run persistence separately.

## Authoritative gardening SQL reward oracle

The DSP repository's `sql/gardening_results.sql` exists on `main` and the `feature/mog-house-gardening` branch. Its records contain `resultId, seed, element1, element2, result, min_quantity, max_quantity, weight`. The feature-branch C++ `gardenutils::LoadResultList` maps outcomes by `(seed << 8) + (element1 << 4) + element2`. **Pot type is not an SQL lookup key**: it influences the strength/selection calculation separately, along with optional weekday, moonphase, furniture auras and other configuration. `weight` participates in selecting a result rather than guaranteeing a single deterministic reward.

The new `garden_rewards.py` parser takes the SQL text **from the selected DSP checkout** and builds the per-combination allowed item/quantity oracle, without executing SQL. The `validate_harvest` result is `PASS` for an allowed item within an allowed quantity range; `FAIL` for a forbidden item or amount; and `BLOCKED` if that combination is absent from the SQL. This validates **individual recorded pot rewards**; mixed-pot, aggregated inventory deltas cannot be assigned to a seed/crystal combination without per-pot harvesting observations. The oracle does **not** validate RNG weight distributions, exact expected item for a random roll, or whether the server actually loaded the same SQL contents at startup.

Live test preflight must record the actual server SQL hash and reload/restart state; if the SQL used by a running server cannot be tied to the checkout, the reward verdict must remain provisional. Longer statistical campaigns can separately compare observed frequencies to configured weights after auditing the exact C++ strength/selection algorithm; do not equate SQL weight with direct per-roll probability.

## Moghancement / Moglification acceptance suite (source-backed)

DSP main sources reviewed:
- `sql/item_furnishing.sql`: itemid, name, storage, moghancement key item, element (0..7), aura strength.
- `src/map/entities/charentity.cpp`: `UpdateMoghancement`, `ChangeMoghancement`, `SetMoghancement`, `MoghancementDebug`.
- `scripts/commands/moghancement.lua`: level-1 GM helper `info`, `set <keyitemid>`, `clear`, `recalc`.

The **real oracle** is `moghancement_oracle.py`, loading furnishing metadata from the selected DSP SQL revision. Sum aura for *installed* furnishings across Mog Safe 1 and Mog Safe 2 (not merely stored). A tied dominant element or zero aura produces key item 0. Otherwise choose the highest-aura installed eligible furnishing of that element, breaking ties by the server iteration order: Mog Safe first, then Mog Safe 2, ascending slot. Replacing the active effect removes the old furniture KI, grants the new KI, applies the new modifiers, updates KI packets and persists via `SaveKeyItems`. The oracle's container labels 1/2 mean logical **Safe 1/Safe 2**, not verified raw `LOC_MOGSAFE` packet IDs; map them explicitly at the adapter boundary.

Run three campaign tiers:
1. **Direct calculation**, offline: every furnishing SQL item individually; same-element combinations, mixed-element dominance, exact element ties, strongest-item ties, zero aura, inactive furniture. Generate item combinations bounded by a budget, with targeted coverage of every distinct KI in SQL. Assert `predict_moghancement` result.
2. **GM-assisted mechanics**, live isolated Mog House: place real furniture in both safes; use `!moghancement info` before/after and `!moghancement recalc` to test the server's calculation. `!moghancement set` is fixture setup only and must not count as furnishing gameplay acceptance.
3. **Player gameplay**, live: use XiHeadless to install/uninstall furniture, exit furnishing menu, and verify the grant/removal of the KI without triggering `recalc` manually. Repeat across layout transitions and re-login persistence. **Headless furnishing/menu support is not yet verified**; mark blocked until built and demonstrated.

Positive IDs:
- `MOG-01` single furnishing for every distinct Moghancement KI.
- `MOG-02` two furnishings same element; largest aura furnishing selects KI.
- `MOG-03` several furniture items; total aura of dominant element wins while strongest eligible piece chooses KI.
- `MOG-04` furniture in each Mog Safe contributes.
- `MOG-05` layout A→layout B replaces prior temporary KI and its modifier.
- `MOG-06` uninstallation removes old KI; relog preserves new active effect.
- `MOG-07` compare `info` aura breakdown and active KI with offline oracle.

Negative IDs:
- `MOG-08` equal maximum aura between two elements yields no Moghancement and clears old KI.
- `MOG-09` only stored, not installed, furniture yields no effect.
- `MOG-10` no furniture yields no effect and removes previous KI.
- `MOG-11` repeat menu exit/recalc does not duplicate KIs or stack modifiers.
- `MOG-12` invalid `set <keyitemid>` refuses unknown KI and leaves state intact.
- `MOG-13` duplicate copies of an item raise aggregate aura but do not duplicate KI grants.
- `MOG-14` strongest-item tie selects first in actual server scan order (regression vs placement-order assumptions).

**Evidence:** selected server SQL SHA, server/headless/Toolkit commits, installed inventory manifest (container+slot), item element/aura and KI metadata, before/after `!moghancement info`, exact held furniture key item set, modifier snapshot and relog outcome. Absence of headless installed-state observation is a BLOCKER, never an inferred PASS. The FFXIclopedia wiki is a useful gameplay reference, but the running DSP source and its SQL are authoritative for expected outcomes.

Moghancement can affect gardening via furnishing auras and `GARDENING_WILT_BONUS`; record the Mog House layout and active KI in each gardening campaign to avoid hidden cross-feature variation.

## Moghancement effect verification (three-stage acceptance)

**Critical user requirement:** receiving the Moghancement/Moglification KI is not sufficient. Validate (A) correct exclusive KI, (B) numeric modifiers correctly applied/removed and persisted, and (C) **real gameplay outcomes** demonstrating the intended modifier actually affects behavior.

Source reviewed: `sarthax/darkstar-to-valhalla` main `src/map/entities/charentity.cpp:moghancementMods`; `SetMoghancement` removes modifiers associated with the prior KI before adding those of the new KI. `!moghancement info` prints active KI, held furniture KIs and nonzero relevant modifiers. Use `!getmod` where available to measure individual values against a before-state baseline; a modifier could already have unrelated contributions.

Verified source mapping highlights:
- Gardening: `GARDENING_WILT_BONUS +36` (consumed by `src/map/utils/gardenutils.cpp` in wilt timing).
- Fishing/crafting Moghancement/Moglification: craft-skill modifiers +1. Mega Moglification: +5.
- Money/Money II: `GILFINDER +10/+15` (consumed in `charutils.cpp` gil awards).
- Experience: `EXPERIENCE_RETAINED +5`; Desynthesis: `DESYNTH_SUCCESS +2`.
- Conquest +6, Region +10; matching-nation conquest +6 and nonmatching-nation no benefit.
- Campaign +5; Skill Gains `COMBAT_SKILLUP_RATE +25` and `MAGIC_SKILLUP_RATE +25`.
- Bounty `EXP_BONUS +10`, `CAPACITY_BONUS +10`; Moglification Experience Boost +15; Capacity Boost +15.
- Status resistance Moglifications: resistance mods +20; **server source calls the amounts placeholders**, so treat as implementation behavior, not proven retail fidelity.
- **Elemental synthesis failure modifiers are checked via KI directly in `synthutils::doSynthFail`, not `moghancementMods`**. The absence of a numeric Mod for these is expected; behavioral validation must inspect/execute the synthesis path.

Catalog: `data/testing/moghancement_effect_validation.json` is an initial source-derived mapping and behavioral test plan. Numeric modifier tests are deterministic; crafting failure rates, resist procs and skill gains need statistically controlled repetitions or an injected deterministic test RNG on an isolated server. Never assert that 10% means every 10th individual event is boosted.

Required negative scenarios: replace KI A with KI B and verify KI A and modifier A gone; remove all installed furnishings and confirm zero related mods; repeat recalc and relog to detect stacking; verify wrong-nation restrictions; confirm equivalent KI effects restored on login; confirm client receives appropriate update after furniture menu exit. Each result needs SQL furnishing set, player nation, active KI, modifier pre/post, gameplay events and server code revision. Distinguish `KEY_ITEM_PASS`, `MODIFIER_PASS`, and `BEHAVIOR_PASS` independently.

## Implemented modifier-delta oracle and behavior pilots

`moghancement_effects.py` now verifies numeric modifiers relative to a measured character baseline, not absolute zero. `evaluate_modifiers` compares baseline → active KI → removed KI to prove correct delta and cleanup. `evaluate_replacement` compares baseline → effect A → effect B to catch leaked A modifiers, even when different effects alter different numeric stats. Missing diagnostic values are `BLOCKED`, never implicitly zero. Synthetic tests cover success, wrong delta, stacking/leak, and missing observations.

### Initial behavioral pilots (not yet run)

- **MOG-BEH-01 Gardening:** baseline `GARDENING_WILT_BONUS`, install Gardening enhancement and assert +36; stage matched disposable pots near the native wilt boundary under the same config, advance normal gardening ticks and compare state with an untreated control; remove furnishing and verify bonus returns to baseline. Avoid `!garden wilt` because it bypasses the timing check.
- **MOG-BEH-02 Money:** compare controlled same-source gil awards with baseline versus Money (+10 GILFINDER) and Money II (+15). Do not assert precise gil increase until confirming award rounding and the actual source path; use stable repeatable rewards.
- **MOG-BEH-03 Skill:** verify +1 crafting modifier for the relevant Moghancement, +5 for Mega Moglification, and effective skill in synthesis calculations. Avoid pretending a single success/failure demonstrates a statistical effect.
- **MOG-BEH-04 Elemental synthesis:** verify the KI is consulted directly in `synthutils::doSynthFail` under correct element and Mog House state, using controlled synthesis trials and a no-enhancement baseline. A missing numeric modifier is expected here.
- **MOG-BEH-05 Replacement and idempotence:** repeatedly switch Money ↔ Gardening layouts; prove both KIs and modifier states transition exclusively and no bonus accumulates after multiple menu exits or relogs.

Each live execution requires (a) approved disposable environment and fixture, (b) server version and configuration fingerprint, (c) original modifier baseline, (d) KI plus modifier evidence, (e) observed game behavior, (f) cleanup results. Do not treat a diagnostic value as proof of actual gameplay outcome.

## Durable feature test results — initial implementation

`src/workbench/server_admin/feature_testing/results.py` provides an append-only SQLite local evidence store. Every result is keyed by `(run_id, case_id, stage)` and captures verdict, UTC timestamp supplied by importer, exact DSP/headless/Toolkit revisions, and structured evidence. Valid verdicts: PASS, FAIL, BLOCKED, SKIPPED, UNKNOWN. `UNKNOWN` means a run produced no usable determination; it is recorded explicitly (never inferred from a missing row) and is never counted or promoted as PASS. The SQLite column has no CHECK constraint, so older databases need no migration. Stages distinguish key_item, modifier, behavior, mechanics and gameplay. Duplicate keys are rejected, never overwritten.

The dashboard serves **read-only** `GET /feature-testing/results` with optional `feature_id` and `case_id` filtering, and displays history on scenario pages. Set `MISSION_TOOLKIT_TEST_RESULTS_DB` to an **absolute local SQLite file path** to view records imported by a trusted local harness. With no configured file, results remain empty; the UI never fabricates green outcomes. This page has no test execution or write API.

No provenance authentication, signed evidence or automatic headless ingestion is provided yet. Importing test records should be restricted to trusted local agents; do not upload raw credentials or player account secrets. Test outcome display does **not** itself validate evidence authenticity. The next slice is a secure local artifact importer with evidence schema validation, run manifest and per-stage verification.

## Local report import (no live execution)

A trusted local runner can now submit JSON evidence through the **offline CLI importer**, rather than through an unauthenticated HTTP write endpoint:

```powershell
python -m workbench.server_admin.feature_testing.importer --catalog data/testing/feature_test_readiness.json --database D:\\MissionToolkitData\\feature_results.sqlite --report D:\\MissionToolkitData\\run-001.json
```

Report schema version 1:
```json
{
  "schema_version": 1,
  "results": [
    {
      "run_id": "run-001",
      "feature_id": "moghancement",
      "case_id": "MOG-01",
      "stage": "modifier",
      "verdict": "BLOCKED",
      "observed_at": "2026-10-18T21:05:00Z",
      "dsp_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "headless_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "toolkit_commit": "cccccccccccccccccccccccccccccccccccccccc",
      "evidence": {"reason": "Headless furnishing menu interaction not verified"}
    }
  ]
}
```
**`BLOCKED` results must carry `evidence.reason_class`** — one of `ENVIRONMENT`, `FIXTURE_ABSENT`, `ORACLE_UNKNOWN` or `OTHER` — and the importer rejects a BLOCKED row without a valid class. `UNKNOWN` rows may carry the same field; any other verdict rejects it. Historical BLOCKED rows that predate this have no class and are read as `UNCLASSIFIED`, which is not comparable for regression purposes (design: `R6_REGRESSION_IMPACT_DESIGN_1199_1210.md`). The captured-observation adapter cannot tell why an observation was missing or invalid, so its BLOCKED rows are written with `OTHER` rather than a more specific claim.

These all-a/b/c commit IDs are **format examples only**, not real evidence; never import them as production provenance. The importer checks known catalog feature/case IDs, stage/verdict, UTC timestamps, full 40-hex SHA format, nonempty structured evidence, duplicate identities, max sizes and atomic commit/rollback. A PASS record also requires `assertions` and `observations` keys; this is only a structural guard, **not an authenticity or truth check**. Trusted source attribution and independent assertion verification remain separate work.

Point `MISSION_TOOLKIT_TEST_RESULTS_DB` at the same SQLite file to view imported history in the Toolkit. No network write route or test execution is enabled. The report must be produced in a trusted environment; guard database access and do not include credentials, tokens or identifiable private account data.

## Captured-observation report adapter

`workbench.server_admin.feature_testing.observation_adapter` now converts **externally captured** observation dictionaries into validated report schema v1 records, via the existing SQL gardening and Moghancement modifier/replacement oracles. Inputs are a run manifest (run ID, UTC observation time, exact 40-character Git revisions), a list of observations, the test catalog and optionally `sql/gardening_results.sql` from the **deployed** DSP checkout. Call `build_report_file(manifest_path, observations_path, catalog_path, output_path, gardening_sql=...)` from a trusted local Python integration; then import its JSON output with the offline importer CLI.

Supported observation kinds:
- `garden_harvest`: `case_id`, `inputs: {seed, crystal1, crystal2}`, `actual: {item_id, quantity}`.
- `mog_modifier`: `case_id`, `baseline`, `active`, `removed`, `expected_delta` (modifier name → integer).
- `mog_replacement`: `case_id`, `baseline`, `old_active`, `new_active`, `old_effect`, `new_effect`.

This adapter is deliberately **offline**: it does not connect to DSP, validate a player's identity, make GM calls, or operate the Headless client. It records `capture_provenance: unverified_external_observation` to prevent misinterpreting syntactically valid imports as authenticated runs. `PASS` is only a *validator verdict against supplied observations*, not proof the server actually produced them. Full live capture, attestation, runtime configuration checks, and behavior-level game assertions remain future milestones.

## Read-only run history views

The `/feature-testing` homepage now includes a run-history table grouped by run ID, latest observation timestamp, covered feature IDs, verdict counts and imported record count. Individual runs open at `/feature-testing/run/{run_id}`, where each stage verdict, source revisions and structured evidence can be inspected. `GET /feature-testing/runs` exposes the read-only grouped summaries. When no database is configured or reports have not yet been imported, the UI shows an explicit empty state rather than implying all tests passed.

These views reflect **imported report records**, not authenticated server executions. The first history implementation reads up to 500 recent records for grouping; it is not yet a complete paginated history for larger campaigns. Test inventory/variable editors and the execution launcher remain separate future slices, with live execution still disabled.
