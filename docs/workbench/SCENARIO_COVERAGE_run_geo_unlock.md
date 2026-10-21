# RUN / GEO unlock quests — source-backed R5 scenario coverage

Issue [#1254](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1254), epic #1197. Source revision [`86d4467d446569c741d76d296e640c3b844ad844`](https://github.com/sarthax/darkstar-to-valhalla/tree/86d4467d446569c741d76d296e640c3b844ad844), not deployed-confirmed. **Design-only; no live quests run.**

## Lane and oracle matrix

| Case | Purpose | Lane | Source predicate / remaining uncertainty |
|---|---|---|---|
| RG-01 | GEO quest-variable and key-item baseline | `observe-now` | Report only observed values; quest status/actual GEO unlock remains UNKNOWN without job/quest readback |
| RG-02 | GEO unlock offered only at requisite level | `needs-mutation` | Source chooses event 33 below threshold vs event 31 above; threshold value is not fabricated and decoded client event must be verified |
| RG-03 | GEO petrified-log trade yields Luopan KI | `needs-mutation` | Source triggers 34 then tradeComplete, removes soil and grants LUOPAN; cannot assert without trade inventory and KI delta |
| RG-04 | GEO locus healing advances wait-dependent state | `needs-mutation` | Source sets DwL_Prog=1 only after random 9–480 sec timer while remaining in locus; no guaranteed fixed elapsed time |
| RG-05 | GEO quest completion grants unlock and two items | `needs-mutation` | On successful npcUtil.giveItem for PLATE_OF_INDI_POISON + MATRE_BELL, source unlocks GEO, grants JOB_GESTURE_GEOMANCER and completes quest |
| RG-06 | RUN quest state and petal baseline | `observe-now` | Actual quest progress and RUN unlocked flag UNKNOWN from vars and KI alone |
| RG-07 | RUN quest petal and Octavien event sequence | `needs-mutation` | Petal only granted while quest accepted and not already held; Octavien selects event 26 on accepted+petal; actual option/packet UNKNOWN |
| RG-08 | RUN completion rewards and pending-state recovery | `needs-mutation` | RUN_COTR=3 on option 1; successful giveItem(20781) unlocks RUN, grants gesture KI, removes petal, completes quest; failure should not claim completion |

## Primary source findings

- [`Sylvie.lua:28–69`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Western_Adoulin/npcs/Sylvie.lua#L28-L69): GEO acceptance, level gate, trade prerequisites depend on quest status, soil and Luopan KIs. Do not assume event-only success.
- [`Sylvie.lua:95–115`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Western_Adoulin/npcs/Sylvie.lua#L95-L115): GEO unlock is downstream of giveItem; requires job state, KI, two-item inventory and quest completion proof.
- [`dances_with_luopans.lua:19–65`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/globals/dances_with_luopans.lua#L19-L65): random resting duration is between source-defined limits while in locus; exact time UNKNOWN.
- [`Yahse_Wildflower.lua:17–22`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Yahse_Hunting_Grounds/npcs/Yahse_Wildflower.lua#L17-L22): RUN petal issued only if quest accepted and KI absent.
- [`Octavien.lua:37–105`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/zones/Eastern_Adoulin/npcs/Octavien.lua#L37-L105): RUN state branches, event-dependent HP/MP effects, reward-pending gate, SOWILO_CLAYMORE then job unlock/quest completion. Comment warns Octavien SQL versus LSB NPC position differs.

## Ranked observe-now scenarios

1. **RG-01** — observe GEO vars `DwL_Prog`, `DwL_Declined` and two KIs only.
2. **RG-06** — observe RUN var `RUN_COTR` and petal KI only.

These observations **do not** establish unlocked-job bits, quest completion, or normal event progression. Those require independent, bounded readbacks.

## Required readbacks, cleanup and UNKNOWNs

- New approved quest-status + unlocked-job readbacks, complete inventory counts, item trade outcomes, client event options and localvars for locus wait. No generic mutations.
- Source quest constants and client IDs are pinned to script comments, but live DAT/capture and deployed DSP SHA were not observed. Do not invent packet IDs or infer runtime readiness.
- Event 26 RUN branch may halve HP/MP; only isolated owner-authorized fixtures should ever exercise that path.
- Canonical schema #1259 owns shared `data/testing/test_specifications.json`; this PR introduces independent staging, test and documentation only.

## Scenario details

Every case in [`data/testing/domain_drafts/run_geo_unlock.json`](../../data/testing/domain_drafts/run_geo_unlock.json) includes BDD narrative, four stable-ID steps, source refs for each step/oracle, expected outcome, readback, UNKNOWN blockers and cleanup. All NOT_RUN.
