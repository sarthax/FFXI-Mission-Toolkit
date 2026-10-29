# Voidwatch R5 — domain scenario coverage

Issue [#1254](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1254); epic #1197. **Source:** [`sarthax/darkstar-to-valhalla@86d4467d446569c741d76d296e640c3b844ad844`](https://github.com/sarthax/darkstar-to-valhalla/tree/86d4467d446569c741d76d296e640c3b844ad844). Runtime/deployed SHA **UNKNOWN**. Design-only; no live runs, merges, GM, or account actions.

## Lane and oracle matrix

| Case | Meaning | Lane | Source-backed oracle / explicit limit |
|---|---|---|---|
| VOID-01 | Officer stock and timestamp baseline | `observe-now` | Existing vars may be zero; record exact snapshot, not presumed initial stock |
| VOID-02 | Tier kill-bit and held abyssite baseline | `observe-now` | Only bits and held KIs explicitly present in the snapshot may be asserted; no tier-upgrade inferred |
| VOID-03 | Voidstone refill from officer stock | `needs-mutation` | Formula is min(stock,carry-held); encoded VOIDSTONE1..6 KI replaces prior level, stock decreases by granted amount; real client event option and deployment must be checked |
| VOID-04 | Insufficient cruor rejects exchange | `needs-mutation` | Implementation returns without cost, KI or item grant if available cruor is below price; require independent before/after balance and item/KI counts |
| VOID-05 | Voidwatch rift spawn and claim | `needs-mutation` | Source schedules a 3-second timer and records VW_RIFT/VW_SPAWNER; actual timely spawn or claim requires entity observations; no fixed network timing assertion |
| VOID-06 | Pyxis slot claim and inventory delta | `needs-mutation` | On successful addItem, ITEM slot becomes zero; on insufficient capacity branch leaves slot intact; random item type UNKNOWN |
| VOID-07 | Repeat take does not duplicate emptied Pyxis slot | `needs-mutation` | ITEM slot already 0 is not added by vwPyxisTake; require zero item delta, not repeated menu acknowledgment |
| VOID-08 | Voidwatch clearance and post-fight teardown | `needs-readback` | Code clears VOIDWATCHER from characters recorded by VW_CLR during vwEndOperation; client status alone cannot prove cleanup callback occurred |

## Independent sources and safety findings

- [`voidwatch_officer.lua:53–97`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/globals/voidwatch_officer.lua#L53-L97): stock fields `VWO_STOCK`/`VWO_STOCK_TS` and interval depend on periapt; source notes some choices are `[D]` design assumptions, not retail proof.
- [`voidwatch_officer.lua:115–126`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/globals/voidwatch_officer.lua#L115-L126): per-member same-zone kill bit; no proof of a particular NM kill from bit alone.
- [`voidwatch_officer.lua:165–199`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/globals/voidwatch_officer.lua#L165-L199): cruor exchange checks funds, duplicate KIs, free inventory; read-only cruor accounting missing.
- [`voidwatch.lua:95–162`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/globals/voidwatch.lua#L95-L162): rare pool and blue/red bonuses include `[D]` assumptions and randomized rolls; never assert a fixed specific drop.
- [`voidwatch.lua:272–301`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/globals/voidwatch.lua#L272-L301): pyxis `ITEM1..8` consumed only after `addItem` succeeds; item presence/menu acknowledgment is not proof of persistence.
- [`voidwatch.lua:303–325`](https://github.com/sarthax/darkstar-to-valhalla/blob/86d4467d446569c741d76d296e640c3b844ad844/scripts/globals/voidwatch.lua#L303-L325): temporary effect 475 cleanup is source intent; duration explicitly unverified.

## Ranked observe-now (design only)

1. VOID-01 — stock/timestamp/KI baseline; strictly no menu interaction.
2. VOID-02 — tier-bit and KI baseline; do not infer kill success.

## Missing observations and gating

- Source SHA is pinned but deployed source, server configuration and event capture compatibility are UNKNOWN.
- Complete cruor, mob claim/local variables, Pyxis slots, rift and status effect readbacks need bounded authorized contracts. Numeric IDs in scripts are not blanket client validation.
- `needs-mutation` cases require explicit disposable-character permission, isolated baseline and cleanup/quarantine. `needs-readback` is not a request to make an unsafe general-purpose SQL endpoint.
- Staged JSON is **not** appended to canonical `data/testing/test_specifications.json` pending #1259 / Agent C additive schema review.

## Per-case ordered BDD, steps, source and UNKNOWNs

Each staged case in [`data/testing/domain_drafts/voidwatch.json`](../../data/testing/domain_drafts/voidwatch.json) contains Given/When/Then, S01–S04, asserted source line/commit at every step, readback, capability candidates, and cleanup; all verdicts NOT_RUN.
