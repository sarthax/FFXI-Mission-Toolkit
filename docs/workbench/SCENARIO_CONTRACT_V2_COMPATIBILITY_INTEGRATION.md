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


## 7. Agent E's 73-case audit: source-drift and capacity reconciliation

Agent E's [draft #1292](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1292) now audits **73** design-only case records across the nine domain PRs (5 *conditional* observe-now, 2 needs-readback, 57 needs-mutation, 9 needs-deploy), all **NOT_RUN**. Agent E fetched **42 distinct pinned DSP commit/path targets** and checked **1,144 source ranges** for in-bounds coordinates. This is useful *syntactic source-location review only*: no original-file SHA-256 attestations, observed runtime deployments, conditional branch oracles, independent readbacks or accepted runner/permission binding result from that check. A Git **blob SHA is not the v2 SHA-256 content field**.

Two source revisions are demonstrably distinct despite valid historical citations:

- Gardening `src/map/utils/gardenutils.cpp` at pinned `330ea8f...` has `SavePot` at line 589 and a dual-safe loop at line 616. The separately reviewed DSP-main revision shifts those to 588 and 615 and has a different blob. **Do not rewrite pinned lines on import or assume a current deployed binary**; perform a new exact-revision/source-byte audit first. The double-safe numeric-slot collision remains a safety stop.
- Nyzul `scripts/commands/nyzuldebug.lua` pinned `2b71b442...` accepts only instance 51; audited DSP `main@86d4467...` accepts 51 **and 52** with an instance-specific leader table. Even if both source text digests are present, a current branch/engine mismatch must block any equivalence claim; diagnostic forced completion is not natural gameplay evidence.
- Chocobo Phase 0 `feature/chocobo-raising-core@55e1baa...` diverges from main; migrations/deployment are unverified and mount/trainer/whistle functionality remains unimplemented. All CHO cases retain primary needs-deploy status.

**Important distinction:** `compatibility_report` can compare a claimed source revision and SHA-256 against **separately supplied** `observed_sources`, but it does not itself obtain or authenticate source bytes or decide gameplay-branch correctness. `MATCHED_PINNED_ONLY` is not permission to run, a proof of client/DSP identity, or a measured test result.

**Capacity gate:** one v1 draft is limited to 32 KiB. The existing SQLite draft store serializes with Python's default `ensure_ascii=True`, so the v2 serializer checks **both compact UTF-8 and ASCII-escaped storage representation lengths**, including when deserializing JSON; Unicode source text cannot bypass the persisted size ceiling. A 73-case staging document must **never** be serialized as one canonical draft. The added synthetic regression exercises individually valid v1 steps whose aggregate serialized payload exceeds 32 KiB; serialization rejects it without a truncated/partially accepted specification.

**Coordination:** retain the same `contract_v2` field names until Agents B/D/E and #1259 approve changes. Agent B can preserve optional metadata in its existing canonical Guided/Advanced validation route; that is not a UI rendering of verified provenance. New authored scenarios remain design-only, with UNKNOWN oracles, unregistered observations/operations blocked, and immutable source-reference retention.


## 8. Reusable noncanonical projection contract for Agents B/D/E

The pure adapter `src/workbench/server_admin/feature_testing/scenario_contract_v2_adapters.py` is explicitly an **offline review aide**. It never constructs a canonical runnable test, evaluates a staged assertion, reads a local DSP tree, mutates SQLite or grants a capability.

| Entry point | Deterministic output | Required non-promotion rule |
|---|---|---|
| `project_domain_case(staging, case_id)` | One exact staged case, unique structural citations normalized to `sources[]` with deterministic `src_<SHA256-prefix>` tooling refs, separately retained **original citation objects and order**, `execution_lane`, step-to-source refs, original readback proposals | All content hashes **null**, no inferred approved identity or oracle; `execution_gate=blocked` on every step, capability `unassigned`, `operation_class=unknown`; `canonical_import_allowed=false` |
| `project_identity_diagnostic(diagnostic, kind=...)` | Copy of Agent D original diagnostic beside conservative typed uncertainty | `EXACT/INFERRED` at most candidate, `AMBIGUOUS` with null identity, unsupported/missing unresolved; `source_identity_verified=false` always |
| `project_expected_candidate(candidate)` | Original Agent D source-expected proposal, separate from `oracle_type=unknown`, `confidence=unknown`, `normative_expected=null` | No source-backed candidate automatically populates a v1 `assertions[].expected` or v2 approved oracle |

The `src_<SHA256-prefix>` identifiers are **purely tooling references** computed from a canonical JSON tuple of (repository, path, commit, first line, last line), *not* an actual DSP content digest, a Git blob hash, game ID, claim of client/server identity, or a trusted source fingerprint. Source order and exact originally staged `url`, `commit`, path and span remain under `source_refs_original`. Different pinned revisions are never silently coalesced. The 20-source namespace limit fails closed and requires a deliberate human-authored split, never silent truncation. Repeated source references may be deduplicated only in normalized metadata; originals are retained.

**Fixtures, source pointers and lanes:** `test_fixtures/scenario_contract_v2_staging_adapter_synthetic.json` copies only source/reference/readback/permission-related fields of the first **noncanonical** staged case in the Gardening (`GARD-01`, needs-mutation), RUN/GEO (`RG-01`, observe-now), and Salvage (`SAL-01`, needs-readback) branches. It is clearly marked a synthetic compatibility snapshot: this is *source-location metadata*, not observed gameplay, source-file content verification, or a new canonical specification. The matching `test_scenario_contract_v2_adapters.py` verifies exact citations, deterministic duplicate source handling, no automatic oracle/promotion, and denial of executable annotations.

**Practical integration for Agent B:** show original source/citation with line/commit and an explicit `SHA-256 NOT REHASHED` warning beside normalized source ref; separately show case lane, missing readbacks, UNKNOWN oracle and blocked step. Do not pass the whole staging projection to `validate_spec` or `save_draft`; editor authoring must construct a **new**, reviewed v1 schema-compliant draft, preserve untrusted rationale separately, and produce its own canonical v1 assertion ID and base-spec digest.

**Practical integration for Agent D:** pass only a bounded copy of the diagnostic to `project_identity_diagnostic`, retaining original alternatives/source-row hash in `source_diagnostic_original`. Agent D's `EXACT` never implies `contract_v2.parameters[].binding_state=independently_source_verified`. Its `expected_candidate` must remain in a separate review envelope until independently accepted normative source/branch conditions and readback exist; its index-projection SHA-256 never substitutes for a DSP source-file content digest.

**Practical integration for Agent E:** case `oracle_refs/oracle_sources/source_refs`, step `oracle_refs/source_refs`, `execution_lane/lane` and `readback.required` are accepted only as declared staging proposals. Missing or contradictory source pins, duplicate step IDs, malformed permission claims and unknown lanes fail closed. The projection intentionally leaves all canonical `oracles[]` and `parameters[]` empty because the staged fields have not yet passed v1 assertion, identity and source-fingerprint review.

**Actual SQLite limit:** `test_scenario_contract_v2_compatibility.py::test_actual_sqlite_storage_bytes_match_v2_contract_and_unicode_limit` uses the real existing `save_draft` against temporary SQLite; it compares persisted `content` BLOB bytes to Python's exact `json.dumps(..., sort_keys=True, separators=(",", ":"))` wire format, proves safe Unicode data persists unmodified and rejects a synthetic otherwise-valid UTF-8-small/ASCII-escaped-too-large draft without creating a second row. This is offline synthetic storage validation, **not** an authenticated HTTP/browser test.

**Independent approval status:** none of the new source-to-v2 projection contracts constitutes a submitted GitHub review. Final PR merge remains separately gated by Agent A's independent review and owner authorization. Current-main non-force reconciliation and fresh GitHub CI must be repeated on the eventual final head.


## 9. Field freeze, nine-domain compatibility and shared offline CI contract

**Proposed field freeze for Agent B's Phase 2 UI (pending independent approval on #1285):** The optional namespace is `contract_v2: {contract_version, sources, parameters, oracles, step_requirements, fingerprints}`, with outer `schema_version:1`. Key names and required object-member sets match `scenario_contract_v2.py`; do not introduce a second editor/evidence schema. **`independently_source_verified` is a syntactic spec-origin source-pin *claim* only**, never separately authenticated game identity or permission. For a truly reviewed identity, an independent source-byte rehash, DSP/client namespace/zone crosswalk, and authorized human/source attestation outside the spec are still required. `source_cited` is a claim of pinned normative source-file location; it is not an approved expected value.

**Compatibility by exact staged aliases:** `project_domain_case` is a deterministic, pure, **NONCANONICAL** validator/projection for the common R5 first-case specimens. The working reference examples are in `test_fixtures/scenario_contract_v2_staging_adapter_synthetic.json`; all are **NOT_RUN, design_only, runner=unassigned**, and preserve every staged citation in `source_refs_original`.

| Staged domain and case | Primary readiness lane | Citation keys present | Named readback key | Migration blocker |
|---|---|---|---|---|
| Gardening GARD-01 | needs-mutation | case `oracle_sources`, step `oracle_refs` | `readback` | Pot `char_inventory.extra`, both-safe complete inventory; numeric slot collision |
| Voidwalker VWK-01 | needs-mutation | case `oracle_sources`, step `source_refs` | `required_readback` | Spawn/pop localvars, claim, safe /heal interaction and source deployment |
| Assault/Nyzul ASLT-01 | needs-mutation | case `oracle_sources`, step `source_refs` | `required_readback` | Instance leader/objective status, debug bypass and pinned Nyzul source drift |
| Missions/Quests MQ-01 | needs-mutation | case `oracle_sources`, step `oracle_sources` | `required_readback` | Source branch/event-result, reward/quest/KI and independent authoritative state |
| Moghancement MOG-01 | needs-mutation | case `oracle_sources`, step `oracle_refs` | `readback` | Installed-furniture two-safe state, active KI/aura modifier; separate from MOG-09 |
| Voidwatch VOID-01 | observe-now *conditional* | case + step `source_refs`, nested `oracle.source_refs` | `readback` | Cruor/mob/Pyxis/claim readbacks, source branch review; no automatic action |
| Salvage SAL-01 | needs-readback | case + step `source_refs`, nested `oracle.source_refs` | `readback` | Live instance/pathos mask, stage/status/temp-item readbacks |
| RUN/GEO RG-01 | observe-now *conditional* | case + step `source_refs`, nested `oracle.source_refs` | `readback` | Quest/job/KI/char_vars scope, incomplete unlock oracle and deployed revision |
| Chocobo CHO-01 | needs-deploy | case + step `source_refs`, nested `oracle.source_refs` | `readback` | Migration/deployment and rollback proof; incomplete training/mount |

**Explicit alias rules:** `execution_lane` and `lane` must agree when both occur; `oracle_refs`, `oracle_sources`, `source_refs`, and `oracle.source_refs` are copied individually in original order and deduplicated **only** by the exact (repository, path, commit, line_start, line_end) source-coordinate tuple in the review projection. `readback` or `required_readback` remains the original unregistered/read-only proposal and is never automatically converted into a runnable v1 `observations[]` entry. The staged `commit` must equal the *declared envelope* DSP commit and match its complete pinned URL. All resulting `sources[].sha256` remain null; source file bytes are never fetched, and a Git blob SHA-1 is not a substitute for SHA-256. Malformed/missing location or commit, a contradictory URL, stale deployed claim, execution-allowed mutation, unexpected source digest, permission claim, or missing named readback **raises ValueError**.

**Reusable offline CI sequence for Agent E PR #1294** (do not import staged records as canonical specifications):

1. Use Agent E's separate `tools/validate_domain_drafts.py` against pinned JSON snapshots and manifest to validate **all 73 staged IDs and fixed lane counts**, canonical catalog exclusion, BDD and source structure. That validator is a separate non-executing workflow; no code from the staged PRs may be executed.
2. For additional v2 **review metadata compatibility**, call `project_domain_case(staging_document, case_id)` on a bounded staged document with explicit `schema_version=1`, `execution_enabled=false` and `source_revision.dsp_commit`/`deployed=UNKNOWN`. A raised `ValueError` fails the review compatibility check; this is *not* a canonical `validate_spec` call. For large cases above 20 unique citation locations, retain the unmodified staging record and flag `HUMAN_SPLIT_REQUIRED`, never truncate refs to fit the canonical draft schema.
3. Assert returned `canonical_import_allowed=false`, `execution_enabled=false`, `independent_verification=NOT_ESTABLISHED`, `oracles=[]`, `parameters=[]`, and all `step_requirements[].execution_gate=blocked`. Copy the original cited refs/readback/lane to the reviewer and preserve every UNKNOWN. **MOG-09** remains the sole existing verified v1 runner, unchanged; the staged MOG-01 example does not overwrite it.
4. Run focused contract v2 pytest plus existing v1 catalog/draft/viewer/Guided/importer regression on the exact PR head, then Workbench Regression and Src Layout Regression on the same commit. A green CI result certifies *software structure and denial conditions only*.

| Validation tier | Can be checked by GitHub CI? | What it establishes |
|---|---|---|
| **Structural** | Yes | Field types/shape, stable IDs/aliases, 73-case manifest, blocked action flags, canonical exclusion, 32KiB persisted draft shape |
| **Source-citation consistency** | Yes | Repository/path/line span/40-hex commit/URL agree with *declared* pin; optionally lines exist in fetched static source; not correctness of expected behavior |
| **Revision/fingerprint comparison** | Yes, for supplied test vectors | No digest supplied => `UNKNOWN`; mismatched supplied spec/engine/source SHA => `BLOCKED`; equality => `MATCHED_PINNED_ONLY` (syntactic only), always execution denied |
| **Independent source/authenticity** | **No, not through this metadata-only GitHub CI** | Requires independent original-source-byte SHA-256 computation, operator-known DSP deployment, local client/DAT identity crosswalk, server readback freshness/completeness, trusted capture originals and source-branch/oracle human review |

No CI result can promote `observe-now` to dispatch permission or stage `NOT_RUN` to gameplay PASS. No domain staging file, Scenario Developer UI, Agent D capture code, server or live runner was changed by this compatibility layer.


## 10. CI failure #39617090965 — repeated source citation validation (fixed on PR #1285)

**Exact failure:** `test_staged_domain_handoff_rejects_missing_fields_mismatch_and_permission_claims[<lambda>8]` changed a step's source `url` while leaving its repository/path/commit/line span unchanged. That source tuple already appeared earlier in the parent case. The noncanonical adapter reused the normalized `src_<hash>` source ID and **returned from the cache before checking that particular occurrence's URL**. The negative test correctly demanded `ValueError`, and remained unchanged.

**Corrected invariant:** Validate **every occurrence** of a staged citation against the envelope's DSP commit, complete pinned repository/path/line URL and canonical source structure *before* looking up or reusing a deduplicated source ID. Cache reuse applies only to the already-validated coordinate tuple. All original citations, including repeated case, oracle and step copies, remain preserved in `source_refs_original`. There is no trusted source-file SHA-256 inferred from the deterministic source-reference ID.

**Focused regressions:** `test_every_duplicate_source_citation_validated_before_ref_reuse` rejects URL tampering at a previously seen step, an appended case duplicate, a nested-oracle occurrence and a first case ref. `test_consistent_duplicate_citations_reuse_ref_without_source_promotion` confirms legitimate repeats still deduplicate in normalized metadata while original citations survive. `test_optional_v2_staging_hints_cannot_gain_runtime_authority` covers `capability=unassigned`, `operation_class=unknown`, `execution_gate=ready/approved`, unsupported `sql_execute` permission and unapproved GM mutations; an accepted `blocked` hint has no execution authority.

**Review boundary:** These are software rejection and normalization tests, not independent gameplay, capture or source-byte authenticity checks. The old CI failure remains part of the suite and is not xfailed, deleted or weakened. Successful validation cannot promote v1 runner states, approve proposed oracles, authenticate Agent D's scoped `EXACT`, supply DSP source SHA-256, or dispatch an action. Always verify the three GitHub workflows against the corrected PR's *actual* current head before integration.
