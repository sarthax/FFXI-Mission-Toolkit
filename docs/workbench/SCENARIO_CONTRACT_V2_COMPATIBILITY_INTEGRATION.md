# Canonical contract v2 — adoption mapping, compatibility audit and blockers

Issue [#1259](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1259), epic [#1197](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1197), draft [PR #1285](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1285). This is an *audit and optional metadata migration plan*, **not** a domain import, an authenticated source-verifier, or an authorization mechanism. Canonical `schema_version` remains **1**.

## 1. Independent compatibility audit against current main

| Source on main | Behavior/contract audited | Effect of optional `contract_v2` |
|---|---|---|
| `src/workbench/server_admin/feature_testing/test_specifications.py::validate_spec` | Strict outer v1, unchanged fixed list of observed fields/operators; MOG-09 is sole `verified_runner` allowlist | PR #1285 adds one optional field and separate metadata validator; no version 2 top-level catalog or widened runner/observation allowlist |
| `data/testing/test_specifications.json` | Published **MOG-09** BDD + assertions, **INV-OBS-01** observation-only, neither has v2 | No canonical data file edits or implicit upgrades; the import and evaluator continue to see the same v1 values |
| `feature_testing.assertion_engine.evaluate` and `normalized_evidence.normalize_mog09` | Compare allowlisted v1 observations/expected literals, sourced entirely from imported report | v2 never supplies an evaluated expected value; unknown oracle cannot turn into PASS. Legacy imported PASS is still unverified |
| `feature_testing.results`, `feature_testing.importer.validate_report` | v1 report requires three engine commits but **does not require spec digest**, rehashed source content or independent readback | `compatibility_report` MUST be called with separately supplied pinned engine/source fingerprints. Do not infer them from a PASS or force legacy runs to match a newly authored spec |
| `feature_testing.spec_drafts._validate_draft/save_draft` | Revisioned SQLite draft, design_only + unassigned, 32KiB limit, no published-spec overwrite | Metadata can be preserved in JSON as-is. A changed case ID or canonical field invalidates any previous `base_spec_sha256`; never copy a previous trusted status |
| `scenario_authoring.editor_router.validate_editor_spec`, `gui/static/scenario_guided_model.js`, `scenario_developer.js` | Guided/Advanced authoring edits existing v1 fields; latest editor may add context handoff separately | PR #1285 makes **no UI change**. Metadata can remain a JSON property, but **no source/binding/step permission UI or trust rendering exists**. Editor fork/copy/reorder must trigger ref+hash revalidation before adoption |
| `feature_testing.scenario_presentation.scenario_presentation`, scenario/run templates | Display-only expected-vs-observed, UNKNOWN when not observed, `independent_verification=NOT_ESTABLISHED` | Metadata is ignored by existing renderer, so v1 behavior does not change; future UI must not equate metadata `source_cited` with independent verification |
| Agent E `data/testing/domain_drafts/*.json` | Rich **staging** envelopes, not accepted canonical specs | Only source-backed optional metadata may be projected into a separate reviewed v1 wrapper. Novel observations/actions/UNKNOWN assertion expressions remain blocked |

Audit result: PR #1285 is an isolated additive metadata validator plus pure comparer and serializer. It is **not** a complete schema v2 runtime or a domain importer. Missing optional namespace remains valid v1. Every enriched spec must still pass original canonical v1 rules. No fixture or metadata can register an executable runner.

## 2. Agent E staged domain → `contract_v2`

| Staged data (Agent E) | Projection | Rule / blocker |
|---|---|---|
| `source_revision.dsp_commit`, `source_revision.dsp_branch`, `source_revision.deployed` | `fingerprints.dsp_commit` may carry a 40-hex *reviewed source revision*; branch and deployed status stay in staging migration notes | A branch SHA is **not proven live deployment**; comparison to an externally verified current DSP SHA required |
| Step `oracle_refs[]` or `source_refs[]`; case-level `oracle_sources[]` / `source_refs[]` | Distinct `sources[]` refs with `repository`, `path`, `line_start`, `line_end`, `revision` copied from source `commit`; `classification=dsp_source` only for actual DSP Lua/SQL/implementation | Existing linked GitHub URL is navigation, not a digest. Most staged citations have **no content SHA-256**: set `sha256=null`, keep confirmation UNKNOWN; do not mint a hash. Deduplicate only exact source *repo/path/span/revision* |
| Staged `assertions[].oracle_state`, `oracle_status`, `expected`, oracle notes | Only after a valid canonical v1 assertion exists: `oracles[].assertion_id`; explicit UNKNOWN → `oracle_type=unknown`, `confidence=unknown`, `source_refs=[]`; separately source-backed **candidate** rules may use `oracle_type=source_rule`/`confidence=candidate` with DSP code ref | Staged `expression=reviewed_oracle_required_no_auto_eval` and free-text UNKNOWN are **not** v1 evaluator operations. Do not invent `equals UNKNOWN`, or import observed values as expected |
| Staged item, KI, NPC, mob, zone references | `parameters[]` with `kind=item|key_item|npc|mob|zone|catalog`, appropriate `namespace`, `identity`, `zone_id`, `source_refs[]`, `binding_state` | Only copy an exact recorded, reviewed identity. Bare numeric ID, label coincidence or unresolved cross-client catalog → `identity=null` and `unresolved` or `ambiguous`. For a verified *claim*, NPC/mob requires zone scope and source revision+hash, still not execution trust. `keyitem` from catalog maps explicitly to `key_item` |
| `steps[].id`, `steps[].action`, `intent`, `execution_authorized`, `manual_execution_allowed`, `mutation`, `run_mode` / `lane` | Reviewed step to `step_requirements[].step_id`; conservative `capability`, `operation_class`, `required_permissions`, `required_readbacks`, `approval_required`, **`execution_gate=blocked`** | Missing action ownership or unknown effect → `operation_class=unknown`; direct GM actions need separate case authorization even if command advertises diagnostic/read-only. Staged `execution_authorized=false` is not a permission grant |
| `required_readback`, `readback`, `required_client_observations`, `required_authoritative_observations`, `observations_required` | Step's **unverified named** `required_readbacks[]` (or separate staged requirement list) | The field accepts bounded names but does **not** register a new observation, query, API, completeness guarantee or permission. Existing canonical `observations[]` is unchanged |
| `xiheadless_candidates`, `xiheadless`, `capabilities.missing`, `blocking_gaps`, `gaps`, `additional_gates` | Candidate capability and human-readable blocking gaps in existing `authoring.blocking_gaps` where v1 constraints permit | XiHeadless tool names, server readbacks and deployed revision need separate allowlist, permission and operator acceptance; do not transform into a supported runner |
| Staging `verdict=NOT_RUN` / `execution_enabled=false` | Keep outside normative oracle; published/draft wrapper must use `design_only` + `unassigned` | NOT_RUN is no imported execution result; do not report PASS or independently verified coverage |

**Concrete noncanonical migration fixture:** `test_fixtures/scenario_contract_v2_gardening_migration_synthetic.json` references staged `spec/gardening:data/testing/domain_drafts/gardening.json`, the existing **GARD-01** source line `sarthax/darkstar-to-valhalla@330ea8f...:sql/char_inventory.sql:19-29`. The illustrative wrapper uses clearly **SYNTH** tooling IDs, `design_only/unassigned`, `session` placeholder, null `expected` and UNKNOWN oracle; it **never migrates GARD-01's normative assertion**. The content digest, deployed DSP commit, actual pot extra, independent readback and scoped pot identity remain UNKNOWN. No GARD-01 case is added to canonical `test_specifications.json`; evaluating the synthetic placeholder assertion is BLOCKED, not PASS.

### Per-domain migration blockers (no mass import)

| Domain / draft PR | Existing staged coverage | Minimum blocked dependency |
|---|---|---|
| Gardening #1277 (GARD-01..09) | `oracle_refs` / `source_refs`, pot-slot code and `char_inventory.extra` | Needs complete *two-safe* container+slot pot-extra fixed-query readback, matching client placement/event and source/config/deploy audit. Numeric `!garden` slot collisions prohibit automatic GM actions |
| Voidwalker #1279 (VWK-01..07) | `source_refs`, RNG-dependent oracle / pop-claim-local vars | Needs POPPED_BY/POPPED_WITH/POPPED_AT authoritative mob local-variable and spawn/claim readback, validated /heal, deployment; probabilistic upgrade cannot be an unconditional expectation |
| Assault/Nyzul #1280 (ASLT/NYZ) | Source-cited entry, floor, objective, GM diagnostics | `nyzuldebug`/warps bypass normal gameplay; no guaranteed normal-entry proof, source-pinned instance status/ID/timer/progress readback or local cleanup |
| Missions/quests #1281 (MQ-01..05) | Source branch/line NPC handlers + stable ordered steps | Client event/result IDs and authoritative quest/var/reward state need local crosswalk; source branch may permit duplicate rewards, so no invented no-duplicate PASS |
| Moghancement #1282 (MOG-01..14) | Source-cited installed aura/KI and distinct GM diagnostic | Need installed-layout/held KI and modifier independent readback; existing MOG-09 runnable v1 is **not** a proven oracle for every new case. Never overwrite legacy MOG-09 |
| Voidwatch #1286 (VOID-01..08) | Diagnostic and normal progression tentative oracle, stage source refs | Source has speculative/temporary behavior; needs cruor/pyxis/spawn/claim/loot readbacks and deployment proof; not a retail correctness oracle |
| Salvage #1289 (SAL-01..07) | Pathos/cells/doors/crates staged source | Active instance/limiter/progress and inventory/door readbacks unavailable; mutation and cleanup approval unresolved |
| RUN/GEO unlock #1290 (RG-01..08) | Quest/job/level predicates, trade, event, petal KI | Read-only var/KI candidates are not complete unlock proof; source-mapped client events, level/quest/job/reward readbacks and server deployment needed |
| Chocobo raising #1291 (CHO-01..09) | Schema/migration/source code and explicitly unimplemented segments | Primary **needs-deploy**, staged migration/rollback and source digest audit; trainer/mount/whistle not implemented, no scenario should claim runtime support |

Across **all** domains: independently rehash actual file bytes at the pinned source revision, verify deployed/selected engine version, reconcile typed NPC/item/KI catalog namespace and zone, audit expected source-branch conditions, approve the exact v1 observation/operation bindings, and secure operator authorization before moving beyond a design-only wrapper.

## 3. Agent D identity/oracle classifications → `contract_v2`

Source: Agent D draft PR #1287, `src/workbench/captures/scenario_identity_readiness.py`, `docs/workbench/CAPTURE_IDENTITY_ORACLE_READINESS_1262.md`; imported captures are *observation* lanes, never normative expectations.

| Agent D classification | v2 parameter projection | What is **not** allowed |
|---|---|---|
| `EXACT` (unique fully scoped indexed source record with declared namespace reconciliation) | **At most** `candidate` until original bytes, zone/client+DSP crosswalk, source digest and operator audit are independently checked. Preserve D's `source_identity_verified=false` | Never map directly to `independently_source_verified`, even with a syntactic pinned digest |
| `AMBIGUOUS` (multiple candidates/conflicting recorded labels) | `ambiguous` and **`identity=null`**; keep full alternatives in D's diagnostic envelope | Do not select a candidate or flatten alternatives |
| `INFERRED` (name/numeric similarity, partial scoped hit) | `candidate` only if a single bounded candidate can be represented without pretending source verification; otherwise `unresolved` | Never claim normalized cross-client identity from equal numbers |
| `UNRESOLVED` | `unresolved`, `identity=null` | Search miss is not proof of missing gameplay entity |
| `UNSUPPORTED` (raw opcode, untyped EventView MesNum, unscopeable dialog) | No v2 typed parameter until a supported namespace exists, or `unresolved` with null identity | No generic guessed `catalog` type hiding an unsupported packet/event/CSID |

Agent D `independent_oracles[].origin=independent_dsp_source`, `from_capture=false`, source file/line/revision/digest and separate `expected_candidate` are **review-only candidates**. When a matching *canonical assertion* exists and a pinned DSP code ref is accepted as a metadata source, the maximum unreviewed v2 description is `oracle_type=source_rule`, `confidence=candidate`; if a matching canonical assertion or source cannot be validated, use `unknown` with **empty source refs**. `SOURCE_CANDIDATE_REVIEW_REQUIRED` is not `source_cited`/verified expectation. Never copy the observed capture value or D's `expected_candidate` into v1 `assertions[].expected` without independent review.

Agent D's `source` hash may be an **indexed capture file** hash rather than a rehash of the normative DSP file. This does **not** satisfy `contract_v2.sources[].sha256` for a `dsp_source`. Preserve the original source-lane checksum and parser/version refs in D's evidence envelope. `source_type=capture_observation` may be referenced for provenance, but is explicitly forbidden as the *only* source for a `source_rule` or `source_literal` oracle. Divergent capture parser/source hashes, different clocks and repeated recorded behavior are review diagnostics, not automatic normative FAIL.

## 4. Scenario Developer rendering and authoring acceptance (Agent B)

Review source: merged #1274 and #1288 plus pending #1283. Editor-owned `scenario_guided_model.js` clones dictionary fields, and Advanced JSON can serialize the optional section, but the current Guided UI has **no accepted widgets** for these metadata records. Integration must be separate, editor-owned work:

1. Show **source cards** with repository-relative path, line span, claimed revision, digest present/missing, source classification, and a direct link only to a validated GitHub/repository source URI. Label `UNHASHED`, `STALE` and `SOURCE_CLAIM_NOT_REHASHED` explicitly. Escape text/URL; do not use source paths as executable commands or arbitrary fetch targets.
2. Show **typed parameter cards** for kind+namespace+zone, recorded candidate alternatives, `ambiguous/unresolved/candidate`; if metadata says `independently_source_verified`, render `DECLARED_PINNED_SOURCE_CLAIM — EXTERNAL_REVIEW_REQUIRED`, not a verified identity badge.
3. Show **per-step restrictions** beside each BDD action: requested capability (candidate), operation class, readback gaps, permissions and **BLOCKED** execution gate, regardless of the old `runner` label. No UI action should infer permission from `gm_diagnostic_candidate` alone.
4. Show **expected oracles** separately from observed imported data. An UNKNOWN oracle must not be displayed as a passable assertion, and `source_cited` is syntactic metadata until source branch, file content and runtime state independently verified.
5. On fork/copy, edited expected assertion, renamed/reordered steps or any canonical change: invalidate prior `base_spec_sha256` comparison; reject stale `step_id`/assertion references and force deliberate human rebinding. Do not silently retain a previous source-verified claim, evidence trust or approved permissions in a new draft.
6. Save exactly the optional metadata or reject with explicit guidance; do not silently strip it in Guided/Advanced toggle. The existing authenticated local draft store remains versioned/design_only/unassigned; no automatic migration of published specs or execution.

## 5. Deterministic revision / source compatibility

`scenario_contract_v2.compatibility_report(spec, observed_versions=None, *, observed_sources=None)` is a **pure structural comparison**, not a hash fetcher or trusted attestation. `base_spec_sha256` is SHA-256 of *v1 core* JSON (sorted keys, compact separators, `ensure_ascii=False`, excluding `contract_v2`). `observed_versions` must contain exact `dsp_commit/headless_commit/toolkit_commit` fields; optional `observed_sources` maps known source refs to exactly `{revision,sha256}`. A local operator/supervisor must separately retrieve original bytes at the intended pinned commit and actually compute SHA-256 before supplying fingerprints. Untrusted claims can match each other without establishing truth.

| Input | Result | Why |
|---|---|---|
| No `contract_v2` (MOG-09 / INV-OBS-01 legacy) | `UNKNOWN` | No historical spec/source pins; v1 remains valid |
| Pinned DSP commit but missing source content digest | `UNKNOWN` | Git line link is **not** byte-level integrity |
| Pinned source digest but no separate supplied rehash, or some missing refs | `UNKNOWN` | No independent file-content comparison |
| Observed source revision or SHA differs from cited source | `BLOCKED` | Source drift/byte mismatch |
| Any DSP/headless/toolkit version mismatch | `BLOCKED` | Incompatible engine versions |
| Edited/forked v1 spec with old `base_spec_sha256` | `BLOCKED` | Specification changed while claims were retained |
| All available pins and separately supplied fingerprints structurally match | `MATCHED_PINNED_ONLY`, independent verification **NOT_ESTABLISHED**, execution **false** | Comparison cannot verify byte retrieval, oracle branch, server state, permission, cleanup or evidence independence |

Additional safety: unknown source refs, extra source fields, non-hex hashes, bool numeric stand-ins, arbitrary capabilities (`sql_execute`/`packet_injection`/`shell`), unsupported permissions (`database_write`), `execution_gate=ready`, and unreviewed `source_cited` oracles fail validation. New v2 metadata never mutates imported evidence or changes a recorded PASS.

## 6. Synthetic acceptance and migration sequence

- **Existing baseline:** `test_fixtures/test_scenario_contract_v2.py` plus unchanged `test_feature_testing_specifications.py`, `test_feature_testing_spec_drafts.py`, `test_feature_testing_scenario_presentation.py`, `test_scenario_guided_editor.py`, `test_feature_testing_importer.py`, `test_feature_testing_normalized_evidence.py` under the focused offline CI.
- **New:** `test_fixtures/test_scenario_contract_v2_compatibility.py` verifies the staged citation remains synthetic, fixed v1 behavior, UNKNOWN orphan/no-hash, contradictory source hash, revision and spec fingerprint, unrecognized ref/permission/capability, and blocked execution; all outputs non-authorizing.
- **Fixture:** `test_fixtures/scenario_contract_v2_gardening_migration_synthetic.json` is an explicit **noncanonical**, non-running demonstration. Its path/source pointer comes from staged Agent E data, but no unknown digest or identity is fabricated.

**Integration order:** (1) B/D/E accept/adjust exact names and source semantics; (2) independently verify original DSP source bytes/hash and deployed revision; (3) review staged expected oracle, every identity and scope, readback and capability; (4) build a distinct canonical design-only v1 wrapper with **real allowlisted fields/expressions** and v2 metadata; (5) confirm editor JSON round-trip, step rebinding and reviewer rendering; (6) only after separate authorization design a future trusted evidence-fingerprint importer and runner gating. No bulk migration or runner widening in #1285.

**Could not verify remotely:** local DSP/client files, source SHA-256 of cited garden SQL, actual deployed DSP engine or XiHeadless build, source-branch conditions, independently complete server readbacks, real character/item/NPC identity crosswalk, or whether the editor visual widgets display metadata correctly. Synthetic GitHub Actions prove only deterministic software behavior.
