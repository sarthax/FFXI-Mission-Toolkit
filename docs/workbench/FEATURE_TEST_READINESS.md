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
