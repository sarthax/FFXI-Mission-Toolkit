# Chocobo Raising R5 — source-backed staged scenarios

Related Toolkit [#1129](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1129), [#1254](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1254), epic #1197. Pin to development-only [`feature/chocobo-raising-core@55e1baa382bcf1905c329c36d3a67fa244dbd6cd`](https://github.com/sarthax/darkstar-to-valhalla/tree/55e1baa382bcf1905c329c36d3a67fa244dbd6cd). **NOT merged/deployed-verified; no runtime verdict.**

## Readiness and source-oracle matrix

| Case | Purpose | Primary lane | Secondary prerequisites | Source confidence |
|---|---|---|---|---|
| CHO-01 | Schema migration preflight, no writes | `needs-deploy` | needs-readback | PROPOSAL_ONLY_NOT_RUNTIME_ORACLE |
| CHO-02 | New character has no raised-chocobo row | `needs-deploy` | needs-readback | PROPOSAL_ONLY_NOT_RUNTIME_ORACLE |
| CHO-03 | Raise record write and relog roundtrip | `needs-deploy` | needs-mutation, needs-readback | PROPOSAL_ONLY_NOT_RUNTIME_ORACLE |
| CHO-04 | Chocobo egg extra data survives reload and move | `needs-deploy` | needs-mutation, needs-readback | PROPOSAL_ONLY_NOT_RUNTIME_ORACLE |
| CHO-05 | User data and registered field chocobo persist | `needs-deploy` | needs-mutation, needs-readback | PROPOSAL_ONLY_NOT_RUNTIME_ORACLE |
| CHO-06 | Character deletion cleans only owned Chocobo row | `needs-deploy` | needs-mutation, needs-readback | PROPOSAL_ONLY_NOT_RUNTIME_ORACLE |
| CHO-07 | Stable trainer, egg handover and daily care plans | `needs-deploy` | needs-mutation, needs-readback | PROPOSAL_ONLY_NOT_RUNTIME_ORACLE |
| CHO-08 | Whistle registration, mounting and appearance | `needs-deploy` | needs-mutation, needs-readback | PROPOSAL_ONLY_NOT_RUNTIME_ORACLE |
| CHO-09 | Rollback is not a safe cleanup shortcut | `needs-deploy` | needs-readback | PROPOSAL_ONLY_NOT_RUNTIME_ORACLE |

## Source-backed gating

- [`README.md:3–16`](https://github.com/sarthax/darkstar-to-valhalla/blob/55e1baa382bcf1905c329c36d3a67fa244dbd6cd/docs/slices/chocobo-raising-core/README.md#L3-L16): Phase 0 C++ binding, item exdata and schema only; trainer scripts, mounting and whistle **not included**. Syntax checked only; migration not applied at documentation time.
- [`up.sql:1–36`](https://github.com/sarthax/darkstar-to-valhalla/blob/55e1baa382bcf1905c329c36d3a67fa244dbd6cd/sql/slices/chocobo-raising-core/up.sql#L1-L36): additive `char_chocobos` keyed `charid`, and blob `char_pet.chocobo_user_data`; this is a proposed schema, not proof of actual live rows.
- [`charentity.h:161–178`](https://github.com/sarthax/darkstar-to-valhalla/blob/55e1baa382bcf1905c329c36d3a67fa244dbd6cd/src/map/entities/charentity.h#L161-L178) and [`lua_baseentity.h:133–139`](https://github.com/sarthax/darkstar-to-valhalla/blob/55e1baa382bcf1905c329c36d3a67fa244dbd6cd/src/map/lua/lua_baseentity.h#L133-L139): 32-byte user state and registered/get/set bindings declared; runtime API behavior remains UNKNOWN.
- [`lua_item.h:75–76`](https://github.com/sarthax/darkstar-to-valhalla/blob/55e1baa382bcf1905c329c36d3a67fa244dbd6cd/src/map/lua/lua_item.h#L75-L76): 24-byte extra-data declarations, not independently verified save/relogin roundtrip.
- [`mountutils.h:28–57`](https://github.com/sarthax/darkstar-to-valhalla/blob/55e1baa382bcf1905c329c36d3a67fa244dbd6cd/src/map/utils/mountutils.h#L28-L57): packed property semantics intentionally unverified for this client.
- [`down.sql:1–3`](https://github.com/sarthax/darkstar-to-valhalla/blob/55e1baa382bcf1905c329c36d3a67fa244dbd6cd/sql/slices/chocobo-raising-core/down.sql#L1-L3): rollback **drops table and column**. Prohibit automatic execution / cleanup on a persistent DB.
- [`TEST_PLAN.md:3–17`](https://github.com/sarthax/darkstar-to-valhalla/blob/55e1baa382bcf1905c329c36d3a67fa244dbd6cd/docs/slices/chocobo-raising-core/TEST_PLAN.md#L3-L17): tests listed as **untested**; never convert that plan into verified outcomes.

## Ranked observe-now

**None.** Branch deployment and migration are unknown/not applied as recorded in the source; readbacks for per-character chocobo row, egg exdata and persistent blob are not present. Primary `needs-deploy` applies to each draft, with explicit secondary `needs-readback` / `needs-mutation`.
## Safety, scope and UNKNOWNs

- The available `scripts/globals/chocobo.lua` addresses rental pricing, not Chocobo Raising. Do not treat rental NPC evidence as care-plan/egg/trainer logic.
- Chocobo Raising LSB implementation is a comparison lead, **not a DSP oracle** until implementation and compatibility are verified.
- No client packets, guessed CSIDs, stable NPC IDs, egg exdata fields, genetic outcomes, accelerated timers or mount behavior asserted.
- Character deletion and `down.sql` would destroy data; require owner-controlled disposable fixtures, verified backup, isolated schema and explicit separate approval; never auto-run.
- The source revision is different from the presently deployed server unless confirmed; R5 drafts are design-only and must not be included as runnable baseline.
- Staged JSON remains independent of #1259 canonical contract changes.

## BDD definitions

Nine cases `CHO-01..09` are written in [`data/testing/domain_drafts/chocobo_raising.json`](../../data/testing/domain_drafts/chocobo_raising.json) with four ordered steps, source citations, readback dependencies, explicit UNKNOWNs, no execution permission and NOT_RUN verdict.
