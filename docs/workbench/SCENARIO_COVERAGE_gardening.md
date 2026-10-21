# Gardening R5: source-backed domain scenario coverage (design-only)

**Issue:** [#1249](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1249) · **Epic:** [#1197](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1197) · **DSP source:** [feature/mog-house-gardening at `330ea8f854cff47aae570aa95d6474f3225f5d49`](https://github.com/sarthax/darkstar-to-valhalla/tree/330ea8f854cff47aae570aa95d6474f3225f5d49) · **Toolkit base:** `3cd36fc770fc1a7cd874874d5bf8fbdfa0de496f`.

**Acceptance status: design only; no client, GM, DB, or XiHeadless execution was done.** No scenario below has a runtime verdict, authenticated observation, or approved runner. The DSP feature source is inspected; the *deployed* DSP commit and `garden_*` configuration are **UNKNOWN**. Source presence is not deployment proof.

## Key source truths and safety boundaries

- `!garden` is permission 1, parameters `sii`, default slot `-1`: [garden.lua:24–43](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/scripts/commands/garden.lua#L24-L43). Do not invoke it from these specs.
- The debug loop enumerates **both Mog Safe and Mog Safe 2**, comparing only the numeric slot: [gardenutils.cpp:612–629](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L612-L629). Thus a slot-qualified mutation may affect two pots. GARD-09 is a **known unsafe path**, not an authorized reproduction.
- `plant` and `crystal1/2` directly set pot state: [gardenutils.cpp:679–709](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L679-L709). They **cannot** verify player-facing placement/feed rules. `grow` uses `max(1, value)`: [gardenutils.cpp:644–652](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L644-L652), so zero is not safe no-op.
- Pot state is encoded in `char_inventory.extra`: [item_flowerpot.cpp:25–36](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/items/item_flowerpot.cpp#L25-L36), [char_inventory.sql:19–29](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/sql/char_inventory.sql#L19-L29). Debug changes persist with `SavePot` [gardenutils.cpp:750–756](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L750-L756); relog durability is still a test assertion, not verified here.
- The source reward oracle loads `gardening_results` and calculates outcomes from pot state and optional configuration; there is **no universal fixed harvest reward**: [gardenutils.cpp:53–77](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L53-L77), [gardenutils.cpp:126–288](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L126-L288), [gardening_results.sql:1–16](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/sql/gardening_results.sql#L1-L16).

## Readiness and oracle matrix

| Case | Scenario | Lane | Oracle state | Prerequisite blocker |
|---|---|---|---|---|
| GARD-01 | Place pot and plant valid seed | `needs-mutation` | UNKNOWN | Player planting binding and post-state oracle not reviewed |
| GARD-02 | Feed permitted crystal at valid growth stage | `needs-mutation` | UNKNOWN | Client feed handler, permissible stages and complete readback missing |
| GARD-03 | Advance growth and harvest valid yield | `needs-mutation` | Source-limited; runtime UNKNOWN | Reward row ordering, client harvest, deployed config, complete readback missing |
| GARD-04 | Reject crystal at invalid stage | `needs-mutation` | UNKNOWN | Disallowed stage source oracle and player handler missing |
| GARD-05 | Reject planting without pot or seed | `needs-mutation` | UNKNOWN | No-pot and no-seed runtime paths not reviewed |
| GARD-06 | Full inventory harvest does not lose or duplicate reward | `needs-mutation` | UNKNOWN | 100-row readback limit prevents completeness; harvest capacity rule UNKNOWN |
| GARD-07 | Growth and treatment survive relog | `needs-mutation` | Source-limited; runtime UNKNOWN | Relog accepted behavior, save boundary and pot readback unverified |
| GARD-08 | Repeat harvest cannot duplicate rewards | `needs-mutation` | UNKNOWN | Repeat-harvest handler and complete inventory snapshots unverified |
| GARD-09 | Same numeric slot in both safes must not dual-mutate | `needs-mutation` | Source-limited; runtime UNKNOWN | GARD-GM-01 scoped command or proved unique-slot preflight required |

**Interpretation:** Every *complete* gardening case requires a client or GM mutation and a missing independent pot-state readback; none is `observe-now`. The missing readback is the first engineering dependency (`needs-readback` for observation slices). Deployment status is UNKNOWN, so `needs-deploy` is *not asserted* as a known fact. All are unassigned, design-only and NOT_RUN. The [existing supervisor readback](https://github.com/sarthax/FFXI-Mission-Toolkit/blob/3cd36fc770fc1a7cd874874d5bf8fbdfa0de496f/src/workbench/server_admin/feature_testing/database_diagnostics.py) gives `location,slot,itemId,quantity` up to 100 rows, not `extra`, row completeness, or garden stages.

## Ordered BDD scenarios, steps and evidence

### GARD-01 — Place pot and plant valid seed

**Purpose:** Source-mapped pot and seed, client placement. **Given:** an explicitly owner-approved disposable character, a pinned DSP build, a complete baseline of both safes and the fixture “Source-mapped pot and seed, client placement”. **When:** Client places pot and plants a seed. **Then:** UNKNOWN: player-facing acceptance and inventory decrement.

1. **GARD-01-S01 / establish baseline:** Observe approved session and both safe locations without writes. **Expected:** exact character, container+slot manifest and complete inventory counts; otherwise UNKNOWN. **Observations:** client inventory, persisted `char_inventory` and decoded pot extra (**missing**). **Assertion:** `GARD-01-baseline-complete`.
2. **GARD-01-S02 / action:** Client places pot and plants a seed. **Expected:** UNKNOWN: player-facing acceptance and inventory decrement. **Capabilities:** `snapshot`, `inventory` (candidates), pot.extra seed+stage and complete inventory; specialized client binding not accepted. **Assertion:** `GARD-01-transition`; if no independently sourced oracle, remain UNKNOWN.
3. **GARD-01-S03 / authoritative comparison:** Capture time-aligned post-action client timeline, server `char_inventory` including `extra`, and all affected pots in **both safes**. **Expected:** all source-backed deltas match; incomplete readback => UNKNOWN, never PASS. **Readback need:** pot.extra seed+stage and complete inventory. **Assertion:** `GARD-01-independent-oracle`.
4. **GARD-01-S04 / cleanup:** Authorized operator reconciles/restores fixture, captures independent pot and inventory state, or quarantines character if incomplete. **Expected:** cleanup independently verified or BLOCKED. **Assertion:** `GARD-01-cleanup-verified`.

**Mutation:** pot enum / seed map / debug bypass; requires separate owner approval, no GM authorization inferred from this plan. **Missing oracle/capability:** Player planting binding and post-state oracle not reviewed. **Source support:** pot enum / seed map / debug bypass; only the specific code references listed in the source index are authoritative. No player-facing packet/event IDs, server outcomes or inventory item values are guessed.

### GARD-02 — Feed permitted crystal at valid growth stage

**Purpose:** Stage-verified planted pot and source-mapped crystal. **Given:** an explicitly owner-approved disposable character, a pinned DSP build, a complete baseline of both safes and the fixture “Stage-verified planted pot and source-mapped crystal”. **When:** Client feeds crystal (never the GM setter). **Then:** UNKNOWN: feed eligibility and consumed quantity.

1. **GARD-02-S01 / establish baseline:** Observe approved session and both safe locations without writes. **Expected:** exact character, container+slot manifest and complete inventory counts; otherwise UNKNOWN. **Observations:** client inventory, persisted `char_inventory` and decoded pot extra (**missing**). **Assertion:** `GARD-02-baseline-complete`.
2. **GARD-02-S02 / action:** Client feeds crystal (never the GM setter). **Expected:** UNKNOWN: feed eligibility and consumed quantity. **Capabilities:** `snapshot`, `inventory` (candidates), pot.extra crystal+stage, inventory delta; specialized client binding not accepted. **Assertion:** `GARD-02-transition`; if no independently sourced oracle, remain UNKNOWN.
3. **GARD-02-S03 / authoritative comparison:** Capture time-aligned post-action client timeline, server `char_inventory` including `extra`, and all affected pots in **both safes**. **Expected:** all source-backed deltas match; incomplete readback => UNKNOWN, never PASS. **Readback need:** pot.extra crystal+stage, inventory delta. **Assertion:** `GARD-02-independent-oracle`.
4. **GARD-02-S04 / cleanup:** Authorized operator reconciles/restores fixture, captures independent pot and inventory state, or quarantines character if incomplete. **Expected:** cleanup independently verified or BLOCKED. **Assertion:** `GARD-02-cleanup-verified`.

**Mutation:** stage enum / debug bypass; requires separate owner approval, no GM authorization inferred from this plan. **Missing oracle/capability:** Client feed handler, permissible stages and complete readback missing. **Source support:** stage enum / debug bypass; only the specific code references listed in the source index are authoritative. No player-facing packet/event IDs, server outcomes or inventory item values are guessed.

### GARD-03 — Advance growth and harvest valid yield

**Purpose:** Isolated pot, pinned result SQL and config. **Given:** an explicitly owner-approved disposable character, a pinned DSP build, a complete baseline of both safes and the fixture “Isolated pot, pinned result SQL and config”. **When:** Operator-authorized acceleration; client performs harvest. **Then:** Conditional permitted item/quantity from pinned SQL+C++; UNKNOWN until fixture/config known.

1. **GARD-03-S01 / establish baseline:** Observe approved session and both safe locations without writes. **Expected:** exact character, container+slot manifest and complete inventory counts; otherwise UNKNOWN. **Observations:** client inventory, persisted `char_inventory` and decoded pot extra (**missing**). **Assertion:** `GARD-03-baseline-complete`.
2. **GARD-03-S02 / action:** Operator-authorized acceleration; client performs harvest. **Expected:** Conditional permitted item/quantity from pinned SQL+C++; UNKNOWN until fixture/config known. **Capabilities:** `snapshot`, `inventory` (candidates), pot extra; reward delta; config; total item rows; specialized client+gm binding not accepted. **Assertion:** `GARD-03-transition`; if no independently sourced oracle, remain UNKNOWN.
3. **GARD-03-S03 / authoritative comparison:** Capture time-aligned post-action client timeline, server `char_inventory` including `extra`, and all affected pots in **both safes**. **Expected:** all source-backed deltas match; incomplete readback => UNKNOWN, never PASS. **Readback need:** pot extra; reward delta; config; total item rows. **Assertion:** `GARD-03-independent-oracle`.
4. **GARD-03-S04 / cleanup:** Authorized operator reconciles/restores fixture, captures independent pot and inventory state, or quarantines character if incomplete. **Expected:** cleanup independently verified or BLOCKED. **Assertion:** `GARD-03-cleanup-verified`.

**Mutation:** growth / reward map / calculation; requires separate owner approval, no GM authorization inferred from this plan. **Missing oracle/capability:** Reward row ordering, client harvest, deployed config, complete readback missing. **Source support:** growth / reward map / calculation; only the specific code references listed in the source index are authoritative. No player-facing packet/event IDs, server outcomes or inventory item values are guessed.

### GARD-04 — Reject crystal at invalid stage

**Purpose:** An independently proven disallowed stage. **Given:** an explicitly owner-approved disposable character, a pinned DSP build, a complete baseline of both safes and the fixture “An independently proven disallowed stage”. **When:** Client attempts invalid crystal feeding. **Then:** UNKNOWN: invalid-feed rule and non-mutation.

1. **GARD-04-S01 / establish baseline:** Observe approved session and both safe locations without writes. **Expected:** exact character, container+slot manifest and complete inventory counts; otherwise UNKNOWN. **Observations:** client inventory, persisted `char_inventory` and decoded pot extra (**missing**). **Assertion:** `GARD-04-baseline-complete`.
2. **GARD-04-S02 / action:** Client attempts invalid crystal feeding. **Expected:** UNKNOWN: invalid-feed rule and non-mutation. **Capabilities:** `snapshot`, `inventory` (candidates), before/after pot extra and crystal inventory; specialized client binding not accepted. **Assertion:** `GARD-04-transition`; if no independently sourced oracle, remain UNKNOWN.
3. **GARD-04-S03 / authoritative comparison:** Capture time-aligned post-action client timeline, server `char_inventory` including `extra`, and all affected pots in **both safes**. **Expected:** all source-backed deltas match; incomplete readback => UNKNOWN, never PASS. **Readback need:** before/after pot extra and crystal inventory. **Assertion:** `GARD-04-independent-oracle`.
4. **GARD-04-S04 / cleanup:** Authorized operator reconciles/restores fixture, captures independent pot and inventory state, or quarantines character if incomplete. **Expected:** cleanup independently verified or BLOCKED. **Assertion:** `GARD-04-cleanup-verified`.

**Mutation:** stage enum / player feed handler UNKNOWN; requires separate owner approval, no GM authorization inferred from this plan. **Missing oracle/capability:** Disallowed stage source oracle and player handler missing. **Source support:** stage enum / player feed handler UNKNOWN; only the specific code references listed in the source index are authoritative. No player-facing packet/event IDs, server outcomes or inventory item values are guessed.

### GARD-05 — Reject planting without pot or seed

**Purpose:** Two separately isolated missing-prerequisite fixtures. **Given:** an explicitly owner-approved disposable character, a pinned DSP build, a complete baseline of both safes and the fixture “Two separately isolated missing-prerequisite fixtures”. **When:** Client attempts planting with absent pot, then separately absent seed. **Then:** UNKNOWN: client rejection and unchanged state.

1. **GARD-05-S01 / establish baseline:** Observe approved session and both safe locations without writes. **Expected:** exact character, container+slot manifest and complete inventory counts; otherwise UNKNOWN. **Observations:** client inventory, persisted `char_inventory` and decoded pot extra (**missing**). **Assertion:** `GARD-05-baseline-complete`.
2. **GARD-05-S02 / action:** Client attempts planting with absent pot, then separately absent seed. **Expected:** UNKNOWN: client rejection and unchanged state. **Capabilities:** `snapshot`, `inventory` (candidates), inventory and pot manifest, full client outcome; specialized client binding not accepted. **Assertion:** `GARD-05-transition`; if no independently sourced oracle, remain UNKNOWN.
3. **GARD-05-S03 / authoritative comparison:** Capture time-aligned post-action client timeline, server `char_inventory` including `extra`, and all affected pots in **both safes**. **Expected:** all source-backed deltas match; incomplete readback => UNKNOWN, never PASS. **Readback need:** inventory and pot manifest, full client outcome. **Assertion:** `GARD-05-independent-oracle`.
4. **GARD-05-S04 / cleanup:** Authorized operator reconciles/restores fixture, captures independent pot and inventory state, or quarantines character if incomplete. **Expected:** cleanup independently verified or BLOCKED. **Assertion:** `GARD-05-cleanup-verified`.

**Mutation:** seed map / client handler UNKNOWN; requires separate owner approval, no GM authorization inferred from this plan. **Missing oracle/capability:** No-pot and no-seed runtime paths not reviewed. **Source support:** seed map / client handler UNKNOWN; only the specific code references listed in the source index are authoritative. No player-facing packet/event IDs, server outcomes or inventory item values are guessed.

### GARD-06 — Full inventory harvest does not lose or duplicate reward

**Purpose:** Full inventory proved with count/capacity. **Given:** an explicitly owner-approved disposable character, a pinned DSP build, a complete baseline of both safes and the fixture “Full inventory proved with count/capacity”. **When:** Client attempts one harvest. **Then:** UNKNOWN: full-bag behavior; desired no-loss/no-dup is not source proof.

1. **GARD-06-S01 / establish baseline:** Observe approved session and both safe locations without writes. **Expected:** exact character, container+slot manifest and complete inventory counts; otherwise UNKNOWN. **Observations:** client inventory, persisted `char_inventory` and decoded pot extra (**missing**). **Assertion:** `GARD-06-baseline-complete`.
2. **GARD-06-S02 / action:** Client attempts one harvest. **Expected:** UNKNOWN: full-bag behavior; desired no-loss/no-dup is not source proof. **Capabilities:** `snapshot`, `inventory` (candidates), complete inventory locations+counts; pot extra; specialized client binding not accepted. **Assertion:** `GARD-06-transition`; if no independently sourced oracle, remain UNKNOWN.
3. **GARD-06-S03 / authoritative comparison:** Capture time-aligned post-action client timeline, server `char_inventory` including `extra`, and all affected pots in **both safes**. **Expected:** all source-backed deltas match; incomplete readback => UNKNOWN, never PASS. **Readback need:** complete inventory locations+counts; pot extra. **Assertion:** `GARD-06-independent-oracle`.
4. **GARD-06-S04 / cleanup:** Authorized operator reconciles/restores fixture, captures independent pot and inventory state, or quarantines character if incomplete. **Expected:** cleanup independently verified or BLOCKED. **Assertion:** `GARD-06-cleanup-verified`.

**Mutation:** result table / persistence schema; requires separate owner approval, no GM authorization inferred from this plan. **Missing oracle/capability:** 100-row readback limit prevents completeness; harvest capacity rule UNKNOWN. **Source support:** result table / persistence schema; only the specific code references listed in the source index are authoritative. No player-facing packet/event IDs, server outcomes or inventory item values are guessed.

### GARD-07 — Growth and treatment survive relog

**Purpose:** Approved pot and save-boundary capture. **Given:** an explicitly owner-approved disposable character, a pinned DSP build, a complete baseline of both safes and the fixture “Approved pot and save-boundary capture”. **When:** Client makes one approved change, logs out, reconnects. **Then:** Source shows pot extra persisted by garden tick and debug; relog durability UNKNOWN.

1. **GARD-07-S01 / establish baseline:** Observe approved session and both safe locations without writes. **Expected:** exact character, container+slot manifest and complete inventory counts; otherwise UNKNOWN. **Observations:** client inventory, persisted `char_inventory` and decoded pot extra (**missing**). **Assertion:** `GARD-07-baseline-complete`.
2. **GARD-07-S02 / action:** Client makes one approved change, logs out, reconnects. **Expected:** Source shows pot extra persisted by garden tick and debug; relog durability UNKNOWN. **Capabilities:** `snapshot`, `inventory` (candidates), raw + decoded pot extra before logout/after relog; specialized client binding not accepted. **Assertion:** `GARD-07-transition`; if no independently sourced oracle, remain UNKNOWN.
3. **GARD-07-S03 / authoritative comparison:** Capture time-aligned post-action client timeline, server `char_inventory` including `extra`, and all affected pots in **both safes**. **Expected:** all source-backed deltas match; incomplete readback => UNKNOWN, never PASS. **Readback need:** raw + decoded pot extra before logout/after relog. **Assertion:** `GARD-07-independent-oracle`.
4. **GARD-07-S04 / cleanup:** Authorized operator reconciles/restores fixture, captures independent pot and inventory state, or quarantines character if incomplete. **Expected:** cleanup independently verified or BLOCKED. **Assertion:** `GARD-07-cleanup-verified`.

**Mutation:** garden tick persistence / SavePot; requires separate owner approval, no GM authorization inferred from this plan. **Missing oracle/capability:** Relog accepted behavior, save boundary and pot readback unverified. **Source support:** garden tick persistence / SavePot; only the specific code references listed in the source index are authoritative. No player-facing packet/event IDs, server outcomes or inventory item values are guessed.

### GARD-08 — Repeat harvest cannot duplicate rewards

**Purpose:** Proven first harvest and recorded item delta. **Given:** an explicitly owner-approved disposable character, a pinned DSP build, a complete baseline of both safes and the fixture “Proven first harvest and recorded item delta”. **When:** Client attempts second harvest on same pot. **Then:** UNKNOWN: rejection/no duplicate requires full independent post-state.

1. **GARD-08-S01 / establish baseline:** Observe approved session and both safe locations without writes. **Expected:** exact character, container+slot manifest and complete inventory counts; otherwise UNKNOWN. **Observations:** client inventory, persisted `char_inventory` and decoded pot extra (**missing**). **Assertion:** `GARD-08-baseline-complete`.
2. **GARD-08-S02 / action:** Client attempts second harvest on same pot. **Expected:** UNKNOWN: rejection/no duplicate requires full independent post-state. **Capabilities:** `snapshot`, `inventory` (candidates), first + second item deltas; pot extra; specialized client binding not accepted. **Assertion:** `GARD-08-transition`; if no independently sourced oracle, remain UNKNOWN.
3. **GARD-08-S03 / authoritative comparison:** Capture time-aligned post-action client timeline, server `char_inventory` including `extra`, and all affected pots in **both safes**. **Expected:** all source-backed deltas match; incomplete readback => UNKNOWN, never PASS. **Readback need:** first + second item deltas; pot extra. **Assertion:** `GARD-08-independent-oracle`.
4. **GARD-08-S04 / cleanup:** Authorized operator reconciles/restores fixture, captures independent pot and inventory state, or quarantines character if incomplete. **Expected:** cleanup independently verified or BLOCKED. **Assertion:** `GARD-08-cleanup-verified`.

**Mutation:** reward calculation / inventory schema; requires separate owner approval, no GM authorization inferred from this plan. **Missing oracle/capability:** Repeat-harvest handler and complete inventory snapshots unverified. **Source support:** reward calculation / inventory schema; only the specific code references listed in the source index are authoritative. No player-facing packet/event IDs, server outcomes or inventory item values are guessed.

### GARD-09 — Same numeric slot in both safes must not dual-mutate

**Purpose:** Two source-confirmed pots in distinct safe locations with same numeric slot. **Given:** an explicitly owner-approved disposable character, a pinned DSP build, a complete baseline of both safes and the fixture “Two source-confirmed pots in distinct safe locations with same numeric slot”. **When:** Read-only collision preflight; **do not call mutating GM**. **Then:** Known source defect: garden debug selects both safes by numeric slot; safe single-pot mutation not proven.

1. **GARD-09-S01 / establish baseline:** Observe approved session and both safe locations without writes. **Expected:** exact character, container+slot manifest and complete inventory counts; otherwise UNKNOWN. **Observations:** client inventory, persisted `char_inventory` and decoded pot extra (**missing**). **Assertion:** `GARD-09-baseline-complete`.
2. **GARD-09-S02 / action:** Read-only collision preflight; **do not call mutating GM**. **Expected:** Known source defect: garden debug selects both safes by numeric slot; safe single-pot mutation not proven. **Capabilities:** `snapshot`, `inventory` (candidates), both safe containers+slot with pot extra; specialized gm binding not accepted. **Assertion:** `GARD-09-transition`; if no independently sourced oracle, remain UNKNOWN.
3. **GARD-09-S03 / authoritative comparison:** Capture time-aligned post-action client timeline, server `char_inventory` including `extra`, and all affected pots in **both safes**. **Expected:** all source-backed deltas match; incomplete readback => UNKNOWN, never PASS. **Readback need:** both safe containers+slot with pot extra. **Assertion:** `GARD-09-independent-oracle`.
4. **GARD-09-S04 / cleanup:** Authorized operator reconciles/restores fixture, captures independent pot and inventory state, or quarantines character if incomplete. **Expected:** cleanup independently verified or BLOCKED. **Assertion:** `GARD-09-cleanup-verified`.

**Mutation:** DebugCommand loop and SavePot; requires separate owner approval, no GM authorization inferred from this plan. **Missing oracle/capability:** GARD-GM-01 scoped command or proved unique-slot preflight required. **Source support:** DebugCommand loop and SavePot; only the specific code references listed in the source index are authoritative. No player-facing packet/event IDs, server outcomes or inventory item values are guessed.

## Capabilities, fixed readbacks, ranked read-only opportunities

| Capability | Currently available | Missing acceptance/readback |
|---|---|---|
| XiHeadless `snapshot`, `inventory` | Listed as existing generic tools; exact current revision/capabilities not interrogated | Verify observed client rows, completeness and specialized planting/feeding/harvest actions |
| Supervisor inventory | Read-only approved-character route, persisted inventory four columns, 100-row cap | Fixed-query SELECT-only `char_inventory(charid,location,slot,itemId,quantity,extra)` with both safe locations, decoded pot fields, row counts and truncation flag |
| Pot diagnostic | Privileged `garden info` source formats location+slot state [gardenutils.cpp:597–608](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L597-L608) | Accepted structured read-only capture and deployed command check |
| Stage/reward oracle | Source enum, result SQL, CalculateResults | Runtime code/config revision, seed/crystal/strength parameters and independently captured reward |
| Garden mutators | Debug command source exists on feature branch | Owner-approved guarded test environment, unique pot selection or GARD-GM-01 container-scoped remedy, plus player interaction binding |

**Prioritized observation opportunities (not full observe-now cases):** 1. Scan persisted both-safe pot IDs and flag numeric-slot collisions (GARD-09 preflight). 2. Confirm pot presence by the source range 216–221 [gardenutils.cpp:620–623](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L620-L623) without inferring planting. 3. Capture revision, save-boundary and inventory truncation/completeness indicators before accepting any comparison. These are read-only **substeps**, not gameplay verdicts.

**First ten cross-domain observe-now cases: NOT YET RANKABLE.** Gardening contributes zero executable `observe-now` cases. Selecting ten without source-backed reviews of #1250–#1254 would falsely imply verified readbacks/oracles; aggregate after the remaining domain PRs and the schema owner's acceptance.

## Handoff to canonical specification owner and integration agent

The accompanying `data/testing/domain_drafts/gardening.json` is intentionally **non-executable**. It carries stable scenario/step/assertion IDs, BDD, provenance, per-step evidence, UNKNOWN and blocked capability mapping. It is **not** loaded by `test_specifications.py`. The canonical v1 validator's observation registry does not currently support `garden_pot_state` / `char_inventory.extra`, so writing placeholder `equals UNKNOWN` assertions would be dishonest. Do **not** modify shared `data/testing/test_specifications.json` or `feature_test_readiness.json` in parallel; reconcile this file sequentially when the schema owner and local integration agent approve the extension.

No source review here verifies a real client planting, feed, harvest rejection, full-bag handling or replay logic. Operators must confirm deployed revision, select isolated authorized characters, collect independent authoritative readback, verify safety/cleanup, and explicitly approve mutation on a per-case basis. CI validates document structure only; it cannot confer gameplay acceptance.

## Pinned source index

- **Command syntax/permission:** [`scripts/commands/garden.lua:24-43`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/scripts/commands/garden.lua#L24-L43) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Plant/stage/element enum:** [`src/map/items/item_flowerpot.h:41-80`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/items/item_flowerpot.h#L41-L80) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Plant-to-seed mapping:** [`src/map/items/item_flowerpot.cpp:112-132`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/items/item_flowerpot.cpp#L112-L132) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Pot extra bytes:** [`src/map/items/item_flowerpot.cpp:25-36`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/items/item_flowerpot.cpp#L25-L36) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Gardening tick and SQL write:** [`src/map/utils/gardenutils.cpp:90-125`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L90-L125) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Result table loading:** [`src/map/utils/gardenutils.cpp:53-77`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L53-L77) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Harvest calculation:** [`src/map/utils/gardenutils.cpp:126-288`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L126-L288) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Stage progression:** [`src/map/utils/gardenutils.cpp:295-337`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L295-L337) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Pot SavePot/Describe:** [`src/map/utils/gardenutils.cpp:589-608`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L589-L608) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Two-container collision:** [`src/map/utils/gardenutils.cpp:612-629`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L612-L629) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Stage/grow mutation:** [`src/map/utils/gardenutils.cpp:635-660`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L635-L660) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Direct plant/crystal setters:** [`src/map/utils/gardenutils.cpp:679-709`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L679-L709) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Result preview and persisted debug mutation:** [`src/map/utils/gardenutils.cpp:736-756`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/src/map/utils/gardenutils.cpp#L736-L756) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Persistent inventory schema:** [`sql/char_inventory.sql:19-29`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/sql/char_inventory.sql#L19-L29) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`
- **Gardening result table/rows:** [`sql/gardening_results.sql:1-16`](https://github.com/sarthax/darkstar-to-valhalla/blob/330ea8f854cff47aae570aa95d6474f3225f5d49/sql/gardening_results.sql#L1-L16) at DSP `330ea8f854cff47aae570aa95d6474f3225f5d49`

## Source-pin versus current DSP main — 2026-10-21 readiness erratum

The cited `feature/mog-house-gardening@330ea8f854cff47aae570aa95d6474f3225f5d49` remains a valid **historical oracle pin**, not an assertion about deployed DSP. Verified against current DSP `main@86d4467d446569c741d76d296e640c3b844ad844`:

- `src/map/utils/gardenutils.cpp` has a **different blob**. Pinned `SavePot` is at line 589 and the dual-Safe `DebugCommand` loop at line 616; current main has `SavePot` at line 588 and the loop at line 615. Do **not** copy line ranges from one revision to the other.
- Both inspected revisions traverse `LOC_MOGSAFE` and `LOC_MOGSAFE2` and match `slotID` without checking container identity, so a numeric-slot filter is **not** a safely unique pot selector. Before any `!garden` diagnostic, implement and verify an explicit unique-container-slot guard on an isolated server fixture; this draft does not authorize debug mutations.
- The Toolkit inventory supervisor currently selects only `location,slot,itemId,quantity LIMIT 100`, excluding `extra`. No complete GARD scenario qualifies as `observe-now`; source location checks alone cannot lift `needs-mutation` or the prerequisite `needs-readback` gate.

Detailed cross-domain reconciliation: [R5 73-case readiness audit PR #1292](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1292). **No oracle revisions, expected outcomes or execution permissions were changed by this erratum.**
