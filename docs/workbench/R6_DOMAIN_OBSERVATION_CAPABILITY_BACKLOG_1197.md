# R6 Domain Observation Capability Backlog

**Companion-only backlog, not an authoritative case inventory.** The single proposed 73-case readiness authority is the [matrix in PR #1292](https://github.com/sarthax/FFXI-Mission-Toolkit/blob/audit/domain-readiness-73-20261021/docs/workbench/SCENARIO_DOMAIN_READINESS_MATRIX_2026-10-21.json), subject to Agent A and Agent C review; #1293 retains these unique capability contracts, while #1294 performs shared offline draft validation. Do not duplicate, rederive or publish a second 73-case index here. All scenarios remain noncanonical, NOT_RUN, and unavailable to dispatch. The matrix's nine source PR head SHAs are the re-audit triggers, not deployed DSP authenticity.

Companion to [audit PR #1292](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1292), [offline domain CI #1294](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1294), epic [#1197](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1197), and contract proposal [#1285](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1285). All contracts are **proposals, not exposed endpoints**. No new live execution permissions, no domain runnable-catalog import.

## Ranked capability/issue matrix

| Priority | Capability / trace | Affected scenarios | Recommended code owner |
|---|---|---|---|
| P0 | [#1295](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1295) Complete inventory, both safes, furnishing flags and completeness | MOG-09, MOG-01..14, GARD-01..09, CHO-04 | Toolkit fixed-query adapter, XIHeadless existing container observer |
| P0 | [DSP #59](https://github.com/sarthax/darkstar-to-valhalla/issues/59) Deployed revision/config/schema/content hash | All 73, especially CHO-01..09 | DSP source/runtime operator; Toolkit consumes only |
| P0 | [#1296](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1296) Named vars/KIs plus quest/job/currency readbacks | RG-01..08, VOID-01..04, MQ-01..05, VWK-01..07 | Toolkit fixed-query adapter |
| P0 | [#1198](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1198), [#1202](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1202) Evidence completeness, independently observed oracle and partial-run diagnosis | All 73, MOG-09 narrow baseline | Toolkit importer/reviewer, XIHeadless #105 evidence contract |
| P0 | [#1198](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1198) UNAVAILABLE is not FAIL | All, especially SAL-01 and VOID-08 | Toolkit assertion/result presentation |
| P1 | [#1297](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1297) Live instance state | ASLT-01..04, NYZ-01..02, SAL-01..07 | Toolkit contract; eventual DSP observer under [#56](https://github.com/sarthax/darkstar-to-valhalla/issues/56) |
| P1 | [#1298](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1298) Mob, spawn, claim, identity | VWK-01..07, VOID-05/08 | Toolkit contract; eventual DSP read-only observer under #56 |
| P1 | [#1299](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1299) Pyxis slots/token/eligibility | VOID-06..08 | Toolkit contract; eventual DSP read-only observer under #56 |
| P1 | [#1300](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1300) Temp items and active status effects | SAL-01..07, VOID-08 | Toolkit contract, DSP/Headless source review |
| P0 safety | [DSP #60](https://github.com/sarthax/darkstar-to-valhalla/issues/60) Explicit unique two-Safe garden debug selector / reject ambiguous numeric slots | GARD-09 (guards debug-assisted GARD-01..08) | DSP reviewed offline-only source fix; no GM automation |\n| P1 | [XIHeadless #107](https://github.com/sarthax/xiheadless-dsp/issues/107) Read-only cleanup verification and quarantine evidence | Future approved mutations across domains | Reuse XIHeadless existing lifecycle/lease work, Toolkit integrates evidence only |

## Current capabilities: reuse rather than reinvent

- Toolkit `src/workbench/server_admin/feature_testing/database_diagnostics.py`: read-only approved-test-character SQL. `test-character-inventory` returns **up to 100** `location,slot,itemId,quantity` rows without `extra`, total count, or pagination. `test-character-vars` accepts 1–50 named `char_vars` (missing rows currently return null). `test-character-keyitems` reads `chars.keyitems` and includes owned/seen bitsets and decoded blob length. Auth and error handling reside in `supervisor.py`. Results are persisted DB, possibly stale against map-server memory.
- XIHeadless `Mcp/McpBrain.cs`: read-only `snapshot` (zone, job, HP/MP, Gil, event), `container_items` (including Mog Safe location 1, Safe 2 location 10, temp location 3), `key_items`, `nearby_entities` (client-seen ID/name/hpp/claimId, max 50), `wait_for_event`. It also already implements mutating/dispatching `furniture_place`, `furniture_finish`, `furniture_remove`, `pot_plant`, `pot_examine`, `pot_dry`, `pot_harvest`, `trade_npc`, `talk_to_npc` and `event_select`. Those existing commands must **not** be duplicated or treated as proof of game effect.
- XIHeadless `Mcp/McpResult.cs` distinguishes `accepted`, `completed`, and `outcome`; `ok: true` is not gameplay PASS. Existing [#105](https://github.com/sarthax/xiheadless-dsp/issues/105), [#126](https://github.com/sarthax/xiheadless-dsp/issues/126), [#127](https://github.com/sarthax/xiheadless-dsp/issues/127) address evidence, comparability and diagnosis. Do not assign their active local owners another implementation here.
- DSP [#56](https://github.com/sarthax/darkstar-to-valhalla/issues/56) is the existing server-side observer security design gate and [#59](https://github.com/sarthax/darkstar-to-valhalla/issues/59) owns source/environment fingerprint planning. A GitHub commit cited in a draft is **not** evidence of the deployed server image, configured script, active database migration or file digest.

## Additional DSP source-safety gate\n\n**GARD-09:** DSP [#60](https://github.com/sarthax/darkstar-to-valhalla/issues/60) separately owns rejecting ambiguous numeric-slot selectors across `LOC_MOGSAFE` and `LOC_MOGSAFE2` in `gardenutils.cpp`. Existing [Toolkit #1295](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1295) covers full pot/inventory readbacks, not the server-side mutation defect. Neither issue grants GM execution. Chocobo source/migration readiness reuses [DSP #55](https://github.com/sarthax/darkstar-to-valhalla/issues/55) and [#59](https://github.com/sarthax/darkstar-to-valhalla/issues/59), all CHO-01..09 remain primary needs-deploy.\n\n## Proposed bounded readback contracts and acceptance

All proposed endpoints require approved disposable-character identity and a trusted read-only grant (e.g., SELECT-only for persisted rows, a separate reviewed map-server observer for in-memory state). Requests specify `run_id, case_id, step_id, observer_scope, charid, requested_fields` plus zone/entity/instance identity where appropriate. Do not accept raw SQL, arbitrary path, shell, GM command, action packet, or unbounded localvar names. Replies carry `source_kind (client_seen | persisted_db | live_server), revision, observer_version, observed_at, identity_state, availability, complete, value, error_code` and immutable evidence references.

### OBS-P0-1 — Complete inventory/furniture (#1295)

**Input** approved `charid, location allowlist, opaque cursor`; **output** `charid,location,slot,itemId,quantity,extra` (decoded safely or clearly marked undecoded), `returned_rows,total_rows,has_more,complete,snapshot_kind,observed_at,source_digest`. **Authority** DSP `char_inventory(charid,location,slot)` and correctly source-reviewed extra flags; independent client `container_items`. **Permissions** SELECT on inventory only, existing allowlist and loopback. **UNKNOWN** partial 100-row result is INCOMPLETE, missing SQL provider UNAVAILABLE, client/server stale NOT_COMPARABLE, not false empty inventory. **Synthetic tests** 101st row, Safe/Safe2 same slot, old-vs-new item extra, duplicates/pagination drift, missing installed flag and unauthorized charid.

### OBS-P0-2 — DSP fingerprint (reuse DSP #59)

**Input** approved test-environment scope and expected run/revision; **output** checked-out HEAD/dirty state, running binary SHA/source manifest digests, sanitized config digest, migration/schema version, fixture hash and time/attestor origin. **Authority** actual DSP local process/build/config/schema, not remote GitHub refs. **Permissions** operator-controlled filesystem/process metadata with secret redaction, read-only schema metadata. **UNKNOWN** mismatch blocks comparison; absent attestor is UNAVAILABLE, not matching by inference. **Synthetic tests** differing binary/source/schema/config/dirty-state; redaction and missing-migration handling.

### OBS-P0-3 — Quest vars, KIs, job and currency (#1296)

**Input** approved `charid, names[] (<=50, no wildcard), quest_ids[], job_ids[], currency_kinds[]`; **output** each named var with `found` separate from `value`, KI owned/seen and `blob_bytes/expected_bytes`, quest `(log,id,status,present)`, job unlocked/main level, Gil/cruor values, `complete,read_at,snapshot_kind,source_schema_digest`. **Authority** already-known `char_vars` and `chars.keyitems`; **quest/job/currency DSP table names must be independently reviewed** before adding queries. **Permissions** SELECT only on reviewed columns/tables. **UNKNOWN** absent var distinct from value 0, unconfigured DB UNAVAILABLE, truncated KI bitmap INCOMPLETE and stale client NOT_COMPARABLE. **Synthetic tests** missing/zero vars, corrupted KI blob, denied charid, incomplete quest data, job locked despite KI.

### OBS-P0-4/5 — Evidence readiness and UNAVAILABLE versus FAIL (reuse #1198/#1202)

**Input** `run_id,scenario_id,step_id,assertion_id,source_artifact_ref,observer`; **output** `availability (AVAILABLE|UNAVAILABLE|DENIED|INCOMPLETE|STALE|ERROR), complete, reason_code, source_revision, observed_value?, expected_oracle_ref?, assertion_evaluation (NOT_EVALUATED|MATCH|MISMATCH), gameplay_verdict (UNKNOWN|BLOCKED|PASS|FAIL), comparability`. **Authority** immutable original report and separately verified server/client observers. **Permissions** read-only access to approved evidence and observation scopes. **UNKNOWN** missing data never becomes a gameplay failure; FAIL only if a complete comparable observation violates an independently reviewed oracle. **Synthetic tests** 503→UNAVAILABLE with empty response, complete empty vs partial empty, stale client/server, interrupted/replayed run and real observed negative outcome.

### OBS-P1-1 — Instance and doors (#1297)

**Input** approved `charid,zone_id,instance_id?`; **output** `instance_id,stage,progress,objective?,timeRemaining,localvars{cellsUsed,stageComplete,exitPoint},door[{entity_id,unSealed,animation,targetable}],server_time,complete`. **Authority** live DSP instance and door entities, **not** `char_vars` or persisted inventory. **Permissions** read-only scoped runtime observer requiring DSP #56 review. **UNKNOWN** NOT_IN_INSTANCE distinct from UNAVAILABLE, EXPIRED distinct from timed-out fetch, debug complete not natural objective PASS. **Synthetic tests** overlapping instances, out-of-order stage/door reads, forced-debug progress, expired timer and teardown race.

### OBS-P1-2 — Mob and claims (#1298)

**Input** approved `charid,zone_id,server_entity_id`; **output** server entity identity, live spawned/status/claim, allowlisted localvars `POPPED_BY/POPPED_WITH/POPPED_AT/VW_RIFT/VW_SPAWNER/VW_CLR`, `source_ref,observed_at,complete`. **Authority** DSP live mob/map runtime, compared to XIHeadless `nearby_entities`. **Permissions** scoped read-only per zone/entity, no spawn/claim commands. **UNKNOWN** wrong identity UNRESOLVED_IDENTITY, not spawned different from provider unavailable; stochastic abyssite upgrade remains conditional. **Synthetic tests** same-name NMs, different claim owners, zero/absent localvars and spawn/despawn race.

### OBS-P1-3 — Pyxis slots and ownership (#1299)

**Input** approved `charid,zone_id,pyxis_id,encounter_ref`; **output** `ITEM1..8,TOKEN,ELIG_self,TAKEN_self,expiry,server_time,complete`, linked to full inventory delta. **Authority** live DSP Pyxis NPC localvars plus persisted inventory. **Permissions** read-only per Pyxis/player, no item grant or other users' data. **UNKNOWN** EMPTY_SLOT/NOT_ELIGIBLE/MISSING_PYXIS/STALE/UNAVAILABLE separate. **Synthetic tests** addItem accepted clears slot, full inventory leaves slot, repeat attempt, concurrent claims and expired encounter token.

### OBS-P1-4 — Temp items/status effects (#1300)

**Input** approved `charid,zone_id,instance_id?`; **output** temp slot/itemId/qty plus effect ID/power/subpower/remaining duration/source entity, `complete,observed_at`. **Authority** server live status and temporary item state (specific C++/Lua storage requires source review), client `container_items(3)` separate. **Permissions** read-only scoped enumeration, fixed caps and IDs. **UNKNOWN** ABSENT only with complete enumeration; incomplete effect list cannot prove Pathos cleared. **Synthetic tests** all 5 Pathos, masked powers, duplicate slot, incomplete read, time drift and genuine exit vs unknown effect loss.

### OBS-P1-5 — Cleanup (reuse XIHeadless #107)

**Input** approved `run_id,lease_id,charid,postconditions[]`; **output** independent lease, entity/instance, inventory/status and artifact-seal postcondition readbacks with `availability,observed,expected,match,quarantine_required`. **Authority** existing lease state plus the above bounded DSP/Toolkit readbacks. **Permissions** **observation only**; never retry mutation, clear item or release lease through this endpoint. **UNKNOWN** partial cleanup remains BLOCKED, force-exit not confirmed normal teardown. **Synthetic tests** stale claim, lingering Pathos, unclean logout, missing lease and incomplete artifact seal.

## Agent C optional contract_v2 adapter requirements

Keep outer `schema_version=1`, preserve MOG-09's historical verified runner and all 73 noncanonical design-only records. Normalize `lane`/`execution_lane` only when equal; Gardening #1277 now mirrors both. Map staged source-ref aliases (step `oracle_refs`, `oracle_sources`, `source_refs`) to v2 sources with path+line+full commit; keep digest NULL until source bytes are independently hashed and deployed revision separately attested. Typed identity needs explicit namespace+zone, ambiguous/unresolved remain blocked. UNKNOWN oracle uses no normative source refs and cannot be mapped to `equals UNKNOWN`; v2 assertion IDs must bind existing canonical v1 assertions, not merely staged per-step IDs. v2 `step_requirements` bind stable step IDs, candidate readbacks/permissions, and **always `execution_gate=blocked`**. Preserve original observed evidence and UNKNOWN/FAIL distinction. Respect 32KiB draft cap; reviewer approval required before any spec projection.

## Safe shortlist and handoff (same priority order as canonical #1292)

**Conditionally observable now means a bounded *read-only baseline*, not a runnable gameplay test or verified oracle.** Rank for new observation coverage is by incremental risk/benefit, not historical runner existence:

1. **RG-01** — approved-character GEO `DwL_Prog`, `DwL_Declined` plus soil/LUOPAN KIs. Quest-state and job unlock remain UNKNOWN.
2. **RG-06** — RUN `RUN_COTR` and petal KI only. No quest completion claim.
3. **VOID-01** — `VWO_STOCK`, `VWO_STOCK_TS`, held KIs; not proof of real-time officer accrual.
4. **VOID-02** — `VWO_TIERS`, `VWO_TIERS2`, abyssites; not a mob kill attribution.
5. **MOG-09** — **already canonical, narrowly supported historical observation** of active KI, aura and imported bag/Safe rows, but no independent empty installed-layout witness. Its prior evidence is not a fresh authenticated run.

No new test is dispatchable by this list. These five require operator-configured SELECT-only/bearer access, approved character, explicit persisted snapshot freshness and full source/identity review for any assertive interpretation. **SAL-01** and **VOID-08** are read-only *in intent* but cannot be observed completely through current endpoints. **Gardening has zero full observe-now cases**; a four-column LIMIT-100 inventory read is only a partial preflight. All nine **CHO-01..09** remain needs-deploy until DSP Phase 0 source/binary/migration/readback attestation. Agent A owns integration review; Agent C owns optional `contract_v2` semantics. No active XIHeadless local-agent assignment or live operations.
