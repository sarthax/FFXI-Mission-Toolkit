# Current Workbench Roadmap

## 2026-10-21 — R6 integrated baseline / R7 active (authoritative scenario status)

**GitHub release baseline:** `main@972ff6fa4337cb5d29a3c8c3eb68c73245f24bb9`. The optional Contract v2 (#1285), unified Scenario Developer (#1283), Evidence Readiness (#1287), sole authoritative 73-case readiness matrix (#1292), central offline validator (#1294) and distinct capability backlog (#1293) have **merged**. All nine domain source-backed **design-only** PRs #1277, #1279–#1282, #1286 and #1289–#1291 are integrated: Gardening 9, Voidwalker 7, Assault/Nyzul 6, Missions/Quests 5, Moghancement 14, Voidwatch 8, Salvage 7, RUN/GEO 8, Chocobo Raising 9.

- **73 distinct staged cases, not 73 passed tests:** 5 *conditional observe-now*, 2 needs-readback, 57 needs-mutation, 9 needs-deploy. Observe-now identifiers: `MOG-09`, `RG-01`, `RG-06`, `VOID-01`, `VOID-02`. Every staged scenario is `design_only`, `runner=unassigned`, `NOT_RUN`; none was promoted to the executable `data/testing/test_specifications.json` catalog. Historical v1 MOG-09 runner is separate and is not evidence that staged scenarios passed.
- **Source confidence:** file:line and pinned revision are candidate citations, *not* independently rehashed DSP bytes or proof of which revision/config/schema is deployed. A source-row match is not an authenticated client entity or normative oracle; missing original capture/readbacks remain UNKNOWN or BLOCKED. Operator acceptance, independent client/server observations, source/deployment attestation, mutation approvals, Chocobo migration and gameplay results are **NOT VERIFIED**.
- **Post-merge CI established:** merged [#1305](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1305) implements `integrated-main` validation of nine checked-in drafts, the sole matrix, 73 unique IDs/readiness lanes and the executable-catalog non-promotion guard, with byte-identical historical merged PR blobs and no deleted-branch fallback. The **actual `push`-to-main** [run #39684273477](https://github.com/sarthax/FFXI-Mission-Toolkit/actions/runs/39684273477) passed at `986f781ed1fe61000b2ca62552018061441b7522` (41 synthetic tests); `workflow_dispatch` and explicit `staged-pr` remain configured for future independently reviewed staging snapshots, not represented as separately run post-merge here. R7 roadmap [#1306](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1306), canonical associations [#1309](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1309), and noncanonical evidence projection [#1308](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1308) are also merged through `main@db8b06abab7cd5f7b0908109184453b30ae3b112`. See the [merged-main R7 release ledger](R7_RELEASE_BASELINE_2026-10-21.md) and [CI and acceptance operator guide](R7_CI_AND_ACCEPTANCE_GUIDE.md). None of this establishes independent DSP/client source or gameplay acceptance.
- **R7 active division:** Agent B owns editor Phase 2 (#1302); Agent C canonical Contract v2 interoperability and source-to-step association (#1259/#1302); Agent D Evidence Reviewer readiness-to-authoring projection (#1262/#1198); Agent E bounded read-only observation contracts (#1295–#1300). Agent A owns GitHub CI, release and issue/roadmap coordination under #1197. **C defines canonical shape → D provides read-only evidence projection → B consumes both.** E does not grant readbacks until capability tests/permissions accepted. No duplicated schema, editor, reviewer, packet decoder, or headless controls.
- **Tracking closeout:** R5 domain authoring issues #1249–#1254 are *design deliverables*, not runtime acceptance. End-to-end #1197, canonical schema enhancement #1259, evidence provenance #1198, importer #1202 and observation #1295–#1300 remain open where full acceptance has not been established. Branches and PR state should always be re-checked live before closure.

**Supersedes the 2026-10-21 “41 planned cases / four domains empty” scenario expansion paragraph below** for the Scenario Developer workstream; retain it solely as dated planning history, not current status. Older roadmap content may describe still-active unrelated capabilities correctly.


Status: ACTIVE REWORK  
Last fully reconciled against merged PR and branch history: **2026-10-06** (full-repository sweep); targeted module audit **2026-10-10**; recent merged-commit/tree documentation reconciliation **2026-10-17** (not a new full runtime audit)  
Authoritative repository: `sarthax/FFXI-Mission-Toolkit`  
Authoritative branch: `main`

This is the authoritative current planning and capability inventory for the Mission Toolkit / Workbench. It is organized by durable capability, not by the chronological order of individual pull requests.

`ROADMAP.md` remains the historical implementation ledger. `AUDIT_STATUS.md` remains a historical/implementation audit log. When older status text conflicts with this file, use this file plus merged `main` history.

## 2026-10-19 — AI test supervisor root-cause investigation backlog (planned)

**Status:** planned, not implemented. The current authenticated /api/supervisor gateway deliberately exposes read-only monitoring and has `execution_enabled: false`. Local Open WebUI with `ornith-1.5:9b` has demonstrated grounded tool use. Keep this research backlog separate from any future operator-authorized test execution.

- [ ] **Run evidence drill-down:** Add `supervisor_run_evidence` with bounded, run-ID-scoped assertions, expected/observed values, client/server snapshots, timestamps, revisions, DLL provenance, and evidence references. Support both `evidence.assertions` and legacy `evidence.evaluation`; current `failed-assertions` only forwards `evaluation` and loses the local observation-runner assertion arrays.
- [ ] **Approved source search:** Add `supervisor_search_source` against allowlisted, pinned DSP, XiHeadless, and Toolkit source checkouts or existing indexed evidence. Return concise source paths, line numbers, revision and context; prevent traversal, secrets exposure, arbitrary filesystem search or execution.
- [ ] **Behavior/Feature Trace research:** Add `supervisor_trace_behavior` as a narrow read-only adapter to existing Feature Trace/Behavior Inspector evidence ranking, scoped to the assertion and relevant implementations rather than an unfiltered graph dump. Explicitly distinguish verified evidence from candidates.
- [ ] **Fixed-query diagnostic catalog:** Add `supervisor_query_diagnostics` with allowlisted characters, per-query parameter schemas, SELECT-only credentials and bounded results. Validate the DSP schema first (including `chars.keyitems` raw `keyitems_t` layout, blob size/endianness/seen bits, and safe read-only decoding); no free-form model SQL. Audit inventory location numbering and truncation (Safe 2 vs wardrobes) before reporting comparisons as complete.
- [ ] **Investigation dossier:** Add `supervisor_investigation_dossier` structured with failing assertions, candidate mechanisms, supporting/refuting citations, source revision, confidence/uncertainty, proposed code/test fix, and a discriminating validation plan. Do not manufacture root-cause certainty when source, packets, or state are missing.
- [ ] **GUI integration and tests:** Add an investigation detail view linked from test-run assertions; exercise empty/malformed evidence, access denial, bounded responses, redaction, SQL nonmutation, version mismatch and LLM tool-use grounding. Test locally with deliberately mismatched synthetic assertions before relying on gameplay failure cases.

**Acceptance gate:** the supervisor can explain one real failed imported run with linked original assertions, bounded log evidence, cited source locations and a falsifiable fix recommendation. Execution, raw MCP control, shell commands, direct code edits and arbitrary DB access remain unavailable to the model.

**Local evidence milestone:** the XiHeadless agent reported two additional clean-build MOG-09 runs, 6/6 assertions each, DLL hash `ef3927a379f5b96f72329418fb12282da7c680a03dbf843fac213219b683a86b`, and imported run IDs `obs-20261019T081629Z` / `obs-20261019T082001Z`; these are agent-reported local observations, not independently replicated by CI. PR #1112 (OpenAPI repair and pipeline report) is merged. Dedicated inventory catalog test `INV-OBS-01` and its run inspector are merged; actual INV-OBS-01 execution and key-item persistence decoding remain unverified. XiHeadless observation-runner PR #3 requires final review.

**First GUI-launched MOG-09 run (2026-10-21):** run `obs-20261021T040036Z` on `xitest05` / charid 21833 was started from the Feature Testing Builder tab (Setup tab enabled, outside-repo data dir) and finished **PASS, 6/6 assertions** with a real client-vs-`char_inventory` comparison (bag and Mog Safe) against `dspdb_fresh` through the read-only supervisor login. Report imported automatically; artifacts under `%LOCALAPPDATA%\MissionToolkit	est_executionrtifacts\`. Fixes that made it possible: xiheadless-dsp #186 (unconfigured supervisor DB is BLOCKED, not a false FAIL), Toolkit #1241-#1246 (mysql-connector fallback, Setup panel, Builder UX, account/char prefill, data dir outside repo). Known gaps unchanged: installed-furniture layout is not readable via MCP, and client key items are not compared with persisted key items (no supervisor key-item endpoint). Earlier imported run `obs-20261021T025326Z` is a stale false FAIL from the unconfigured-DB bug and should be disregarded.

## Scenario expansion (opened 2026-10-21, epic #1197)

Only MOG-09 and INV-OBS-01 are runnable; 41 planned cases across gardening, voidwalker, assault/nyzul, missions/quests and moghancement are blocked, and voidwatch, salvage, run/geo and chocobo have no cases. Plan: (1) git agents draft oracle-backed specs per domain (#1249-#1254, brief `SCENARIO_EXPANSION_AGENT_BRIEF.md`); (2) supervisor key item/char_vars readback (#1256, PR #1248); (3) spec-driven observation runner (#1255, local); (4) mutating cases only with per-case owner approval.


## 2026-10-18 capability-inventory gap correction (targeted)

**Important:** The October 17–18 documentation/navigation cleanup was not a comprehensive feature census. This roadmap, the in-app `gui/templates/roadmap.html`, and historical ledgers are manually maintained and can diverge. Do not interpret the number of recent roadmap entries as the number of shipped features.

Recent **merged-main** capabilities missing or insufficiently represented in the in-app roadmap at this checkpoint:

- [x] **Retail Version Explorer** — historical PlayOnline manifest browsing, planning, downloaded artifact catalog and version comparison; merged PR #1073. This is a research/asset workflow, not proof of full retail patch reconstruction.
- [x] **Selective PlayOnline retail downloader** — manifest inspection and bounded file retrieval, staging/non-overwrite safeguards, integrity and provenance validation, and cross-platform CI work; merged PRs #1069, #1071, #1072. Successful live download validation is recorded separately from universal compatibility.
- [x] **Read-only POL1 unpack/code evidence** — bounded decoded-text inspection and cross-build evidence tools; merged PR #1068. Decoding evidence is not executable validation.
- [x] **Client DAT command evidence** — exact command lookup and cross-build wardrobe research; merged PR #1067.
- [x] **Kuluu/headless client comparison research** — audit documentation merged PR #1070, not a shipped client integration.
- [x] **Assault shared-dependency impact ranking** — merged PR #1074, a prioritization aid rather than port/acceptance completion.
- [~] **Wardrobe 5–8 compatibility research** — server/client gap research on main (#1075); full modern packet implementation and runtime acceptance are not complete.
- [~] **Protocol Compatibility evidence model and Binary Inspector view** — draft PR #1085; **not merged** at this checkpoint. Do not present as a shipped feature.

**Remaining gap:** This list is a verified sample of recent omissions, not an exhaustive reconciliation of every route, merged PR, help page, and domain. Follow-up should inventory merged changes by capability, associate each with a visible module/route and documentation owner, and flag missing GUI roadmap entries automatically.

## 2026-10-18 documentation and navigation housekeeping (targeted reconciliation)

**Scope:** GitHub main merges #1047–#1059 (including #1061 merged into #1059), operator guides, Help/roadmap and navigation regressions. This is a targeted source and reported local acceptance update, **not** another full-repository runtime audit. The October 6 full-sweep date remains unchanged.

- [x] **Help and operator documentation:** Guides for Synth, Assault, RUN/GEO, Voidwalker, Live Client/3D and Feature Trace merged (#1047–#1050). GM Command Center guide corrected for implemented opt-in command sending (#1051).
- [x] **Documentation safeguards:** CI triggers on documentation changes and checks guide references, Help links and source-level sidebar routes (#1052–#1058).
- [x] **Sidebar route audit:** All 22 formerly unexplained sidebar paths have source-level route explanations (parameterized domains/viewer, Character Editor, replay, calculators). Historical route-map omissions did not establish 404s. See [sidebar audit](SIDEBAR_ROUTE_AUDIT_2026-10-18.md).
- [x] **Mounted route and representative HTTP checks:** #1059 incorporated the local agent fixes in #1061: FastAPI included-router matching and template globals for Synth and nine Auction House modules. Local Windows agent reported mounted-route PASS with xi_tinkerer 0.141.1 and HTTP 200 for Help, Roadmap, Abyssea, Character Editor, Live Client replay/bridge, WS calculator, Synth and Auction House Help. Zone 0 3D redirected to zone 44 with the configured database; a bare worktree without zones data failed on missing DB. ASGI calls did not run lifespan startup.
- [~] **CI qualification:** Linux lacks the optional compiled xi_tinkerer wheel, so the mounted-app test reports NOT RUN there. Seven CI checks passed on #1059; that is not a separate Linux mounted-route PASS.
- [~] **Outstanding acceptance and upkeep:** Continue updating guides/help/roadmap on functional PRs; broader dynamic link/browser testing, dedicated walkthroughs for newer domains/calculators, and live DSP/Windows end-to-end acceptance are still open.

**Status precedence:** October 10/17 entries below are dated baselines. This update supersedes their pending documentation/navigation claims only, not the unfinished product capabilities.

## 2026-10-17 recent merged capability reconciliation

See [scope, evidence, and follow-up matrix](ROADMAP_HELP_SYNC_AUDIT_2026-10-17.md). The statuses below describe merged code, **not automatic proof of live DSP/Windows acceptance**.

- [x] **GM Command Center:** command categories, player target, command lookups, favorites/history/presets, parsed Lua parameter hints, opt-in live send and privileged confirmation; operator guide: [SERVER_GM_COMMAND_CENTER.md](SERVER_GM_COMMAND_CENTER.md).
- [x] **Calculators:** gear-aware melee and related weapon skill, magic, healing and pet calculation work, including RUN/GEO job-grade updates; source parity and representative combat/casting tests remain.
- [x] **RUN / GEO toolkit domain:** tracking page and gaps inventory merged. These are *already added to the user's server* per operator; gap tracking must not be confused with missing server job support.
- [x] **Voidwalker domain UI:** zone/spawn and NM filtering, tier/path progression graphs and Abyssea branch presentation merged; full data/runtime behavior validation remains open.
- [~] **Voidwalker coverage follow-up (2026-10-18, PR #1063):** read-only six-area validation counts and prioritized NM test queue proposed; this summarizes recorded per-NM results, not live DPS/DSP acceptance or complete source coverage. The outstanding backlog includes position checks, skill/script parity, colored abyssite transitions, other zones and Abyssea scope.
- [x] **3D Zone Viewer/Live Client improvements:** multiple zone geometry DATs, instance selector and texture transparency correction; live-client auto-zone/player centering, stable live picker, headless receiver freshness and combat/dialog activity panel merged. Repeatable client acceptance for zone variants, reconnect, multiple entities, and DSP server confirmation remains open.
- [~] **Assault tracking:** imported Topaz issues and fix-log comparisons facilitate development; per-instance DSP porting and validation are not thereby complete.
- [~] **Feature Trace / Wiki:** existing evidence and research tooling remains under quality and runtime-acceptance review. Do not mark all relevance, scrape, batch-import or source-line correlation goals complete on the basis of UI availability.
- [~] **Documentation follow-ups:** initial operator walkthroughs and navigation checks merged; targeted newer-domain/calculator guides, broader dynamic-link/browser coverage, and integrated DSP/Windows acceptance remain. See October 18 update.

## 2026-10-11 Live Client movement status correction

- [x] **Native Ashita movement architecture and 3D controls merged:** SDK-built DLL with player XYZ readback, armed movement/warp/speed/STOP, file-based control channel, live client API, 3D viewer target picking, compass nudges, coordinates, bookmarks and zone checks. The operator reports successful integrated movement. See [Live Client delivery/acceptance ledger](LIVE_CLIENT_DELIVERY_ROADMAP.md#current-movement-capability-audit--2026-10-11-supersedes-older-historical-gates-below).
- [~] **Independent acceptance remains:** client-local commands return `server_confirmed=false`; retain separate DSP/Topaz GM `!logpos` observations, zone and relog checks, STOP/disarm stress, dual-client isolation, SDK version compatibility and optional auto-arm risk assessment.
- [~] **Broader original goal:** reusable capture correlation, full unified native capture, verified 2D destination movement/autonomous path following, and multi-zone spatial calibration are separate incomplete milestones; do not equate successful 3D warp with route navigation.
- **Status note:** older 2026-10-10 paragraphs below are dated baselines, not statements that native movement is still absent.

## 2026-10-10 targeted module documentation reconciliation

**Scope and evidence:** Key Items code and merged PRs #868, #875, #880, #881, #883, #889, #891, #896, #899, #900, #902, #905, #910 and #911; existing Auction House status/help, Live Client bridge guide and Synth UI/API. This targeted update **does not supersede** the October 6 repository-wide baseline for unreviewed modules.

- [x] **Key Items (DSP-first read-only research):** active DSP bare source constants, normalized-name/ID readiness, collision protection, health diagnostics, per-item decision explanations, static Lua require/grant/remove references, persistent incremental SQLite cache, per-file source/operation/line evidence, Feature Trace search handoff and copyable citation bundles. See `docs/workbench/KEY_ITEMS_GUIDE.md`.
- [~] **Key Items pending:** local DSP source/runtime acceptance; evidence-backed alias reconciliation; broader verified dynamic/helper call coverage; exact Feature Trace source-line/entity linkage; indexing performance/freshness instrumentation. CI validates implementation contracts, **not** a user's live DSP install.
- [x] **Auction House DSP core:** existing authoritative status and integrated help already document browse/transactions/economy/rewards, player actions and scoped Test-write safety. Preserve maintenance designation and explicit Test-profile/write gates; no new write capability is asserted here. See `docs/workbench/AUCTION_HOUSE_CAPABILITY_STATUS.md` and `/auction-house/help`.
- [~] **Live Client:** documented Ashita-side bridge, managed local receiver, replay/waypoints and 3D spatial alignment diagnostics on `main`. Live Windows read/write compatibility and map coordinate calibration still require environment-specific testing. See `docs/workbench/LIVE_CLIENT_BRIDGE.md`; synthetic CI does not prove in-game operation.
- [~] **Synth & Crafting:** `/synth` recipe browse/audit/preview workflows and legacy schema adapters are present; distinguish source-based recipe/ingredient auditing from verified in-game crafting and guard Test-only mutation paths. Usage is summarized in `/auction-house/help` and the module UI; dedicated operator validation remains.
- [~] **Cross-module documentation discipline (ongoing):** on every functional PR update this file, the relevant module guide, in-tool help, and GUI roadmap summary. Reconcile the historical `ROADMAP.md` only as a dated ledger, not by rewriting old entries.

## Status rules

- `[x]` = merged to `main` and covered by regression/CI or equivalent validation.
- `[~]` = substantial foundation exists, but the capability is intentionally incomplete or evidence-limited.
- `[ ]` = planned / not yet implemented.
- Closed PRs that were superseded, transplanted, or replaced are not roadmap capabilities.
- As of this reconciliation, Behavior Inspector, Feature Trace provider/closure work, native modern-LSB Nyzul support, Research contradiction/evidence deepening, protocol PR #545, and final Phase D source-layout ownership cleanup are merged into `main`; current `main` is the product baseline for these capabilities.

---

# 1. Core Workbench architecture

- [x] Canonical evidence/provenance model for source, feature, entity, implementation, dependency, capture evidence, findings, migrations, validation, packages, and research output.
- [x] Feature and Package remain distinct concepts.
- [x] `src/workbench/...` is the canonical implementation layout; mature editors, capture tooling, validation code, runtime bridges, application host, settings store, and related modules are package-owned while thin compatibility imports/launchers preserve older entry points.
- [x] Source Layout Regression protects packaged imports and editable-install behavior.
- [x] Shared shell navigation has top-level category menus plus persistent Sections navigation.
- [x] Global runtime context exposes the active named server environment without leaking credentials.

# 2. Server environments and runtime context

Merged October 3 work changed the Workbench from a family-only/single-root model to first-class named environments.

- [x] Named profiles: Live, Test, Dev, Backup, Other.
- [x] Profiles support LandSandBoat, Topaz, DSP, and compatible custom forks.
- [x] Settings is the canonical environment-management surface.
- [x] Profiles can be created, edited, enabled/disabled, activated, tested, and deleted.
- [x] Native server configuration remains authoritative for DB connection discovery.
- [x] Active environment is visible in the shared shell.
- [x] Generic/admin tooling resolves the active environment through the canonical runtime bridge.
- [x] Zone Editor, Item Editor, model catalog, Entity Profile, Character Editor, and generic Zone Plot paths consume named environments where appropriate.
- [x] Multiple same-family environments are preserved independently rather than collapsed by lineage.
- [x] Legacy Topaz/DSP paths remain only as bootstrap/fallback/reference compatibility roots.
- [x] LIVE-target editing requires explicit confirmation where the UI exposes mutation.
- [x] DSP/Topaz config inputs may be server root, `conf`, or native `map*.conf`; LSB settings paths are normalized to the canonical root.
- [~] Some older lineage-specific utilities still intentionally use explicit DSP/Topaz reference roots rather than the active admin environment.

# 3. Character Editor

The Character Editor is now a mature guarded administration surface across DSP / Topaz / LandSandBoat rather than an experimental viewer.

## Read / presentation

- [x] Schema-aware character overview across major row-backed and packed-state categories.
- [x] Dense responsive presentation with sticky header/tabs and a sticky changed-fields apply bar.
- [x] Friendly field labels, units, dropdowns for known enums, filtering, hide-zero, changed-only views, pagination, and tab counts.
- [x] Raw physical storage is demoted behind Advanced/collapsed presentation where semantic editors exist.
- [x] Inventory is grouped by container and optimized for current-state browsing.
- [x] Key Items, spells, abilities, weapon skills, titles, and visited zones default to owned/learned/set state with Browse All available.
- [x] Checkout-local mission/key-item catalogs for DSP/Topaz/LSB.
- [x] Legacy DSP mission/assault names resolve from `missions.lua` banner structure; mission value `65535` is shown as None.
- [x] Semantic merit catalogs:
  - LSB structured merit metadata where available;
  - DSP legacy merit catalog derived from checkout-local `sql/merits.sql` plus merit C++/header definitions;
  - lineage-local category/name/rank/cost/job metadata rather than substituting a modern server's definitions.
- [x] MariaDB date/time values are serialized safely at the HTTP boundary.

## Guarded mutation families

- [x] Inventory add, move, quantity, and remove across directly verifiable persistent containers.
- [x] Scalar character/job/stat/skill/point fields on explicit schema allowlists.
- [x] Learned spell learn/unlearn.
- [x] Blacklist add/remove.
- [x] Packed missions and key items.
- [x] Packed quests, Assault, Campaign, Eminence, abilities, weapon skills, titles, visited zones, and Blue Magic state where codec/schema evidence supports them.
- [x] LSB-only persistent administrative fields through explicit allowlists.
- [x] Every supported write path uses offline verification, preview/approval, stale-state recheck/fingerprint, explicit transaction handling, and audit recording.
- [x] Audit Undo covers supported row-backed, scalar, packed, spell, blacklist, inventory, and LSB-admin operations.
- [x] Character Editor DB connections default to autocommit for reads so preview/read operations do not leave an implicit transaction that breaks later explicit writes.

## Progression research integration

- [x] Mission/quest **State Surface** endpoint scans active-server Lua and exposes source-evidenced references to charvars, key items, items, events, mission/quest state, titles, gil/fame, and related hooks/source lines.
- [x] Character state is enriched against those references and literal guards are evaluated where possible.
- [x] UI exposes Trace Current/per-entry trace for mission and quest rows.
- [x] State Surface can hand off to existing Key Item, Variables, Inventory, and Unlock editors.
- [x] Mission trace regression in the State Surface pipeline was fixed in the October 3 usability pass.
- [x] Progression transition bundles group trigger/event, persisted preconditions, runtime-only requirements, state changes, rewards, removals/consumption, completion, next activation/transport, timers, source evidence, and `why blocked` reasoning.
- [x] Transition bundles expose conservative read-only projected results with known before-values only where character evidence resolves them; no mutation is performed or implied.
- [x] Concise progression assessment classifies the selected state as Ready, Waiting on runtime input, Blocked by persisted state, Inconsistent, Completed, No modeled next action, or Unavailable where the evidence supports it.
- [x] Persisted blockers can hand off to their guarded Character Editor surfaces while runtime-only requirements remain diagnostic.
- [x] The progression bundle/result/assessment contract is regression-covered on modern LSB and legacy DSP/Topaz flows, including trade-gated runtime requirements and completed prerequisite chains.
- [~] Continue expanding deterministic progression reasoning only where source/runtime evidence proves additional helper-generated or cross-feature behavior.

## Intentionally read-only

- [~] Status effects and effect timers.
- [~] Recast timers.
- [~] Pet IDs/runtime pet BLOB state.
- [~] Runtime disconnect/session state.
- [~] Unknown lineage-specific fields without a verified persistence contract.
- [x] Progression transition/result previews and assessments are explicitly diagnostic/read-only and do not add an automatic reset/advance write path.

These are deliberate safety boundaries, not generic missing editors.

**2026-10-20 bounded Feature Trace investigation trail:** A first read-only navigation slice now carries up to eight prior selected roots in the URL and renders clickable backtrack breadcrumbs with the current Question/depth/direction. It is selection history only, not evidence-path verification, automatic browser draft recovery, backend persistence, cross-tool pins, or saved investigations. The existing saved/resumable roadmap items below remain open; this is a navigation precursor that must be tested on real data separately from the #1228 relevance audit.

**2026-10-20 first named-save milestone:** Feature Trace now has an explicit browser-local Save/Resume/Delete surface layered on its bounded URL investigation trail, with up to 20 named views (optional notes), validated same-origin URLs, read-only current-graph re-tracing, corrupted/quota-storage failure handling and no evidence-body persistence. **Named saves are explicit and browser-local**; an independent opt-in, one-slot, best-effort local recovery draft is available. Backend persistence and source-version rehydration are not yet implemented. This is the first milestone toward the broader unchecked cross-tool roadmap below, tracked at [#1235](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1235). Independent real source/ranking acceptance remains [#1228](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1228).

- [x] Feature Trace: explicit browser-local named navigation bookmarks (not server persistence), 20-record bound, Resume/Delete.
- [x] Add separately opted-in, one-slot browser-local draft recovery (navigation URL only; best-effort page exit; manual deletion; no revision pinning; synthetic CI only).\n- [~] Design/review access permissions, schema, provenance digest and revision-aware backend-persisted named investigations before adding server writes. **RFC v0 proposed, not approved**: `FEATURE_TRACE_SHARED_INVESTIGATIONS_RFC.md`; host principal/ACL, storage policy and index-version token decisions remain blocking.
- [ ] Implement revision-aware stale identity/edge checks, saved pins and forks; then propagate a shared saved-investigation model across Behavior Trace and Character progression.

## Saved / resumable trace investigations — planned 2026-10-11

- [ ] Add a shared saved-investigation/session model for **Feature Trace, Behavior Trace, and Character Mission/Quest Progression**.
- [ ] Persist the investigation root, active node, pinned breadcrumb/path, saved alternate branches, hop depth, filters/overlays, expanded/collapsed state, and optional user name/notes.
- [x] Provide opt-in best-effort browser-local last-view draft recovery (single navigation slot, not source evidence).\n- [ ] Provide explicitly permissioned backend-persisted named investigations that survive browser, Workbench, and machine restarts.
- [ ] Add **Resume Investigation** and saved-investigation browsing so a user can return to the exact research path without rebuilding the graph walk.
- [ ] Rehydrate saved IDs against current graph/evidence data rather than duplicating evidence; visibly flag nodes/edges that changed or disappeared since the session was saved.
- [ ] Preserve multiple investigations per feature/mission and support branching from a saved fork without overwriting the original trail.
- [ ] Keep the saved path suitable for later reproducible research/provenance export.
- [ ] Build this on the bounded pin/history navigation from PR #990 before propagating the shared navigation model across all three trace surfaces.

# 4. Feature Trace / Implementation Path

**2026-10-20 guided question navigation:** Existing Feature Trace modes are now directly selectable on the search form rather than discoverable only through a typed `@mode` prefix. Explicit mode/depth/direction persist on trace-internal links; a return-to-legacy control keeps the unfiltered view accessible. The legacy default and original provider/identity evidence contracts are unchanged. CI tests the production handler and Jinja behavior, including prefix compatibility and invalid-mode fallback. This is *not* verified relevance, ranking acceptance, gameplay evidence or the requested first-screen 1–2-hop projection. Issue #1228 remains blocked on real indexed cases.



**2026-10-20 Feature Trace presentation correctness:** Read-only provider-generated candidates in focused traces previously lacked the `from_node`, `to_node` and `depth` fields expected by the actual Relationships template. The display adapter now supplies the recorded endpoints/depth, separates provider provenance from persisted canonical evidence, and avoids rendering an empty edge table for runtime summary groups. CI covers actual Jinja HTML escaping, source endpoints and distinctions. This fixes evidence readability but **does not** select which graph edges should be shown first; the real-data relevance audit remains pending on #1228.

**P0 audit integrity follow-up:** Before scoring a reviewed case, the campaign evaluator now cross-checks the exported JSON's exact case/root/mode identity and generated/native audit edge fingerprints. Unversioned, swapped or modified exports must fail closed. This is input integrity, not relevance ranking or runtime acceptance. No accepted three-case baseline is recorded yet.

**2026-10-20 P0 audit export unblocker:** Stage A real-data baseline is still NOT RUN as of this source review. A local-only read-only exact-root exporter (`scripts/export_feature_trace_relevance.py`) now produces bounded backend edge JSON for the existing manual scorer without opening the Workbench host, starting the client, or writing indexed DBs. Browser first-visible edges, critical path ground truth, and locator correctness remain separate independent operator annotations. Linked tracker: [#1228](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1228). The relevance-first projection remains gated by the measured and reviewed three-case baseline.

**2026-10-20 P0 relevance milestone:** [issue #1228](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1228) separates the existing provider/identity foundation from unproven first-screen usefulness. CI can score reviewed annotations and validate the three-case campaign schema, but **no real-data campaign scorecard has been accepted**. Local Claude/operator must measure Absolute Virtue Implementation, WotG Cait Sith Mission, and one exact ordinary NPC; record the resolved identity, source revisions, verified required paths, first-view precision, source-locator coverage, and click-through burden. Only after this baseline may a remote-safe, opt-in relevance-first 1–2-hop projection be implemented and retested. Saved investigations follow that UI acceptance. See `FEATURE_TRACE_RELEVANCE_AUDIT_2026-10-11.md` and `FEATURE_TRACE_AUDIT_RUNBOOK.md`.

Feature Trace is now a mature cross-source implementation/evidence navigator at a deliberate real-data testing boundary. Provider-native relationships are read-only navigation evidence and remain distinct from canonical graph truth. The combined workflow and evidence boundary are documented in `docs/workbench/BEHAVIOR_FEATURE_TRACE_GUIDE.md`; the closure matrix and current stopping point are documented in `docs/workbench/FEATURE_TRACE_CLOSEOUT_2026-10-04.md`.

- [x] Cross-source providers for SQL, LSB, Topaz, DSP, Client, Capture, Research, Validation, Package, and reference-wiki records.
- [x] Source-native wiring and bounded provider drill-down.
- [x] Entity identity bridging across server IDs, client ENTITY snapshots, captures, and client-build drift.
- [x] Fail-closed ambiguity for numeric collisions and conflicting identities.
- [x] Evidence Dossier and Implementation Path views.
- [x] Lua API → C++ binding/implementation evidence where source proves the relationship.
- [x] Runtime/capture drill-down to exact normalized observations and source provenance.
- [x] High-volume traversal bounds/truncation reporting.
- [x] Mission/quest State Surface extraction reused by Character Editor.
- [x] Focused Feature Trace modes generate/display provider-native relationship evidence without writing synthetic canonical graph edges.
- [x] Focused modes cover implementation, triggers, effects, dependencies, mission progression, runtime evidence, identity, diagnosis, and all-evidence navigation.
- [x] Deterministic server relationships include supported item-detail → base-item, spawn → group, group → pool, pet → pool, Blue Magic spell/skill, instance membership/entity, and exact reference-wiki claim-alignment paths.
- [x] `mob_droplist` rows are indexed with complete-row read-only composite identity because supported upstream schemas do not provide a stable primary key.
- [x] Deterministic drop-chain traversal supports **spawn → group → pool / drop rows → item** without creating canonical graph edges as a side effect.
- [x] Feature Trace branch reconciliation preserved unique drop-chain work by transplanting it onto newer `main` rather than merging a diverged branch wholesale; superseded alternate scenario UI work was deliberately excluded.
- [x] Executable trace benchmark contracts can verify mode, root kind, relationship concepts/count, and required generators; the NM benchmark proves end-to-end drop/item traversal.
- [x] `MAPPED` reference-wiki mappings can navigate to an exact indexed implementation target when `target_table + target_key` resolve uniquely; ambiguous/unresolved/duplicate targets fail closed.
- [x] Captures can navigate to the exact client identity snapshot for their recorded `client_build` only when one `identity_snapshots.version` matches; duplicate build snapshots fail closed.
- [x] Research sessions, Validation runs, and migrations can navigate from explicit stored canonical feature IDs to exact feature roots.
- [x] Research sessions can navigate from explicit stored entity roots to exact canonical entities.
- [x] Migration actions can navigate from explicit stored artifact IDs to exact canonical artifacts.
- [x] Generic Research/Validation `subject_id` closure requires exactly one canonical namespace match; cross-namespace ambiguity produces no link.
- [x] Provider→canonical closure remains presentation/navigation evidence only and does not persist synthetic canonical graph edges.
- [x] Workbench/Src Layout regressions cover wiki-target closure, capture→client-build closure, provider→canonical feature/entity/artifact closure, duplicate-target rejection, and cross-namespace ambiguity rejection.
- [~] Pause speculative provider expansion until real-object testing identifies concrete deterministic gaps. A future phase may add reverse discovery from canonical nodes back to provider records under the same exact-ID/fail-closed rules.

# 5. Behavior Inspector / scripted behavior

Behavior Inspector is at closeout state as a mature evidence-first scripted-behavior inspector. Its durable capability and safety contract is documented in `docs/workbench/BEHAVIOR_INSPECTOR_CLOSEOUT.md`; its relationship to Feature Trace is documented in `docs/workbench/BEHAVIOR_FEATURE_TRACE_GUIDE.md`.

## Extraction

- [x] Generic Lua behavior model for NPCs, mobs, doors/objects, zone scripts, instances, timers, callbacks, state, conditions, effects, shared helpers, entity references, environment checks, and runtime-relative IDs.
- [x] Named state reads/writes across player/entity/instance/server scopes.
- [x] Verified literal state transitions where read/write identity and guards prove the relationship.
- [x] Shared `xi.<module>.<function>` helper resolution with exact/ambiguous/unresolved states and one-level impact expansion.
- [x] Bare-global helpers included only when reachable from modeled hooks.
- [x] Timer, queue, and listener callbacks retain explicit ownership, source spans, and callback-specific behavior while the complete technical evidence remains available for audit.

## End-user presentation

- [x] **Clarified Flow is the default view**, with Plain Behavior and Technical Graph preserved as adjacent views.
- [x] Clarified Flow preserves source-proven branch structure and exposes event lifecycle identity, stage → event → next-stage summaries, verified stage-value continuity, and navigation back to exact stage/branch evidence.
- [x] Cross-hook event identity and stage continuity remain explicitly non-causal/`UNPROVEN` unless independent runtime evidence proves ordering.
- [x] Behavior chains are grouped as **Trigger → Requirements → Actions / Events → Results / State Changes**.
- [x] Common Lua/API concepts are translated into end-user language while preserving the technical identity as secondary evidence.
- [x] Plain Behavior uses one backend-generated evidence-preserving projection contract consumed by the browser rather than a second semantic implementation.
- [x] Internal rule/helper-call/callee plumbing is collapsed while source-proven guards, helper identity/inputs/effects, state, targets, and exact technical node IDs remain available for drill-down.
- [x] Callback flows are partitioned: parent hooks show scheduling/registration, callback triggers own their downstream effects, and source-span filtering removes duplicate callback-body presentation without deleting Technical Graph evidence.
- [x] Concise summaries use only extracted graph labels, relationships, and proven source spans; unsupported runtime semantics remain unknown rather than inferred.
- [x] Plain Behavior cards drill into the same exact node metadata/evidence rather than creating a separate truth model.
- [x] Technical Graph remains available as the detailed evidence/debug view.
- [x] Technical graph supports wheel zoom, pointer-centered zoom, drag-pan, Zoom +/- controls, Fit, Reset View.
- [x] Selecting a node highlights upstream prerequisites and downstream effects as a directed causal path while dimming unrelated sibling branches.
- [x] Node details live in a persistent right-side inspector with independent scrolling, collapse/expand, and responsive stacked fallback.
- [x] Behavior Inspector and Feature Trace now have an explicit workflow boundary: Behavior explains source-proven Lua behavior; Feature Trace explains cross-source implementation/evidence relationships.
- [x] Further support for new/dynamic Lua idioms is additive evidence expansion, not unfinished foundational Behavior Inspector work; unsupported semantics remain raw/generic evidence rather than guessed behavior.

# 6. Mission / quest extraction

- [x] Generic mission/quest state-machine representation with guarded transitions, ALL/ANY gates, lifecycle effects, branch/convergence modeling, implementation gaps, and source provenance.
- [x] Branch-aware Lua extraction and structurally discovered completion/helper behavior.
- [x] Key-item, item, trade, event, timer, zone, mission/quest prerequisite, reward, teleport, and progression-state extraction across supported LSB DSL patterns.
- [x] Cross-feature prerequisite closure with explicit unresolved symbols.
- [x] Stress metrics and tested complex WotG mission/quest chains.
- [x] Reusable multi-zone progression and minigame/state-machine frameworks.
- [x] Transition bundles combine persistent state writes with event side effects, rewards/removals, completion/next-state activation, runtime requirements, projected outcomes, and blocker reasoning for Character Editor diagnosis.
- [x] Legacy DSP/Topaz handler normalization feeds the same progression-inspector contract for supported patterns.
- [~] Continue extracting helper-generated or highly dynamic transitions only when deterministic evidence supports them; do not infer runtime ordering from static mentions alone.

# 7. Entity / Event / CSID research

- [x] Entity Profile/Dossier aggregates SQL wiring, Lua behavior, captures, client identity, event/dialog references, and implementation gaps.
- [x] Conservative server/client CSID reconciliation.
- [x] Variable-length EVENT decoding for bounded statically provable formulas.
- [x] EVENT flow preserves work-area/options/captured parameters without assigning unsupported gameplay meaning.
- [x] Entity research handoffs connect Feature Trace, Behavior Inspector, Events/CSIDs, captures, and implementation diagnostics.

# 8. Character/client DAT assets and Item Editor

- [x] DAT Inspector and client resource inspection.
- [x] Client ENTITY identity extraction and portable client snapshots.
- [x] Model catalog/viewer and zone/model correlation.
- [x] Item Editor backend is packaged under `src/workbench/editors/items` with root compatibility imports.
- [x] Item DAT tooling is packaged while preserving backup/journal semantics.
- [x] Item Editor consumes named active server environments.
- [x] Item Editor/related client tools preserve SQL/client reconciliation, validation, backups, constrained edits, and rollback-oriented patch workflows.
- [x] Persistent **client item DAT cache**:
  - default lazy extract-on-first-use;
  - optional one-time Build All action in Settings;
  - parsed item metadata stored in SQLite;
  - icons stored as normal PNG files;
  - client-install/snapshot isolation;
  - source DAT size/mtime validation and selective regeneration;
  - cache clear returns automatically to lazy extraction.
- [x] Character inventory uses the cache-backed icon path and defers icon URLs for collapsed containers.
- [x] Client item cache health reports per-DAT fresh/stale/missing records, orphaned rows and missing icons; complete status requires current source signatures rather than counting obsolete rows. Settings surfaces repair needs without eager extraction.
- [x] DAT Inspector exposes installed xi-tinkerer decoder availability separately from file-level parse recognition; missing decoder methods are explicit, not mistaken for failed DAT reads. See `CLIENT_ASSET_CACHE_FORMAT_AUDIT_2026-10-10.md`.
- [~] Extend the generic Client Asset Cache concept beyond item metadata/icons to additional reusable models/textures/maps/assets only where parser semantics are proven.

# 9. Zone Editor / spatial viewers

- [x] Modern Zone Editor under packaged editor source layout.
- [x] Server-aware editing through named environment context.
- [x] Spatial entity/path visualization, labels/IDs/positions/search, navigation helpers, model integration, bookmarks/templates, and review/bulk workflows.
- [x] Capture 2D/3D viewer routes and Zone Editor handoffs are covered by live-app route regressions.
- [x] Standalone 3D viewer identifies client DAT versus cached OBJ mesh source and surfaces recoverable load failures with retry controls; visual verification on local FFXI DATs remains pending.
- [x] Standalone 3D viewer can toggle mob/NPC/door/captured spawn markers with shared search and marker-count feedback; visual smoke test pending.
- [x] Standalone 3D viewer provides read-only camera XYZ/view-heading diagnostics, go-to XYZ, and page-session save/restore viewpoints. Coordinates use existing viewer transform; local visual acceptance remains pending.
- [x] Standalone viewer supports 30 named session viewpoints, return-to-initial-zone framing and read-only focus on filtered spawns; texture issue in Bastok Markets and Markets [S] remains separate backlog pending real DAT verification.
- [x] 3D Zone Viewer layout replaces stacked above-map settings rows with a compact left overlay rail and collapsible tabbed drawer (Zone, Layers, Camera, Live, Capture, Info). Existing controls/IDs are reparented rather than recreated; local visual acceptance still pending.
- [x] 3D Viewer adds read-only selected-entity inspection from marker click and entity focus, with available source/model/level/HP/XYZ fields and a verified numeric-ID link to the existing Entity Inspector route; visual smoke testing pending.
- [x] 3D Viewer entity inspection links numeric IDs to existing Feature Trace and Capture Evidence dossier destinations, retaining inspection while visibility/search filters change; still requires browser smoke testing.
- [x] 3D Viewer inspector workflow batch: camera focus, copied ID/game XYZ, Find Similar launch into searchable entity picker, and capture-list selection sharing the inspector; browser smoke test pending.
- [x] 3D Viewer inspector next/previous controls browse current visible entities with wraparound and focus, show position/count, highlight the selected marker, and restore marker colors on close; real browser acceptance pending.
- [x] 3D Viewer Live tab optionally plots up to 12 other connected same-zone clients as separate blue read-only markers, using bounded parallel projections and stale-marker cleanup; reports selected bridge request latency and keeps primary follow behavior unchanged. Browser/Ashita smoke test pending.
- [x] Read-only Live viewer secondary-client chooser, matching-zone position/heading arrows and selectable camera focus/follow; controller cleanup and primary/secondary follow exclusivity; browser/Ashita testing pending.
- [x] Live Client 3D Viewer observed-entity picker exposes up to 100 nearby bridge entities through the existing read-only entity inspector with canonical game coordinates and numeric-ID research links; keeps ID selection across normal polls, clears on disconnect, browser smoke test pending.
- [x] Read-only live Ashita viewer now interpolates player marker and orbit follow between snapshots using frame time, stale-sample guard, and teleport snap; multi-client markers remain future work, local browser acceptance pending.
- [~] 3D Viewer vegetation alpha-mask correction: detect binary RGBA cutout pixels independently of MMB blending flag so grass/fences need not render as opaque black rectangles; real Sauromugue Champaign [S] visual acceptance pending.
- [x] 3D fly camera movement uses capped elapsed frame time and normalized direction, making speed consistent across frame rates and diagonal travel; real-browser acceptance remains pending.
- [x] 3D live DAT mesh pipeline audits instance transforms, skips non-finite/singular matrices without inventing placements, and reports mirrored/skipped counts; real-client visual correctness still requires validation.
- [x] 3D viewer records per-DAT prefab material/texture diagnostics (missing/malformed RGBA, alpha/water/sky tags) while preserving rendering transforms and untextured fallbacks; real DAT visual verification pending.
- [~] DXT1 three-color palette index 3 was incorrectly opaque black in shared decoder; fixed to transparent, with executable regression. Verify grass/billboard cutouts in Sauromugue Champaign [S] in local viewer before marking visually resolved.
- [x] 3D Viewer surfaces live-DAT and OBJ fallback diagnostics in a read-only expandable panel with copyable JSON; real client validation pending.
- [x] 3D live-DAT viewer Info diagnostics adds a reversible force-opaque comparison and per-prefab texture-name, blending flag, RGBA alpha count inspector; test Bastok Markets floor geometry with toggle off/on before classifying missing material versus transparency.
- [~] Bastok Markets and Bastok Markets [S] user-reported ground/building texture gaps: removed shared zone parser's incorrect majority-texture substitution; now report unresolved original texture names in 3D diagnostics. Local comparison and companion-DAT resolution are still pending; other sampled zones appear acceptable.
- [~] DAT texture resolver can match unique case/whitespace/null-normalized texture names, reports alias-match counts, and leaves ambiguous references unresolved. Confirm against real Bastok client DATs before marking fixed.
- [x] Model catalog failures from unrecognized gear-slot indices no longer abort the complete catalog.
- [x] Nyzul Editor preserves explicit DSP/Topaz legacy-layout handling while routing modern LandSandBoat checkouts through the native adapter.
- [x] Native modern-LSB Nyzul adapter parses `floor_generation.lua`, current objective/layout selection, YAML-backed entity tables, native boss/Rampart positions, shared spawn pools, and fail-closed unsupported mappings; merged in PR #544.

# 10. Capture ingestion and evidence

## Ingestion families

- [x] Windower PacketLogger / PacketViewer and z16-style sources.
- [x] Ashita Packeteer.
- [x] MalRD PacketDB packets plus CHATLOG.
- [x] NPCLogger SQLite/Lua/Widescan.
- [x] EventView, ActionView, HPTrack, IDView, KITrack, LevelRange, AttackDelay, PathLog.
- [x] MissionTrack, ShopStock, GuildStock, SpawnTrack, WeatherTrack, CraftTrack, CheckParam, POITrack, ConquestTrack, PriceLog/findPrice, StatTrack and related historical structured formats.
- [x] Windower Logger chat files.
- [x] PCAP / PCAPNG network captures.
- [x] Video/OCR evidence remains separate from raw protocol evidence.

## Integrity/search/correlation

- [x] Content-addressed source manifests and exact parser/table lineage.
- [x] Duplicate/session-overlap detection and clock-continuity diagnostics.
- [x] Exact row/block/SQLite provenance and source viewer with hash verification.
- [x] Safe parser-specific rebuild rules.
- [x] Cross-source packet correlation with verified/ambiguous states rather than fuzzy automatic merging.
- [x] Capture Data Explorer for structured/raw datasets.
- [x] Modular Evidence Search across events/dialogue, protocol, entities, battle/actions, items/KIs, shops, crafting, chat/text, movement/spatial, and environment/world state.
- [x] Campaign/session manifest import support and message-ID shift handling.
- [x] Capture spatial JSON routing bug fixed and plot viewer routing guarded by live-app regression.
- [x] Evidence-backed lobby/search/map stream classification and framing from PR #545 is part of the merged baseline, including fail-closed unknown TCP handling and source-backed handoff evidence.
- [~] Continue lobby/world/search protocol research only where representative real captures justify additional decoder certainty or semantics.

# 11. Packet / protocol research

- [x] Manual and bulk packet decode.
- [x] Packet Viewer-style presentation/handoffs.
- [x] Packetlyzer reference DB improvements including XiPackets-named opcodes and corrected verified field offsets.
- [x] PCAP/PCAPNG frame parsing and bidirectional TCP reconstruction with gaps/retransmissions/conflicts preserved.
- [x] Conservative lobby TCP classification/framing/decoder foundation.
- [x] PR #545 merged evidence-backed lobby/search/map classification, source-backed search framing/crypto evidence, strict same-flow sequencing, non-AH response parsing, exact UDP map handoff, and conservative endpoint/session diagnostics without guessing unknown protocol semantics.
- [~] Validate and extend decoder coverage against representative real captures; preserve unknown/ambiguous classifications when evidence is insufficient.

# 12. Video / OCR / temporal evidence

- [x] YouTube/video OCR workflows.
- [x] Saved screen/preprocessing profiles for known overlay families.
- [x] Cross-frame OCR consensus and packet-symbol-assisted correction with raw OCR preserved.
- [x] Capture/video timestamp alignment using explicit anchors and offset/drift diagnostics.
- [x] Screenshot/key-event/note evidence with provenance.

# 13. Research Sessions and wiki/reference evidence

- [x] Persistent Research Sessions with provider/model, permissions, budgets, timeout, replay, tool transcripts, evidence IDs, proposals, and final reports.
- [x] Local Ollama support without silent provider fallback.
- [x] Contradiction browsing across canonical findings, snapshots, and research proposals.
- [x] Evidence-backed contradiction dossiers group existing records into explicit sides with value/status/confidence/source-snapshot provenance, conservative completeness states, ResearchSession scoping, truncation visibility, and exact Feature Trace handoffs; merged in PR #546.
- [x] BG Wiki / FFXIclopedia claim-level alignment and conflict detection with provenance.
- [x] Reference Evidence Detail exposes canonical claim provenance and exact claim/mapping Feature Trace handoffs without duplicating mapped-target closure logic.
- [x] Dual-wiki `REFERENCE_CONFLICT` findings render BG Wiki vs FFXIclopedia side-by-side from importer-preserved claim IDs/excerpts while retaining `REFERENCE_ONLY` semantics and selecting no winner; merged in PR #547.
- [x] Feature Trace can close exact `MAPPED` reference-wiki targets into indexed implementation rows when target identity resolves uniquely.
- [~] Additional claim-to-implementation or provider-specific presentation should be driven by real-data gaps rather than inferred mappings; the planned contradiction/evidence deepening work is otherwise complete.
- [x] Background URL scrape (BG Wiki, FFXIclopedia, WikiWikiJP) into a temp DB, merged by `INSERT OR REPLACE`; Japanese stored verbatim with display-time translation (`WIKI_TRANSLATE_CMD`, no bundled engine). Re-scraping a URL overwrites the row; no history is kept.
- [~] **Wiki V2 structured-document foundation** — preserve source-format/raw source plus typed document blocks (headings, prose, lists, definitions, tables, links), render them as article structure instead of `<pre>` blobs, and retain a degraded legacy-text fallback for already-flattened imports. BG/FFXIclopedia can be re-parsed from existing MediaWiki source without network access; WikiWikiJP pages gain full structure when selectively re-scraped, so a whole-site crawl is not a prerequisite.
- [x] **Japanese Wiki local translation + client terms (2026-10-10):** Wiki tab *Translation* runs a user-selected local Ollama model (saved setting, Model dropdown, no env var needed), chunking long pages, 600 s timeout, `num_ctx` sized per request, and skipping blocks with no Japanese text; drafts stay cached and never become evidence. Sugoi-14B-Ultra is the preferred model (shisa-v2-12b tested: similar speed, weaker on game terms). Tab *Client terms* searches the local client text DB (`data/ja_en_text.db`: auto-translate phrases, items, zones) in English/Japanese/kana, with a Search JP Wiki link; Japanese article pages can *Highlight client terms* (bracketed, English hover, side list) and *Show terms in English*. Routes: `/wiki/translate/models|model`, `/wiki/client-terms/search|annotate`. Client terms are lookup aids only.
- [ ] **Wiki translation follow-ups:** show applied client terms per block in the bilingual view; "translate selected section"; resume BG import job; model quality on game-specific names remains unverified.
- [~] **Multilingual discovery/topic identity** — cross-source search covers stored titles/text, structured blocks, the existing BG index, cached machine-English translations, and reviewed aliases. Canonical English topic links can associate Japanese and English source pages without changing the Japanese evidence text; automated JP↔EN alignment/translation-derived aliases remain future work.
- [ ] **Page history and scrape freshness verification:** audit present ingestion/history tables before implementing anything; ensure unchanged-source hashes skip rewrites, changed revisions are retained, scrape jobs report update/unchanged status, and orphaned translation-cache records are cleaned up. Do not assume a page-history table exists without verifying the running schema.
- [~] Wiki typed reference extraction: preserved source links promote into revision-stamped `ENTITY_REFERENCE` claims/mappings, and explicitly labelled structured sections now produce conservative binary `REFERENCE_*` relationships for Drops/Rewards/Location/Requirements (including Japanese heading equivalents). A direct graph edge is emitted only when both endpoints resolve uniquely; otherwise the relation remains reviewable but untraversed. Reviewed canonical JP↔EN topics can resolve Japanese endpoints without making translation authoritative. Broader template/table-field semantics and arbitrary prose interpretation remain.
- [~] Register structured wiki pages/blocks/topics as richer Feature Trace providers: pages, blocks, topics, and topic membership now have exact source-native catalog identities/links; imported mapped claims are traversable in both directions so an implementation entity can discover incoming wiki reference evidence while preserving the original `REFERENCE_ONLY` edge semantics. Broader typed page/section relationship presentation remains.
- [ ] Relationship graph view on wiki pages and Entity dossiers (filter by edge type and source; mark confirmed client/capture/DB edges apart from wiki-only edges). Pilot on the Voidwatch NM / zone / abyssite / key-item chain.
- [x] **Wiki V2 review foundation (PRs #671–#714, selected):** structured article/table/template preservation, source-cell provenance, reviewed JP/EN topic suggestion and explicit approval/dismissal, source proof links, filtered candidate review queue, status-aware pagination, return navigation, and reviewer success feedback. These are review tools, not automatic topic authority.
- [x] **Wiki V2 full-corpus reparse validation:** parser `wiki-doc-v6-html-table-spans` reparsed on a working copy of the whole local DB (0 failures, idempotent); report in `WIKI_FULL_CORPUS_VALIDATION.md`. Open: raw source for 516 FFX / 601 JP pages, `retrieved_at`, stable table locators before any production reparse.
- [~] **Wiki V2 branch reconciliation:** #714 review counts merged; #703 and #707 are stale/overlapping with later merged changes and must be reconciled rather than blindly merged.
- [ ] **Next priority — typed Wiki extraction:** inventory real BG/FFXIclopedia/JP sample templates, infoboxes, and two-column tables; add an allowlisted field schema for drops/rewards/spawns/requirements/quests with raw source locators, conservative ambiguity handling, and review-only candidates. Do not mine arbitrary prose into trusted edges.
- [ ] **Next priority — multilingual field alignment:** correlate source-original Japanese section/field labels with English canonical field categories; translations supply discoverability/suggestions only until reviewed. Preserve Japanese raw values and distinguish alias evidence from translation.
- [ ] **Next priority — Feature Trace review drill-down:** connect explicitly reviewed typed Wiki fields and topic/section pages to source-native evidence without changing REFERENCE_ONLY authority, and validate across NPC/mob/zone/item/quest examples.
- [ ] **Selective source recovery:** inventory legacy flattened WikiWikiJP records and selectively re-scrape pages to restore source structure; retain crawl pacing/rate-limiting and avoid any full-site re-ingest requirement.


# 14. Package / migration / validation

- [x] Dependency-aware package planning and scope review.
- [x] Conditional dependencies remain reviewable instead of silently becoming mandatory.
- [x] Patch-plan drift checks, approval states, file apply journals, and rollback.
- [x] Validation runs tied back to canonical evidence.
- [x] Feature Trace can navigate explicit Research/Validation/Package feature/entity/artifact references back to exact canonical nodes without creating graph edges.
- [x] Source/target conversion support where deterministic and audited.
- [x] Phase D packaging moved mature root implementations into logical `src/workbench/...` homes while preserving intentional compatibility imports/launchers.
- [x] Final Phase D source-layout ownership cleanup is complete: the settings store and application host are package-owned, historical root `settings.py` and `gui_server.py` compatibility surfaces are retired, and Workbench/Src Layout/Character Editor regressions cover the final boundary.

# 15. CI / regression safety

- [x] Workbench Regression suite.
- [x] Src Layout Regression suite.
- [x] Dedicated Character Editor Regression suite, including pytest fixtures and executable regression scripts.
- [x] Focused GUI/client snapshot/research/DAT inspector jobs.
- [x] Live-app route regressions for sensitive routing surfaces.
- [x] Character Editor progression regressions cover modern LSB and legacy DSP/Topaz transition-bundle, projected-result, assessment, and UI contracts.
- [x] Behavior Inspector regressions cover extraction, complex state/event flows, callbacks, shared helpers, Clarified Flow/Plain View projection, backend/UI contract parity, stage/event lifecycle contracts, and source-layout service boundaries.
- [x] Feature Trace regressions cover deterministic provider relationships, fail-closed ambiguity, focused modes, executable scenario contracts, NM drop/item traversal, wiki→implementation closure, capture→client-build closure, and provider→canonical feature/entity/artifact closure without synthetic canonical edges.
- [x] Application-host/settings changes are included in Character Editor/server-admin regression path coverage after the final Phase D migration.
- [x] Documentation reconciliation should occur after major multi-PR feature batches rather than allowing README/roadmap drift to accumulate again.

---

# 16. Auction House administration and Economy BI

Operator summary: `AUCTION_HOUSE_CAPABILITY_STATUS.md`. Economy detail: `AUCTION_HOUSE_ECONOMY_INTELLIGENCE.md`.

- [x] Single hub at `/auction-house` (Economy, Items, Sellers, Restock, Inbox, plus Seeder/Presets/Activity/Cleanup/Rewards); legacy page URLs forward to it.
- [x] Write flags are settings-backed (Settings -> Auction House) with an env-var override; the Help page lists every requirement and the blocked code it produces.
- [x] Shared action drawer for Buy/Return/Restock/Inbox with typed profile-name confirmation, backdrop, and a Close button that is not hidden under the site header.
- [x] Inbox delivery supports gil as well as items.
- [x] Economy Intelligence: KPI strip with prior-period deltas and sparklines, Market activity chart, Price movers with thin-evidence flagging, "Where to look" queues (needs supply, oversupplied, stagnant, seller concentration), category sell-through/time-to-sale, player and account lookup.
- [x] Daily snapshots of supply and sell-through in the toolkit SQLite DB (background loop plus "Record now"); Supply history chart.
- [x] Baselines: each snapshot metric compared with the median of its previous snapshots (usual range = median +/- 2 MAD); reports "building" until 7 earlier snapshots exist.
- [x] Admin-impact overlay: completed toolkit actions (seed, restock, Admin Buy, return, rewards, player listing/purchase) marked on the activity chart and listed with item median price 7 days before/after. Pointer, not proof.
- [x] Test-data seeding in the Seeder tab: history, scenarios (monopolised/stagnant/flooded), clear. Test profile only, gated, confined to fake sellers 990000-990024.
- [x] Items page: Recent Sales stacked above uncapped Active listings, price-markup chip vs recent-sale median, listing filters (text/price/type/markup) that scope bulk actions, active seller/item links with Back.
- [x] Supply/sell-through deltas on the Economy supply card (vs snapshot ~7d earlier). Sellers page: markup chip on listings, 30-day sales, gil, sell-through and median time-to-sell per seller, Recent sales stacked above uncapped Active listings, filters, item links with Back.
- [x] Economy anomaly detection (Anomalies card): price shifts, volume spikes, over/underpriced listings, seller listing floods, each against its own history (median/MAD). Restock and Inbox share a multi-character picker (browse, type name/id, remove chips); Restock spreads listings across several sellers.
- [x] Synthetic category seeding consolidated into Restock ("Add a whole category", multi-seller, same preview/confirm path); the Seeder panel now points there. Player-backed listing and Market history stay in the Seeder.
- [x] Presets: 18 built-in Restock/Cleanup presets, editable in a native Presets tab with Edit/Back; Restock uses a configurable default seller (AHRestock, synthetic id in 990000-990999) when no character is picked.
- [x] Native Cleanup tab with seller/item search pickers, preset loading and an empty-state hint showing oldest listing age.
- [x] Items status toggle (Active / Unlisted / All) backed by `/auction-house/console/catalog.json`; unlisted items show sales history.
- [x] Buyers tab (`buyers.json`, `buyer.json`; `buyer_stats.py`, unit-tested): per-buyer spend, overpaid purchases vs item median (>=50%), gil refund of the overpay via the rewards flow. Buyers keyed by name (DSP sold rows have no buyer id); refund needs a `chars` row.
- [x] "Buy as..." (player purchase) folded into Items/Sellers listing rows; Listing Manager kept only as a legacy view.
- [x] Fixed the confirm drawer (missing `dwConfName` element) that blocked Buy/Return/Restock/refund drawers from opening.
- [~] DSP runtime validation: project owner confirms Auction House is **clean and stable against DSP**, with successful runtime testing; existing DSP MyISAM listing test is documented separately. The exact per-operation verified matrix is not yet captured, so do not reopen completed tests or imply every operation is individually verified.
- [~] Snapshot-based supply/sell-through comparisons depend on multiple dated observations; current prior-period activity/KPI trends and supply snapshot comparisons already exist. Validate multi-day behavior, rather than reimplementing the deltas.
- [x] Anomaly detection exists (price shifts, volume spikes, mispriced listings, seller floods); forecasting is a distinct optional enhancement dependent on sufficient authentic history.
- [x] Inbox "all characters on selected account" recipient mode with a one-character anchor, verified account linkage, bounded preview, and GUI selector (PR #749). Broader account-based filters outside Inbox remain optional.
- [x] Read-only DSP MyISAM recovery guidance surfaced in listing/purchase readiness (PR #743); non-transactional crash windows **remain** and automatic crash recovery is not supported.
- [x] Reward campaign retry safety: original-environment binding, per-recipient outcome integrity, failed-only retry preview and guarded conflicts on incomplete results (PRs #740, #747). Per-recipient durable in-flight evidence and review-required outcome tracking were subsequently added in PR #786; no automatic retry of uncertain delivery.
- [x] Analytics correctness/performance: future timestamps excluded from 7-day snapshots and anomaly event windows; per-metric baseline sample counts and nonnegative lower bounds; anomaly evidence sample quality; cached per-item medians/evidence counts (PRs #754, #756, #758, #760, #762).
- [x] DSP MyISAM crash-persistent diagnostic cases and per-recipient Inbox attempt journal; ambiguous outcomes require operator reconciliation, never automatic double delivery (#786).
- [x] One-time operator-approved DSP/Topaz Test scheduled reward campaigns with exact-profile revalidation, claim-once execution, cancellation and review-required states (#786).
- [x] Character Editor-style augment picker, full-catalog Inbox item bundle chooser, item icons, hover facts and circular AH ↔ Item Browser ↔ Item Editor navigation (#787, #792, #795, #797).
- [x] Restock/Cleanup searchable icon-backed item selection, shared Workbench item-picker foundation for AH views, item/seller favorites, remembered tabs/filters/selections and read-only CSV exports (#797, #802, #808, #812, #816).
- [x] Item quick actions (including Add to Inbox bundle), saved named augmented reward definitions and source/catalog validation (#814, #815).
- [ ] Dedicated Topaz TEST validation; DSP test evidence does not establish Topaz parity.
- [~] LSB read/preview/policy support exists; broader LSB write workflows remain deferred pending runnable LSB Test evidence.
- [x] Source-backed, four-slot custom augmented-item preview and reusable named configuration library (#786, #787, #815); [~] experimental disabled-by-default one-recipient DSP Test augmented-mail executor requires real Mog pickup persistence validation. Production authorization is not planned.

**Remaining AH operator acceptance (2026-10-09):** execute controlled DSP Test interruptions for MyISAM and Inbox journals, exercise one-time Test schedules and augmented-item pickup/persistence, verify multi-day snapshot trends, and separately validate Topaz. Broad LSB writes await an LSB Test environment. Core DSP feature development is complete; AH is in **maintenance mode** subject to these acceptance checks.

**Auction House feature audit / actionable TODO (updated completion reconciliation below):** [`AUCTION_HOUSE_GAP_AUDIT_TODO_2026-10-08.md`](AUCTION_HOUSE_GAP_AUDIT_TODO_2026-10-08.md). This distinguishes implemented, user-tested, intentionally gated, environment-unverified, and optional enhancement work.

---

- [x] Arbitrage tab (underpriced listings, post-for-profit, vendor loops) with a vendor-ratio Cleanup rule and two built-in presets; restock presets accept include/exclude item lists; More tools regrouped; Inbox campaigns now record the chosen template.
- [x] Synth & Crafting module at `/synth` (`server_admin/synth`): schema-adaptive over `synth_recipes` for DSP/Topaz/LSB, ingredient availability + missing report, audit, SQL create/edit/delete preview per flavor, export/port, gated Test-write apply.
- [ ] Open: vendor-loop data exploit (shop prices below BaseSell) is documented but not fixed; synth audit cannot see gathering/fishing/quest sources.


# 17. Workbench UI Framework / Unified Module Layout

The shared `base.html` shell already unifies global navigation, workspace context, theme variables, and common dense UI primitives. The next UI architecture phase should unify **module composition and geometry** so independently developed tools stop drifting in width, spacing, panel sizing, controls, and interaction structure.

- [x] Add a shared Workbench page wrapper above `base.html` for module-level layout contracts rather than navigation/chrome alone.
- [x] Define a small set of canonical page archetypes:
  - Browser — search/filter + result list/table + pagination;
  - Detail/Dossier — summary/header + evidence/detail sections;
  - Workbench/Inspector — navigator + primary workspace + inspector;
  - Editor — navigator + editable surface + properties/actions;
  - Dashboard/Console — status/KPI/action strip + panels/tables.
- [x] Standardize page header/title/status/action regions, help/about affordances, read-only/write-capable badges, empty/loading/error states, and shared filter/search rows.
- [x] Standardize one-, two-, and three-pane layout primitives including reusable sidebar/inspector widths, panel gaps, and responsive stacking; scrolling/sticky behavior remains workspace-specific until migrated.
- [ ] Replace repeated page-local geometry such as arbitrary `main` padding, max-widths, toolbar heights, and control sizing with shared Workbench design tokens.
- [x] Define shared tokens for page padding, toolbar/control height, panel gap, table row density, sidebar sizes, inspector width, and responsive breakpoints.
- [ ] Keep feature-specific visualization/layout behavior where required (Zone Editor canvas, Packet Viewer byte presentation, Auction House economy surfaces, etc.) while removing feature-specific reinvention of basic UI geometry.
- [ ] Convert existing `dense-toolbar`, `dense-panel`, tabs, cards, chips, tables, forms, and inspector patterns into documented reusable primitives where their contracts are already stable.
- [x] Add a UI/template contract regression: new module pages must use the standard Workbench wrapper/archetype or explicitly opt into the legacy/custom allowlist with a reason.
- [ ] Inventory current templates against the archetypes and migrate them systematically by workspace rather than opportunistically when features happen to be edited. Foundation adopters: SQL Browser (Browser), Validation (Dashboard), and Research Evidence (Detail). Research workspace migration is complete: Sessions, Contradictions, Gaps, Session Detail, and Evidence now use the shared wrapper. Validation workspace migration is complete: Dashboard, Runs, Run Detail, and Live Target now use the shared wrapper. Packages workspace migration is complete: Library, Scope Review, Create Package, and Review & Readiness now use the shared wrapper. Backport workspace migration is complete: Package Workflow, Lua Converter, SQL Converter, and Binding Reference now use the shared wrapper. ID Drift workspace migration is complete: Overview and Category Detail now use the shared wrapper. LLM workspace migration is complete: Assistant and Call Detail now use the shared wrapper. Events / CSID workspace migration is complete: Browser and Event Detail now use the shared wrapper. Wiki Compiler migration is complete and now uses the shared Workbench wrapper. Capture Path Plot migration is complete: Single Path and All Paths now use the shared wrapper while retaining specialized visualization geometry. Client Overview migration is complete and now uses the shared Dashboard wrapper. Binary Inspector migration is complete and now uses the shared Workbench wrapper. Behavior Inspector migration is complete and now uses the shared Workbench wrapper. Dialog Drift overview migration is complete and now uses the shared Dashboard wrapper. Per-zone Dialog Drift report migration is complete and now uses the shared Detail wrapper. Roadmap page migration is complete and now uses the shared Dashboard wrapper. Help page migration is complete and now uses the shared Detail wrapper. System confirmation/status pages (backup delete/restore, rebuild, shutdown/restart) are migrated to the shared wrapper. Entity Gaps diagnostic browser migration is complete and now uses the shared Browser wrapper. Key Items browser migration is complete and now uses the shared Browser wrapper. Assault Missions browser migration is complete and now uses the shared Browser wrapper. Zones browser migration is complete and now uses the shared Browser wrapper. Dialog Browser migration is complete and now uses the shared Browser wrapper while preserving jump/pagination and evidence drill-down. Domains index migration is complete and now uses the shared Dashboard wrapper. Feature Checker migration is complete and now uses the shared Workbench wrapper. Packet Tools migration is complete and now uses the shared Workbench wrapper. Assault Domain landing page migration is complete and now uses the shared Dashboard wrapper. Message-ID Shift Master migration is complete and now uses the shared Workbench wrapper. Capture delete confirmation migration is complete and now uses the shared Editor wrapper. Capture Help migration is complete and now uses the shared Detail wrapper. Capture Add Files, New Capture, and Source Evidence migrations are also complete on the shared wrapper. Bulk Ingest, Bulk Ingest Job, and Metadata Import are now migrated as a second capture-admin batch. Capture Review Queue and Related Evidence are now migrated while preserving quarantine and deterministic-correlation semantics. Capture / Video Alignment and modular Capture Evidence Search are now migrated while preserving all interaction and evidence semantics. Captures library, Capture Detail, and Capture Packet Browser are now migrated to the shared wrappers without changing their evidence or maintenance behavior. Capture Packet Viewer, Capture Data Explorer, and Capture Timeline complete the Capture workspace wrapper migration while retaining their specialized inspection layouts. Manual Packet Decoder plus Entity Lookup/Detail are now migrated to the shared UI framework without changing decode or evidence-dossier behavior. Item Browser and Item Script Health are now migrated as well, with Item Health’s previously implicit server-script repair write boundary made explicit in the shared shell. Feature Trace and the Home data/tools dashboard are now migrated, with rebuild/install actions explicitly separated from read-only status reporting. Domain Detail and Model Viewer are now migrated while preserving Voidwatch/Salvage evidence workspaces and the full-width 3D renderer. DAT Inspector and 3D Zone Viewer are now migrated as well, with the Zone 3D derived-mesh cache write boundary made explicit. The YouTube OCR index and per-run workbench are now migrated, with prerequisite installs, extraction/layout changes, capture creation, and deletion clearly marked as write-capable actions. Settings is now migrated as a dedicated configuration workbench with its cross-tool mutation boundary made explicit. Character Editor is now migrated to the shared Editor shell while preserving adapter-specific schemas, offline write locks, and preview/confirm safety. Item Editor is now migrated as well, preserving DAT synchronization, backup/journaling, batch preview/apply, restore, and undo/redo semantics. Zone Editor is now migrated to the shared full-width Editor shell while retaining its dedicated control bar, canvas/panel geometry, cache operations, and save/undo/redo behavior. Nyzul Isle Layout Editor is now migrated as well, preserving DSP/Topaz/modern-LSB generation adapters, optional navmesh evidence, Lua export, and persistent exclusion semantics. Synth & Crafting is now migrated to the shared Workbench shell while preserving recipe browsing, audits, comparisons, economy analysis, editor behavior, and read-only SQL export. Auction House Activity, Economy Intelligence, Help/Status, and Reward History are now migrated as the first Auction House cohort; read-only evidence surfaces remain distinct from Economy’s toolkit-local snapshot recording. Auction House Administration, Console, and Presets are now migrated as the second cohort, with preview-only overview controls, preset-state writes, and guarded Test-only operational mutations explicitly distinguished. Auction House Cleanup, Listing Manager, and Seeder are now migrated as the final cohort. The legacy UI allowlist is empty: all current module templates now use the shared Workbench page contract, with guarded Test-only execution semantics preserved.
- [x] Preserve behavior during migration; visual/layout normalization did not intentionally change feature semantics, write safety, evidence meaning, or route ownership.
- [x] Complete the workspace-by-workspace migration after the source-layout/root-cleanup realignment reached a stable boundary. Unified UI migration is closed with zero legacy templates.


# Highest-value next work

1. **Complete active root cleanup / bootstrap retirement** — finish the bounded compatibility-shim, standalone-script, workspace/resource, and final root-allowlist work tracked in `ROOT_CLEANUP_STATUS.md` without reintroducing import/path coupling.
2. **Feature Trace real-data validation** — exercise the current closure model against representative NPC/entity, mission, drop-chain, capture/client-build, reference mapping, and migration/package cases. Implement more Feature Trace wiring only when testing exposes a deterministic gap.
3. **Protocol real-capture validation** — exercise the merged PR #545 lobby/search/map classifier and decoder coverage against representative captures; add semantics only when source/structural evidence proves them and preserve fail-closed unknowns.
4. **Client Asset Cache expansion** — only for proven asset families where reusing pre-extracted data materially improves interactive tools.
5. **Broader client/server synchronization and named-system reconstruction** — extend deterministic comparison/validation workflows without weakening provenance rules.
6. **Auction House live-write validation** — run the remaining restock, Buy, Return, MyISAM purchase, and gil-delivery tests against a real Test server before treating those mutation paths as operationally closed.

A future Feature Trace development phase may add **reverse discovery** from a canonical feature/entity/artifact back to Research, Validation, Package, Capture, or reference records that explicitly point to it. Treat that as a distinct phase after real-data testing, not unfinished cleanup.

A future source-layout/bootstrap phase may retire root compatibility launchers and the root `workbench` bootstrap after every supported setup/start/CI path installs the package or explicitly uses `src`. That is intentionally separate from completed Phase D implementation ownership.

# Documentation map

- `README.md` — durable product overview and quick start.
- `docs/workbench/ROADMAP_CURRENT.md` — this file; authoritative current capability/status inventory.
- `docs/workbench/RECENT_CHANGES_2026-10-03.md` — detailed recent reconciliation and merged-change summary through the prior batch.
- `docs/workbench/CHARACTER_EDITOR_CLOSEOUT.md` — current Character Editor safety/capability contract.
- `docs/workbench/BEHAVIOR_INSPECTOR_CLOSEOUT.md` — current Behavior Inspector capability/evidence/closeout contract.
- `docs/workbench/BEHAVIOR_FEATURE_TRACE_GUIDE.md` — combined Behavior Inspector / Feature Trace workflow, evidence boundaries, and October 4 implementation summary.
- `docs/workbench/FEATURE_TRACE_BRANCH_RECONCILIATION_2026-10-04.md` — branch-level Feature Trace reconciliation and drop-chain transplant record.
- `docs/workbench/FEATURE_TRACE_CLOSEOUT_2026-10-04.md` — current Feature Trace closure matrix, fail-closed rules, regression coverage, and testing boundary.
- `docs/workbench/PHASE_D_ROOT_CLEANUP_STATUS.md` — final Phase D source-layout ownership closeout and remaining compatibility/bootstrap boundary.
- `docs/workbench/UI_FRAMEWORK.md` — shared module wrapper, canonical archetypes, geometry tokens, migration rules, and template contract.
- `docs/guides/SETUP.md` — current user setup and named environment configuration.
- `docs/guides/TOOLING_OVERVIEW.md` — living tooling/component overview.
- `docs/workbench/AUCTION_HOUSE_CAPABILITY_STATUS.md` — Auction House operator summary.
- `docs/workbench/ROADMAP.md` — historical implementation ledger.
- `docs/workbench/AUDIT_STATUS.md` — historical implementation/audit notes.
### Live Client remaining delivery plan — reconciled 2026-10-10

**Detailed prioritized roadmap:** [LIVE_CLIENT_DELIVERY_ROADMAP.md](LIVE_CLIENT_DELIVERY_ROADMAP.md). This is the forward-looking work plan with B1–B17 batches, dependencies, required Windows evidence, go/no-go gates, operator controls and acceptance criteria. Existing older notes below are historical implementation evidence, not a claim that native writes or end-to-end travel are complete.

**Merged baseline:** 3D Viewer PRs #943–#957 (including DXT1 correction #947, forced-opaque diagnosis #948 and live-entity selection/highlighting #957) are on `main`. Read-only camera, live multi-client, entity selection, hover and research navigation are implemented but need Windows/browser acceptance. Bastok missing-floor behavior remains unverified; do not mark repaired. **Outstanding primary goals:** dependable multi-client lifecycle, verified entity identity and spatial calibration, bidirectional command protocol, authorized real client movement, feedback-guided navigation, and canonical Capture research session workflow.

### Live Client cloud development follow-up

Current Live Client delivery status (supersedes older pending statements below):

| Area | Current status | Remaining work |
| --- | --- | --- |
| Recorded sessions and unified GUI | Implemented; cloud/browser tested: playback, speed, seek/scrub, multiple recordings, replacement/unload, duplicate IDs | Continue regression; actual simultaneous game clients still unverified |
| Ashita read-only player/entity provider | Runtime observations accepted in zones 50, 235, 107, 172, 52, 51 and 48; cap/truncation output covered | Loaded-build identity, catalog-ID agreement, complete enumeration and slot-reuse behavior |
| Opt-in zoning recovery | Test D demonstrates four transitions, four 5-second gaps and resumed export in one file | First failed run, inactive loading, long-zone timeout and logout/relogin testing |
| Raw entity diagnostics | Type/status/spawn flags exported in 623 Test D observations; semantics unknown | Populated target/subtarget roles and known-action interpretation |
| Spatial/waypoint integration | Raw 2D projections, trace/entity markers, waypoint/path library and visit isolation implemented | Verified transforms for zone maps/3D, collision/navmesh and placement callbacks |
| Capture and research integration | Passive packet exporter, canonical import, exact stored packet locators and entity research searches merged (#759/#765/#763); cloud tested | Paired Windows packet/telemetry fidelity and reviewed identity/event/CSID correlation; no automatic trusted joins |
| Independent native Windows adapter | Identity/research foundations only; no operational attachment or controls | Verified process/module attachment and standalone reads before individually authorized/audited writes |
| Appearance/animation/inventory/party diagnostics | Published API candidates; not a delivered feature | Add narrow opt-in observations through existing services after lifecycle/packet acceptance |

Next development/testing order: (1) preserve zoning/gap/diagnostic evidence in reports and
regressions; (2) runtime logout/relogin, long-zone and populated target-role acceptance;
(3) paired passive packet provenance/fidelity and existing Capture correlation;
(4) known-entity identity and calibrated spatial joins; (5) additional Ashita diagnostic
profiles; (6) standalone native attachment/read support, then separately authorized
controls with audit/readback/restoration. Useful cloud work continues between Windows
runs. No supported-build, verified map transform or operational game-write claim is made.


- Recorded-session console: independent identities for duplicate-client recordings; observed-time play/pause and speed; timeline seek; runtime replace/unload; independent observation comparison. See [Live Client resume guide](LIVE_CLIENT_BRIDGE.md).
- Read-only observation capture: named player/observed-target waypoint downloads and full recorded path export up to the replay cursor, preserving raw coordinates, source identity and zone/instance metadata. The persistent waypoint library supports player/target capture, name/zone search, rename/delete and atomic portable JSON import/export. Raw distance/XYZ comparison and optional trace markers require matching recording session, source and recorded visit; legacy/unknown contexts are excluded. Verified map placement and game writes remain pending.
- Runtime evidence tooling: offline recording reports summarize cadence, zone/instance transitions, raw coordinate ranges and targets; optional PE metadata/hashes identify supplied files without executing them. Supplied Ashita EXE/DLL resources report `4.0.0.2`, distinct from verification of the loaded runtime. See [Windows/Codex test handoff](LIVE_CLIENT_WINDOWS_HANDOFF.md).
- Validation covers synthetic offline telemetry and real-browser console behavior. Native Windows/FFXI telemetry, calibrated zone overlays and writable development adapters remain unverified/incomplete.
- Live Client now uses the shared fluid Workbench page and Client navigation. Relative traces preserve zone/instance discontinuities and spatial aspect ratio. [Native source research](LIVE_CLIENT_NATIVE_RESEARCH.md) documents framework interfaces and real-client validation prerequisites; it does not mark Windows integration complete.
- Experimental Ashita v4/Windower read-only observation exporters have Lua 5.1 source-to-file-feed cloud tests. After the PR #698 entity-zone fix, an authorized user supplied a successful Ashita recording: 121 frames/120 seconds in zone 50, with movement, headings and eight selected targets; reported game version `30191204_1` and stairs traversal without zoning. Cloud replay/feed decoding and Chromium regression use an anonymized copy. Trace planes are selectable X/Y, X/Z and Y/Z; Ashita initially uses X/Y without rewriting coordinates. Verified build identity, broader lifecycle/logout, multiple clients and calibrated map transforms still require runtime evidence; test D now supplies limited zone-transition evidence; process detection and game writes remain incomplete.

- [Tako / Clipper reference audit and bridge decision](LIVE_CLIENT_REFERENCE_AUDIT.md): public sources inspected; application archives unavailable. Next slice is bounded read-only Ashita loaded-entity inventory, then Windows identity/lifecycle and coordinate calibration. Standalone memory attachment, authorized controls/restoration, placement callbacks and live navmesh comparison remain incomplete. Clipper root GPLv3 and C# LGPLv3-or-later headers require licensing resolution before reuse.
- Ashita reuse follow-up: selected-target observations can retain optional published server IDs separately from client indexes and reject target changes during sampling. Cloud-tested only; new identity fields need Windows evidence. Minimap documentation confirms entity-rendering behavior, not a telemetry export API. Reuse Capture packet ingestion/correlation and existing packet schemas; bounded loaded-entity enumeration is cloud implemented; packet observation and game-control writes remain pending.
- Bounded Ashita inventory has supplied runtime observations in zones 235 and 107: explicit `start <id> inventory`, source-backed slots 0–2303, 32 named entities/sample with target priority, truncation metadata/UI and sampling-change guards. Default selected-target mode and legacy recordings remain supported. Runtime bounds/validity, entity kinds/status and complete inventory are not established; next is Windows cap/lifecycle/diagnostic-role evidence and verified coordinate/identity integration.
- Live Client zoning test slice: opt-in `inventory-zoning` pauses only tagged player-entity mismatch, requires two original-identity/same-zone samples, bounds recovery to 30 seconds and retains fatal inactivity/identity/API/clock/storage failures. Legacy modes are unchanged; packet streams stop on pause. Synthetic tests and a four-file test package support next Windows zoning/logout evidence; test D confirms four recovered transitions in one session, while broader transition/lifecycle compatibility remains unverified.
- Entity inspection in the integrated Live Client console supports name/decimal/hex-ID search and raw-distance ordering, retains duplicate-name identities and scope/truncation warnings, and leaves playback unchanged. Cloud/Chromium validated; no entity navigation or calibrated map placement is implied.
- Supplied bounded Ashita inventory runtime evidence now covers 30 frames in zone 235 and 24 in zone 107, with 1,035 nonzero server-ID observations and no reported truncation. Anonymized fixtures exercise report/projection/replay boundaries. This verifies observed export coverage only; zone transitions, concurrent clients, cap behavior, server catalog identity, raw diagnostics/target roles, lifecycle and packet fidelity remain pending.
- Inventory-aware runtime reports summarize declared scopes, truncation, entity counts and nonzero reported server-ID coverage, retaining source/zone/instance context in distinct-observation counts. Legacy scope and zero/absent IDs remain unknown; completeness, target roles and server identity are never promoted to verified from these metrics.
- Observation captures from the console are bound to displayed frame/session-generation tokens; stale waypoint/library/path captures reject with refresh guidance, including identical recording replacement and feed updates. Legacy API calls remain compatible. This is cloud-tested consistency protection, not native identity verification or write authorization.
- Portable path samples retain source/version, instance, Toolkit session/generation, recorded segment and inventory scope/truncation through parsing/serialization. Path splitting and replay traces preserve source/instance/visit and non-increasing-time boundaries; legacy context remains unknown. Cloud-tested foundation for later calibrated spatial/navmesh analysis, not route validation.

### Live Client waypoint recording isolation — 2026-10-09

Saved waypoint captures now retain the Toolkit recording generation. Raw comparisons exclude older or unknown generations, including replacement with an identical recording under the same session ID. Export/import preserves this context; seeking and restarting the original recording keep its waypoints comparable. Older waypoints remain available for management and export, but must be recaptured for comparison. Regression coverage uses the supplied anonymized Ashita recording. This is recording consistency validation, not Windows compatibility or coordinate calibration.

### Live Client recorded entity trace markers — 2026-10-09

The recorded trace optionally shows up to 100 current entity observations as purple squares in X/Y, X/Z or Y/Z. Hover details preserve literal names, client indexes, reported server IDs (or unknown) and raw XYZ. Bounds include displayed markers; source observation scope and truncation remain visible. Markers match the player instance hint and clear on frames without entities. The console binds trace collection to its displayed observation token, rejecting seek/replacement or collection-time changes instead of combining an old projection with a new path. Existing trace API clients may omit the token. Cloud/browser validation includes the supplied anonymized Ashita recording; calibrated zone maps, identity verification and live Windows testing remain pending.

Overlapping browser trace requests also discard superseded responses, preventing an older refresh from appending duplicate geometry to a newer plot. A browser regression deliberately delivers responses out of order and fails without the response guards. CI now exposes concise failing assertions through annotations when full log downloads are unavailable.

### Live Client / Ashita research reconciliation — 2026-10-09

- [Current capability matrix](LIVE_CLIENT_REFERENCE_AUDIT.md#reconciliation-with-ashita-capability-research--2026-10-09) reconciles PR #753 with main's providers, inventory, replay, markers, waypoint/path provenance, native boundaries and existing research/editor services. No active Live Client PR or unfinished branch was displaced; old recording/spatial heads are merged ancestors.
- Existing ObservationSource/TelemetryProducer, telemetry v1, registry and feed/replay UI already support multiple sources. Extend the original Ashita addon as preferred observation provider; retain Windower and future native paths. No duplicate abstraction/exporter/schema/UI or copied third-party implementation is required.
- Additive entity observations retain optional raw type/status/spawn flags and source-reported target/subtarget roles. Unavailable fields stay unknown; raw type never infers kind. Published subtarget mode determines slot 0/1 roles, with identity/context rechecks and unchanged bounded explicit export. Existing entity table displays the diagnostics. Cloud tests do not establish Windows compatibility or semantics.
- Next sequence: passive packet hook/provenance feasibility and canonical Capture ingestion, qualified research evidence joins, then optional animation/item diagnostics. Runtime inventory/role/lifecycle/multi-client testing and spatial calibration remain pending. Native standalone identity/reads and individually authorized controls remain separate unimplemented work; no write/profile/restoration capability is claimed.

### Passive Ashita packet source / canonical Capture — 2026-10-09

- The original addon now has a separately enabled, bounded event/emote packet profile tied to active telemetry identity. Original hook bytes, direction/time/sequence/zone/source, rate drops and hook-time flags are retained; no event mutation, injection or blocking is added.
- Existing Capture upload/folder ingestion/rebuild, capture_raw_packets and source locators handle the stream. Existing decoder/UI/correlation remain authoritative; unknown opcodes and original/header disagreements remain evidence.
- Classified implemented but only synthetically/offline tested. Hook bytes/flags are not verified final wire traffic or blocking; Windows fidelity/performance and clock/event joins remain pending. See the [reference evidence and limits](LIVE_CLIENT_REFERENCE_AUDIT.md#passive-ashita-packet-source--canonical-capture--2026-10-09) and [addon commands](../../addons/workbench_live/README.md#optional-passive-packet-observations-ashita-only).
- Offline Live Client reports can bind retained packet/frame candidates to existing Capture packet-view locators through an explicit read-only database/ID selection. Source hash, exact spans, unique ownership, canonical bytes/metadata and producer provenance must match; ambiguous or changed evidence gets no link. Existing Capture sequences/decoder are retained, with no database writes or verified runtime/semantic joins. Synthetic importer/report regressions pass; paired Windows exports remain pending.
- Next: source/time/zone/ID-qualified Capture/Feature Trace links and runtime correlation evidence. Broader diagnostics, calibrated maps and native controls remain independent work.

- Live Client offline packet evidence report: optional stopped Ashita packet JSONL is validated by the existing Capture adapter and matched only to exact declared recording label/client/adapter/version/zone/time frames. Reports retain source hashes and line/byte/frame locators with bounded candidate details; mismatches and ambiguity remain explicit. No decoder, database writes, verified server/instance joins or causal claims are added. Synthetic regression coverage is complete; paired Windows telemetry/packet evidence and reviewed research UI links remain pending.

- Live Client entity research handoff: explicitly reported nonzero server IDs now provide unverified ID searches in existing Capture, Entity Browser and Feature Trace views. Source context remains in link tooltips; client indexes/unknown IDs never become queries. No new browser, decoder, schema or graph relationship. Cloud projection/browser regression coverage is added; runtime/catalog identity review and paired packet evidence remain pending.


### 3D Viewer texture diagnostic follow-up — 2026-10-10

- [x] Material alpha diagnostics moved from the full-width bar above the map into the Info drawer; label now clarifies disabling transparency is debug-only and may create expected black billboard rectangles.
- [x] Optional click-to-inspect client DAT scenery now identifies prefab, instance, triangle count, mirroring and the matching material alpha audit; no DAT/server modifications.
- [x] Scenery evidence inspector now captures source prefab, group instance, material alpha audit, distance, triangle count and mirrored flag; optional prefab isolation is view-only and exportable as JSON.
- [ ] Determine whether distant vegetation uses authored LOD geometry or runtime switching from actual client DAT evidence, not only visual overlap.
- [ ] Bastok Markets / Bastok Markets [S] missing floors/buildings remain separate unverified rendering issues.
- [ ] Browser acceptance in affected zones with normal/default alpha (debug unchecked).

## Unified Live Client Bridge — movement control + research capture (approved direction, 2026-10-09)

**Priority:** Promote bidirectional, low-latency Live Client development control and canonical research capture to a shared architectural milestone. The intended outcome is direct interaction with an authorized running FFXI client: observe live XYZ/heading/entities, move or guide the player toward a Toolkit-selected location, and record correlated research evidence. This is **not** path-file replay or a second Capture subsystem.

**Current reality:** Ashita observation, bounded JSONL, passive event/emote hook samples, playback, and canonical Capture ingestion exist with limited runtime and synthetic evidence. Native movement writes, verified control profiles, an operational bidirectional transport, full capture profiles, and real paired Windows evidence are **not yet implemented/validated**. Existing action enums are contracts, not active controls. Preserve the no-write fail-closed default until an authorized, version-verified adapter is tested.

### Shared architecture and ownership

- **Client providers:** Original Ashita v4 addon/API adapter first; retain Windower compatibility and evaluate existing Ashita plugins/addons, Packeteer, PacketViewer/CaptureSuite, NPCLogger, EventView and ActionView as *reference or ingest providers*, subject to actual APIs, provenance, compatibility and licensing. Optional native Windows adapter is independent and requires verified build/process identity. Do not assume an external tool exposes a writable interface merely because it captures logs.
- **Local bridge:** Versioned bidirectional localhost protocol with explicit selected client/session identity, request IDs, acknowledgments, capabilities, heartbeat/liveness, monotonic sequencing, bounded queues, retry/timeout semantics, reconnect generations and readback. Separate high-priority movement/stop/control traffic from backpressured research streams. Preserve source file/archive provenance and never silently bridge across clients or zones.
- **Live development:** Real-time XYZ/heading/target/entity observation; authorized nudge/precise XYZ movement as the first verified write; waypoint/entity destination and feedback-guided travel subsequently; calibrated 2D/3D map integration, movement progress, navmesh/height diagnostics and reviewed NPC/mob placement proposals.
- **Research Capture:** Profile-driven event/CSID, NPC interactions, combat/action, entity state, inventory, movement and packet observations, as supported by real source interfaces. Bounded original bytes and hook stage, direction, flags, timestamps/clock basis, drop/gap counts, source identity and hashes. Stream or batch through the **existing canonical Capture ingress and storage**. Reuse Packet Viewer, decoder, manual/bulk decode, Capture Query, Entity Browser, Feature Trace, evidence locators and cross-capture search. Do not create competing packet interpretation/UI/database or infer server IDs, causes or wire fidelity from timestamp proximity.
- **Sessions:** A single selected research session may associate telemetry, commands/acknowledgments, packet streams, server environment, and original capture sources using explicit provenance. Preserve uncertainty and source boundaries. Read-only observations and placement proposals must never implicitly write game memory or server DB.

### Implementation batches and acceptance gates

1. **Provider/reference inventory and interface contract:** Audit installed/published Ashita v4 addon/plugin capture and control interfaces plus the Toolkit's existing Capture formats. Document what each can observe, execute, and export, version limitations and license obligations. Define typed bridge envelopes and compatible source IDs without replacing telemetry v1 or current capture adapters.
2. **Bidirectional transport MVP:** Localhost bridge, read-only live telemetry plus simulated command request/ack/reject, client selection, liveness and restart. Enforce bounded buffers, backpressure on capture data, isolated high-priority stop commands, authorization and generation matching. CI with synthetic two-client/disconnect cases, then Windows roundtrip measurement; durable JSONL fallback remains usable.
3. **Unified passive research collection:** Add vetted capture-provider registrations and selectable bounded profiles, loss/error metrics, explicit recording start/stop and validated import into canonical Capture. Compare producer-reported packet data to independent authorized evidence. Preserve source hashes/raw bytes and stage; never change packets or make unverified opcode/cause claims.
4. **First genuine client movement:** Identify supported Ashita control API or justify independent native adapter; verify executable/module and live session. Implement one tightly bounded development-only XYZ nudge/position operation with preconditions, audit, readback, rejection/correction detection and kill switch. Prove on authorized DSP/Topaz test client; replay adapters stay read-only.
5. **Assisted navigation + spatial UI:** Exact-position, waypoint and NPC/entity destinations; feedback-loop travel with progress and interrupt/obstruction detection rather than blind path playback; calibrated Zone Editor 2D/3D marker/camera and navmesh route review. Separate client-local position changes from server-accepted movement.
6. **Correlated development/research workflows:** Toolkit-triggered *Locate → Move → Record Interaction → Inspect Capture/CSID/Feature Trace* with explicit evidence links, selected server/zone/instance context, timebase qualifications and uncertainty. No automatic SQL edits.
7. **Advanced controlled utilities and hardening:** Evaluate speed, elevation, collision/visibility controls and temporary restoration individually only with supported adapters and versioned readback. Test zoning, logout/relogin, client crash, unsupported builds, two clients, capture overload, process replacement and safe teardown on Windows.

**Milestone for original Tako-style goal:** An authorized user selects a destination in the Toolkit, issues Move, observes the **actual running character** approach it with live status and stop/recovery, and can record the resulting interaction into the existing Capture research pipeline. Report each capability separately as contract, synthetic-tested, Windows-tested or verified supported; do not equate a replay or matching packet timestamp with successful control.

**Parallel-work boundaries:** Do not displace current Wiki, Auction House or unrelated refactor work. Implement in isolated PRs, CI green before merging; controls remain disabled for unsupported clients or unverified sessions.


### 2026-10-10 — DAT Inspector decoder capability reconciliation

The DAT Inspector now distinguishes **callable installed xi-tinkerer parsers** from
empirically parsed DAT files. Missing bindings and missing registered decoder
functions are reported separately from an available decoder rejecting a DAT.
The associated format audit is in
`docs/workbench/CLIENT_ASSET_CACHE_FORMAT_AUDIT_2026-10-10.md` and bounded
regressions in `test_fixtures/test_dat_parser_capability_audit.py`.
Do not treat decoder availability as verified DAT format support, and do not bundle
copyrighted game assets or modify the Live Client bridge as part of this audit.


## Capture review workflow — 2026-10-10

- Persistent manual missing-data, invalid/suspect-data, and follow-up review items now use the existing capture review queue.
- Manual items are non-blocking by default; reviewers can explicitly quarantine a capture from derived/aggregate results until the item is resolved.
- Capture Detail can create, resolve, dismiss, and review the full history; the global Review Queue shows automated and manual items together.
- Next: automatic request fulfillment matching and tag/content-type completeness checklists using this same workflow.

### 2026-10-11 — 3D Viewer live control usability corrections

- Live Ashita position now defaults enabled, while preserving the existing explicit `live=1` URL client/zone/follow overrides. The **Heading preview** defaults to 0° instead of the obsolete 180° marker calibration; historical shared URLs specifying heading remain honored.
- Observed Entity selection is preserved across rapid telemetry refreshes: the select list is reconstructed only when entity identity/labels change, so selecting and inspecting an entity remains practical at 10/20 Hz. On client loss/zone change the selection still clears.
- Viewer toolrail has **Warp to player** (camera focus on live player, no character movement) and **Warp target** (delegates to the existing armed, zone-aware native Warp to target action). Quick warp is disabled until the native channel is armed and a map target is selected. No new write bypass or server-confirmation assertion.
- Remaining UX acceptance: real-browser test with an open dropdown during live polling, keyboard selection, missing client, toolrail layout at narrow viewports, armed/disarmed transitions and cross-zone pending target behavior.

### 2026-10-11 — Live Entity Streaming V2 (bounded implementation)

The Ashita Direct Live Bridge now samples loaded entity slots separately from the player at **2 Hz** while retaining the configured 1/5/10/20 Hz position stream. It uses the existing `capture_ashita` inventory enumerator with a **128-entity limit**, preserves entity client index, reported server ID, name, XYZ/heading, raw status/type and target roles, and sets `entities_truncated` when over the cap. The existing recording export continues to default to 32 entries. The decoder accepts up to 256 bounded entities. The 3D viewer enables Nearby entities by default and uses reported `server_entity_id` or `client_index` for its picker identity. The read-only projection and same-zone safeguards remain in place.

**Evidence limits:** loaded client entity slots are not the complete zone spawn database. This slice does not yet provide classified player/NPC/mob filters, dynamic scan cadence settings, history trails, or a validated full-zone inventory. Runtime Ashita acceptance and sustained payload/performance measurement remain required. Source identity and zone changes invalidate cached entity observations, and the map must not show disconnected/stale observations as fresh.

### 2026-10-14 — Unified 3D entity inspector / exact-ID comparison

The existing 3D Viewer spawn inspector is reused for live observations; there is no second inspector or marker restyle. Live rows explicitly distinguish reported `server_entity_id` from the ephemeral Ashita `client_index`. Missing server IDs no longer fall back to a client slot in research links or Copy ID. The inspector includes reported heading, raw status/type, client source, observation timestamp, and one-to-one *exact reported-ID* comparisons with loaded server map records (configured XYZ, Euclidean distance, optional model difference). No exact ID / multiple same-ID records are explicitly unresolved. A roaming mob's distance from its configured spawn is context, not automatically a bug.

This is an in-browser source comparison, **not** authoritative catalog identity validation, proof of spawn correctness or persistent data-gaps classification. Acceptance remains in a live Windows viewer session with a mixture of known IDs, unknown IDs, recycled slots, and moving mobs; follow with source-provenance-linked Data Gaps integration, filters and freshness presentation.

### 2026-10-14 — Live entity search and freshness UX

The existing 3D Viewer Live panel adds a bounded name/server-ID/client-slot search across received live observations without changing the overlay marker colors or creating another inspector. Live markers and selector options with observation age above 3 seconds are hidden as stale; the visible/total count reports stale and filter state. The unified inspector shows observation age and marks stale selected evidence; research links remain restricted to reported server IDs, never fallback slots. The implementation uses the observation timestamp supplied through the authenticated projection feed, not a newly invented client timestamp. Browser / real-Ashita acceptance is still required, particularly during reconnect, zoning and clock skew. Source-backed DSP/Topaz catalog verification and typed NPC/mob/player filters remain a later increment; raw entity-type integers must not be presented as verified classifications.

### 2026-10-14 — 3D Viewer entity provenance and matching correction

The unified inspector's exact reported-server-ID comparison now checks the **complete loaded map data**, not just currently visible/filtered markers. It distinguishes a normal `/zoneplot/{zone}/data.json` map record from `CAPTURE_SPATIAL_URL` capture-derived spatial observations; the latter must never be called configured server spawn coordinates. Match basis and unresolved/ambiguous IDs are shown explicitly. Live-to-record distance is diagnostic context, not a data-integrity verdict. This is still read-only UI comparison, **not** independent catalog ID validation or a Data Gaps write. Browser/live-client acceptance remains pending. Next: audited source-backed entity ID reconciliation against DSP/Topaz catalog, including zone/instance and entity-type namespaces.
