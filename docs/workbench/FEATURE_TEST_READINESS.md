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
