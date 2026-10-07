## 2026-09-30 — Spatial and Environment Evidence Search modules

- Added Spatial & Movement and Environment & World State modules to the modular cross-capture Evidence Search workspace.
- Spatial search combines entity position snapshots, aggregated NPC/mob path presence, POI observations, and SpawnTrack observations.
- NPC/mob path results deliberately aggregate by capture + zone + entity, reporting path-point and leg counts instead of returning every path sample as a search hit.
- Environment search uses the already-normalized WeatherTrack and ConquestTrack structured families and searches zone plus source payload text.
- Both modules preserve Data Explorer drill-down to their canonical source datasets; no inferred packet associations are introduced.
- The planned first-pass Evidence Search module set is now complete. Remaining work is richer evidence correlation, especially explicit packet relationships where provenance/correlation supports them.

## 2026-09-30 — Modular Capture Evidence Search foundation

- Replaced the two-mode Cross-capture Search presentation with a reusable evidence-module registry.
- Existing Events & Dialogue and Raw Protocol searches now live inside the same module workspace without breaking legacy mode=events / mode=packets URLs.
- Added real cross-capture modules backed by canonical data for Entities, Battle & Actions, Items & Key Items, Vendors & Shops, Crafting, and Chat & Text.
- Battle search spans action observations, HP observations, and attack-delay evidence rather than a single table.
- Items/KI search spans key-item events plus item-bearing structured observations.
- Vendor search spans ShopStock buy/sell, GuildStock, and PriceLog families already normalized into capture_structured_records.
- Crafting search uses CraftTrack structured observations, including payload text for material/result lookup.
- Chat search spans canonical capture_chat_observations plus legacy capture_caplog_chat.
- Search results use a shared evidence-card shape with Capture/Timeline/Data Explorer handoffs and Entity Profile where identity is available.
- Data Explorer coverage was expanded to canonical chat, structured records, network flows/ranges/messages, and video/OCR observations so module results never drill into an unsupported dataset.
- Spatial and Environment remain the next module families; no new ingestion/schema was introduced in this slice.

## 2026-09-30 — Zone Editor cleanup, 3D viewer fix, and packet input expansion

- Removed the legacy Zone Editor page/template from active UI navigation. /zoneplot remains only as a permanent compatibility redirect to the current /zoneplot2 editor; the shared /zoneplot/* data/mutation APIs remain because the current editor uses them.
- Fixed the Server 3D Viewer Jinja crash: a responsive CSS rule began with "{#viewer-container", which Jinja parsed as an unterminated template comment. The template now compiles normally.
- Packet Decoder bulk mode now accepts multiple uploaded files and capture bundles and runs them through the same capture-ingestion adapters used by Captures.
- Manual Packet Decoder now uses a large multiline textarea submitted by POST and accepts either plain hex or a full PacketLogger/PacketViewer hex-grid block.
- Added the provided 2025-05-01 0x037-style multiline hex-grid shape as an explicit regression fixture.
- Uploaded sources retain detected format/status, and mixed decoded rows carry their own direction/opcode/raw bytes into Open in Packet Viewer.
- No packet decoding schema semantics, capture ingestion behavior, or Zone Editor mutation APIs were changed.

## 2026-09-30 — Capture Data Explorer foundation

- Reframed /captures/query from a raw physical-table dump into a dataset-aware Capture Data Explorer.
- The 18 existing capture datasets are grouped by investigative purpose: Entities & Spatial, Battle & Actions, Events & Dialogue, Items & Progression, Protocol & Raw Evidence, Provenance & Integrity, and Capture Metadata.
- Each dataset now has a human-readable label/description and curated first-glance columns instead of rendering every database column horizontally.
- Complete physical rows remain available under per-result Raw row / provenance drill-down, preserving low-level forensic access and export fidelity.
- Raw packet rows link directly to Packet Viewer; entity-bearing rows link to Entity Profile; rows retain Capture/Timeline drill-down.
- Result page size is reduced from 200 to 100 because each result is now an evidence card rather than an ultra-wide table row.
- Capture navigation now distinguishes Evidence Search (cross-capture discovery) from Data Explorer (deep dataset/table inspection).
- CSV export remains based on the complete physical dataset and existing filters; no capture schema or ingestion semantics changed.
- Next Capture UX slice: modular Evidence Search framework, migrating Events/Dialogue and Raw Packets into reusable modules before adding Battle, Vendor, Crafting, Entity, Items/KIs and Spatial modules.

## 2026-09-30 — Bulk Packet Decode workbench routing fix

- Fixed Packet Tools' Bulk Decode action so it opens the modern coordinated Packet Viewer / Decoder in bulk mode instead of the legacy standalone bulk page.
- Bulk PacketLogger / PacketViewer text is still parsed with the existing capture-ingestion parser and decoded with the same packet decoder backend.
- Bulk results now remain inside the modern workbench and each row can open its exact direction/opcode/raw bytes in the coordinated field + raw-byte viewer.
- The legacy packets_bulk.html template was removed; /packets/bulk GET remains as a compatibility redirect and POST remains the bulk-processing endpoint.
- Added packet UI regression contracts for the Bulk Decode route and per-row viewer handoff.

## 2026-09-30 — Configurable shell branding

- Replaced the hard-coded ValhallaXI shell brand with per-install settings while retaining the existing logo/text as defaults.
- Settings can now show/hide shell branding, set custom brand text, upload a PNG/JPG/WEBP/GIF icon, or restore the default ValhallaXI icon.
- Brand changes are read per request and apply after Save without restarting the toolkit.
- Uploaded icons are validated as real images, limited to 2 MB, stored under the existing static tree, and ignored by Git as user runtime data.
- Empty brand text supports icon-only branding; disabling branding removes the shell brand entirely without affecting workspace navigation.
- Shared shell regression coverage now verifies default, custom, and hidden brand states.

## 2026-09-30 — Static Lua shop acquisition bridge

- Audited current LSB plus predecessor DSP/Topaz shop storage before implementation. LSB ordinary shops use pair-row stock tables passed to xi.shop.general / xi.shop.nation; DSP and Topaz use flat alternating item/price arrays with dsp.shop.* / tpz.shop.*; modern LSB guild inventory is centralized in scripts/data/guild_shops.lua.
- Added conservative cross-fork Lua shop adapters for those verified patterns. Detection is based on stock/call shape rather than /npcs/ path location, so supported shop definitions in NPC, zone, instance, module, or other Lua files can be extracted. Unsupported dynamic stock expressions are reported instead of guessed.
- Guild stock preserves vendor name, prices, initial/max/target stock, restock rate, no-sell flags, and shared-stock aliases.
- Unified acquisition catalog now emits SOLD_BY alongside DROP_POOL, SYNTHESIS, SYNERGY, and SCRIPTED_REWARD, preserving DSP/TOPAZ/LSB source-family provenance.
- Numeric item literals may participate in verified external-obtainability handoff. Symbolic xi.item.* literals remain unresolved until explicit item-identity reconciliation; no enum/value guess is made.
- Curio Vendor Moogle and other special/dynamic shop systems remain intentionally outside this producer until separately profiled.
- Added focused shop-parser/catalog regression and CI coverage.

## 2026-09-30 — Unified acquisition catalog foundation

- Added a source-neutral acquisition catalog over already-audited producer families: mob drops, synthesis, synergy, and scripted Lua rewards.
- Acquisition rows preserve source family/table/identity, confidence, evidence IDs, rates, recipe requirements, ingredient IDs, crystal/key-item requirements, and scripted reward provenance.
- VERIFIED DROP_POOL and SCRIPTED_REWARD item literals can now supply the external-obtainability input used by the existing recursive crafting closure.
- The catalog explicitly does not invent canonical item identities. Scripted rewards currently use opaque obtainable nodes, so graph-node reconciliation remains a separate explicit step.
- SHOP is explicitly listed as unsupported until a logical shop schema/profile is audited; no physical table assumptions are guessed.
- Added focused CI regression combining drop, crafting, synergy, scripted reward, and crafting-closure handoff.

## 2026-09-30 — Package Scope / Create / Review workflow UX

- Package Scope, Create, and Review now use the shared dense shell and a common three-stage workflow bar: Scope → Create → Review, with Package Library always available.
- Scope Review emphasizes closure/review/gate state, unresolved dependencies, and per-item decisions while moving explanatory decision guidance and guardrails behind focused disclosures.
- Per-dependency decision controls are laid out as a compact decision/reason/tags/save grid without changing review requirements or scope semantics.
- Create Package replaces the table-form layout with a compact two-column assembly form and promotes Review & Readiness immediately after creation.
- Package creation result artifacts are grouped into materialized, missing, and skipped sections rather than one long vertical result.
- Review & Readiness keeps overall status KPIs visible and groups package summary, dependency scope, execution plan, and validation package into focused evidence sections.
- Package planning, scope ledger, review gating, assembly, validation metadata, and apply-readiness semantics are unchanged.

## 2026-09-30 — Client Overview build-comparison UX refresh

- Client Overview now uses the shared dense shell and presents installed-client fingerprint, saved binaries/probes, imported snapshots, snapshot import, and build comparison as distinct workspace sections.
- Installed fingerprint remains immediately visible; binary and saved-probe detail moves behind expandable sections.
- Imported client snapshots stay directly visible with EVENT/ENTITY/DIALOG counts.
- Snapshot import moves into an on-demand form, while build comparison remains expanded as the primary cross-client workflow.
- EVENT comparison now uses compact KPI cards, with ENTITY/actor coverage and EVENT result tables grouped into focused expandable sections.
- Direct handoffs to Model Viewer, DAT Inspector, and Binary Inspector are promoted into the workspace toolbar.
- Snapshot extraction, identity ingestion, Feature Trace mirroring, comparison semantics, confidence rules, and CSV export behavior are unchanged.

## 2026-09-30 — Wiki Compiler and Research Session workflow UX

- Wiki Compiler now behaves as an evidence-review workspace: page/source lookup and build/compare actions stay at the top, claim mapping review is the primary expanded evidence surface, dual-wiki comparison is secondary/on-demand, and compiled report sections/excerpts are progressively disclosed.
- Wiki linked-entity results now have compact found/ambiguous/not-found KPI cards and per-kind expandable tables instead of one long vertically stacked report.
- Research Session Detail now behaves as a session console: compact identity/context cards, bounded Run / Replay controls, and separate expandable sections for full metadata, budgets/usage, tool transcript, proposals, and final report.
- Run/replay semantics, permission profiles, provider/model budgets, evidence links, proposal payloads, and final reports are unchanged.
- GUI regressions now protect the dense workflow contracts while retaining existing functional assertions for research execution and wiki evidence/review behavior.

## 2026-09-30 — Library and search workspace UX refresh

- Item Browser, Key Items, Dialog Browser, SQL Index Browser, Zone Browser, Assault Missions, and Binding Reference now use the shared dense shell with compact search/filter/result chrome.
- Dialog Browser retains its evidence-rich result drill-down but reduces row/header spacing and moves the explanatory copy behind About.
- Assault Missions no longer renders every mission's full client text and wiring rollup expanded at once; mission cards are expandable.
- Dialog Drift, entity Data Gaps, Domains, and Feature Checker now use compact status/navigation surfaces instead of large introductory blocks.
- Research Sessions, Research Contradictions, Evidence Detail, and Research Gaps now use consistent compact research navigation, filter bars, and count/status headers.
- Research Session creation is collapsed by default so session history remains immediately visible.
- Regression contracts compile each refreshed template and guard the canonical /researchgaps route.
- Wiki Compiler and Research Session Detail were intentionally excluded: both are workflow-heavy pages whose remaining UX problems require a dedicated information-architecture pass rather than simple density.
- Browse/search semantics, evidence rules, server/reference joins, and research logic are unchanged.

## 2026-09-30 — Captures workspace UX refresh

- Capture Detail was rebuilt as a compact evidence workspace: one action/navigation bar, high-value counters, compact metadata cards, collapsible health/provenance/edit/secondary-data sections, and an in-page NPC/entity filter.
- Capture Timeline now uses the dense shell with a sticky compact tab bar and tighter filter/panel spacing.
- Packet Browser and capture-native Packet Viewer use denser navigation, cards, and context layout; decoded field inventories collapse per browser row to avoid oversized tables.
- Cross-capture Search, raw Capture Query, New Capture, Add Files, Alignment, Source Evidence, and delete confirmation now use consistent capture-workspace navigation and compact controls.
- Capture / Video Alignment is grouped into expandable correlation/model/anchor/evidence/landmark/candidate sections instead of rendering every evidence table at once.
- Capture Help keeps a reading-oriented width but now exposes supported ingestion immediately and collapses deeper protocol/history/gap sections into expandable references.
- Capture 2D single/all-path plot pages now use the dense shell and expand to 1100–1200px responsive work areas instead of the previous 520–640px cap.
- This pass is presentation/QOL only. Capture ingestion, evidence normalization, packet decoding, timeline semantics, alignment math, provenance, and plotting coordinate logic are unchanged.
- Shared GUI regression coverage compiles and checks all refreshed capture templates.

## 2026-09-30 — Selective compact admin/list rollout

- Captures, Validation Dashboard, Validation Runs, and Package Library now use the shared dense shell and compact command/filter bars.
- High-frequency list actions are promoted into persistent compact toolbars; explanatory copy moves behind lightweight disclosures where appropriate.
- Validation and package list views preserve their existing read-only semantics and filtering behavior.
- Package Scope/Review/Create and Client Overview were intentionally left on their roomier layouts for now because they are workflow-heavy surfaces that need a more deliberate restructuring pass rather than simple density.
- Help and documentation surfaces remain reading-oriented rather than adopting dense workstation mode.

## 2026-09-30 — Compact lookup / event / packet tools rollout

- Entity Lookup now uses the shared dense shell with a compact search header and an on-demand About disclosure.
- Events / CSID Browser now uses a compact zone/query command bar and dense result header.
- Event View now uses the dense shell, tighter evidence-card spacing, and a more compact dossier header while preserving all decompile/runtime/server-reference content.
- Packet Tools now uses the dense shell, collapses explanatory copy behind About, and groups manual decode / bulk decode / opcode browsing into compact command surfaces.
- Lookup, event decompile, capture correlation, server-reference, and packet decode semantics are unchanged.
- Shared shell regression coverage now protects Entity, Events, and Packet Tools dense layouts.

## 2026-09-30 — Compact Feature Trace rollout

- Feature Trace now uses the shared dense shell and a compact trace command bar.
- The explanatory intro moves behind an About disclosure so searches and results start at the top of the workspace.
- Implementation Path cards, summaries, branch grids, and status chips use denser spacing while preserving evidence/provenance content.
- Evidence Dossier is presented as an expandable dense card, with semantic trace controls and statistics grouped directly beneath it.
- Runtime capture/packet observations move behind a collapsed disclosure by default; bounded lazy loading behavior is unchanged.
- Relationships retain their existing grouped drill-down behavior but use compact section headers.
- No Feature Trace evidence semantics, canonical identity rules, provider traversal, binding drill-down, or runtime observation logic changed.
- Shared shell regression coverage now protects the Feature Trace dense layout contract.

## 2026-09-30 — Compact Item Editor rollout

- Item Editor now uses the shared dense shell and a compact top command bar.
- Server selection and search controls are consolidated into dense toolbar surfaces.
- The long introductory explanation moves behind an on-demand About disclosure.
- The constrained batch editor is collapsed by default into a details surface instead of permanently occupying vertical space.
- Session history and selected-item controls reuse the shared dense toolbar pattern.
- The selected item editor starts closer to the top of the viewport without changing edit, DAT reconciliation, backup, journal, compare, or validation behavior.
- Shared shell regression coverage now protects the Item Editor dense layout contract.

## 2026-09-30 — Compact viewer rollout

- Model Viewer now opts into the shared dense shell, uses the shared dense side-panel/toolbar primitives, and reclaims vertical space without changing model resolution or rendering behavior.
- Server 3D Zone Viewer now opts into the dense shell, moves its long explanatory copy into an on-demand details card, uses a compact command toolbar, grows the Three.js viewport relative to available browser height, and links directly into the new Zone Editor layout for the same zone.
- Viewer rendering, client DAT parsing, capture overlays, navmesh, fly mode, and model animation semantics are unchanged by this presentation pass.
- Shared GUI regression coverage now protects the dense viewer shell contract.

## 2026-09-30 — Compact Workbench shell v2

- The shared application shell is now one persistent compact global row instead of three permanently stacked context/workspace/subsection rows.
- Primary workspaces remain directly visible on desktop; narrow layouts switch to a workspace menu without changing route ownership.
- Active-workspace subsections move into a bounded dropdown, including nested domain/tool groups and existing mutation/legacy cues.
- Project/source/target/client context remains available in a compact Context popover rather than consuming permanent vertical space.
- Shared dense-workstation primitives now cover toolbars, panels, tabs, drawers, cards, control height, and common left/right panel widths.
- `/zoneplot2` is the first dense consumer: it keeps the shared shell visible, removes its one-off hidden-header/menu hack, and reuses shared dense toolbar/panel/tab/drawer classes.
- Navigation data and canonical IA ownership remain in `workbench/gui_shell.py`; this is a presentation/layout change, not another navigation model.
- The next rollout targets Model Viewer / 3D Viewer, then Item Editor and evidence-heavy inspector pages after shell validation.

## 2026-09-30 — Feature Trace binding evidence hardening

- Provider binding-index build failures are now distinct from a successfully built index that lacks a method; failed indexes emit `INDEX_UNAVAILABLE` rather than false `NOT_INDEXED` evidence.
- Case-fold collisions preserve all registered-name candidates as `CASE_AMBIGUOUS` instead of choosing one arbitrarily.
- Duplicate binding registrations retain class/file/location summaries, and same-class implementation overload candidates are counted and bounded rather than collapsed.
- Source-read status is explicit for missing/out-of-root/read-error binding files.
- Engine summaries now expose raw-vs-deduplicated API observations, ambiguous/multi-location calls, helper binding counts, deterministic callbacks, and binding-index status.
- Focused regression covers Topaz/SOL, DSP/LUNAR, duplicate registrations, case ambiguity, index failure, path containment, helper calls, callbacks, and implementation candidates.

## 2026-09-30 — Feature Trace Lua → binding → engine drill-down

- Resolved server Lua branches now expose syntax-level direct API calls from the existing Behavior Inspector model and join those method names to binding-registration evidence from the configured provider tree.
- LSB/Topaz-style trees are indexed through SOL_REGISTER; DSP trees through LUNAR_DECLARE_METHOD. Exact, case-only, and unindexed outcomes remain distinct.
- Binding locations expose class, C++ file, registration line/excerpt, and a bounded implementation-candidate excerpt when an exact class::method definition is visible in the same source file.
- Shared-helper API calls reuse the same binding index; callback ownership comes from the existing bounded Behavior Inspector callback graph.
- A binding registration proves the Lua-to-C++ handoff name/location only. It does not by itself establish the semantics or correctness of the C++ implementation.
- Unindexed and case-only calls are review cues, not declarations that a Lua script is invalid.
- Binding Reference navigation preserves the originating Feature Trace entity context, and Behavior API nodes link directly to Binding Reference.
- The read-only /features/trace/binding.json endpoint exposes the same binding lookup evidence without mutating graph state.

## 2026-09-30 — Feature Trace source-level implementation drill-down

- Server Lua excerpts are resolved at request time from the configured LSB/Topaz/DSP checkout through the existing Behavior Inspector resolver; source text is not copied into the canonical graph or catalog database.
- Feature Trace auto-selects a Lua source only when exactly one normalized script/entity name matches inside the provider-specific tree. Multiple exact matches and fuzzy/content-only matches remain review candidates rather than being guessed.
- Resolved sources expose a bounded first-40-line preview, hooks, Behavior graph JSON handoff, and literal CSID links emitted by the existing scripted-behavior analysis.
- Server catalog roots and downstream provider-native steps expose direct SQL Index Browser links using the exact provider table and identity.
- Behavior Inspector, Event wiring, and SQL entity rows now include Feature Trace handoffs so cross-tool navigation is bidirectional.
- Source previews and cross-tool links are presentation/navigation evidence only; they do not create new canonical dependency edges or upgrade confidence.


## 2026-09-30 — Feature Trace Implementation Path diagnostics

- Implementation Path now distinguishes unique mapping, drifted IDs to one root, no mapping, partial mapping, numeric collisions, and multiple canonical roots instead of collapsing these into generic ambiguity.
- Canonical identity summaries expose recorded identifiers, direct relationship/evidence counts, bounded evidence/provenance rows, and canonical-node integrity state.
- Provider branches now report provider/domain, exact native-link counts/depth/targets, source identity/alias fields, match basis, and source inspect links where available.
- A read-only `/features/trace/path.json` endpoint exposes the same resolution/path diagnostics for troubleshooting without changing graph state.
- Missing relationships remain UNKNOWN; diagnostics explain why traversal is unavailable without inferring absence or implementation failure.
## Repository structure
- Began staged repository restructuring with `workbench/` package namespaces.
- Canonical schema, graph, and provenance implementations now live under `workbench/core/`; root modules are compatibility shims.
- Lua event surface analyzer now lives under `workbench/analyzers/server/lua_events.py`; the historical root entry point is a compatibility shim.
- No repository-wide move was attempted; subsystem migrations remain independently reviewable.

# Workbench Audit Status

## 2026-09-28 — Video OCR evidence alignment workstream

The YouTube OCR pipeline is being promoted from a transcript-oriented research aid into a provenance-aware runtime evidence producer.

The first implementation pass is scoped to:
- video-relative timestamps and frame provenance on every OCR observation;
- conservative ingestion of parsed on-screen packet observations as `VIDEO_OCR` evidence, explicitly distinct from raw/binary packet captures;
- canonical packet-node linkage suitable for Feature Trace and later server/client correlation;
- path containment/identifier hardening for OCR run and section access.

The next alignment layer will use these time-addressable observations as anchors between gameplay video, real capture/logger sessions, and screenshots of key events. Alignment must preserve uncertainty and must never infer that OCR text is equivalent to packet bytes.

Implemented in PR #76: timestamp/frame provenance now survives OCR parsing, linked captures ingest `capture_video_observations`, canonical packet edges use `VIDEO_OCR` + `INFERRED` rather than raw-packet authority, timestamp sampling uncertainty is recorded, and run/section identifiers are containment-checked before filesystem access.


Last updated: 2026-09-25

## 2026-09-25 — Binding Compatibility Engine

Added a generic, source-snapshot-aware comparator for the common C++ API/binding index produced
for Topaz, DSP, LSB, and custom server trees. It compares Lua name, wrapper class, registration
system, resolved C++ symbol, and indexed function signature without preferring SOL2 or LUNAR.

Results distinguish exact structural matches, registration representation drift,
renamed/class-drift candidates, implementation drift, bindings missing from the indexed target
surface, and unresolved or ambiguous resolution. Every result retains both snapshot IDs and the
complete source/candidate binding and function evidence. Missing results explicitly mean
`INDEXED_SURFACE_ONLY`; partial macro extraction is never promoted to proof of absence.

The JSON result includes canonical `AnalysisResult` and `Finding` records and can be imported
directly into the Workbench graph. Focused regression coverage exercises every classification,
mixed-snapshot rejection, deterministic output, provenance retention, CLI output, and graph
persistence. The engine contains no Assault, Wardrobe, or other feature-specific rules.

## Current milestone
Foundation preserved; canonical graph storage now has schema-checked core records; build-condition/generated-source evidence is indexed conservatively; packet opcode indexing now recognizes explicit switch/case and handler-registration patterns, while remaining lexical-only when no deterministic dispatch evidence exists.

## New work completed
- [x] Directly inspected the bundled dsp-engine-changes/_example_change scaffold.
- [x] Confirmed the engine-change convention is README + real scoped diff + verification evidence.
- [x] Added engine_change_index.py for evidence-first indexing.
- [x] Added docs/workbench/ENGINE_CHANGE_AUDIT.md.
- [x] Verified the existing project evidence for a real Lua/C++ API-shape mismatch in GetNPCByID.
- [x] Verified the existing mob_groups logical-vs-physical identity warning and content-duplication safeguard.
- [x] Added generic Function/FunctionSignature/Binding/EnumDefinition records.
- [x] Added conservative external-root C++ API indexing.
- [x] Added standardized AnalysisResult/Finding records.
- [x] Corrected canonical graph feature schema to match the Feature record (8 fields rather than the earlier 5-field table).
- [x] Added graph persistence for ValidationRun and a self-test covering Feature, Artifact, MigrationAction, ValidationResult, Implementation, and AnalysisResult records.
- [x] Added build_condition_index.py for conditional-compilation and generated-source evidence. It records conditions and GENERATED_FROM relationships without evaluating unknown build environments.
- [x] Kept packet opcode indexing explicitly evidence-first: token occurrence is not classified as a runtime handler.

## Priority queue
### P0 — Core
- [x] Stable main branch identified as protected baseline for rework.
- [x] Universal/core architecture defined.
- [x] Server adapter architecture defined.
- [x] Evidence/Finding model defined.
- [x] Feature/Implementation/Dependency model defined.
- [x] Canonical graph implementation (generic SQLite schema + record importer).
- [x] Standard machine-readable findings/results.
- [ ] Provenance service consolidation.

### P0 — Migration
- [x] Lua converter audited.
- [x] SQL converter audited.
- [x] Binding audit audited.
- [x] SQL live validation audited.
- [x] Initial Feature/Package graph analyzer integrated with existing package reports.
- [ ] General Feature Migration Engine.
- [x] Generic bidirectional Feature Trace engine over canonical graph.
- [x] Initial Feature Checker requirement/status evaluation over capability evidence.
- [ ] Dependency-aware package analyzer.
- [ ] Generalized validation pipeline.

### P0 — Engine
- [x] Generic EngineChange architecture defined.
- [x] Engine-change workspace audited.
- [x] Evidence-first engine-change indexer added.
- [x] C++ header/declaration index.
- [x] C++ definition/symbol index.
- [x] Enum/constant index.
- [x] Lua binding -> C++ resolution (conservative exact matching).
- [x] C++ dependency graph (conservative lexical edges).
- [x] Build-system integration analyzer (conservative source-list evidence).
- [x] Build-target records and explicit CMake source -> target relationships (lexical evidence only).
- [x] Compile-condition/generated-source analyzer (conservative evidence).
- [x] Engine migration classifier (conservative API/binding comparison).
- [x] Packet dispatch/opcode extraction patterns (conservative; requires an indexed server source tree).

### P0/P1 — Client
- [x] Item DAT architecture audited.
- [x] Client/server authority concept defined.
- [x] General Capability record and canonical graph storage.
- [x] CapabilityRequirement persistence and canonical `REQUIRES` graph relationships.
- [ ] General ClientCapability service.
- [ ] DAT asset resolver consolidation.
- [ ] Dialog drift service.
- [x] Generic EXE/DLL static analysis validated against supplied real FFXI binaries; deeper bounded byte/xref/function-candidate analysis implemented.

### P0/P1 — Runtime
- [x] Capture indexing audited.
- [x] Packet decoder audited.
- [ ] Packet -> handler -> feature relationships.
- [x] ValidationResult core record defined.
- [x] Initial validation pipeline adapter.
- [x] ValidationRun canonical record and single-run orchestration envelope.
- [ ] Multi-validator ValidationRun orchestration.
- [ ] Automated regression fixtures.

### P1 — Architecture cleanup
- [ ] Extract GUI domain services incrementally.
- [ ] Formalize LLM evidence workflow.
- [ ] Consolidate duplicated ID/entity logic.
- [x] Standardize source snapshot fingerprints (deterministic content/path SHA-256).
- [x] Attach source snapshot provenance to C++ API, dependency, build-target, finding, and analysis records.
- [x] Add generic Capability record and canonical graph persistence.

### P1+ — Domain plugins
- [ ] Assault plugin.
- [ ] Nyzul plugin.
- [ ] Salvage plugin.
- [ ] Abyssea plugin.
- [ ] Einherjar plugin.

### Latest continuation — graph relationship resolution
- Added deterministic post-import resolution of `cpp-symbol:<qualified_name>` packet/engine edges to canonical `functions.function_id` records.
- Resolved handler-symbol edges are upgraded to `VERIFIED` only when an exact qualified C++ function symbol exists; unresolved relationships remain untouched.
- Binding records already create canonical `BINDS` relationships to resolved C++ functions.
- Added conservative `build_condition_index.py` for preprocessor conditions and build-generation markers; it intentionally does not evaluate compiler environments or claim exact generated-artifact mappings.
- Packet opcode self-test CLI syntax was corrected and retained as a deterministic dispatch regression check.

### Latest continuation — provenance and capability foundation
- Added deterministic snapshot attachment to C++ API, C++ dependency, and build integration analysis output.
- Build-target source relationships now carry snapshot provenance.
- Added generic `Capability` core record and persisted capabilities in the canonical SQLite graph.
- Canonical graph self-test now exercises capability persistence and dependency-edge snapshot storage.
- Client capability remains an evidence-driven service; no EXE/DLL capability is asserted until the actual binaries are available.


### Latest continuation — Feature Trace foundation
- Added `feature_trace.py`, a domain-agnostic canonical graph traversal tool.
- Supports starting from a canonical node ID or an unambiguous partial name/identifier search.
- Supports outgoing, incoming, or bidirectional traversal with bounded depth and relationship filtering.
- Trace output preserves edge relationship, status, confidence, evidence ID, source snapshot, metadata, visited nodes, and traversal paths.
- Explicitly documents that graph connectivity is evidence navigation, not proof that a feature is implemented or absent.
- Capability requirements now also create canonical `REQUIRES` edges, allowing feature -> capability tracing.
- Wiki/reference material is designated as a future launch/navigation adapter: it can identify the canonical subject, but reference data is not promoted to server/client truth.


### Latest continuation — Feature Checker
- Added `feature_checker.py` on top of the canonical capability model.
- Checks each declared capability requirement independently and distinguishes MISSING, UNKNOWN, PRESENT_UNVERIFIED, VERIFIED, and CONTRADICTED evidence.
- Reports implementation records and validation results separately rather than treating them as proof of capability.
- Produces a descriptive aggregate state without a numeric score.
- This establishes the backend contract for the eventual GUI workflow: select a feature/entity, trace its relationships, then inspect requirement-level evidence.


### Latest continuation — system graph connector
- Added `workbench_connect.py` as the first integration adapter from the existing consolidated SQLite index into the canonical Workbench graph.
- Bridges indexed NPC identities to capture observations, Assault mission records to canonical Features, wiki pages to canonical NPCs as reference/navigation relationships, and captured packets to packet nodes.
- Creates stable node IDs such as `npc:<id>`, `feature:assault-mission:<id>`, `capture:<id>`, `packet:<opcode>`, and `wiki:page:<normalized-title>`.
- Preserves source roles: server DB is server evidence, captures are observed runtime evidence, and Wiki is reference/navigation evidence only.
- This connector intentionally creates graph relationships rather than duplicating the detailed source/index tables; the existing SQLite index remains the detailed data cache.


## 2026-09-25 — capture reverse tracing and second reference wiki

- Added `capture_backtrace.py` as the first capture-rooted reverse checker. It walks captured entities, actions, packets, spawn candidates, and event/message identifiers toward canonical server/client evidence without treating an unindexed edge as proof of absence.
- Capture numeric event identifiers are deliberately retained as `MESSAGE_OR_EVENT_ID` until packet/server-event evidence proves a CSID/startEvent/csid interpretation.
- Added `ffxiclopedia_adapter.py` for reproducible offline MediaWiki XML ingestion. FFXIclopedia is a separate reference source from BG Wiki; future conflicts are findings, not silent source selection.
- Added `docs/workbench/CAPTURE_BACKTRACE_AND_REFERENCE_WIKIS.md` documenting the reverse capture chain and dual-wiki evidence model.

- Added `workbench_connect_server.py` to import C++ API, Lua binding, enum/constant, build-target, and dependency analyzer outputs into the canonical graph while preserving source-snapshot provenance and evidence confidence.
- This establishes the first reusable server-side chain: binding → C++ function, C++ source → build target, and dependency/packet edges can now coexist with capture, feature, and capability nodes in one graph.

- Added `capture_graph_connect.py` to promote capture event identifiers into canonical server-event nodes only when the indexed `npc_event_refs` table independently confirms the literal CSID in the same zone; matched Lua event scripts are linked as artifacts. Capture action names can also create conservative inferred mob-skill candidate edges.
- This establishes the first semantic bridge from runtime capture observations into server event/script/action data while preserving `UNKNOWN`/`INFERRED` states where semantics are not proven.

- Added `lua_event_index.py`: conservative server Lua event/API surface extraction with source snapshot provenance, designed to let capture-derived CSIDs resolve into actual Lua handler context and subsequent binding/C++ analysis without assuming semantics from numeric IDs alone.


## 2026-09-25 — server graph Lua bridge

- Extended `workbench_connect_server.py` with an optional Lua event-surface input and consolidated source DB verification path.
- A Lua event is connected to a canonical server-event node only when `npc_event_refs` independently confirms the same literal event ID in the same zone and NPC script.
- Verified event → Lua function edges retain server-source snapshot provenance; Lua colon-call → binding edges remain `INFERRED` name-only candidates until object/class semantics are proven.
- The bridge therefore produces a traversable capture/event → Lua function → binding → C++ path without converting ambiguous Lua method names into false-positive class resolutions.


## 2026-09-25 — class-aware Lua binding candidate refinement

- Extended the packaged Lua event analyzer to record function parameters and conservative wrapper-class hints for conventional FFXI callback names such as `player`/`npc`/`mob` → `CLuaBaseEntity` and `instance` → `CLuaInstance`.
- These mappings are explicitly hints, not semantic proof. Unknown/local object names remain untyped.
- Updated both the server graph connector and capture graph connector to use a class hint to narrow same-name binding candidates when available; unresolved calls continue as name-only inferred candidates.
- This materially reduces false candidate fan-out for overloaded Lua API names such as `getID` while preserving conservative evidence status.


## 2026-09-25 — Lua graph bridge regression fixture

- Repaired the capture graph connector's class-aware candidate block so the source contains executable Python newlines rather than escaped newline text.
- Added `test_fixtures/test_server_lua_graph_bridge.py`, a synthetic end-to-end regression fixture for C++ API/binding import plus verified event → Lua handler and inferred class-hinted Lua → binding traversal.
- The fixture also asserts that an unmatched CSID does not create an event implementation edge and that the binding → C++ `BINDS` relationship remains present.
- This creates a durable guard for the current conservative confidence boundary: event identity may be VERIFIED by independent `npc_event_refs`; callback parameter typing remains INFERRED.


## 2026-09-25 — direct packet handler graph resolution

- Rechecked PR #2 after GitHub restrictions were removed. The branch is 153 commits ahead and 0 behind `main`; GitHub still reports the draft PR mergeable flag false, so this is not branch divergence from `main`.
- Extended `packet_opcode_index.py` to recognize an explicit `case OPCODE: handler(...)` dispatch form and emit a VERIFIED `packet -> cpp-symbol` `HANDLED_BY` edge. Plain switch/case dispatch without a directly invoked symbol remains a verified dispatch-location edge only.
- Added server-source snapshot/evidence IDs and stable edge IDs to packet relationships.
- Extended `workbench_connect_server.py` to materialize packet opcode nodes before importing packet relationships, allowing canonical graph resolution to connect exact `cpp-symbol:` handler targets to indexed C++ functions.
- The packet self-test now requires the direct handler-symbol relationship and rejects a weaker generic REFERENCES edge for that same dispatch line.


## 2026-09-25 — deterministic packet-handler symbol completion

- Extended canonical graph alias resolution for packet dispatch handlers that are emitted as unqualified `cpp-symbol:<name>` nodes.
- Exact qualified C++ symbols remain preferred. An unqualified symbol is promoted to a canonical function only when the C++ API index contains exactly one matching function name; ambiguous short names deliberately remain unresolved.
- Added `test_fixtures/test_graph_cpp_symbol_resolution.py` covering unique unqualified resolution, exact qualified resolution, and preservation of ambiguous candidates.
- This closes a practical gap between direct switch/case packet dispatch extraction and the canonical C++ function graph without guessing namespaces/classes.


## 2026-09-25 — handler dependency and build-target chain

- C++ dependency extraction now scopes namespace-qualified enum/constant uses and packet-token uses to the containing indexed C++ function definition when a conservative function span is available; file-level fallback remains for unresolved scope.
- Canonical graph resolution now maps a dependency target to an enum/constant record only when exactly one indexed symbol matches. Ambiguous symbols remain unresolved.
- Build integration now emits function → build-target `BUILDS_INTO` edges when a function definition resides in a source file explicitly associated with a CMake target. This preserves the existing caveat that CMake condition/generator evaluation has not been executed.
- Together with direct packet handler resolution, the graph can now represent `packet → handler function → enum/constant` and `packet → handler function → build target` without promoting ambiguous lexical matches.

## 2026-09-25 — capture packet implementation backtrace

- Added a synthetic regression fixture proving that decimal capture opcode `42` joins canonical `packet:0x02a` and continues through a VERIFIED packet-handler relationship to the canonical C++ function.
- `capture_backtrace.py` now canonicalizes observed opcodes before graph lookup and includes a bounded outbound `implementation_path` so a capture report can expose packet → handler → dependency/build relationships while preserving each edge’s status, confidence, and evidence ID.
- Capture observation remains runtime evidence only; handler and downstream implementation claims still require independent graph evidence.


## 2026-09-25 — feature candidate traversal design

Runtime observations should reach features only through recorded canonical relationships. Candidate paths must retain relationship IDs, evidence IDs, confidence, status, and graph distance. Reachability is navigation evidence and must not be promoted to feature ownership or requirement semantics without an explicit relationship proving that meaning.


## 2026-09-25 — explicit feature semantics

Feature Checker now reports explicit semantic graph relationships separately from capability requirement records. Only REQUIRES, IMPLEMENTS, IMPLEMENTED_BY, USES_CLIENT_CAPABILITY, and VALIDATED_BY edges sourced from the feature are surfaced in this semantic section. Generic REFERENCES or graph reachability remain navigation evidence and do not change the aggregate capability verdict.


## 2026-09-25 — Feature Checker dimension policies

Requirements, implementation, and validation remain independent evidence dimensions. Implementation and validation aggregation are now isolated policy functions with a focused regression fixture. The top-level Feature Checker status remains the capability-requirement verdict for compatibility; no combined numeric completion score is produced. Fixtures are committed but are not considered executed unless run by a runtime or CI workflow.


## 2026-09-25 — Workbench core regression CI

A dedicated GitHub Actions workflow now executes the self-contained Workbench regression fixtures on both branch pushes and pull requests. The suite is green on commit `2decb508243ea4d2b58c5424b683f17ec04b73a1` for both the push and PR #2 runs. This provides executed validation for packet identity, graph symbol/enum resolution, Feature Trace enum nodes, feature-candidate traversal, Feature Checker dimensions, semantic graph mirroring, and capture packet graph paths. Client binaries, live game runtime, and server/database integration remain outside this CI scope.


## 2026-09-25 — Evidence confidence tightening

Function-scoped enum/constant references remain INFERRED even when enum identity is exact, because lexical function ownership is not semantic proof. Qualified enum identities such as `State::READY` are now recognized against the extracted enum index. Function-to-build-target mapping now uses VERIFIED confidence only for exact source-path matches; a basename fallback is accepted only when unique and remains INFERRED, while ambiguous duplicate basenames produce no function-level build edge. The expanded Workbench regression suite is green on commit `78e8bb26847115b6bc450124eadcf14d8f09109e` for both push and PR #2 runs.


## 2026-09-25 — Evidence-aware LLM research roadmap

The existing LLM integration was audited as a narrow but useful draft assistant: Open WebUI/Ollama provider access, read-only SQLite tools, logging, and explicit unverified-draft labeling. A dedicated architecture is now documented in `docs/workbench/LLM_RESEARCH_ARCHITECTURE.md` and Phase 8 of the roadmap. The target is a provider-neutral ResearchSession/orchestration layer with typed Workbench tools, bounded snapshot-scoped source crawling, evidence/provenance trails, contradiction detection, proposal-only migration/patch generation, and model-independent evaluation fixtures. Arbitrary filesystem/SQL mutation remains outside the LLM authority boundary.

## 2026-09-25 — First public source-to-target migration smoke

The Workbench now performs a real public repository migration smoke using pinned snapshots: LandSandBoat/server `3747feee0e38ab5c0283c4fe8deea7f0a9022351` as source and archived DarkstarProject/darkstar `ee1f489efbdee2d95a4f1a6c842790da9f54306e` as target. Generic instance slicing for Excavation Duty (instance 6300) resolves the LSB SQL dependency slice and compares it against the DSP logical schema. The executed CI job found 217 source logical records requiring IMPLEMENT because the archived DSP snapshot contains no matching instance-6300 feature slice. LSB source counts were: 1 instance, 34 instance-entity memberships, 7 NPCs, 27 mob spawns, 73 mob groups, 48 mob pools, and 27 drop rows. This is an architecture/migration-gap test, not proof that all 217 records should be copied literally; later dependency-aware conversion and target-ID/collision rules must refine these actions before package generation.


## 2026-09-25 — LLM Research & Agent backlog

The existing LLM integration is confirmed to be a narrow local-model layer: `llm_client.py` connects to Open WebUI/Ollama, `llm_db_tools.py` exposes read-only SQLite research calls, `llm_log.py` records interactions, and the GUI exposes prompt/tool transcripts. The rework will preserve those safety properties but promote LLM functionality into a first-class evidence-aware research subsystem.

Priority implementation order:
1. provider abstraction and ResearchSession persistence;
2. typed Workbench tools for graph/feature/server/entity/C++/packet/capture/source queries;
3. bounded crawling of configured/pinned source repositories;
4. FindingProposal and MigrationAction proposal staging;
5. validation orchestration tools;
6. GUI evidence/proposal trails;
7. optional additional providers only behind the same tool/evidence contract.

Models may research broadly and propose changes, but they do not receive arbitrary write access to source trees, SQLite databases, DATs, or generated packages. Deterministic migration/validation services remain the only application path.


## 2026-09-25 — First real cross-fork mission E2E

A pinned public-repository end-to-end comparison now runs Excavation Duty from LandSandBoat commit `3747feee0e38ab5c0283c4fe8deea7f0a9022351` against legacy Darkstar commit `ee1f489efbdee2d95a4f1a6c842790da9f54306e`.

Executed CI verified:
- semantic mission match by unique normalized name `excavation_duty`;
- source instance ID `6300` maps to legacy DSP instance ID `21`;
- the migration planner emits `RENUMBER / AUTO_MIGRATABLE` rather than treating the numeric drift as unrelated records;
- instance membership contains 33 shared entity IDs, 1 LSB-only entity ID (`17035542`), and 8 legacy-DSP-only entity IDs in the pinned snapshots;
- the implementation script moved from modern LSB `scripts/assaults/Lebros_Cavern/excavation_duty.lua` to legacy DSP `scripts/zones/Lebros_Cavern/instances/excavation_duty.lua`, recorded as path drift rather than absence.

This is the first executed source-to-target feature slice using two real external FFXI server repositories. It validates the adapter/logical matching direction while also demonstrating that entity membership and script layout require explicit migration analysis beyond ID renumbering.


## 2026-09-25 — Flagship public cross-fork E2E moved to Ancient Vows

Assault remains in CI as a migration-drift and incomplete-content stress test, but it is no longer treated as the public completeness benchmark. The flagship public-source E2E now uses Chains of Promathia 2-5, Ancient Vows, across pinned LandSandBoat and legacy Darkstar snapshots.

The first executed Ancient Vows run verified:
- exact battlefield registry identity: BCNM/battlefield ID 960, zone 31, name `ancient_vows`;
- exact nine-Mammet entity coverage for IDs 16904193 through 16904201 between LSB YAML/template data and DSP `bcnm_battlefield.sql`;
- real implementation surfaces on both sides for the battlefield and Mammet behavior;
- modern LSB mission orchestration and era level-cap policy surfaces;
- legacy DSP mission completion embedded in the battlefield script;
- representation drift where legacy DSP stores battlefield policy/membership in SQL while modern LSB moves substantial policy into Lua/YAML.

A generic `FeatureSurface` comparison layer now models semantic artifact roles and entity coverage separately from physical paths. This allows path/layout drift to be reported without treating a different repository layout as missing implementation.

Limbus remains a candidate for legacy-preservation/audit testing rather than the primary modern-source completeness E2E because current LSB preserves old Limbus primarily under documentation after retail client-data changes.


## 2026-09-25 — Ancient Vows public E2E reaches canonical Feature Checker

The flagship public-repository E2E now runs the pinned LSB/DSP Ancient Vows feature through:
1. server adapters and real SQL/YAML/Lua source inspection;
2. logical battlefield registry comparison;
3. generic FeatureSurface comparison;
4. canonical graph persistence with snapshot-scoped entity references;
5. canonical ValidationRun/ValidationResult persistence;
6. Feature Checker.

Executed CI verifies:
- `implementation = IMPLEMENTATIONS_VERIFIED`;
- `validation = VALIDATIONS_VERIFIED`;
- `requirements = NO_REQUIREMENTS_DECLARED` (no capability requirements have yet been declared for this feature);
- exact nine-Mammet entity coverage across the two pinned snapshots;
- snapshot-scoped entity references prevent raw numeric IDs from being silently treated as cross-fork semantic identity;
- representation drift is preserved separately from validation success.

The next gap is behavioral/capability equivalence across different artifact layouts. A source-only artifact role (for example a dedicated mission script) must not automatically imply a missing target behavior when the target implements that behavior inside another artifact.


## 2026-09-25 — Domain plugin framework foundation

Phase 6 has been expanded from a list of named systems into a two-layer content model:

1. reusable content archetypes/frameworks such as simple turn-ins, multi-zone progression, battlefield instances, multi-stage missions, minigames, and repeatable system containers;
2. named system packages such as Assault that compose those reusable frameworks and add only system-specific rules.

The first plugin API now lives under `workbench/plugins/domain/` with:
- `ContentArchetype`;
- `DomainPluginSpec`;
- `PluginContext`;
- `DomainPlugin`;
- `DomainPluginRegistry`;
- declarative built-ins for reusable battlefield, quest/mission, multi-zone progression, minigame, and Assault package metadata.

The battlefield framework explicitly covers BCNM/KSNM/ISNM/ENM/mission-battlefield families as reusable shapes rather than separate core concepts. Assault composes the battlefield and quest/mission frameworks rather than duplicating them.

Ancient Vows now exercises this layer in real pinned LSB→DSP CI: it activates `framework.battlefield` and `framework.quest_mission`, while `system.assault` remains inactive. The plugin registry/composition fixture and Ancient Vows cross-fork E2E are green.

See `docs/workbench/DOMAIN_PLUGIN_ARCHITECTURE.md`.


## 2026-09-25 — Dependency-aware migration package planning

Phase 7 now has a non-destructive package-plan foundation. Existing generic MigrationAction records can be ordered from explicit canonical dependency edges, NOT_REQUIRED actions are excluded from execution planning, manual/unknown actions keep the plan in review state, and dependency cycles block the plan instead of guessing an order. The regression fixture is included in Workbench Regression CI and passed on run 272.


## 2026-09-25 — Phase 7 package pipeline foundation

The Workbench now has a non-destructive package pipeline from ordered MigrationActions through machine-readable package manifests, plan-scoped Lua/SQL conversion, plan-scoped validation, safe staging, SHA-256 materialization provenance, validation-package metadata, and reversible file apply journaling. Legacy full-folder package conversion remains supported. Live SQL/database apply and rollback are intentionally not automated yet.

Ancient Vows now exercises the package-plan and validation-package layers in the pinned LSB→DSP flagship E2E.


## 2026-09-25 — Explicit migration backend routing

Migration package steps now bind to an exact converter backend when one exists. The existing Topaz→legacy-DSP Lua and SQL converters are registered behind a generic backend registry. Unsupported routes, including current LSB→DSP artifact conversion, are marked explicitly and rejected by the legacy package converter instead of silently reusing the wrong transformation logic.

Validation-package readiness now propagates converter support: semantic compatibility and staging can still succeed while conversion readiness remains MANUAL_REQUIRED. Domain plugins can also contribute conservative migration guidance; the reusable battlefield plugin reports NOT_REQUIRED only when capability and entity coverage are aligned.


## 2026-09-25 — Battlefield reshape and generated-package milestone

The reusable battlefield plugin now models the modern LSB → legacy DSP representation split without leaking battlefield rules into the universal core. It can derive LSB battlefield policy and mob-group structure from source evidence, compare/propose DSP `bcnm_info` policy and `bcnm_battlefield` membership changes, verify legacy DSP callback-surface coverage, and classify framework-object Lua as structural adaptation rather than missing engine bindings.

The corrected Ancient Vows flagship confirms four real engine binding candidates are present in DSP with zero missing bindings, while its framework methods remain a structural representation concern. Source-derived policy, membership, and callback checks all resolve equivalent against the pinned DSP target, so no target SQL is generated.

Safe reshape proposals can now emit target-ready generated SQL artifacts, attach them to package manifests, stage them with SHA-256 provenance, and receive validation-package checks. Unified package assembly writes the manifest, validation package, source materialization journal, and generated-output journal without touching a live database.


## 2026-09-25 — Package cohesion verification

The migration package pipeline now includes a cohesion verifier for assembled workspaces. It verifies that the package manifest, validation package, source materialization journal, generated-output journal, staged files, and recorded SHA-256 hashes agree. Missing or tampered package artifacts are reported as package failures before any target application step.

This closes the review-package integrity gap between package assembly and later apply/rollback workflows.


## 2026-09-25 — Ancient Vows package cohesion gate

The flagship Ancient Vows LSB→DSP E2E now verifies the fully assembled migration workspace with the package cohesion service. The test requires manifest, validation metadata, source/generated journals, staged files, and recorded SHA-256 hashes to agree before the package is considered reviewable.


## 2026-09-25 — Apply-readiness gate

Assembled migration packages now have an explicit apply-readiness assessment. A package is READY only when package cohesion passes and validation status is READY. MANUAL_REQUIRED validation remains review-only, while cohesion failures, blocked validation, missing validation metadata, or unknown validation states block application. This gate does not apply SQL to a live database.


## 2026-09-25 — Ancient Vows apply-readiness boundary

The flagship Ancient Vows package now proves the intended safety boundary: the assembled workspace is internally COHERENT, but apply readiness remains MANUAL_REQUIRED because the LSB→DSP converter route is not yet registered as supported. Package integrity therefore does not bypass converter/validation readiness.


## 2026-09-25 — Conditional LSB→DSP Lua backend

The migration backend registry now recognizes LSB→DSP Lua through a dedicated conditional backend instead of reusing the Topaz→DSP converter implicitly. The backend only auto-converts a narrow proven-safe residual subset. Modern `xi.*` namespaces and LSB framework-object orchestration remain MANUAL_REQUIRED pending dedicated evidence-backed rewrite rules.

Package manifests preserve this as `CONDITIONAL`, validation adds a converter-preflight requirement, and the legacy package runner refuses conditional steps until preflight clears them. Ancient Vows now reports conditional Lua conversion while SQL remains unsupported, so apply readiness stays MANUAL_REQUIRED.


## 2026-09-25 — Artifact-level converter preflight

Conditional migration backends can now preflight each artifact independently against real source text. Passing files are promoted from CONDITIONAL to SUPPORTED in a derived manifest, while framework-heavy, namespace-unsafe, missing, or otherwise unresolved files remain conditional/manual-review. This does not mutate the original manifest or authorize target application by itself.


## 2026-09-25 — Ancient Vows artifact preflight

The flagship Ancient Vows LSB→DSP E2E now runs the conditional Lua backend preflight against the real pinned mission and battlefield scripts. Both artifacts correctly remain MANUAL_REQUIRED because they contain modern framework/namespace structures that have not yet received verified legacy-DSP rewrites. No file is promoted merely because the route itself is recognized.


## 2026-09-25 — Battlefield representation planning

The reusable battlefield plugin now produces a single representation plan that combines legacy DSP SQL policy, battlefield membership, and callback-surface handling. Safe additive/update SQL reshapes are distinguished from callback semantics; callback bodies are never invented. When the target callback surface is already aligned, callbacks are marked NOT_REQUIRED rather than generated.

Ancient Vows exercises this planner and resolves READY with no manual battlefield representation surfaces because its pinned DSP target already has equivalent policy, membership, and callback coverage.


## 2026-09-25 — Plugin reshape action refinement

Domain plugins can now feed safe, role-scoped MIGRATION_RESHAPE findings back into the generic migration planner. The core only understands generic source-role metadata and explicit safe_auto/proposed_action flags; it does not contain battlefield semantics.

The battlefield representation planner uses this path to mark verified source roles such as battlefield_script, level_cap_policy, and entity_registry as NOT_REQUIRED when legacy DSP already provides an equivalent representation. Ancient Vows verifies this refinement while leaving mission_script outside the battlefield plugin's authority.


## 2026-09-25 — Refined actions drive package contents

Package generation now consumes refined migration actions instead of maintaining a separate hardcoded conversion list. The generic feature planner keeps source-only roles under review until an explicit representation rule resolves them, and safe plugin reshape findings can remove those resolved roles before package planning.

For Ancient Vows, the registry and battlefield representation no longer enter the converter queue. Only the unresolved mission script remains as an executable migration step, reducing the staged source package from three artifacts to one while preserving MANUAL_REQUIRED status.


## 2026-09-25 — Ancient Vows mission representation trace

The flagship now decomposes the modern LSB mission script into explicit lifecycle requirements and traces each requirement into distributed legacy DSP target scripts. Ancient Vows currently resolves two target behaviors as represented (Misareaux status 0→1 and Monarch Linn mission completion) and two as missing in the pinned DSP snapshot (Justinius event 128 and Riverne Site #A01 status 1→2/event 100).

This confirms the remaining mission artifact is a real partial-implementation gap rather than a path/layout false positive.


## 2026-09-25 — Mission gap proposal artifacts

Mission representation gaps can now emit proposal-only generated artifacts without being treated as target-ready code. Proposal outputs are attached to the package manifest, materialized with provenance, included in cohesion checks, and force a GENERATED_PROPOSAL_REVIEW validation state.

Ancient Vows now emits two review artifacts for its verified missing DSP lifecycle surfaces: the Justinius event-128 branch and the Riverne Site #A01 status 1→2/event-100 progression. These proposals are not auto-applied and do not make the package apply-ready.


## 2026-09-25 — Generated-output cohesion path correction

The first mission proposal package exposed a verifier mismatch: generated-output journals record `relative_path`, while package cohesion previously checked only `package_path`/`path`. The cohesion verifier now accepts the generated journal's canonical relative-path field, and regression coverage includes generated proposal artifacts.

This closes a real package-integrity blind spot discovered by the Ancient Vows flagship.


## 2026-09-25 — Deterministic mission patch previews

The Workbench now has review-only source patch operations with exact anchors and in-memory preview validation. Patch operations require an exact expected occurrence count and never write target files.

Ancient Vows uses this layer to prove that both missing mission lifecycle proposals are structurally placeable in the pinned DSP target: a Justinius event-128 branch and the Riverne Site #A01 mission-status/event-100 progression. These remain proposal/review artifacts and are not auto-applied.


## 2026-09-25 — Proposal-backed package actions

The migration planner can now replace a monolithic source artifact action with an explicit REVIEW_PROPOSALS action when a domain plugin has decomposed the remaining behavior into reviewable target proposals. REVIEW_PROPOSALS stays MANUAL_REQUIRED, does not resolve to a converter backend, and does not stage the original source file.

Ancient Vows now uses this path for its mission_script role. Its package contains the two generated mission patch proposals and no longer queues or materializes the original LSB mission Lua.


## 2026-09-25 — Machine-readable patch plans

Review-only patch operations can now be packaged as a machine-readable WORKBENCH_PATCH_PLAN artifact. Each target entry records the exact operations, source SHA-256, preview SHA-256, and preview validation status so later approval/apply tooling can detect target drift before modifying files.

Ancient Vows now packages a patch plan covering its Justinius and Riverne mission gaps alongside the human-readable proposal artifacts. The plan is proposal-only and does not authorize application.


## 2026-09-25 — Drift-aware patch approval gate

Review-only WORKBENCH_PATCH_PLAN artifacts now have a drift-aware approval assessment. Before a plan can reach READY_FOR_APPROVAL, every target file must still match the reviewed source SHA-256, the exact patch anchors must replay cleanly, and the resulting in-memory preview must reproduce the reviewed preview SHA-256.

Ancient Vows now exercises this gate against the pinned DSP target. READY_FOR_APPROVAL is still not an apply action and does not modify target files.


## 2026-09-25 — Explicit human patch approval state

Technical patch readiness and human approval are now separate states. A patch plan that passes drift checks can reach READY_FOR_APPROVAL, but deterministic apply remains ineligible until a matching WORKBENCH_PATCH_APPROVAL_REQUEST record is explicitly APPROVED. Approval records are bound to the exact patch-plan SHA-256.

Ancient Vows now packages a PENDING approval request for its mission-gap patch plan and verifies execution eligibility remains AWAITING_APPROVAL.


## 2026-09-25 — Approved deterministic patch apply

The Workbench now has a deterministic patch apply/rollback service behind both technical readiness and explicit human approval. It revalidates the reviewed patch plan against the current target, refuses PENDING/unmatched approvals, backs up every target file, writes an apply journal with before/after hashes, and supports rollback.

Regression coverage uses temporary files only. Ancient Vows remains AWAITING_APPROVAL and is not applied to the pinned DSP target.


## 2026-09-25 — Patch-plan approval linkage integrity

Package cohesion now verifies that every packaged WORKBENCH_PATCH_APPROVAL_REQUEST is cryptographically linked to an actual packaged WORKBENCH_PATCH_PLAN by SHA-256. A swapped, stale, missing, or malformed approval request/patch plan pair now fails the top-level package cohesion gate.

Ancient Vows exercises this linkage because its package contains both the mission-gap patch plan and its PENDING approval request.


## 2026-09-25 — Unified patch lifecycle status

Patch-package consumers now have one lifecycle assessment instead of reconstructing state from multiple artifacts. The lifecycle service evaluates package cohesion, patch-plan technical readiness, approval state, optional apply journals, and target drift to report states such as AWAITING_APPROVAL, ELIGIBLE_FOR_DETERMINISTIC_APPLY, APPLIED, ROLLED_BACK, DRIFTED, or PACKAGE_FAILED.

Ancient Vows now reports AWAITING_APPROVAL directly from its assembled package and pinned DSP target.


## 2026-09-25 — Read-only patch lifecycle CLI

The unified patch lifecycle service is now exposed through `python -m workbench.cli.patch_status <package_root> <target_root>`. The command is read-only, reports the authoritative lifecycle as JSON, and can optionally consume an apply journal. It does not approve or apply patches.


## 2026-09-25 — Unified package review summary

Assembled migration packages now expose one review summary combining manifest identity, execution/exclusion counts, generated-artifact count, validation status, package cohesion, apply readiness, and patch lifecycle.

Ancient Vows now reports AWAITING_APPROVAL through this consolidated package review summary, with one remaining review action and four generated review artifacts.


## 2026-09-25 — Read-only package review CLI

The consolidated package review summary is now exposed through `python -m workbench.cli.package_review <package_root> <target_root>`. The command reports migration identity, action/artifact counts, validation, cohesion, apply readiness, and patch lifecycle as JSON without granting approval or write authority.


## 2026-09-25 — Lua local type propagation

Lua event analysis now preserves conservative wrapper-class hints beyond callback parameters. Direct local aliases inherit the callback parameter class, and returned-object classes can be supplied through an explicit return-type hint table. The server graph bridge preserves the hint source (parameter, alias, or configured return type) while CALLS edges remain INFERRED.

No method-name guessing or confidence upgrade is performed.


## 2026-09-25 — Evidence-backed Lua return typing

Lua event analysis can now derive returned-object wrapper hints directly from the indexed C++ API surface. A hint is accepted only when a Lua binding resolves to a C++ function whose indexed return type names another wrapper class present in the same binding surface. Local aliases and returned objects therefore carry provenance-rich class hints without method-name guessing.

The server graph bridge preserves these hints as INFERRED CALLS evidence; no class hint upgrades an implementation edge to VERIFIED.


## 2026-09-25 — DSP packet dispatch resolution

Packet indexing now recognizes the pinned legacy DSP runtime dispatch table pattern `PacketParser[opcode] = &SmallPacket...` and emits VERIFIED HANDLED_BY edges directly to the real C++ handler symbol. Generic opcode references remain INFERRED and are not promoted to runtime handlers.

A focused regression fixture now covers this dispatch path.


## 2026-09-25 — Canonical implementation dependency chain

The graph resolver now resolves exact namespaced enum dependencies such as `State::READY` to canonical enum nodes while preserving the original edge confidence. Combined with existing binding→function and function→build-target edges plus verified packet-handler resolution, the Workbench can represent packet→handler, binding→function, function→enum/constant, and function→build-target relationships in one canonical graph.

A dedicated integration regression covers this chain.


## 2026-09-25 — Package analyzer canonical graph import

The legacy Feature/Backport Package Analyzer now emits canonical graph-compatible Feature, Artifact, DependencyEdge, Migration, and MigrationAction records while preserving its compatibility fields. It can optionally import those records directly into the Workbench graph through `--graph-db`.

Regression coverage verifies the analyzed package becomes queryable through canonical graph tables.

## 2026-09-25 — Legacy evidence graph bridges

The remaining legacy evidence paths now feed canonical graph records. `entity_profile` field provenance can import as Evidence + Finding records with explicit contradiction findings when sources disagree, reusing an existing NPC identifier when possible. Namespace-map confidence checks can import identifier-presence Evidence + Findings while preserving that name presence is only INFERRED semantic confidence.

Capture/packet graph integration already existed, so this closes the immediate entity_profile/map-confidence/capture/packet ingestion queue item.


## 2026-09-25 — ValidationRun suite orchestration

The validation layer now supports deterministic multi-validator suites. Independent dimensions remain separate, each validator produces a canonical ValidationResult, and the suite produces one canonical ValidationRun with per-dimension status metadata. Required failures determine the overall run state without hiding optional or dimension-specific results.

The legacy single-validator CLI remains compatible, while `validation_pipeline.py --suite ... --graph-db ...` can execute a suite manifest and persist the run/results into the Workbench graph.


## 2026-09-25 — Backport package GUI service extraction

The `/backport/package` GUI route now delegates conversion, binding/sanity checks, SQL collision/duplication checks, and report generation to `workbench.migrations.legacy_package_service`. The route retains its existing form/template contract while business orchestration moves behind a reusable Workbench service.

A service-level regression covers successful workflow execution plus invalid-package and verify-only error boundaries. This is one bounded extraction step; the GUI remains intentionally incremental rather than being rewritten wholesale.


## 2026-09-25 — Phase 8 research foundation

The evidence-aware research layer now has an implemented foundation rather than architecture-only documentation:

- persistent ResearchSession storage with pinned source/target snapshots, budgets, replay metadata, tool transcripts, proposal staging, and verification state;
- explicit READ_ONLY_RESEARCH / PROPOSE_CHANGES / VALIDATION_ORCHESTRATOR permission profiles;
- provider-neutral LLM contracts plus an Open WebUI compatibility adapter backed by the existing llm_client implementation;
- a typed, permission-aware research tool registry that logs tool calls and evidence IDs into ResearchSession history;
- a bounded read-only source crawler with configured roots, include/exclude globs, extension allowlists, file/byte budgets, and no write surface;
- native canonical graph.search / graph.trace research tools with bounded traversal and preserved evidence/confidence/status;
- a bounded provider/tool research runner that enforces tool/provider-call budgets and persists only a DRAFT/INCOMPLETE report state.

No model-generated conclusion is promoted directly to canonical truth, and no research path receives direct source/package/database mutation authority.


## 2026-09-25 — Typed research domain tool expansion

The research layer now exposes typed read-only Workbench tools beyond generic graph/source access:

- feature.inspect / feature.check
- entity.lookup
- binding.lookup
- packet.lookup / packet.handlers
- validation.inspect / validation.status
- server.symbol / cpp.symbol
- server.enum / enum.lookup
- server.build-target / build.target
- capability.inspect
- migration.inspect

These tools read canonical Workbench records, return evidence IDs/confidence/status where available, and run through the permission-aware ResearchToolRegistry so calls are recorded in ResearchSession transcripts. They do not expose arbitrary write operations or bypass canonical evidence semantics.


## 2026-09-25 — Capture, reference, and client/DAT research tools

The evidence-aware research layer now includes three additional read-only typed tool families:

- capture.search / capture.backtrace — indexed runtime capture discovery and capture→server/client evidence backtracing;
- reference.search / reference.compare — bundled BG Wiki/reference corpus lookup explicitly labeled REFERENCE/INFERRED rather than implementation truth;
- client.capability — canonical client capability/observation lookup;
- dat.lookup / dat.describe — read-only client item DAT record and DAT layout/capacity inspection through the existing client DAT decoder.

The capture backtrace path also received a latent packet-node identity fix so packet observations use the canonical packet identity helper. None of these tools expose DAT patch/injection, capture mutation, reference writes, or client file writes.


## 2026-09-25 — Research proposal verification gate

Research-generated changes now pass through a deterministic proposal gate before any canonical Workbench record can be created.

Implemented proposal types:
- FindingProposal
- MigrationActionProposal
- ValidationResultProposal

Authority is separated:
- PROPOSE_CHANGES may stage proposals;
- READ_ONLY_RESEARCH may inspect proposal status;
- VALIDATION_ORCHESTRATOR may verify and promote.

Verification fails closed on missing supporting evidence, missing canonical parent records, unsupported proposal shapes/actions/statuses, or contradicting evidence. VERIFIED Findings and ValidationResults additionally require at least one non-REFERENCE evidence source, so wiki/reference evidence alone cannot become canonical verified truth.

Successful promotion writes only the supported canonical record type and records verification metadata plus the promoted record id back on the staged proposal. The research runner itself still has no direct canonical mutation authority.


## 2026-09-25 — Generic client EXE/DLL research pipeline

A feature-agnostic, read-only client binary research pipeline is now implemented.

Implemented surfaces:
- dependency-free PE32/PE32+ indexing with cryptographic hashes, PE metadata, sections, RVA/file-offset mapping, imports, exports, bounded ASCII/UTF-16LE strings, and entry-point/image metadata;
- canonical graph ingestion as CLIENT_BINARY Artifact + CLIENT_SOURCE Evidence/Findings, with stable evidence identities and bounded string-corpus provenance;
- read-only typed research tools: client.binary-info, client.sections, client.imports, client.exports, client.string-search, client.address-evidence, and client.binary-diff;
- deterministic cross-index comparison by metadata, section layout, imports, exports, and encoding+text string presence;
- local-only .workbench/client-binaries/ index/cache convention, with proprietary EXE/DLL inputs remaining outside source control.

The pipeline intentionally does not contain Wardrobe-specific detectors and does not patch, hook, or write client binaries. Feature-specific research can consume this generic evidence layer without dictating core architecture.


## 2026-09-25 — Real FFXI client binary validation

The generic client binary pipeline was exercised against real FFXI client files supplied outside source control:

- FFXiMain.dll — PE32/i386, multi-section client module with a nonstandard executable POL1 section and a virtual executable .text section with zero raw bytes;
- FFXiResource.dll — conventional PE32/i386 resource/support module;
- FFXiVersions.dll — conventional PE32/i386 version/COM support module;
- FFXi.dll — smaller PE32/i386 entry/support module with a nonstandard POL1 executable section.

Static indexing successfully extracted PE metadata, section tables, imports, exports, and bounded string corpora from all four files. FFXiMain additionally demonstrated why the analyzer must surface layout limitations rather than assume a conventional raw .text section. That behavior is now represented as bounded layout-warning evidence and covered by regression.

The supplied FTABLE/VTABLE pair was also sanity-checked as a separate DAT-index evidence layer: VTABLE contains one-byte virtual-volume entries and FTABLE contains a corresponding 16-bit entry for every VTABLE record. The EXE/DLL analyzer intentionally does not absorb this DAT mapping layer.


## 2026-09-25 — Generic deeper client binary analysis

The client-binary research layer now extends beyond PE metadata/string/import/export indexing without introducing feature-specific assumptions.

Implemented:
- bounded hexadecimal byte-pattern search with one-byte wildcards, section/executable filters, result limits, and small context windows;
- conservative xref candidate recovery for relative CALL/JMP/Jcc encodings plus little-endian VA/RVA value matches;
- conservative function-entry candidate recovery from the PE entry point, exports, and executable direct-call targets;
- new read-only research tools: `client.byte-search`, `client.xrefs`, and `client.function-candidates`;
- standalone `client_binary_analyze.py` CLI for local proprietary binaries;
- dependency-free regression coverage in `test_fixtures/test_client_binary_deep.py`, now included in Workbench regression CI.

Confidence boundary:
- exact byte-pattern locations are VERIFIED observations;
- opcode-relative xrefs are INFERRED candidates because instruction boundaries are not independently decoded;
- raw VA/RVA matches are INFERRED because constants may be data;
- PE entry point/export RVAs are verified seeds, while direct-call function candidates remain INFERRED and no function-body recovery is claimed.

The original FFXI DLL uploads are not stored in source control and are not available to every execution runtime. The deeper tools therefore return `BINARY_UNAVAILABLE` when an index exists but its recorded source binary cannot be opened. This preserves provenance instead of treating absence from the current runtime as absence from the client.\n\nValidation: Workbench Regression run #1074 is green on commit `d2d55bdcb3d0553e72e62b98c5bbd2460430a040`, including `test_client_binary_index.py`, `test_client_binary_research.py`, and the new `test_client_binary_deep.py` fixture.


## 2026-09-25 — Capture → Lua → binding/C++ resolution hardening

The class-aware Lua event path is now flow-sensitive and provenance-carrying rather than a callback-parameter-only heuristic.

Implemented:
- repaired the relocated `workbench.analyzers.server.lua_events` module, removing a duplicated stale implementation and malformed regex declaration;
- callback parameter wrapper hints remain conservative seeds only;
- local aliases propagate an existing wrapper hint transitively;
- API-return assignments can derive a receiver type from indexed C++ binding/function return signatures;
- conflicting return-wrapper candidates for the same receiver/method are rejected instead of selecting one;
- unknown assignments invalidate any previously inferred local type so stale hints do not leak forward;
- emitted Lua call records now carry a class-hint trace plus the binding/function/snapshot evidence that supported an API-return hint;
- both server and capture graph connectors preserve the same PARAMETER / LOCAL_ALIAS / API_RETURN_TYPE resolution labels and metadata;
- CALLS relationships remain INFERRED. No parameter-name, alias, or return-type hint upgrades runtime object identity or implementation status to VERIFIED.

Regression coverage:
- `test_lua_event_typing.py` covers alias propagation, API-return propagation, ambiguity rejection, provenance, and reassignment invalidation;
- `test_server_lua_graph_bridge.py` is now part of the main regression workflow so capture/server Lua graph integration cannot silently drift again.


## 2026-09-25 — Generic ID/content collision analysis foundation

A source-neutral collision analyzer now operates on `ServerAdapter` `LogicalRecord` output instead of raw Topaz/DSP/LSB SQL schemas.

The analyzer distinguishes:
- `EXACT_IDENTITY_EQUIVALENT` — same adapter-defined logical identity and identical normalized non-identity fields;
- `ID_CONTENT_COLLISION` — same logical identity occupied by different normalized content;
- `CONTENT_RENUMBER_CANDIDATE` — identical normalized semantic fields under different logical identities, retained as INFERRED rather than asserted entity equivalence;
- duplicate source/target identities;
- unresolved identities with missing/null components;
- source-only and target-only records.

Identity namespaces are scoped by logical record type and the adapter-defined identity tuple. Composite identities therefore prevent a reused numeric component from being treated as a collision when its surrounding identity scope differs.

The analyzer intentionally does not use name-only equivalence and does not replace the existing canonical/entity identity model. It is an additional migration-safety analysis over normalized records. Migration-planner gating and typed research-tool exposure remain follow-on integration work.


## 2026-09-25 — Collision-aware migration planning

Generic ID/content collision findings now influence migration safety rather than remaining informational-only.

Planning behavior:
- `EXACT_IDENTITY_EQUIVALENT` becomes `NOT_REQUIRED / COMPATIBLE`;
- `ID_CONTENT_COLLISION` becomes `MANUAL_REVIEW / BLOCKED`;
- `CONTENT_RENUMBER_CANDIDATE` becomes `RENUMBER / MANUAL_REQUIRED`;
- duplicate identities block deterministic migration;
- unresolved/source-only/target-only identities remain explicit manual-review work.

The generic package planner now propagates any `BLOCKED` or `FAILED` action to package status `BLOCKED` instead of collapsing it into `MANUAL_REQUIRED`. This prevents an automatic migration package from appearing merely reviewable when a target identifier is already occupied by different content.

Renumber candidates are intentionally not AUTO_MIGRATABLE: identical normalized fields are evidence of a remap candidate, not proof that two records are the same gameplay entity.


## 2026-09-25 — Collision research tool exposure

Collision-derived migration hazards are now available through the typed read-only research layer.

New tools:
- `collision.inspect`
- `migration.collisions` (alias)

The reader queries canonical `migration_actions` joined to canonical migration records, so it exposes the same classifications that affected package safety rather than rerunning an untracked side-channel analysis. Results preserve collision classification, analyzer confidence/status, source/target logical identities, identifier namespaces, and source/target snapshot IDs, with migration-level snapshot metadata retained as a cross-check.

Filtering is available by migration, feature, and collision classification. The tools are READ-only under the existing research permission profiles and do not create or mutate migration actions.

Regression runs #1117 and #1118 are green with collision inspection coverage in `test_research_domain_tools.py`. Registry coverage also verifies the new tools are exposed only as READ tools.


## 2026-09-25 — Live target validation foundation

The Workbench now has a generic adapter-aware live database validation path that complements, but does not replace, the specialized `workbench.validation.live_db.sql_check` MariaDB tooling.

Implemented:
- `workbench.migrations.live_target_validation` compares expected adapter-normalized `LogicalRecord` records against current live target rows using target adapter physical table/column mappings;
- the live reader is DB-API based and issues SELECT-only queries;
- results distinguish VERIFIED, MISSING, CONTRADICTED, AMBIGUOUS, UNKNOWN, and FAILED live states;
- successful live comparison validates database representation only and does not imply runtime behavior;
- live results can persist as canonical `ValidationRun` and `ValidationResult` records;
- connection credentials are never persisted in canonical validation metadata;
- `python -m workbench.cli.live_target_validation` supports read-only SQLite validation and optional MySQL/MariaDB validation via `mysql-connector-python`;
- MySQL/MariaDB passwords are read from an environment variable (default `FFXI_DB_PASSWORD`) rather than accepted as a normal CLI argument.

The specialized `workbench.validation.live_db.sql_check` remains separate because it contains specialized package ID/content-duplication logic, including `mob_groups` live-conflict analysis. Existing admin/write tooling is not removed or absorbed into the generic validator.


## 2026-09-25 — Logical schema coverage audit and FeatureSurface rule expansion

The server adapter layer now has an explicit cross-profile schema-coverage analyzer instead of relying on manually inferred completeness.

`workbench.adapters.servers.schema_coverage` reports, per Topaz/Topaz-Next/DSP/LSB logical table:
- physical table name;
- adapter-defined logical identity fields;
- mapped logical fields;
- parsed physical fields;
- parsed physical fields not yet mapped into the logical model;
- identity fields lacking mappings;
- per-table coverage status.

A profile matrix makes lineage-specific representation drift visible without pretending physical schemas are interchangeable. Existing adapter mappings remain authoritative; the coverage audit does not invent mappings for unaudited tables.

FeatureSurface migration planning now emits explicit review actions for:
- source-only capabilities;
- capability status/confidence drift;
- source/target entity membership drift;
- shared semantic roles whose paths/representation differ.

These additions make migration-rule gaps first-class rather than leaving them implicit in comparison output.

Logical schema mapping is intentionally still open: item_basic, item_weapon, item_usable, spells, traits, and other broader server families need audited field mappings before full coverage can be claimed.


## 2026-09-25 — Broader item/spell/trait logical schema mappings

Logical schema coverage now includes audited mappings for:
- `item_weapon`: item identity/name, skill/subskill, item-level skill/parry/magic-accuracy adjustments, damage type, hit count, delay, damage, and unlock points;
- `item_usable`: item identity/name, valid targets, activation/animation timing, charges, use/reuse delays, and AOE;
- `spells`: identity/name plus job/group/element/targeting/skill/cost/timing/message/animation/enmity/range/content fields, with lineage drift retained;
- `traits`: composite trait identity plus job/level/rank/modifier/value/content metadata.

The profile model deliberately preserves server-lineage differences instead of normalizing them away. The legacy DSP spell profile omits the newer family field already recorded by the project audit, while the LSB spell profile carries newer radius/status-effect fields. The project DSP trait profile continues to preserve its audited legacy merit-id difference rather than inheriting a modern schema.

Regression coverage verifies cross-lineage equivalence for stable item shapes and explicit logical differences for lineage-specific spell/trait fields. Workbench Regression #1171 is green.

`item_basic` remains intentionally unmapped in this pass. Its source SQL is very large and will receive a separate audited schema extraction rather than an inferred mapping.


## 2026-09-25 — item_basic logical schema mapping

The core `item_basic` table is now represented in the server adapter logical schema.

Shared logical fields include:
- item ID and sub-ID;
- internal name and sort name;
- stack size;
- item flags;
- auction-house category;
- base sell value.

Legacy Darkstar/Topaz-era profiles retain `NoSale` as logical `no_sale`. Current LSB retains the shared fields but replaces that legacy representation with explicit `item_type` and adds `name_jp`; LSB's wider physical flags integer remains the same logical flags field.

The adapter does not collapse these differences. Cross-lineage comparison therefore surfaces the missing/added fields explicitly instead of incorrectly declaring the rows identical.

This completes logical coverage for the core item family used by current toolkit workflows: `item_basic`, `item_equipment`, `item_weapon`, and `item_usable`. The remaining Logical schema roadmap work is broader system-table coverage rather than the basic item model.


## 2026-09-25 — Phase 1 connector reconciliation

The previously open Phase 1 connector item was audited against the current branch.

Canonical bridges now exist for:
- entity_profile provenance;
- namespace/map confidence findings;
- runtime capture observations/events/actions;
- packet observations and handler traversal;
- assembled backport/package reports.

The final missing piece was BACKPORT_REPORT issue persistence. `feature_package_analyzer.py` now emits canonical report Evidence, an AnalysisResult, and Finding records for parsed report issues in addition to Feature/Artifact/Migration/MigrationAction records. The generic JSON graph importer now accepts Evidence records directly.

Workbench Regression #1189/#1190 is green after adding the complete canonical Finding shape. Phase 1 report-to-graph connectivity is therefore closed at the P0 architecture level.


## 2026-09-25 — P0 adapter and snapshot-capability closure

TopazNextAdapter and CustomForkAdapter now have explicit regression coverage beyond construction:
- Topaz-Next retains a distinct lineage/profile identity while normalizing shared logical records as TOPAZ_NEXT;
- CustomForkAdapter requires an explicit base profile, preserves base tables unless overridden, and normalized records carry the custom fork family/physical table identity;
- neither adapter mutates the base Topaz profile.

Snapshot capability production now extends beyond FeatureSurface:
- server schema mapping coverage emits per-logical-table snapshot observations;
- binding compatibility emits conservative target-snapshot binding observations, with indexed exact matches remaining INFERRED rather than promoted to runtime truth;
- live-target DB validation emits aggregate target-snapshot representation observations;
- Feature Checker already selects the target-snapshot observation when evaluating requirements.

Workbench Regression #1192 validates the adapter behavior and #1205/#1206 validates the capability producers.


## 2026-09-25 — P0 migration route matrix

The migration backend registry now exposes a deterministic support matrix across Topaz, Topaz-Next, DSP, and LSB for Lua/SQL artifact routes.

P0 does not require converters for every fork pair. The closure rule is:
- a proven backend may advertise SUPPORTED;
- a route with deterministic content gating may advertise CONDITIONAL;
- all other routes must be explicitly UNSUPPORTED;
- absence of a backend is never treated as implicit compatibility.

Current matrix highlights:
- Topaz -> DSP Lua: SUPPORTED;
- Topaz -> DSP SQL: SUPPORTED;
- LSB -> DSP Lua: CONDITIONAL;
- LSB -> DSP SQL: UNSUPPORTED;
- Topaz-Next routes do not inherit Topaz converter authority automatically.

Workbench Regression #1210 is green with route-matrix coverage.


## 2026-09-25 — Cross-fork collision and minimum client P0 closure

ID/content collision coverage now includes public cross-fork regression fixtures based on audited Darkstar/Topaz/LSB SQL shapes. The fixtures prove stable shared item_weapon identity/content equivalence and explicit same-ID normalized spell drift across legacy DSP and Topaz-era schemas. Synthetic fixtures continue to cover ambiguous, unresolved, and renumber-candidate cases.

The minimum P0 client layer is now implemented in `workbench.client.dat_adapter`:
- read-only normalized ClientDatRecord over the existing audited `item_dat_tools` parser;
- explicit ClientServerFieldBinding records for core item identity/flags/stack/type/equipment/weapon/usable fields;
- conservative field comparison that returns VERIFIED, CONTRADICTED, or UNKNOWN without inferring unbound fields;
- snapshot-scoped client DAT record capability/evidence persistence.

This P0 layer does not replace or broaden DAT write authority. Existing specialized `item_dat_tools` patch/create/delete logic remains separate; generalized Workbench DAT editing remains P1.

The full core regression step is passing after the cross-fork fixture identity-shape correction, including the client DAT adapter regression.


## 2026-09-25 — Core schema boundary and runtime P0 closure

P0 logical schema coverage is now explicitly bounded to the shared server surfaces required by the current Workbench architecture and flagship migrations: core item tables, spells, traits, instances, NPC/mob pools/groups/spawns/drops, battlefield registry/membership, and deterministic SQL extraction. The schema-coverage matrix remains the mechanism for identifying future unmapped fields/tables, but mapping every server table is not a P0 requirement.

Runtime validation P0 is also closed. Existing capture ingestion already preserves NPC state/history, paths, actions, HP/events, event packets and raw packets. Canonical capture/packet graph connectors and reverse backtrace are present, and ValidationRun/ValidationResult orchestration is persistent and dimension-aware.

A new integrated runtime regression proves:
capture-index-shaped evidence -> canonical packet observation -> capture backtrace -> deterministic runtime validation -> canonical ValidationRun/ValidationResult.

Workbench Regression #1236 is green with this integrated runtime fixture.


## 2026-09-25 — P0 architecture closure

The P0 workbench architecture is now closed on `workbench-rework/audit-foundation`.

Closure is based on implemented behavior and regression evidence rather than unchecked roadmap intent. Phase 1, Phase 2 P0, Phase 3, the P0 subset of Phase 4, and the P0 subset of Phase 5 are complete under the documented boundaries.

Final closure evidence:
- the core regression suite remains green through the schema, adapter, binding, collision, client-DAT, live-target, capture, packet, and runtime-validation additions;
- Workbench Ancient Vows Cross-Fork #129 completed successfully on the current branch head using pinned LandSandBoat and legacy Darkstar public snapshots;
- the flagship test still preserves MANUAL_REQUIRED where LSB->DSP representation/converter authority is not sufficient, rather than upgrading uncertainty to success.

P0 intentionally does not include:
- generalized DAT writing/migration orchestration;
- every SQL table in every fork;
- dialog drift or richer client packet/DAT synchronization;
- additional runtime probes beyond the current indexed/capture/backtrace/validation foundation;
- domain-specific system packages;
- GUI exposure for the new backend architecture;
- live SQL/database apply/rollback.

Those items continue in P1+ and do not reopen the P0 architectural foundation.


## 2026-09-25 — GUI information architecture and route mapping

The current GUI has been mapped into the proposed workspace architecture without changing routes, templates, navigation, or backend behavior.

Artifacts:
- `docs/workbench/GUI_INFORMATION_ARCHITECTURE.md`
- `docs/workbench/GUI_ROUTE_MAP.json`
- `test_fixtures/test_gui_information_architecture.py`

The live `gui_server.py` route surface contains 149 FastAPI method/path registrations. Every registration now has exactly one canonical GUI home and a migration disposition. The map is regression-checked so future route additions/removals must be deliberately incorporated into the information architecture.

Canonical top-level workspaces:
- Home / Project
- Features
- Domains
- Backport & Migration
- Captures
- Server
- Client
- Validation
- Packages
- Tools
- Settings

Captures remains a first-class workspace. Domains is now the first-class GUI home for system-specific development/admin workflows; its taxonomy is organizational only and does not imply implemented plugins. Assault and Nyzul Isle are grouped under Domains > Battle Systems. Zone Plot and Item Editor remain under Tools > Editors because they perform generic mutations, while domain pages may link into those tools instead of duplicating them. The current LLM/research interface is preserved for later REWORK rather than removal. The existing Backport Package route is retained as LEGACY compatibility until the future Packages workspace reaches functional parity.

Current route ownership:
- Home / Project: 3
- Features: 1
- Domains: 5
- Backport & Migration: 10
- Captures: 20
- Server: 18
- Client: 3
- Tools: 62
- Settings: 13
- Validation: 5
- Packages: 7

The high Tools count is dominated by the supporting APIs/actions of the existing Zone Editor and Item Editor and does not imply those tools will be flattened into generic navigation. The Domains count currently consists of the Assault landing page plus the existing Nyzul page/data/action routes.

No existing GUI capability was removed or hidden by this milestone.


## 2026-09-25 — Shared GUI application shell

Implemented the shared GUI shell and subsequent Domains workspace expansion without redesigning existing Nyzul/Zone Editor internals. The current FastAPI surface is 149 routes.

The shared `base.html` shell now provides:
- all eleven current top-level workspaces: Home / Project, Features, Domains, Backport & Migration, Captures, Server, Client, Validation, Packages, Tools, and Settings;
- workspace-specific subsection navigation over existing routes, with planned backend-first views shown as unavailable rather than linked to invented pages;
- first-class Captures navigation with library, import, search, query, and path views;
- persistent project/source/target/client context derived from current settings and real path availability;
- explicit `UNKNOWN` snapshot/build identities when a root exists but no selected canonical snapshot/build is recorded, and `Not configured` when no real configured/detected root is available;
- visually distinct mutation links for Zone Editor and Item Editor;
- a first-class Domains workspace with placeholder high-level categories for Abyssea, Battlefields, Battle Systems, Conflict / Battle, Combat, Dynamis, Escha, Hobbies, HELM, Events, Missions, Quests, Records of Eminence, Trust, and Other;
- Assault and Nyzul Isle grouped under Battle Systems; the existing /nyzul implementation is preserved and now owned by Domains rather than Tools;
- preserved direct access to LLM/research, Wiki, Model Viewer, legacy Backport Package, diagnostics, lookup/decode tools, and current editor workflows.

`workbench.gui_shell` owns the read-only shell model and resolves active workspace ownership from `GUI_ROUTE_MAP.json`; it does not add routes, select snapshots, or mutate settings. Validation and Packages are now functional top-level workspaces. The existing Backport Package route stays available as an explicitly labeled legacy workflow.

Regression coverage in `test_fixtures/test_gui_shell.py` reruns the 149-route information-architecture check, verifies dynamic route ownership including Domains/Battle Systems, verifies configured versus unknown context semantics, and renders representative Home, Captures, and mutation-editor templates through the shared shell. The Workbench regression workflow runs this shell test.


## 2026-09-25 — Real packed-DLL deeper pass

Real `FFXiMain.dll` deeper pass completed: mapped POL1 entry point, unmapped virtual `.text` exports, 1,678 function-entry candidates, and 22 IAT-matched FF 15/FF 25 candidates. Added read-only `client.import-refs`; all byte-scan control-flow results remain INFERRED. See `CLIENT_BINARY_RESEARCH.md`.


## 2026-09-25 — Feature Trace + Feature Checker GUI

The Features workspace now exposes the existing canonical Workbench analysis backends directly:

- `/features/trace` wraps `feature_trace.search_nodes()`, `node_info()`, and `trace()` for evidence-preserving graph navigation;
- `/features/check` wraps `feature_checker.resolve_feature()` and `check_feature()` for requirement, implementation, and validation status inspection;
- both pages are read-only and open the existing canonical `workbench.db` only when it already exists and contains the required graph tables; opening the GUI does not create an empty graph database;
- Feature Checker preserves separate requirements, implementation, and validation dimensions and does not synthesize a numeric score;
- Feature Trace preserves status, confidence, evidence IDs, and the existing warning that connectivity is navigation evidence rather than proof of implementation;
- the GUI route surface is now 137 method/path registrations and remains covered by the route-map regression.


## 2026-09-25 — Validation workspace GUI

Validation is now a functional top-level workspace rather than a shell-only placeholder:

- `/validation` provides a read-only dashboard over canonical `ValidationRun` and `ValidationResult` history;
- `/validation/runs` supports run/name/feature search and status filtering;
- `/validation/runs/{run_id}` shows run identity, source/target snapshots, feature association, timestamps, result types/statuses, evidence IDs, and notes;
- pages reuse the existing canonical `workbench.db` and do not create an empty graph database when it is missing or uninitialized;
- no new validators, aggregate scores, or inferred validation semantics were introduced;
- Live Target is exposed separately from persisted history browsing so connection/input handling remains explicit;
- the GUI route surface is now 140 method/path registrations.


## 2026-09-25 — Live Target Validation UI

The Validation workspace now exposes `/validation/live-target` as a safe GUI over the existing adapter-aware live database validator:

- GET renders the normalized-record input and target connection form; POST runs validation;
- the JSON input contract matches `workbench.cli.live_target_validation` rather than introducing a second representation;
- SQLite connections use read-only URI mode; MySQL/MariaDB passwords are read only from the selected environment variable and are never persisted;
- validation remains SELECT-only through `DBAPITargetReader` and existing server adapters;
- per-record differences and VERIFIED/MISSING/CONTRADICTED/AMBIGUOUS/UNKNOWN/FAILED states are presented without inventing a score;
- optional persistence writes only canonical validation/capability evidence and records `credentials_persisted=False`;
- database representation success remains explicitly separate from runtime, packet/capture, Lua, and client validation;
- the GUI route surface is now 142 method/path registrations.


## 2026-09-25 — Packages workspace GUI

Packages is now a functional top-level workspace with a read-only first implementation:

- `/packages` discovers assembled migration-package workspaces beneath the configured project/backport root by locating `WORKBENCH_PACKAGE_MANIFEST.json`;
- package discovery shows migration/feature identity, source/target family, manifest status, and execution-step count without modifying package contents;
- `/packages/review` calls the existing consolidated package-review service and presents overall status, validation status, cohesion, apply readiness, patch lifecycle, action counts, execution steps, and validation-package metadata;
- package paths are resolved beneath the configured project root and rejected if they escape that root;
- target-root input is read-only and is used only for existing patch-lifecycle drift/readiness checks;
- no approval, apply, rollback, package mutation, or target mutation action was added in this milestone;
- the existing `/backport/package` workflow remains available as explicitly labeled legacy compatibility until the new Packages workspace reaches creation/apply parity;
- the GUI route surface is now 144 method/path registrations.


## 2026-09-25 — Package creation GUI

The Packages workspace now supports canonical package generation without target application:

- `/packages/create` lists canonical migrations from `workbench.db` and accepts the source checkout root, source/target server families, and a package destination relative to the configured project root;
- POST reconstructs existing MigrationAction and Artifact records, loads explicit artifact-to-artifact dependency edges from the canonical graph, builds the dependency-aware PackagePlan, builds the standard package manifest, and calls the existing package assembly service;
- package destinations are constrained beneath the configured project/backport root and existing non-empty package folders are not overwritten;
- source artifacts are copied only through the existing package materializer, which constrains artifact paths beneath the supplied source root;
- creation writes only the reviewable package workspace (manifest, validation package, provenance/materialization journals, and planned source artifacts); it does not approve or apply changes to a target;
- successful creation links directly into Packages > Review & Readiness;
- approval/apply/rollback remain future UI work and must preserve the existing readiness, drift, explicit-approval, backup, journal, and rollback gates;
- the GUI route surface is now 146 method/path registrations.


## 2026-09-25 — Grouped Domains navigation

The Domains workspace navigation was converted from a flat arrow-prefixed placeholder list into explicit parent/child groups. The shared shell now renders grouped domain categories as disclosure menus: only high-level domains are visible initially, child subsections are revealed when the group is opened, and the group containing the active route opens automatically. Assault and Nyzul Isle remain children of Battle Systems. This is a presentation/navigation change only; route ownership and domain/plugin semantics are unchanged.


## 2026-09-25 — Package dependency closure and scope review

A first interactive dependency-closure workflow now sits between canonical migration analysis and package creation:

- `workbench.migrations.package_scope` walks bounded transitive canonical graph dependencies from MigrationAction artifact roots and records discovery path, relationship, evidence, confidence, snapshot, node type, and packageable artifact metadata;
- newly discovered transitive dependencies default to QUESTIONABLE rather than being silently included/excluded or assumed target-equivalent;
- reviewer decisions are persisted separately from graph evidence as AUTO, INCLUDE, QUESTIONABLE, TARGET_EQUIVALENT, NOT_REQUIRED, or EXCLUDE, with independent tags; target-equivalent/not-required/exclude decisions require an explicit reason;
- non-artifact transitive dependencies cannot be resolved by INCLUDE alone because there is nothing materializable yet; they must resolve to an artifact or receive an explicit reviewed disposition;
- reviewed scopes store a deterministic SHA-256 fingerprint and become STALE if dependency closure/evidence/decisions later change;
- explicit user EXCLUDE remains permitted for agency but produces a MANUAL_REQUIRED package rather than automatic apply readiness;
- `/packages/scope` exposes the review workflow, while two POST routes persist individual decisions and freeze a resolved scope;
- package creation now requires a reviewed scope, incorporates reviewed root exclusions, adds newly included transitive artifacts conservatively as MANUAL_REVIEW actions, and embeds the complete dependency decision ledger in schema-3 package manifests;
- schema-3 apply readiness requires dependency_scope.package_gate == READY; older schema-2 packages remain legacy-compatible and are visibly identified as lacking the new ledger;
- regression coverage now includes closure, reason requirements, non-artifact guardrails, review freezing, stale invalidation, and schema-3 apply gating;
- the GUI route surface is now 149 method/path registrations.

This milestone establishes review/agency/guardrails, not proof of complete FFXI dependency discovery. The next audit must compare automatic discovery against manually enumerated dependencies for a complex mob and representative instance/mission. See `PACKAGE_SCOPE_REVIEW.md`.


## 2026-09-26 — Medusa dependency proof baseline

Arrapago Reef Medusa is now the first concrete package dependency-discovery proof case. A machine-readable manual truth set lives at `test_fixtures/fixtures/dependency_truth_cross_zone_entity.json` and is documented in `MEDUSA_PACKAGE_PROOF.md`.

Verified source relationships include Medusa entity 16998862; four adjacent Lamia Exon helper entities 16998863–16998866; helper spell list 28 and skill list 171; Medusa skill list 725 with skills 1808/1809/1810/1812/1813/1814; dedicated skill scripts; the `job_special` mixin and EES_LAMIA/eagle-eye-shot dependency; Medusa loot symbols; title/text dependencies; and separate Al Zahbi/Bhaflau Besieged variants that are explicitly related but not default Arrapago package dependencies.

The proof exposes real current discovery gaps rather than declaring false closure: modern LSB zone YAML is not normalized by the current SQL-oriented server extractor; mob skill-list/spell-list membership and mob-skill definitions are not first-class logical dependency types; helper-ID arithmetic is not resolved; YAML loot is not linked to item records; require/mixin edges are not guaranteed; and Medusa-specific Lua→binding→C++ closure is not yet proven end to end.

The fixture is regression-checked so future analyzer work must preserve the full proof boundary, including the important rule that same-name Besieged variants are research relations rather than automatic package members.


## 2026-09-26 — Coiler dependency proof baseline

Coiler is now the second package dependency proof case. The machine-readable truth set is `test_fixtures/fixtures/dependency_truth_attachment_runtime.json`, documented in `COILER_PACKAGE_PROOF.md`.

The proof distinguishes inventory item identity (`xi.item.COILER = 2413`) from the internal `item_puppet` record (8583 / attachment index 135), then traces the behavior through dynamic C++→Lua attachment dispatch, `coiler.lua`, shared `automaton.lua` modifier logic, `xi.mod.DOUBLE_ATTACK`, maneuver/Optic Fiber scaling, puppetutils unlock/equip/persistence behavior, `char_pet` attachment state, and downstream automaton weapon-skill consumers of `xi.automaton.getExtraHits`.

It also establishes two dependency semantics the package model must distinguish from hard requirements: acquisition paths such as Rararoon/Ob should be reviewer-controlled scope, while Optic Fiber/Overdrive are conditional interactions that modify behavior without being prerequisites.

Current generic discovery does not yet model `item_puppet`, inventory→internal puppet identity, dynamic attachment-name dispatch, char_pet persistence, conditional interactions, acquisition-scope relations, or the complete Coiler downstream consumer fan-out. These are now explicit analyzer requirements rather than silent omissions.

The Medusa proof was also corrected in this pass: Al Zahbi/Bhaflau Medusa variants and the shared Besieged subsystem are conditionally coupled lifecycle dependencies, not automatic out-of-scope variants. At the audited LSB revision, Besieged mob lifecycle hooks exist but are empty, demonstrating that expected system behavior may need to be surfaced as an incomplete semantic dependency even when direct source traversal cannot prove it.


## 2026-09-26 — Automaton acquisition graph proof

Economizer and Heat Seeker now extend the Coiler proof into acquisition semantics. The new truth set is `test_fixtures/fixtures/automaton_acquisition_dependency_truth.json`.

The important result is that acquisition cannot be one generic edge. Economizer demonstrates shop plus externally documented quest/instance and ANNM reward paths, while Heat Seeker demonstrates shop, pooled mob drops, and an externally documented Alchemy synthesis recipe that itself depends on Iatrochemistry, a Fire Crystal, and five ingredient identities. Current LSB source contains the Heat Seeker synthesis recipe directly in `sql/synth_recipes.sql` (recipe 62525), including Iatrochemistry, crystal, and ingredient IDs. Glass Sheet is itself recipe 62531, making recursive precursor closure mandatory.

Required generic acquisition relations now include SOLD_BY, DROPPED_BY, CRAFTED_BY, REWARDED_BY, REQUIRES_INGREDIENT, REQUIRES_KEY_ITEM, REQUIRES_CRAFT, USES_CRYSTAL, and ALTERNATE_ACQUISITION. Acquisition paths must be independently reviewable from core item behavior, and selecting synthesis/reward paths must recursively expose their own prerequisite graph.

## 2026-09-26 — Client Binary/DAT Inspector pages and binary probes

- Added read-only `/datinspector` and `/binaryinspector` GUI pages (Client group) over the existing CLI/research layer; see CLIENT_BINARY_RESEARCH.md.
- Added `workbench/client/binary_probes.py`: client binary probes persisted as capability observations plus optional feature `CapabilityRequirement`s (hit VERIFIED, miss UNKNOWN). Tests: `test_fixtures/test_binary_probes.py`.
- Also this session: SQL parser salvage of corrupted legacy-DSP `mob_spawn_points` rows (`build_sql_index.py`), and `dat_extractor_bin.ensure_dat_extractor()` auto-building the gitignored dat-extractor for the four dashboard rebuilds.
- Open: probe-set files + GUI runner; Client Overview / Build fingerprint page; hand-fix 3 remaining corrupt rows in external old-dsp-reference SQL.


## 2026-09-26 — Recursive crafting/producibility closure

Server adapter profiles now normalize ordinary `synth_recipes` and `synergy_recipes` as distinct logical recipe types. A new `workbench.migrations.crafting_closure` service recursively evaluates a selected crafting acquisition path.

The Heat Seeker proof now uses current LSB server data directly: recipe 62525 yields Heat Seeker and requires Iatrochemistry plus Hecteyes Eye, Lightning Anima, Glass Sheet, Homunculus Nerves, Plasma Oil, and a Fire Crystal. Glass Sheet is recipe 62531 and recursively requires Rock Salt, Shell Powder, Silica x6, and a Fire Crystal. The closure regression verifies that Heat Seeker remains unresolved until every Glass Sheet precursor is independently obtainable; a missing Iatrochemistry key item also blocks the recipe.

Synergy is represented as a separate crafting system and requires explicit server runtime and client capability. A recipe cannot be marked viable merely because its row exists if the target/client lacks the required crafting system.

This establishes recipe recursion but not complete leaf obtainability. Shop, drop, battlefield reward, appraisal, HELM, gardening, exchange, and other acquisition analyzers still need to converge on the same acquisition graph. A package must remain unresolved when any selected crafting-path leaf lacks a proven acquisition route.


## 2026-09-26 — WotG25 branching mission proof

The Will of the World / Fate in Haze nation-quest bridge is now a dedicated mission-state proof case. The machine-readable truth set is `test_fixtures/fixtures/wotg25_branching_mission_truth.json`, documented in `WOTG25_MISSION_PACKAGE_PROOF.md`.

The proof demonstrates that mission closure is fundamentally a state-machine problem, not merely a file dependency problem. Mission 25 itself is small (Raustigne/event 149), but Mission 26 gates progression through `xi.wotg.helpers.meetsMission26Reqs`, which is an OR branch across Bastok `What Price Loyalty`, San d'Oria `Blood of Heroes`, and Windurst `Howl from the Heavens`.

The Bastok chain is fully enumerated through Beneath the Mask and What Price Loyalty: NPC actors, zones, CSIDs/events, quest Prog states, item trades, Wax Seal/Sack of Victuals/Commander's Endorsement lifecycle, zone-in triggers, reward items, and event-finish transitions. What Price Loyalty explicitly contains a not-implemented instance placeholder (event 10000), which must remain an IMPLEMENTATION_GAP rather than count as completeness.

The San d'Oria branch adds fishing key-item acquisition, trades, spawned NM/death transitions, text references, and battle content. The Windurst quest IDs and Mission-26 completion gate exist, while source search did not find the expected quest scripts, despite external reference documentation describing a large quest chain; this is now tracked as EXPECTED_BRANCH_MISSING_OR_UNIMPLEMENTED rather than silently absent.

The proof adds requirements for generic mission/quest state-machine extraction, zone-scoped CSID/event identity, event parameters/update/finish semantics, NPC/entity resolution, key-item lifecycle, OR branches, timer/day gates, default-action conflict checks, external-reference expectation edges, and separate mission viability versus completeness.

## 2026-09-26 — Wardrobe feature linked to client probe set; live toolkit on audit branch

- `client_probe_sets/mog_wardrobe.json` now defines `feature:mog-wardrobe-5-8` and marks `/wardrobe5-8` probes as requirements; `binary_inspector.save_probe_set()` upserts the feature and requirements. Real result: `UNKNOWN_REQUIRED_CAPABILITY`.
- DAT/Binary Inspector routes added to `GUI_ROUTE_MAP.json` (Client) so the nav link renders; `test_gui_information_architecture.py` counts routes dynamically instead of a stale hard-coded 134.
- `D:\Claude\mission_toolkit` now runs local branch `live-audit-foundation` tracking `origin/workbench-rework/audit-foundation` (push with `git push origin HEAD:workbench-rework/audit-foundation`). `workbench.db` was built there via `workbench_connect.py`; it is untracked and not gitignored — do not commit it.

## 2026-09-26 — Dialog drift overview (read-only)
- Added `/dialogdrift` (Client) and `dialog_drift_overview.py`; no package/migration/apply code touched.
- Reads `dialog_drift_report` + `dialog_text`; for each zone finds the single id shift that explains most mismatches. Result on the current data: 204 of 220 mismatched zones have one systematic offset (191 at -1, 13 at -6); 16 are scattered. This is INFERRED (loose text match), a hint for review, never auto-applied.
- The underlying report was last built 2026-09-06; rebuild via `build_dialog_index.py` if stale. First page load takes ~17s (cached afterwards).
- Test: `test_fixtures/test_dialog_drift_overview.py`.

## 2026-09-26 — Research gap detection (read-only)
- Added `/researchgaps` (Client) and `research_gaps.py`; graph is opened read-only and never created by the page.
- Current live graph: 4 unresolved requirements (all `feature:mog-wardrobe-5-8` wardrobe5-8 probes, UNKNOWN), 64,638 orphan NPC entities, 36,480 DISCOVERED-only relationships, 6 empty analysis tables.
- Test: `test_fixtures/test_research_gaps.py`. Does not cover the roadmap's research-plan execution item (line 256).

## 2026-09-26 — Domains framework foundation
- Added `workbench/domains/` (definitions.json + service.py), routes `/domains` and `/domains/{key}`, nav links for every Domains entry. 14 domains defined from a scan of the offline BG Wiki dump (Abyssea, Battlefields, Conflict, Combat, Dynamis, Escha, HELM, RoE, Trust, Hobbies, Events, Missions, Quests, Other).
- Read-only; touches no package/migration/apply/graph code. Test: `test_fixtures/test_domain_definitions.py`.
- Limits: entity/field lists are a first-pass framework, not verified against server schemas; globs are candidate paths checked at runtime. No per-entity list/edit/compare views yet.


## 2026-09-26 — Snapshot-aware identity resolution implementation

The legacy ID Drift concept is now generalized into a snapshot-aware identity-resolution foundation.

Implemented:

- `workbench/core/services/identity_resolver.py`
  - arbitrary source/target identity snapshots;
  - namespace-neutral identity records and persisted mappings;
  - semantic EVENT identities that do not use the raw numeric ID as identity;
  - cross-snapshot comparison and single-ID resolution;
  - `EXACT` vs `TARGET_EQUIVALENT` vs unresolved/ambiguous outcomes;
  - package-facing identity closure (`READY`, `MANUAL_REQUIRED`, `BLOCKED`);
  - caller SQLite connection settings are preserved during resolution.

- `workbench/client/identity_extract.py`
  - installed-client extraction using the existing xi-tinkerer `export-dat` contract;
  - FTABLE/VTABLE copy + SHA-256 provenance;
  - selected/all-zone dialog export;
  - portable manifest with client fingerprint and per-zone failures.

- `workbench/client/identity_snapshot.py`
  - full manifest ingestion so a multi-zone client build is registered once;
  - portable snapshots can be compared later without keeping the original install available.

- `workbench/cli/client_identity_snapshot.py`
  - CLI extraction/optional direct ingestion.

- `workbench/runtime/observed_transition.py`
  - capture transitions now retain `client_snapshot_id`.

- `workbench/runtime/identity_bridge.py`
  - typed capture EVENT/CSID values can be translated from their source client snapshot to a selected target snapshot;
  - unresolved `MESSAGE_OR_EVENT_ID` values are explicitly withheld from translation.

Regression coverage:

- `test_identity_resolver.py`
- `test_client_identity_snapshot.py`
- `test_client_identity_extract.py`
- `test_capture_identity_bridge.py`

The synthetic cross-client proof currently models one semantic event sequence shifting from 10/11/12 in an older client to 11/12/13 in a newer client. The resolver maps semantic identity rather than applying a blind numeric offset.

This closes the first structural part of **identity-resolution closure**. The next real proof requires extracting a second FFXI client build and comparing actual per-zone resources. Stronger event fingerprints beyond normalized dialog text and integration into Package Scope/Readiness remain open.


## 2026-09-26 — Event fingerprinting milestone

Snapshot-aware EVENT identity now uses decoded client event resources, not raw CSID/event numbers.

Implemented:

- event DAT extraction from the vendored FFXI-Resources zone map;
- exact bytecode SHA-256;
- decoded opcode/instruction-length structural fingerprints;
- dependency-free AST opcode-shape decoder for minimal environments;
- immediate-data reference resolution for message-id arguments;
- composite event fingerprints using referenced Retail dialog text;
- DIALOG_TEXT_ID separation from EVENT identity;
- actor-scoped source event resolution using capture actor/server ID;
- confidence-aware package identity closure.

Safety behavior:

- raw event/CSID number is never semantic identity;
- same dialog text alone is LOW confidence;
- undecoded coarse shape is LOW confidence;
- structural/composite decoded matches are HIGH;
- duplicate target candidates remain ambiguous;
- target actor IDs are not assumed equivalent to source actor IDs.

Regression coverage now includes:
`test_event_fingerprint.py` and `test_event_identity_resolution.py`, in addition to the existing
snapshot extraction and capture bridge fixtures.

The next real validation gate is comparison against a second actual FFXI client build.


## 2026-09-26 — Event identity resolver stabilized

The EVENT identity path now has a stable cross-client comparison contract.

Implemented since the initial fingerprint milestone:

- dependency-free AST decoding of vendored FFXI-EventsDump opcode definitions;
- inherited opcode argument/length resolution;
- parser implementation name removed from semantic hashes;
- portable special entity-role evidence in structural fingerprints;
- ordinary raw entity ids excluded from semantic hashes;
- unknown-opcode structural matches downgraded to LOW confidence;
- ranked EVENT resolution:
  - exact bytecode -> VERIFIED;
  - composite structure + Retail text -> HIGH;
  - fully decoded structure -> HIGH;
  - coarse/unknown structure -> LOW;
- unique-best-candidate requirement; ties remain ambiguous;
- capture bridge now uses ranked EVENT resolution at minimum HIGH confidence;
- bulk source-snapshot -> target-snapshot EVENT drift comparison;
- CLI JSON/CSV reporting via `workbench.cli.event_identity_compare`.

Current identity regressions all pass in Workbench Regression before the unrelated pre-existing Coiler
truth-fixture failure:

```text
snapshot identity resolver self-test: PASS
client identity snapshot self-test: PASS
event structural fingerprint self-test: PASS
event identity resolution self-test: PASS
installed client identity extraction self-test: PASS
capture identity bridge self-test: PASS
```

The next external validation gate is no longer synthetic: ingest a second real FFXI client build and
inspect actual cross-build EVENT drift/ambiguity distributions.


## 2026-09-26 — Target actor/entity identity resolution

EVENT resolution now treats target actor identity as independent evidence rather than assuming
source and target actor/server IDs are portable.

Implemented:

- generic snapshot-aware `ENTITY` records and source-to-target entity resolution in
  `workbench/core/services/identity_resolver.py`;
- explicit ingestion of numeric actor representations only when a semantic entity symbol is
  already established by entity-profile or ID-drift evidence;
- HIGH/VERIFIED actor mappings constrain target EVENT candidates to the mapped target actor;
- unresolved, ambiguous, and low-confidence actor mappings retain their outcome in EVENT result
  metadata and safely use the existing fingerprint ranking without a target-actor guess.

Regression: `test_event_actor_identity_resolution.py` proves actor-ID drift, duplicate target
event candidates under separate actors, ambiguous entity identity, unresolved actor mapping, and
same-actor exact mapping. The fixture is included in Workbench Regression.


## 2026-09-26 — Multi-client identity snapshots surfaced in Client Overview

The next real-client validation gate is now accessible through the GUI rather than requiring a
manual CLI sequence.

Implemented on the Client Overview surface:

- retained the existing installed-client fingerprint;
- list imported client identity snapshots from `workbench.db`;
- display build/family/region/language/source path/extraction time and
  EVENT/ENTITY/DIALOG record counts;
- identify snapshots that correspond to the currently installed client;
- import a second client directly from a client root using the existing xi-tinkerer extraction
  and manifest-ingestion services;
- extract all zones known to the canonical zone database;
- reject missing required client files, missing xi-tinkerer, duplicate snapshot ids, and
  non-empty output locations before extraction;
- store portable extracted payloads under git-ignored `client_snapshots/`;
- compare any two imported snapshots with the existing actor-aware bulk EVENT resolver;
- expose EXACT, TARGET_EQUIVALENT, ambiguous, LOW_CONFIDENCE, and unresolved totals;
- display source/target actor and event ids plus confidence, match basis, and reason;
- export the comparison as CSV.

Focused regression coverage is in `test_fixtures/test_gui_client_snapshots.py` and is included in
the Workbench Regression workflow. The existing identity, extraction, capture bridge, and shared
GUI shell regressions remain part of the same CI job.

This closes the tooling gap that previously blocked second-client validation from the GUI. The
remaining external gate is to import an actual second retail client build and inspect the resulting
cross-build identity distributions.


## 2026-09-26 — ResearchSession audit trail exposed in GUI

The Phase 8 research backend already persisted replay-oriented ResearchSession records, typed tool
calls, evidence ids, proposals, budgets, usage, and final reports. That state is now visible through
an audit-first GUI surface at `/research`.

Implemented:

- session history ordered by latest activity;
- compact tool-call/proposal counts;
- session creation for question/provider/model, permission profile, source/target snapshot context,
  feature/entity roots, and max-tool-call budget;
- no automatic provider execution from the creation form;
- detail view for budgets, usage, replay metadata, verification state, final report, typed tool
  transcript, arguments/results, and collected evidence ids;
- proposal visibility including supporting and contradicting evidence and verification requirements;
- shared-shell ownership under Tools > Research: Sessions;
- machine-readable GUI route-map coverage;
- focused `test_gui_research_sessions.py` plus the existing ResearchSession, GUI route-map, and
  shared-shell regressions in a dedicated CI job.

This improves auditability without expanding mutation authority. Provider execution/replay remains
behind the existing bounded ResearchRunner and typed permission-aware tool registry until a
separate explicit run-control UX is added.

## 2026-09-26 — Ollama Direct research provider

The evidence-aware research layer now has two provider implementations behind the same
`LLMProvider` contract:

- Open WebUI via the existing compatibility client;
- Ollama Direct via the local HTTP API.

The direct adapter supports model discovery, capability inspection, non-streaming chat, normalized
usage counters, and provider metadata. A provider factory now resolves configured provider ids
without coupling ResearchRunner to concrete provider classes.

The adapter does not silently fall back between providers. Connectivity, HTTP, and response-shape
failures remain explicit so research sessions cannot mistake an unavailable provider for an empty
or successful answer.

Regression coverage in `test_research_provider.py` is no-network and verifies Open WebUI
compatibility, Ollama Direct model/capability/chat normalization, provider selection, and explicit
unsupported-provider behavior.

## 2026-09-26 — DAT Inspector UX cleanup

The Client > DAT Inspector has been upgraded from a raw numeric-ID/raw-JSON utility into a
user-facing client-resource inspection workflow.

Selection now supports three entry paths:

- direct numeric DAT ID;
- zone + common DAT family, with the DAT ID derived automatically;
- direct client-relative DAT path such as `ROM/7/44.DAT`.

The zone selector is populated from the toolkit's canonical zone database when available. Direct
paths are restricted to files inside the configured FFXI client root and must resolve to a
`.DAT` file.

Results now present:

- file identity, DAT ID/family hint, ROM-relative path, size, and SHA-256;
- previous/next DAT navigation for ID-based inspection;
- successful vs rejected parser counts;
- human-readable parser labels and compact decoded summaries;
- collection counts/field names when a parser returns structured data;
- expandable decoded previews instead of unconditional raw JSON dumps;
- a 64-byte hex/ASCII header view for unsupported or unknown DAT formats;
- rejected parser diagnostics in a collapsed table.

The underlying parser strategy remains conservative: multiple successful parsers are shown as
separate compatible interpretations rather than forcing one guessed file type.

Focused regression coverage is in `test_fixtures/test_gui_dat_inspector.py` and includes
zone/family ID derivation, client-root path safety, parser summaries, result rendering, navigation,
and selection-mode wiring.

## 2026-09-26 — Safer variable-length EVENT opcode fallback decoding

The dependency-free EVENT fingerprint fallback no longer drops immediately to `RAW_ONLY` for every
vendored opcode class that defines `calculate_length`.

The opcode-source AST loader now extracts only a narrow, auditable subset of source-defined
length rules:

- direct byte selectors such as `data[offset + 1]`;
- literal equality/set/range comparisons;
- literal bit-mask tests;
- literal selector-to-length dictionaries with literal defaults;
- literal return lengths only.

The fallback evaluates those normalized rules without executing arbitrary vendored parser code.
Computed instruction lengths are still checked against remaining bytecode. Unsupported formulas,
unrecognized selector expressions, invalid lengths, or incomplete bytecode remain fail-closed as
`RAW_ONLY`.

Regression coverage proves representative variable-length classes including 0x1F, 0x59, 0x9D, and
0xAB, plus an intentionally unsupported dynamic formula that must remain unresolved. The full
Workbench core regression test step passes with this decoder enabled.

## 2026-09-26 — Bounded ResearchSession Run / Replay controls

The Research Sessions GUI now executes the existing bounded `ResearchRunner` without bypassing
the typed-tool or permission-profile boundaries.

The session detail page exposes explicit controls for:

- provider and model;
- maximum typed tool calls;
- maximum provider calls;
- timeout per provider call;
- temperature;
- optional provider base URL.

A session may be run in place only once. Once a transcript or final report exists, the GUI requires
**Replay** instead. Replay creates a new child ResearchSession with `replay_of` metadata, copied
question/context/permission profile, independent budgets and provider/model controls, and a fresh
tool transcript. The original session is never cleared or overwritten.

The GUI runtime registry currently exposes the canonical read-oriented graph/domain tool families
through the same `ResearchToolRegistry` used elsewhere. Provider selection uses the provider
factory (Open WebUI or Ollama Direct); permission enforcement remains inside the registry.

Run controls are persisted in replay metadata, usage/tool transcripts remain durable, and invalid
budgets/timeouts/temperature fail before provider execution.

Focused regressions cover first execution, immutable replay cloning, override persistence,
already-run protection, invalid controls, GUI rendering, route ownership, and the existing
ResearchRunner/provider/session tests.


## 2026-09-26 — Client ENTITY equivalence coverage and diagnostics

The portable client identity pipeline now extracts and ingests per-zone ENTITY name resources.
This closes the gap where actor-aware EVENT resolution could consume externally established ENTITY
mappings but normal client snapshot imports did not themselves contribute ENTITY evidence.

Added:

- dialog/entity DAT-family extraction for both zone-id ranges;
- portable `ENTITY` manifest resources and ENTITY-name parser;
- zone-scoped ENTITY identity ingestion with client-resource provenance;
- bulk ENTITY source-to-target comparison and detailed single-actor diagnostics;
- explicit ambiguity handling for duplicate target names;
- actor diagnostic metadata on every EVENT comparison row;
- Client Overview actor-identity coverage table with constraint-ready, equivalent, ambiguous, and
  unresolved counts;
- actor diagnostics in CSV export;
- corrected dialog-record counting for the actual `DIALOG_TEXT_ID` namespace.

The resolver still fails closed: duplicate or weak ENTITY evidence never becomes an actor
constraint simply because numeric ids happen to line up.


## 2026-09-26 — Research contradiction filtering and evidence drill-down

The Research workspace now exposes a read-only contradiction browser and canonical Evidence detail
surface.

Implemented:

- explicit CONTRADICTED Finding discovery;
- same-subject/same-field Finding value-conflict detection;
- cross-snapshot capability-observation disagreement detection;
- ResearchSession proposal contradiction discovery;
- filtering by ResearchSession, canonical subject, and Evidence type;
- clickable Evidence IDs from typed tool transcripts and supporting/contradicting proposal evidence;
- Evidence detail backlinks into canonical findings, relationships, validations, capabilities,
  implementations, ResearchSession tool calls, and proposals;
- dedicated Tools > Research: Contradictions navigation;
- deterministic regression coverage in both focused research CI and the full core regression job.

The feature intentionally surfaces disagreements without adjudicating them. Deterministic
verification/promotion remains a separate authority path.


## 2026-09-26 — P1 logical schema expansion: abilities and combat skills

The generic server-adapter schema now covers four additional cross-fork SQL surfaces:

- `abilities`;
- `weapon_skills`;
- `mob_skills`;
- `mob_skill_lists`.

The mappings were grounded against the archived Topaz release schema and the pinned DSP/LSB
snapshots already used by Workbench migration tests. Shared legacy fields normalize to the same
logical records while modern LSB-only radius fields remain explicit drift:

- `abilities.radius`;
- `weapon_skills.radius`;
- `mob_skills.mob_skill_aoe_radius` → logical `aoe_radius`.

Mob skill-list membership uses the composite logical identity
`(skill_list_id, mob_skill_id)`.

These records deliberately model registry/configuration metadata only. The existence of an ability
or skill row does not prove its Lua/C++ runtime implementation, packet behavior, animation support,
or client capability. Those remain separate dependency/evidence surfaces.

Regression coverage extends the existing broader logical-schema and cross-profile coverage tests.
P1 remains open for additional generic surfaces such as item modifiers/latents and progression
tables.


## 2026-09-26 — P1 logical schema expansion: item modifiers and latents

The server-adapter schema now covers three additional generic equipment-effect surfaces across
Topaz, Topaz-Next, DSP, and pinned LSB:

- `item_mods` → logical `item_modifiers`;
- `item_mods_pet` → logical `item_pet_modifiers`;
- `item_latents` → logical `item_latents`.

The audited physical shapes are compatible across the three server lineages. Logical identities
preserve physical uniqueness:

- item modifier: `(item_id, modifier_id)`;
- pet item modifier: `(item_id, modifier_id, pet_type)`;
- latent item modifier:
  `(item_id, modifier_id, value, latent_id, latent_parameter)`.

This intentionally models only the SQL assignment records. Modifier IDs, pet-type values, latent
condition IDs, and runtime behavior still require enum/engine evidence before migration can be
considered semantically verified.

Regression coverage extends both the broader cross-fork logical normalization suite and the schema
coverage matrix.


## 2026-09-26 — P1 logical schema expansion: progression

The server-adapter layer now covers job-point and merit definition drift without assuming that all
forks store progression data in the same format.

### Job points

`job_points.sql` exists in Topaz, DSP, and pinned LSB with the same physical columns, but numeric
`job_pointid` values drift between legacy and modern data. The logical identity is therefore
`(job_id, name)`, while `job_point_id` remains a comparable representation field. This allows
the Workbench to report a renumbering rather than treating the same semantic job-point entry as an
unrelated record.

### Merits

Topaz and DSP store merit definitions in `merits.sql`. Modern LSB explicitly dropped that SQL
registry and moved the definitions to `data/merits.yaml`.

The adapter now has:

- a legacy SQL `merits` logical mapping for Topaz/Topaz-Next/DSP;
- an LSB YAML producer that emits the same logical `merits` record type keyed by `merit_id`;
- shared comparable fields for `merit_id`, `name`, and `value`;
- explicit legacy-only fields such as upgrade count, jobs mask, upgrade id, and legacy category id;
- explicit LSB-only fields such as upgrade-cost key, category key/id, category max upgrades, and
  resolved job-name lists.

Missing representation-specific fields remain `MISSING_FIELD_VALUE`; they are not inferred.
Regression coverage proves both legacy equivalence and the modern representation split.


## 2026-09-26 — P1 logical schema expansion: combat support

Four additional generic server surfaces are now represented across Topaz, Topaz-Next, DSP, and
pinned LSB:

- `mob_pool_mods` → logical `mob_pool_modifiers`;
- `mob_spell_lists`;
- `skill_caps`;
- `skill_ranks`.

The audited physical schemas and primary keys match across the three lineages.

Logical identities are:

- mob pool modifier: `(pool_id, modifier_id)`;
- mob spell-list membership: `(spell_list_id, spell_id)`;
- skill-cap curve row: `level`;
- per-job skill-rank row: `skill_id`.

`skill_caps` retains all rank buckets `r0` through `r13`, while `skill_ranks` retains rank
assignments for WAR through RUN. These two surfaces can now be traced together when evaluating
skill availability/caps.

For `mob_pool_modifiers`, `modifier_id` meaning depends on the `is_mob_modifier` namespace and
the corresponding engine enums. SQL presence alone is therefore not treated as semantic proof.
Regression coverage validates cross-fork normalization and profile coverage.


## 2026-09-26 — Revised priority queue complete

The five-item revised next-work priority is complete.

Completed sequence:

1. safer variable-length EVENT opcode decoding;
2. bounded ResearchSession Run / Replay controls;
3. cross-client ENTITY equivalence coverage and diagnostics;
4. Research contradiction filtering and canonical Evidence drill-down;
5. P1 logical schema expansion beyond the P0 core.

The P1 expansion was completed through four evidence-backed tranches:

- combat registries;
- item modifiers and latents;
- progression, including LSB merit YAML representation;
- combat-support tables.

Schema breadth is no longer treated as an open-ended blocker. Additional generic mappings should be
added when a concrete feature/package or validation path exposes a missing dependency surface.


## 2026-09-26 — Generalized client DAT migration/write orchestration: PATCH_EXISTING

The first generalized Workbench client-DAT write path now bridges the read-only
`ItemDatAdapter`, migration-package review artifacts, and the mature low-level
`item_dat_tools` writer without allowing planning code to mutate client files.

Implemented:

- `ClientDatOperation` for reviewed `PATCH_EXISTING` operations;
- proposal-only `WORKBENCH_CLIENT_DAT_PLAN` generated artifacts;
- full-record client fingerprinting plus optional expected-field checks;
- re-read/drift validation before approval;
- explicit `WORKBENCH_CLIENT_DAT_APPROVAL_REQUEST` tied to the reviewed plan hash;
- approved apply that invokes the low-level writer only after technical readiness and human approval;
- apply journals containing DAT/category/record/format/target and low-level backup metadata;
- deterministic rollback by restoring the exact pre-write snapshot (or removing a newly created overlay target);
- package-integrity checks linking packaged client-DAT plans to their approval requests;
- deterministic regression coverage proving that planning does not call a writer, drift blocks
  approval, pending approval blocks apply, approved apply invokes the writer once, and rollback
  restores the original bytes.

The low-level `patch_client_item` return payload now includes additive backup/target-existence
metadata so higher-level orchestration can journal and reverse the edit.

This milestone intentionally supports existing-record patches only. New-item client allocation,
DAT injection, server SQL coordination, and any FTABLE/VTABLE/index mutation remain a separate
follow-on because they require multi-artifact identity/allocation guarantees.

## 2026-09-27 — Reconciliation audit and sample-name cleanup

A current-`main` reconciliation found several milestones newer than this audit's original queue.

### Confirmed implemented
- Variable-length EVENT decoding is implemented conservatively in `workbench/client/event_fingerprint.py`, including bounded rule extraction and fail-closed behavior for unsupported dynamic length formulas. Regression: `test_fixtures/test_event_fingerprint.py`.
- Automatic client ENTITY identity ingestion is implemented through `workbench/client/identity_extract.py` and `workbench/client/identity_snapshot.py`, with event/identity regressions. Raw client names are evidence, not guaranteed globally unique semantic identities; duplicate-name disambiguation remains future enrichment.
- P1 server logical-schema coverage has expanded in `workbench/adapters/servers/profiles.py`, `progression.py`, and `schema_coverage.py`, with coverage regressions for combat abilities/skills, item modifiers/latents, progression tables, mob support tables, skill caps/ranks, synthesis, and synergy.

### Naming audit
Repository path inspection found sample-derived generic artifact names only in two proof documents, two truth-set fixture filenames, and two regression filenames. No generic production Workbench module was named after either sample.

The artifacts were renamed by architectural role:
- `docs/workbench/COILER_PACKAGE_PROOF.md` -> `docs/workbench/DEPENDENCY_PROOF_CASE_ATTACHMENT.md`
- `docs/workbench/MEDUSA_PACKAGE_PROOF.md` -> `docs/workbench/DEPENDENCY_PROOF_CASE_CROSS_ZONE_ENTITY.md`
- `test_fixtures/fixtures/coiler_attachment_dependency_truth.json` -> `test_fixtures/fixtures/dependency_truth_attachment_runtime.json`
- `test_fixtures/fixtures/medusa_arrapago_dependency_truth.json` -> `test_fixtures/fixtures/dependency_truth_cross_zone_entity.json`
- `test_fixtures/test_coiler_dependency_truth.py` -> `test_fixtures/test_dependency_truth_attachment_runtime.py`
- `test_fixtures/test_medusa_dependency_truth.py` -> `test_fixtures/test_dependency_truth_cross_zone_entity.py`

Concrete Coiler/Medusa names remain inside those documents and truth sets where they identify real evidence. They must not be used as names for reusable services, analyzers, graph concepts, framework APIs, or generic regression roles.

### Audit rule
Proof-case naming must describe the behavior or dependency shape being tested. Game-content names belong only in subject/evidence data or deliberately content-specific plugins.


## 2026-09-27 — Generic mission/quest state-machine foundation

Added `workbench/plugins/domain/mission_state_machine.py` as a content-neutral behavioral model rather than encoding a specific mission in framework code. It provides explicit states, guarded transitions, ALL/ANY dependency gates, zone+actor+CSID event identity, generic transition effects, lifecycle analysis, expected implementation-gap visibility, and branch-readiness analysis.

`workbench/plugins/domain/mission_representation.py` now projects state-machine transitions and lifecycle subjects into representation requirements, preserving the existing proposal/review workflow instead of replacing it.

Focused regressions:
- `test_fixtures/test_mission_state_machine.py`
- `test_fixtures/test_mission_representation.py`

Next work is source extraction and canonical graph/evidence emission. The existing branching mission truth set remains a stress-validation subject; its content names do not define framework APIs.


### Branching mission ingestion proof

The existing branching mission truth set now ingests through `workbench/plugins/domain/mission_ingest.py` into the generic state-machine contract. The proof verifies nation alternatives as an `ANY` gate, zone+actor+CSID identities, Prog state ranges, key-item lifecycle semantics, and visible implementation/missing-branch gaps.

The ingestion intentionally marks truth-set CSIDs as `unassigned_progress_edge` rather than guessing which exact progress transition they cause. Exact CSID → state-edge assignment is now a concrete requirement for the Lua source extractor.

Regression: `test_fixtures/test_mission_truth_ingestion.py`.


### Multi-mission mechanic stress probe

Additional LSB mission shapes were compared against the generic model:

- **Kazham's Chieftainess** — simple linear NPC/event completion plus next mission and key-item reward.
- **Ancient Vows** — mission variable progression, zone-in event, battlefield-win guard, completion, and post-win teleport.
- **The Road Forks** — parallel mission-status channels, timed/expiring key-item lifecycle, recursive timer, spawned-NM/death gates, distance/position/nation conditions, local variables, and no-action/message outcomes.
- **Three Paths** — multiple parallel subpaths converging on completion, trade/consume gates, spawned encounters, multiple battlefields, titles, and client-handled transport.

New model/extractor gaps exposed by this probe:
- parallel named mission-status channels and ALL-path convergence;
- temporal guards/effects and timer expiry;
- spawned-entity and mob-death transitions;
- spatial/distance guards;
- explicit battlefield-result identity as a first-class guard;
- teleport/client-transport/title/message/no-action effects;
- replaceDefault/priority/default-action conflict semantics;
- stronger distinction among persistent mission vars, local vars, and mission-status channels.

Coverage fixture/regression:
- `test_fixtures/fixtures/mission_mechanic_coverage_probe.json`
- `test_fixtures/test_mission_mechanic_coverage.py`


### Mission mechanic vocabulary + LSB extractor foundation

The generic model now represents the stress-probe mechanics directly: persistent/local state channels, ALL-path convergence, timer/spatial/entity/battlefield/trade conditions, and spawn/transport/title/message/timer/no-action effects. Dispatch semantics such as `replaceDefault()` remain extractor/evidence metadata rather than behavioral effects.

Added `workbench/plugins/domain/mission_lsb_extract.py` as a conservative static LSB Lua extractor foundation. It recognizes literal zone/actor/events, mission-status writes, persistent/local variable writes, key-item lifecycle calls, battlefield-win checks, spawned entities, titles, timers, and mission completion. Exact guard → trigger/CSID → effect transition correlation remains the next extractor step.


### LSB handler correlation and source-proven state edges

The LSB extractor now correlates literal Mission DSL handler blocks into `MissionTransition` records. It preserves zone/actor/CSID identity, handler trigger kind, literal guards, and literal effects with source-line metadata. A second conservative pass materializes concrete channel-value state endpoints only when a single literal channel guard/write proves the edge; ambiguous multi-channel handlers remain unresolved rather than guessed.

Regression: `test_fixtures/test_mission_lsb_correlation.py` covers an Ancient Vows-shaped trigger/event-finish/battlefield completion flow including CSID 6, mission Status writes, battlefield 32001 guard, completion, and teleport.


### Cross-handler mission event chaining

The LSB extractor now joins initiating NPC/zone/trade handlers to a unique same-zone `onEventFinish[CSID]` handler. The resulting logical transition preserves initiating actor identity, zone+CSID identity, combined guards/effects, and both source spans. Same numeric CSIDs in different zones cannot collide.

Declarative Mission DSL actor handlers such as `['Actor'] = mission:progressEvent(114)` are now extracted as unconditional NPC triggers and participate in the same chaining pass. Dispatch modifiers such as `replaceDefault()` and `importantEvent()` are retained as metadata.

Regression coverage includes a Kazham's Chieftainess-shaped declarative completion edge and Ancient Vows-shaped NPC, zone-in, state-write, battlefield, completion, and teleport flows.


### The Road Forks real-source stress pass

Pinned the current LSB `scripts/missions/cop/3_3_The_Road_Forks.lua` as a regression fixture and ran the generic extractor against its full mission shape.

The first pass exposed six parser gaps: local mission-status aliases, zone-out handlers, helper/timer behavior outside mission sections, entity spawned-state guards, message-return outcomes, and the final two-path convergence check. All six are now represented/extracted in the current stress probe:
- local aliases propagate to named mission-status channel guards;
- `onZoneOut` is a first-class transition trigger;
- `:isSpawned()` / negated spawn checks become entity conditions;
- San d'Oria + Windurst terminal status is recovered as an ALL completion gate;
- player helper functions such as `jewelTimer` emit timer/helper behavior;
- message calls become MESSAGE effects.

Regression: `test_fixtures/test_mission_lsb_road_forks_stress.py`.


### Three Paths real-source worst-case stress pass

Pinned current LSB `scripts/missions/cop/5_3_Three_Paths.lua` and exercised the generic mission extractor across its three parallel subpaths.

The stress pass exposed and then promoted into generic extraction support:
- helper-defined three-path completion convergence (`LOUVERANCE/TENZEN/ULMIA == 14`);
- dynamic mission-status range iteration used by `isMissionComplete()`;
- not-equal mission-status guards;
- exact player-position guards;
- `npcUtil.popFromQM` spawned encounters;
- completed-trade effects;
- mission-level reward title/next-mission metadata;
- helper-call completion gates attached to completion handlers;
- client-handled transport annotations;
- event priority / important-event / replace-default dispatch provenance.

The current Three Paths probe has no remaining mechanic marked as an unsupported gap. This does not imply arbitrary Lua is fully parsed: dynamic expressions/helpers outside recognized conservative patterns remain evidence requiring later parser expansion.

Regression: `test_fixtures/test_mission_lsb_three_paths_stress.py`.


### Scripted-NM content-map stress — Absolute Virtue

Absolute Virtue was used as the first non-mission behavior-map stress case, with both its own LSB script and Jailer of Love's spawning script treated as one evidence closure.

This content does not naturally reduce to mission CSID/state progression. It adds a generic combat-behavior map over the same canonical evidence graph:
- entity lifecycle/combat hooks;
- cross-entity death -> probabilistic delayed spawn;
- runtime enmity/claim transfer;
- cross-entity local-state dependencies;
- HP-threshold phase transitions;
- randomized recurring action windows;
- player-action response and mutable ability-lock sets;
- dynamic combat modifiers;
- spell behavior overrides;
- magic-hit/day-element responses;
- related-entity death/despawn cleanup;
- runtime loot-table override.

The key architectural finding is that the canonical graph can remain shared, while scripted NMs require a combat-behavior extractor/plugin rather than being forced through the mission state-machine representation.

Probe: `test_fixtures/fixtures/absolute_virtue_behavior_probe.json`
Regression: `test_fixtures/test_absolute_virtue_behavior_probe.py`


## 2026-09-27 — Feature Trace Evidence Dossier and runtime drill-down

Feature Trace now treats semantic topology and high-cardinality runtime observations as separate presentation domains. A presentation-only Evidence Dossier summarizes root identity, semantic facet counts, and runtime/capture counts without manufacturing relationships or treating missing facets as proof of absence.

Runtime evidence is summarized as opcode/semantic group → capture. Raw observations are omitted from the initial trace payload and are available only through the bounded `/features/trace/runtime.json` drill-down (maximum 250 observations per request). Runtime edges continue to stay out of semantic traversal topology, while semantic `OBSERVED_*` relationships without runtime/capture evidence remain available to validation/semantic views.

Relationship sections now render their own classified edge members rather than repeating the complete semantic edge list under every heading. Catalog-only objects remain valid dossier roots even when no canonical dependency edges exist.

This is a presentation/navigation milestone. It does not claim that every indexed source has an explicit catalog provider yet, nor that the populated local databases were validated in this GitHub-only execution environment.


### Feature Trace catalog provider boundary

Feature Trace catalog discovery now has an explicit provider registry for the established server SQL/index families (core SQL, LandSandBoat, Topaz, and DSP). Providers declare table identity columns, display-name columns, object type, and provenance without creating canonical graph relationships.

The prior schema-based table discovery remains as a compatibility fallback for custom/older indexes and is labeled `schema-fallback` in catalog provenance. This is intentionally incremental: client, capture, research, validation, and package providers can move behind the same registry later without a flag-day rewrite.


### Feature Trace evidence-domain providers

The catalog-provider registry now covers durable searchable records from Client, Captures, Research, Validation, and Packages in addition to the server SQL families.

Included provider roots:
- Client: identity snapshots and identity records.
- Captures: capture bundles only.
- Research: research sessions and proposals.
- Validation: validation runs and validation results.
- Packages: migrations, migration actions, and package scope reviews.

High-cardinality runtime internals such as raw packets, capture history rows, capture event rows, and research tool calls are intentionally excluded from catalog discovery. They remain drill-down evidence rather than top-level catalog objects.

Catalog-only roots continue to produce a valid Evidence Dossier even when they have no canonical semantic edges. Provider/domain provenance is shown in search results and dossier identity.


### Provider-backed Feature Trace inspection

Catalog providers can now expose a bounded set of source-native scalar fields for catalog-only roots without converting those fields into canonical graph relationships.

Current examples include:
- client snapshot family/build/source/fingerprint context;
- client identity namespace/numeric ID/zone/actor/confidence/evidence;
- capture mission/build/content metadata;
- research session/proposal state;
- validation run/result status and subject context;
- migration/package status, target/source snapshot context, and scope review state.

Where a stable GUI detail route already exists, the dossier also exposes an internal "Open source view" link. Provider IDs used in path parameters are URL-encoded before rendering.

This is inspection metadata only. It does not alter dependency topology, evidence authority, validation status, or migration readiness.


### Source-native provider links

Feature Trace now exposes a small set of exact source-schema links for catalog-only records without promoting those links into canonical graph topology.

Current links:
- client identity record -> client snapshot;
- research proposal -> research session;
- validation result -> validation run;
- migration action -> migration;
- package scope review -> migration.

These links are one-way and source-native by design. Reverse one-to-many expansion is not performed, preventing client snapshots, runs, or migrations from exploding into large catalog trees. Users can follow a link to the related catalog root and inspect it there.

The catalog resolver now checks both `workbench.db` and `ffxi_zone_database.db` when a second catalog connection is supplied. This fixes a boundary bug where Workbench-native catalog results (Client/Research/Validation/Packages) could appear in search but fail to resolve when opened from the GUI.


### Composite catalog identity safety

Feature Trace catalog providers now support composite source identities. Server `mob_groups` records are keyed by `(zoneid, groupid)`, so catalog discovery no longer treats `groupid` as globally unique.

Search results now emit stable composite IDs such as:
`catalog:lsb_mob_groups:zoneid=75&groupid=38`

Legacy single-key IDs such as `catalog:lsb_mob_groups:38` resolve only when that group ID is unique in the indexed table. If multiple zones contain the same group ID, resolution returns UNKNOWN rather than selecting an arbitrary row.

Known provider table names are also reserved when their schema does not match the declared provider contract. A malformed or version-drifted known table is not reinterpreted through the heuristic schema fallback.


### Deterministic server-source catalog links

Feature Trace now asks a server adapter for a narrow set of exact source-native relationships encoded by the indexed SQL schemas. These remain dossier navigation links and are not inserted into canonical semantic topology.

Current server-source links:
- item equipment/weapon/usable record -> item_basic with the same item ID;
- mob group -> mob pool through mob_groups.poolid;
- mob spawn point -> zone-scoped mob group through mob_spawn_points.groupid plus the zone decoded from the entity ID.

The mob-spawn relationship uses the same FFXI entity-ID zone encoding already used elsewhere in the toolkit: `(entity_id >> 12) & 0xFFF`. Because mob-group catalog identities are composite `(zoneid, groupid)`, duplicate group IDs in different zones resolve to the correct group instead of an arbitrary row.

Each server-derived link exposes a short evidence basis in the Feature Trace dossier. The FFXI-specific decode lives under `workbench/adapters/servers`, not in the generic catalog core.


### Provider alias search and match provenance

Feature Trace provider discovery now searches declared source-native aliases in addition to the provider's primary identity and display-name columns.

Current examples include:
- client identities: numeric ID, zone key, actor key, owner key, and evidence ID;
- client snapshots: family, source location, and fingerprint;
- captures: capturer, content type, zones, mission name, and client build;
- research sessions/proposals: provider/model, feature/entity roots, session ID, proposal type, and state;
- validation: feature/subject/run/evidence/source/target context and status;
- migrations/packages: source/target snapshots, migration/artifact IDs, status, and reason.

Search results expose a `matched_on` field and the GUI shows it explicitly. These aliases improve discovery only; they do not create canonical identities or graph relationships.


### Expanded server catalog coverage

Explicit server catalog providers now include durable named records for mob skills and pets across the core SQL, LandSandBoat, Topaz, and DSP indexes. Status effects are also explicit provider objects where the corresponding fork index exists, while preserving fork provenance.

Pets expose a deterministic source-native `PET_USES_POOL` link through `pet_list.poolid`. Mob skills and status effects are discovery/inspection objects only in this milestone; no behavioral dependency is inferred from their presence.

Unnamed bridge tables such as `blue_spell_list`, `mob_droplist`, and `instance_entities` remain excluded from top-level catalog discovery until they have an explicit stable identity/presentation contract.


### Instance membership catalog records

Feature Trace providers now support unnamed source tables through explicit generated-label contracts. The first use is server `instance_entities`, whose durable identity is the composite `(instanceid, id)`.

An instance-membership record is presented with a generated label such as `Instance 100 entity 17000001` and exposes only deterministic source-native links:
- `INSTANCE_MEMBER_OF` -> the matching `instance_list` record;
- `INSTANCE_ENTITY_NPC` -> an NPC record only when the exact ID exists in that fork's `npc_list`;
- `INSTANCE_ENTITY_MOB` -> a mob spawn record only when the exact ID exists in that fork's `mob_spawn_points`.

The entity type is not inferred from the numeric ID alone. These records remain catalog/source navigation evidence and are not inserted into canonical semantic topology.


### Blue Magic wiring catalog records

The server provider layer now exposes `blue_spell_list` as an explicit unnamed bridge object across core SQL, LandSandBoat, Topaz, and DSP. Its stable identity is `spellid`, with `mob_skill_id` retained as source detail/search provenance and a generated display label such as `Blue spell wiring 500`.

Each wiring record exposes only exact same-fork source-native links:
- `BLUE_SPELL_SPELL` -> the matching `spell_list.spellid`;
- `BLUE_SPELL_MOB_SKILL` -> the matching `mob_skills.mob_skill_id`.

This makes Blue Magic ID wiring directly discoverable and navigable without asserting that the linked spell or mob skill is behaviorally correct or implemented.


### Server event/CSID reference catalog

The shared `npc_event_refs` index is now an explicit Feature Trace provider. Each row uses its real composite identity `(source, zone_name, npc_script, csid)` and a generated label that preserves fork, zone, actor script, and CSID.

This deliberately does not treat CSID as globally unique. If the same CSID appears for multiple sources/scripts/zones, all records remain independently discoverable and a legacy CSID-only catalog ID is rejected as ambiguous rather than selecting one row.

These are source-script event references, not proof that the client event exists or that the corresponding mission transition is correct.


### Key-item catalog providers

Feature Trace now exposes the three key-item catalogs that are actually persisted by the current indexers:
- `keyitems_ours` as the LandSandBoat-primary server key-item catalog;
- `topaz_keyitems` as the Topaz server key-item catalog;
- `keyitems_external` as retail/reference evidence.

DSP has no corresponding persisted key-item table in the current DSP index and is intentionally left UNKNOWN rather than synthesized from another source.

Because `keyitems_ours` and `keyitems_external` do not have database primary-key constraints, the generic catalog resolver now verifies that single-column provider identities are unique before resolving them. Duplicate logical IDs fail closed as UNKNOWN instead of selecting the first row.


### Mob group/pool provider inspection context

Feature Trace mob-group providers now expose source-native inspection context when present: `poolid`, `dropid`, respawn time, and min/max level. Mob-pool providers expose `familyid` and `modelid`.

`poolid`, `dropid`, `familyid`, and `modelid` are searchable aliases with `matched_on` provenance. This improves investigation of server records without creating synthetic drop-row objects or asserting gameplay semantics from the numeric values alone.


## 2026-09-27 — Mission source extraction to canonical graph evidence

The generic mission/quest extractor can now project its state-machine output into ordinary Workbench graph records through `workbench/plugins/domain/mission_graph_emit.py`.

The projection emits:
- a canonical mission `Feature`;
- the Lua source `Artifact` plus a `DISCOVERED` implementation record;
- mission-state and transition entities;
- reusable server event identities keyed by source family + zone + actor + CSID;
- source-family/zone actor identities where the actor is known;
- feature-scoped mission-local state subjects;
- source-visible key-item/title/battlefield/entity symbols;
- evidence-backed `HAS_STATE`, `HAS_TRANSITION`, `FROM_STATE`, `TO_STATE`, `TRIGGERED_BY_EVENT`, `EVENT_ACTOR`, `REQUIRES`, and `AFFECTS` relationships.

Extractor confidence and implementation status are preserved. Static source evidence never upgrades inferred transitions to VERIFIED, and implementation presence is recorded as DISCOVERED rather than runtime-correct.

Mission-local channels such as `mission_var:Status` are feature-scoped so unrelated missions cannot collapse onto the same graph node. Server event identities are intentionally reusable across features when source family, zone, actor, and CSID match exactly.

`mission_graph_ingest.py` provides a bounded ingest surface. It previews by default and requires explicit `--write` before persisting to a Workbench DB.

Regression: `test_fixtures/test_mission_graph_emission.py` covers extraction, source-line evidence, event/actor identity, condition/effect links, persistence through the canonical graph schema, Feature Trace traversal, reusable event identity, and mission-local state isolation.

This milestone does not claim runtime correctness, full Lua parsing, or exact branch semantics for dynamic expressions the conservative extractor does not understand.


## 2026-09-27 — Exact mission event/CSID reconciliation

Emitted mission server-event identities can now be reconciled against existing source/client evidence through `workbench/plugins/domain/mission_event_reconcile.py`.

The reconciler is intentionally exact and conservative:
- source-script support requires an exact `npc_event_refs` match on source family + zone + actor script + CSID;
- client support requires an independently established ENTITY semantic identity matching the source actor in the same zone;
- only then is an exact EVENT row accepted for the same client snapshot + zone + actor representation + CSID;
- duplicate actor identities or duplicate EVENT rows remain `AMBIGUOUS`;
- missing actor identity or missing EVENT rows remain unresolved;
- no actor aliasing, numeric-actor inference, CSID translation, or fingerprint equivalence is invented by this service.

Exact results may be persisted as ordinary graph navigation edges:
- `SUPPORTED_BY_SOURCE_REF` -> the source event-ref catalog row;
- `SUPPORTED_BY_CLIENT_EVENT` -> the client EVENT identity record.

`mission_event_reconcile.py` previews by default and requires explicit `--write` before persisting exact support edges.

Regression: `test_fixtures/test_mission_event_reconciliation.py` covers exact source/client reconciliation, evidence-backed persistence, and fail-closed actor ambiguity.


## 2026-09-27 — Branch-aware mission handler extraction

The conservative LSB mission extractor now expands multiline top-level `if / elseif / else` handler trees into separate transition alternatives instead of flattening mutually exclusive guards and effects into one transition.

Key behavior:
- each literal branch path gets its own transition, event return, guard set, effects, source-span metadata, and branch path;
- effects from sibling branches are never merged into the same transition;
- `elseif` and `else` paths are explicitly marked `branch_guard_complete=false` because prior-branch falsehood is not synthesized; their confidence is therefore UNKNOWN rather than overstated;
- unsupported multiline/nested branch forms retain the previous literal condition/effect evidence but are marked `unexpanded_nested_branch=true` and UNKNOWN instead of being presented as fully correlated;
- event chaining now fans one initiating CSID into multiple branch-specific `onEventFinish[CSID]` outcomes rather than refusing to chain when more than one finish alternative exists;
- chained outcomes preserve trigger/finish branch paths and propagate UNKNOWN confidence when either side has incomplete branch semantics.

Regression: `test_fixtures/test_mission_lsb_branching.py` covers different CSIDs returned by `if/elseif/else`, branch-specific key-item/status effects, and multi-outcome event chaining. Existing multiline battlefield guards remain conservatively represented rather than discarded.

This is still a conservative static extractor. It does not claim arbitrary Lua control-flow recovery, loop-sensitive path semantics, or synthesized negation of prior `elseif/else` branches.


## 2026-09-27 — Post-effect mission convergence ordering

Mission transitions now support an optional first-class `post_effect_gate` in addition to their ordinary precondition `gate`. The field is appended to the generic transition contract so existing positional constructors remain compatible.

The LSB extractor uses this only when source ordering is proven conservatively:
- branch extraction records the common source text that executes before each literal guard;
- when a recognized completion helper guard depends on state channels and the pre-guard prefix writes one of those same channels, the helper's convergence conditions are classified as a post-effect gate;
- if ordering cannot be proven (unsupported nested/multiline control flow), the conditions remain conservative precondition evidence and the path remains incomplete/UNKNOWN rather than being reordered speculatively.

This corrects the Three Paths terminal pattern:
1. write the current path status to `14`;
2. evaluate `isMissionComplete(player)` across Louverance/Tenzen/Ulmia;
3. complete the mission only if all three are now `14`.

The post-effect gate survives state materialization and event chaining. Canonical mission graph emission stores the ordered gate on the transition entity and emits generic `REQUIRES` evidence edges annotated as `post-effect`. Mission representation requirements also retain the post-effect convergence description.

Regressions:
- `test_fixtures/test_mission_lsb_three_paths_stress.py` requires all three terminal handlers (CSIDs 853/854/855) to carry three-path convergence as a post-effect gate, not a precondition, and verifies chained transitions preserve it.
- `test_fixtures/test_mission_graph_emission.py` verifies ordered convergence survives canonical graph projection.
- `test_fixtures/test_mission_representation.py` verifies migration/representation requirements retain the ordering.

This does not implement arbitrary intra-handler control-flow execution. Post-effect classification requires a recognized guard and a source-proven write overlap.


## 2026-09-27 — Generic mission completion-helper discovery

Mission convergence extraction no longer depends on a helper being literally named `isMissionComplete`.

`extract_dynamic_completion_gates()` now discovers local player helpers structurally. A helper qualifies only when it:
- is declared as `local function <name>(player)`;
- iterates a contiguous range of one `xi.mission.status.<family>` enum;
- checks the loop variable through `getMissionStatus(..., iterator) ~= <literal terminal value>`;
- contains a false return for an incomplete member and a true return path.

The status-family endpoints and observed intermediate symbols are then projected into an ALL dependency gate. Handler correlation links a guard to the specific discovered helper by its actual call name. Existing post-effect ordering remains generic: if source code before that guard writes one of the helper's required channels, the convergence gate remains post-effect.

The legacy `extract_dynamic_completion_gate()` function remains as a backward-compatible single-gate view: it prefers `isMissionComplete` when present, otherwise returns the sole structurally discovered helper only when unambiguous.

Comment text is stripped before helper semantics/calls are evaluated, preventing commented examples from manufacturing convergence behavior.

Regression: `test_fixtures/test_mission_generic_completion_helpers.py` uses a renamed `allPathsReady(player)` helper and verifies structural discovery, exclusion of an unrelated helper, helper-call linkage, and post-effect ordering.

This remains intentionally conservative. Helpers with dynamic range endpoints, nonliteral terminal values, non-player signatures, or structurally different completion logic remain unresolved rather than guessed.

## 2026-09-27 — Mission actor context scoped by Lua table structure

Mission handler actor context no longer uses the lexical "most recently seen actor" heuristic.

The extractor now derives literal Lua table spans for zone entries and actor entries:
- a zone handler receives a zone only while its source line is inside that zone's `{ ... }` table;
- an actor is attached only while the handler is structurally inside that actor's table;
- one-line declarative actor events remain handled explicitly and do not create synthetic actor scopes;
- zone-level handlers after one or more NPC blocks remain actorless rather than inheriting the last NPC name.

This closes a real identity-leakage class where zone-level `onEventFinish` handlers could be mislabeled as belonging to the last actor table encountered lexically.

Event chaining now also uses actor scope when available. Finish candidates are indexed by `(zone, CSID, actor)`; a trigger first uses exact actor-scoped finish handlers and falls back to an actorless zone-level finish only when no exact actor-scoped handler exists. Two actors reusing the same CSID therefore no longer cross-chain each other's effects.

Regressions:
- `test_fixtures/test_mission_actor_scope_context.py` covers two actor triggers followed by zone-level finish handlers, declarative actor events, zone-level zone-in context, and two actors deliberately reusing the same CSID with separate actor-local finish handlers.
- `test_fixtures/test_mission_lsb_correlation.py` now explicitly asserts that the Misareaux zone-level event-finish handler does not inherit the preceding `_0p2` actor.

The table-scope parser remains conservative and literal. Dynamically constructed mission tables or nonliteral table assignments remain unresolved rather than receiving inferred actor context.

## 2026-09-27 — Conservative Lua function-block parser hardening

`_balanced_function_blocks()` now yields only outermost executable Lua function blocks instead of starting a second block for nested callbacks.

The parser precomputes comment/string-stripped structural lines and ignores:
- single-line comments;
- quoted single/double-string contents;
- basic multiline block comments (`--[[ ... ]]`);
- basic Lua long strings (`[[ ... ]]`).

Once an outer function block is balanced, every nested `function` start inside that span is suppressed as an independent block. This prevents nested timer/callback functions from being reprocessed as separate mission helpers/handlers while keeping their source inside the enclosing function for conservative behavior extraction.

Regression: `test_fixtures/test_mission_function_block_parser.py` combines fake function syntax in comments/strings, a nested timer callback, one real helper, and one real mission handler. It requires exactly two outer blocks and one helper transition.

The parser still uses conservative lexical balancing rather than a full Lua AST. Extended Lua long-bracket delimiters such as `[=[ ... ]=]` remain outside this parser and should fail conservatively if they affect executable block structure.

## 2026-09-27 — Direct key-item grant extraction fix

The LSB mission extractor now distinguishes and correctly recognizes both key-item grant call shapes:
- `npcUtil.giveKeyItem(player, xi.keyItem.X)`;
- `player:addKeyItem(xi.keyItem.X)`.

The previous combined regex incorrectly required a `player` argument after both calls, so direct method-style `player:addKeyItem(...)` grants were silently omitted from findings and transition effects.

`test_fixtures/test_mission_lsb_extract.py` now requires both grant forms to appear as `key_item_grant` findings and `GRANT` transition effects.

## 2026-09-27 — Exact mission distance comparator semantics

Mission distance guards now preserve the literal comparator from `player:checkDistance(npc)` instead of collapsing every comparison into `WITHIN_DISTANCE`.

Mappings now use the generic state-condition operators already supported by the model:
- `<` -> `LT`;
- `<=` -> `LE`;
- `>` -> `GT`;
- `>=` -> `GE`.

The subject is `player_to_actor_distance`, making outside-distance guards (`>`/`>=`) representable without reversing their meaning and preserving strict versus inclusive boundaries.

Regressions:
- `test_fixtures/test_mission_distance_comparators.py` covers all four comparator forms;
- `test_fixtures/test_mission_lsb_road_forks_stress.py` now requires the real Loose Sand guard to extract as `LT 0.5`.

## 2026-09-27 — Conservative mission state materialization

`materialize_channel_states()` no longer connects a guard on one state channel directly to a write on a different channel as though they were one progression axis.

Materialization rules are now explicit:
- one guard + one write on the same channel -> materialize both endpoints (`same_literal_channel`);
- one guard only -> materialize only the source endpoint (`guard_only_literal_channel`);
- one write only -> materialize only the target endpoint (`write_only_literal_channel`);
- one guard and one write on different channels -> leave both endpoints as `source:any` and mark `cross_channel_ambiguous`.

The transition metadata records the guard and write subjects so cross-channel behavior remains inspectable without manufacturing a false state edge.

Regression: `test_fixtures/test_mission_state_materialization.py` covers all four cases and verifies that cross-channel synthetic states are not created.


## 2026-09-27 — Client transport attached to exact mission transition

Explicit source annotations that an event transport/exit is handled by the client are now attached as first-class `CLIENT_TRANSPORT` effects on the exact extracted handler path that contains the annotation.

This replaces the previous file/handler-level metadata-only treatment:
- branch-aware extraction evaluates transport annotations against each `_HandlerPath`;
- sibling branches do not inherit a client-transport effect from another branch;
- event chaining preserves the effect only on the corresponding logical outcome;
- the existing standalone `client_transport_effects()` helper remains available for file-level inspection.

Regressions:
- `test_mission_lsb_three_paths_stress.py` requires Mine Shaft 2716 event 3 to carry the transport effect while event 32001 does not;
- `test_mission_lsb_branching.py` proves one annotated branch receives `CLIENT_TRANSPORT`, its sibling does not, and only one chained event-6 outcome retains the effect.

The annotation remains source evidence, not proof of the client destination or runtime transport correctness.


## 2026-09-27 — Mission helper branch semantics and invocation linkage

Mission helper extraction and handler linkage are now explicit and branch-aware.

Changes:
- handler correlation records exact `helper(player)` calls per extracted handler path in `metadata.helper_calls`;
- sibling branches do not inherit helper calls they do not contain;
- `extract_helper_transitions()` now uses the same conservative branch-path expansion as mission handlers instead of flattening mutually exclusive helper effects into one transition;
- helper branch confidence falls to UNKNOWN when branch guards remain incomplete/unexpanded;
- recursive helper calls are marked explicitly in helper transition metadata;
- canonical mission graph emission creates feature-local `MISSION_HELPER` nodes and `CALLS_HELPER` edges from the exact invoking transition.

Helper effects are deliberately not inlined into the caller. This preserves asynchronous/recursive semantics such as Road Forks `jewelTimer(player)`, where timer/message/key-item behavior occurs inside the helper and may repeat later rather than happening immediately at the invocation site.

Regressions:
- `test_mission_lsb_road_forks_stress.py` requires only the exact Loose Sand branch that grants the Mimeo Jewel to call `jewelTimer`, and verifies branch-specific helper behavior including recursive timer scheduling;
- `test_mission_graph_emission.py` verifies `CALLS_HELPER` survives canonical graph projection.

This remains conservative static linkage. Dynamic function references, aliases, higher-order callbacks, and nonliteral helper invocation are not resolved.


## 2026-09-27 — Exact COMPLETE_TRADE extraction

Mission `COMPLETE_TRADE` effects are now recognized only from executable Lua, not raw source substrings.

The extractor now evaluates `player:tradeComplete()`, `mission:complete(player)`, and `mission:noAction()` against comment/string-stripped executable text. This prevents comments or quoted examples from manufacturing gameplay effects.

Branch/path scoping remains intact:
- only the branch containing the executable trade-complete call receives `COMPLETE_TRADE`;
- event chaining preserves it on the corresponding logical outcome only.

Regressions:
- `test_mission_complete_trade.py` proves comments and strings containing `player:tradeComplete()` do not create the effect while the real sibling branch does;
- `test_mission_lsb_three_paths_stress.py` requires Mine Shaft 2716 event 3 to carry exactly one `COMPLETE_TRADE`, and the chained TRADE→event-3 transition to preserve exactly one copy.


## 2026-09-27 — Mission extractor stress metrics

The mission/quest extractor now exposes first-class diagnostic metrics so large source scripts can be stress-tested quantitatively instead of relying only on hand-picked assertions.

`mission_extraction_metrics()` reports:
- total transition count and transitions by trigger kind;
- event-transition count;
- branch-transition count and incomplete-branch count;
- state-channel count;
- guard operator counts;
- effect-kind counts;
- helper invocation counts;
- recognized source-handler count;
- modeled source-handler count;
- unmodeled source-handler count plus exact source spans;
- event-chain count;
- event-chain branch fan-out;
- ambiguous event-chain candidate groups;
- initiating event triggers with no matching finish handler.

`correlate_lsb_handlers()` now records source-handler coverage directly. A recognized handler that produces no modeled condition/effect/event is not silently lost: its source span is retained as an unmodeled-handler diagnostic.

`chain_event_transitions()` now records ambiguous candidate groups separately from intended branch fan-out and counts unmatched initiating event triggers.

Canonical mission feature metadata carries the extraction metrics, and `mission_graph_ingest.py` prints a concise preview summary before any optional write.

Regressions:
- Road Forks and Three Paths stress fixtures assert real-source metric invariants and key guard/effect/helper counts;
- `test_mission_extractor_metrics.py` proves an unsupported handler is counted as unmodeled and duplicate same-CSID finish handlers are flagged as an ambiguous chain group;
- `test_mission_graph_emission.py` verifies extraction metrics survive canonical feature projection.

These metrics are diagnostics, not quality scores or implementation verdicts.


## 2026-09-27 — Reusable multi-zone progression / hunt framework

`framework.multizone_progression` now has a concrete reusable analyzer instead of metadata-only activation.

The framework lives outside `workbench.core` and models generic:
- stages and objectives;
- zone coverage;
- NPC/kill/zone/event trigger kinds;
- objective counts;
- state conditions/effects;
- AND/OR stage prerequisite gates;
- optional objectives/stages;
- entry stages and completion gates;
- evidence provenance.

Structural analysis reports:
- reachable/unreachable stages;
- dependency cycles;
- distinct zone coverage;
- cross-zone prerequisite edges;
- prerequisite fan-out;
- ANY-gated alternative entry;
- ALL-gated convergence;
- terminal stages;
- objective trigger mix;
- required/optional objective counts;
- structural completion-gate reachability.

`MultiZoneProgressionPlugin` consumes a `progression_model` through `PluginContext`, emits evidence-backed `PROGRESSION_STRUCTURE` and `CROSS_ZONE_DEPENDENCY` findings, and exposes the topology through its report surface.

`project_progression_graph()` emits ordinary canonical graph navigation records without adding progression-specific fields to the universal schema:
- feature -> `PROGRESSION_STAGE` via `HAS_STAGE`;
- stage -> `PROGRESSION_OBJECTIVE` via `HAS_OBJECTIVE`;
- stage prerequisites via `REQUIRES`;
- objectives -> zones via `LOCATED_IN`;
- objective subjects/events via `REFERENCES` / `USES_EVENT`;
- objective conditions/effects via `REQUIRES` / `AFFECTS`.

Graph persistence is deliberately non-destructive: an existing Feature or canonical Entity is not replaced by a generic progression fallback record. Mission/progression-local state subjects are feature-scoped.

Regression: `test_fixtures/test_multizone_progression_framework.py` covers normalization, validation, fan-out/branch/convergence topology, cross-zone dependencies, cycles, empty/invalid models, evidence propagation, plugin findings/reporting, non-destructive graph persistence, and Feature Trace traversal.

`STRUCTURALLY_READY` means only that the declared dependency model is structurally reachable. It is not a runtime-completion or implementation verdict.

## 2026-09-27 — Reusable minigame / puzzle framework

`framework.minigame` now has a concrete structural analyzer and canonical graph projection.

The framework models generic:
- interactions and trigger kinds;
- temporary state conditions/effects;
- named timers and optional durations;
- timer start/cancel/expiry-outcome wiring;
- scoring deltas;
- WIN/LOSS/TIMEOUT/DRAW/ABORT outcomes;
- repeatable reset paths;
- reset state/timer/score coverage;
- evidence provenance.

Structural analysis distinguishes validation errors from lifecycle gaps. It reports:
- interaction trigger counts and outcome/result counts;
- timer lifecycle closure (started, cancellable, expiry outcomes);
- mutable temporary-state subjects;
- reset state/timer coverage;
- scoring-rule count and score-reset coverage;
- explicit win/loss presence;
- structural gaps such as unopened timer lifecycle, missing reset coverage, missing score reset, or missing terminal result classes.

For repeatable minigames, reset coverage is conservative: every reset path must clear the declared temporary state, cancel active timers, and reset score when scoring exists. Permanent reward effects are not treated as temporary state that must be reset.

`MinigamePlugin` consumes a `minigame_model` through `PluginContext`, emits a `MINIGAME_STRUCTURE` finding plus targeted `TIMER_LIFECYCLE_GAP` / `RESET_COVERAGE_GAP` findings, and exposes structural lifecycle details through its report surface.

`project_minigame_graph()` emits ordinary canonical navigation records without adding minigame fields to the universal schema:
- feature -> timers/interactions/outcomes/resets;
- interaction -> timer via `STARTS_TIMER` / `CANCELS_TIMER`;
- timer -> timeout/outcome via `EXPIRES_TO`;
- interaction/outcome conditions/effects through `REQUIRES` / `AFFECTS`;
- reset coverage through `RESETS`;
- interaction subjects through `REFERENCES`.

Persistence is non-destructive for existing canonical Feature/Entity rows, and temporary state/score identities are feature-scoped.

Regression: `test_fixtures/test_minigame_framework.py` covers a structurally complete repeatable timed-scoring puzzle, timer/reset gaps, invalid references, one-shot behavior, evidence-backed graph projection, non-destructive persistence, Feature Trace traversal, and plugin findings/reporting.

`STRUCTURALLY_READY` is a declared lifecycle/topology result only; it does not prove runtime timing, scoring, rewards, or client interaction behavior.

## 2026-09-28 — Capture/video timeline alignment

Implemented a source-neutral alignment layer for linking gameplay-video time to real capture clocks without pretending the repository's independent logger tables share one universal timeline.

- explicit anchors carry video time, capture time, capture clock kind, source type, references, confidence, and notes;
- one anchor creates offset-only alignment; two or more anchors fit drift with RMS/max residual diagnostics;
- raw PacketLogger and EventView timestamp streams expose independent capture-relative candidate clocks;
- VIDEO_OCR and real capture opcodes are compared to surface shared packet landmarks, with unique one-to-one pairs flagged as strong candidates but never auto-accepted;
- the capture GUI has a dedicated alignment workspace, one-click prefill for unique packet pairs, video jump links, and support for manual/packet/event/screenshot anchor labels;
- screenshot/key-event attachment persistence remains a follow-on milestone, but the anchor model already reserves SCREENSHOT as a source type.

## 2026-09-28 — Screenshot and key-event evidence layer

Timeline alignment now has a persisted key-evidence layer rather than treating screenshots as comments on anchors.

- evidence types include SCREENSHOT, KEY_EVENT, FRAME, and NOTE;
- records can carry an observed video timestamp, capture timestamp + clock basis, an existing alignment anchor, or any compatible combination;
- when only one timeline coordinate is observed, the GUI may display the opposite coordinate as an alignment-derived estimate without writing that estimate back as observed truth;
- uploaded screenshots are limited to validated PNG/JPEG/WebP/BMP image content, stored under a per-capture evidence root outside static mounts, and served only through a DB-backed evidence route;
- key evidence retains source references, notes, confidence, MIME type, alignment-anchor linkage, and metadata;
- canonical capture graph ingestion emits a KEY_EVIDENCE entity and HAS_EVIDENCE relationship while keeping the interpretation distinct from packet/event truth.

## 2026-09-28 — Cross-frame OCR consensus and packet-symbol assistance

The packet-overlay OCR path now separates raw parsing from conservative structural normalization.

- raw OCR and the parser's original direction/opcode/packet symbol/field keys remain preserved under `raw_parsed`;
- packet-name correction reuses the existing Packetlyzer-backed packet definition index and requires a minimum similarity plus separation from the runner-up;
- a known opcode may corroborate/canonicalize the packet symbol, while a high-confidence packet-symbol match can recover the canonical opcode;
- field-key correction is scoped to the selected packet definition and never fuzzy-corrects field values;
- repeated observations of the same structural packet within a bounded video-time window vote on exact field values, including interleaved EView history stacks;
- tied field-value votes remain explicitly unresolved rather than guessed;
- capture ingestion uses the effective packet view but embeds raw parsing, symbol corrections, scores/source definitions, consensus votes, and source frames in VIDEO_OCR provenance;
- the OCR GUI displays raw-vs-effective structural values, correction details, consensus support, and unresolved ties.

## 2026-09-28 — Reusable OCR screen layouts and preprocessing profiles

The video OCR pipeline now separates reusable screen geometry from image preprocessing and parsing semantics.

- sections persist a capture profile and an independent preprocessing profile;
- named preprocessing presets cover standard grayscale OCR, FFXI chat, high-contrast EView/packet overlays, and compact addon/NPCLogger text;
- preprocessing is non-destructive: source/cropped frames remain unchanged while Tesseract receives the configured grayscale/autocontrast/invert/threshold/sharpen/upscale/PSM transformation;
- OCR provenance records the preprocessing profile used for every observation;
- built-in chat/EView/NPCLogger/research-combo layouts define reusable region roles but intentionally omit invented crop coordinates;
- a configured run can be saved as a local reusable multi-region layout containing real crop coordinates, fps, capture profile, and preprocessing profile per region;
- coordinate-complete saved layouts can be applied to another OCR run to recreate all configured regions; built-in coordinate templates remain visible guidance but are not offered as apply targets;
- saved layouts live under local `mission_reports_v2` workbench state rather than tracked source data;
- CLI `frames` and `run` paths expose the same preprocessing choices as the GUI.

## 2026-09-28 — Claim-level wiki evidence mapping

The Wiki Compiler now has an evidence ledger instead of only a readiness/link resolver.

- `reference_wiki_claims` preserves source ID, page/revision identity, section, exact reference excerpt, claim type, content hash, and `REFERENCE_ONLY` authority;
- explicit MediaWiki links become `ENTITY_REFERENCE` claims while list instructions from useful gameplay sections become unmapped `SECTION_STATEMENT` claims for later corroboration;
- `reference_wiki_mappings` records conservative exact/normalized identity candidates with MAPPED, AMBIGUOUS, UNRESOLVED, or UNMAPPED status rather than dropping failures;
- `reference_wiki_mapping_reviews` lets a human CONFIRM or REJECT an identity proposal without mutating the source claim;
- BG Wiki and FFXIclopedia remain distinct source IDs and revision domains;
- the canonical graph receives REFERENCE_CLAIM entities, REFERENCE evidence records, and MENTIONS/MAY_MENTION edges. A confirmed mapping can verify identity linkage, but metadata retains `authority=REFERENCE_ONLY`;
- rejected mappings are reconciliation-safe: a subsequent graph import removes any previously emitted edge;
- Feature Trace now catalogs claims, mappings, and reviews;
- the Wiki Compiler UI exposes source selection, evidence-map rebuild, claim provenance, candidate mappings, and confirm/reject review controls.

This is a mapping/evidence foundation, not a semantic truth extractor. Dual-wiki conflict detection, typed mechanics/progression claims, and corroboration against server/client/runtime evidence remain follow-on work.

## 2026-09-28 — Dual-wiki claim alignment and conflict detection

BG Wiki and FFXIclopedia claim ledgers can now be compared as peer reference sources.

- page alignment is keyed by normalized title and preserves BG-only, FFXIclopedia-only, and dual-source states;
- entity-reference claims align deterministically on normalized subject identity;
- section statements are compared only within matching sections and are paired conservatively by text similarity;
- high-similarity statement pairs are marked AGREEMENT; moderate similarity remains DIVERGENT rather than being forced into conflict;
- REFERENCE_CONFLICT is emitted only for deterministic contradiction signals currently supported: differing numeric values in otherwise structurally similar statements, or opposite negation polarity in otherwise structurally similar statements;
- unpaired claims remain BG_ONLY or FFXICLOPEDIA_ONLY so source coverage gaps are visible;
- canonical graph import creates REFERENCE_WIKI_ALIGNMENT analysis results and reference-only findings: agreements are SUPPORTED/INFERRED, conflicts are CONTRADICTED/INFERRED, and divergent/one-sided claims remain UNKNOWN;
- no source is ranked or selected as correct, and every comparison preserves both excerpts/revisions plus `authority=REFERENCE_ONLY`;
- the Wiki Compiler exposes a side-by-side comparison view with conflict kind, similarity, excerpts, and revision provenance;
- Feature Trace catalogs page/claim alignment records for later research navigation.

This remains a reference-comparison layer. Server/client/runtime corroboration is the next evidence step and is intentionally not inferred from wiki agreement alone.

## 2026-09-28 — Capture integrity and provenance hardening

The capture system now has a dedicated integrity layer rather than relying on source paths and ad-hoc parser results.

- deletion safety is live-schema-aware: the explicit child-table registry is retained for auditability, but deletion also discovers every current table with a `capture_id` column so newly added capture-owned tables cannot silently orphan rows;
- the known VIDEO_OCR, alignment-anchor, key-evidence, source-manifest, and lineage tables are explicitly registered, and per-capture key-evidence files are removed from disk on capture deletion;
- `capture_source_manifest` records SHA-256, byte size, detected format, parser name/version, row count, status/error, and ingestion timestamp for source files;
- both individual-file and folder/archive ingestion paths content-address their real source bytes;
- `capture_ingest_lineage` preserves source-file → parser/version → normalized table-family lineage plus the source locator basis supported by the parser;
- lineage precision is deliberately honest: existing parsers are currently guaranteed at file/table-family level with locator basis, while exact per-normalized-row line/block offsets remain a follow-on where formats/parsers can support them deterministically;
- the capture health service reports independent dimensions for source integrity, parser coverage, lineage, client context, packet evidence, entity evidence, timeline alignment, and duplicate source hashes;
- duplicate bytes across differently named captures are surfaced as an integrity issue rather than automatically merging sessions;
- the capture detail GUI exposes the health dimensions and expandable source manifest/parser provenance.

This hardening improves evidentiary provenance without changing captured observations or promoting parser output to stronger authority.

## 2026-09-28 — Exact capture content identity and source-version history

Follow-up to the Capture Integrity hardening merged concurrently on main:

- `capture_content_manifest` stores a path-independent SHA-256 over the current non-auxiliary source set, preserving multiplicity while excluding filenames and packaging-only metadata;
- exact duplicate captures can therefore be identified even when their files were renamed, moved, or re-zipped;
- `capture_source_artifacts` preserves content/parser versions append-safely, so changed bytes uploaded later under the same filename no longer erase the earlier provenance record;
- the existing `capture_source_manifest` remains the current/latest-by-filename compatibility view used by health and parser coverage;
- Capture Health now distinguishes exact whole-capture duplicate identity from individual shared-source-file overlap;
- capture detail exposes the full fingerprint and links exact duplicate capture candidates plus the source-history query;
- failed archive uploads are hashed and recorded with `archive_open` parser provenance even though ingestion failed;
- dynamic capture-owned table discovery automatically makes both new provenance tables deletion-safe.

This is exact-content duplicate detection, not partial session-overlap inference. Packet/event/time fingerprints for partially overlapping sessions remain a separate roadmap item.


## 2026-09-28 — Exact capture row locator foundation

The capture provenance layer now supports an explicit `capture_row_locators` ledger for normalized rows whose source formats expose deterministic physical boundaries.

- EventView text ingestion records a stable normalized-row key, source SHA-256, exact physical line range, and UTF-8 byte span for each `capture_eventview` row.
- Locator details preserve packet opcode/class/command context without replacing the normalized packet row itself.
- Capture health reports exact-row locator availability separately from the existing file-to-record-family lineage.
- Capture deletion discovers and removes locator rows with the rest of the capture-owned schema.
- No precision is fabricated for legacy/SQLite parsers that do not yet expose a trustworthy row/block boundary.

This is the first parser-specific implementation of the broader exact-row provenance roadmap item; other capture formats remain incremental follow-up work.


## 2026-09-28 — Raw packet exact source locators

PacketLogger/PacketViewer ingestion now preserves exact source-block provenance through the cross-file chronological merge.

- each normalized `capture_raw_packets` row records the originating packet-log filename and source SHA-256;
- locator keys bind to the final merged `seq`, not the parser's pre-merge file order;
- exact physical line spans are retained for every parsed packet block;
- UTF-8 byte offsets are retained only when the decoded source round-trips byte-for-byte, otherwise byte precision is left NULL rather than fabricated;
- re-ingestion replaces the raw-packet locator set idempotently so stale row keys cannot survive a new chronological merge.

This extends exact row provenance from EventView decoded packets to raw binary packet-log evidence.


## 2026-09-28 — Capture 2D/3D spatial viewer parity

The capture plotter is no longer a path-only static visualization.

- a shared capture spatial payload now exposes every capture-observed entity with a real XYZ position, including fixed NPCs/props with no PathLog history;
- 2D capture plotting can filter by name/entity ID and optionally renders name, ID, and XYZ labels directly on the coordinate-aligned zone mesh;
- the 2D entity table now exposes model, XYZ, HP%, and path availability instead of a path-only legend;
- 3D capture mode consumes capture-observed markers rather than silently relying on live server spawn metadata for the capture overlay;
- 3D hover/proximity labels include capture entity ID and XYZ, with model/HP/path context where available;
- 3D capture search filters markers and provides click-to-focus results while preserving the normal zone viewer's mesh, time-of-day, fly mode, wall opacity, and navmesh behavior.

The normal zone viewer remains the source of zone geometry/navmesh behavior; the capture layer now supplies capture-specific entity observations on top of it.


## 2026-09-28 — CapLog exact row provenance

CapLog ingestion now emits exact physical-source locators for every normalized row it produces.

- ID View rows in `capture_events` retain exact source line, source hash, normalized row key, timestamp, opcode, and opcode-name context;
- HP Track rows in `capture_hp_events` retain their exact CapLog line and mob context;
- embedded EView rows in `capture_eventview` retain the full two-line header + field block as one locator span;
- untagged in-game chat/system rows in `capture_caplog_chat` retain their exact source line and active zone/timestamp context;
- byte offsets are recorded only when UTF-8 decode/encode round-trips exactly;
- re-ingestion clears only CapLog-owned locator rows for that source file before rebuilding them, preventing stale locators without disturbing provenance from sibling source files.

This closes exact row attribution for the highest-value mixed capture source while leaving unsupported precision unclaimed for parser families that still need dedicated work.


## 2026-09-28 — KITrack / IDView / HPTrack / ActionView exact provenance

Exact source attribution now covers four more legacy text capture families.

- KITrack key-item acquisition/loss rows retain their exact header-delimited source block, source hash, normalized key, event type, key-item ID/name, and physical line/byte span.
- IDView/simple supports both real corpus formats: single-line packet records and blank-line-delimited multi-line records. Both now emit exact locators while preserving their existing normalization behavior.
- HPTrack standalone observations retain exact physical source lines for both known real renderings ("Defeated ..." and "[HP Track] Killed ...").
- ActionView/simple rows retain exact source lines keyed to the same stable action_key used by capture_actions; skipped non-record lines do not distort physical line numbers.
- Re-ingesting any of these source files replaces only that file/table locator set, keeping provenance idempotent without deleting sibling-source evidence.
- UTF-8 byte precision is recorded only when the decoded text round-trips exactly.

The next provenance boundary is no longer text parsing in these families; it is trustworthy row attribution for SQLite-backed sources and the remaining lower-value legacy parsers.


## 2026-09-28 — Partial-session overlap and clock continuity diagnostics

Capture integrity now detects two classes of cross-source problems that exact file hashing cannot cover.

- Partial/overlapping-session detection fingerprints normalized runtime observations across events, EventView packets, key-item events, actions, and non-trivial raw packets.
- Candidate overlap is deliberately conservative: it requires either shared evidence across multiple families or a large, highly-contained raw-packet overlap. It is surfaced as a review candidate, never auto-classified as an exact duplicate.
- Overlap fingerprints exclude timestamps so captures of the same underlying session can correlate even when logger clocks or capture starts differ.
- Clock continuity uses timestamp-bearing exact row locators in physical source-file order rather than normalized-table order, avoiding false continuity after parser sorting/merging.
- Time-only streams treat late-night to early-morning transitions as legitimate midnight rollover.
- Backward wall-clock jumps greater than one second and in-file timestamp-format changes are surfaced with source filename/line provenance.
- Diagnostics are visible directly on Capture Detail and remain non-destructive: no timestamps, alignments, or capture identities are rewritten automatically.

Parser-specific rebuild/reingestion orchestration remains the next unfinished capture-integrity item.


## 2026-09-28 — Safe parser-specific capture rebuild

The remaining capture-integrity rebuild milestone now has a bounded, exact-ownership implementation.

- Rebuild is available only for parser families with exact row locators: EventView, IDView/simple, KITrack, HPTrack, ActionView/simple, CapLog, and PacketLogger/PacketViewer.
- The original source folder/archive must still be accessible and each source's current bytes must match the stored SHA-256 before any normalized data is changed.
- Manual/upload captures whose original bytes were not persisted are explicitly reported as unavailable rather than reconstructed from hashes.
- Single-source rebuild deletes only normalized rows whose true primary keys are covered by that source file's exact row locators. Ambiguous shared row ownership causes a refusal.
- PacketLogger/PacketViewer rebuilds the whole packet-file family because the final capture_raw_packets sequence is a chronological merge across opcode files; every family member is hash-validated first.
- Parser work is wrapped in a SQLite savepoint so parser failure restores the prior normalized rows.
- Capture identity and user-maintained state are preserved: capture_id, mission/capturer/video metadata, tags, alignment anchors, curated key evidence, and whole-capture content fingerprint remain intact.
- Capture Detail now exposes per-source rebuild controls or the exact reason a source is not safely rebuildable.

This completes the current Capture integrity and provenance hardening subsection; additional exact-locator coverage for SQLite-backed and lower-value legacy formats can continue incrementally without blocking the integrity foundation.


## 2026-09-28 — SQLite-backed capture row provenance

Exact capture provenance now extends to the three primary SQLite-backed runtime sources.

- NPCLogger.db `entries` rows map exactly to `capture_npc_entries`; `history` rows map exactly to `capture_npc_history`.
- ActionView.db `entries` rows map exactly to `capture_actions`.
- LevelRangeTrack.db `entries` rows map exactly to `capture_level_range`.
- Each locator records the exact source-file SHA-256, source SQLite table, SQLite rowid, source key fields, and normalized Workbench primary key. Line/byte offsets remain NULL because they are not meaningful for SQLite pages.
- Re-ingestion replaces each file/table locator family idempotently.
- These parser families are now admitted to the safe source-rebuild framework, so hash-identical accessible source databases can be re-parsed while preserving capture metadata, tags, alignment anchors, curated evidence, and capture identity.


## 2026-09-28 — Legacy text/CSV provenance completion and path-leg schema correction

Exact row provenance now covers the remaining recognized legacy normalized capture sources.

- NPCLogger Lua `tables/` and `database/` snapshots emit exact physical-line locators for both `capture_npc_path` samples and the last-seen `capture_npc_entries` state.
- NPC PathLog and PC PathLog CSV rows emit exact CSV-row line/byte locators.
- Widescan emits exact line provenance for rows it actually inserts into `capture_npc_entries` and for its `capture_level_range` observations; `INSERT OR IGNORE` rows that did not produce normalized state are not falsely claimed.
- AttackDelay emits exact header-delimited source blocks for each aggregated mob-delay record.
- Lineage locator-basis declarations were reconciled with real parser precision (including KITrack/AttackDelay block semantics and Widescan level-range output).
- A schema bug was corrected: `capture_npc_path` declared `leg` but omitted it from the primary key even though legacy Lua ingestion uses separate legs for `tables/` and `database/`. Existing DBs migrate in place to `(capture_id, zone_db, entity_id, leg, step)`, preserving existing rows; future independent legs no longer overwrite one another.
- Safe rebuild now recognizes NPCLogger Lua, NPC/PC PathLog, Widescan, and AttackDelay. Where two sources truly overlap the same normalized current-state row, rebuild remains conservatively unavailable rather than guessing ownership.

With this milestone, every currently registered normalized capture parser has an exact provenance strategy appropriate to its physical source format.


## 2026-09-28 — Feature Trace exact capture-source drill-down

The completed capture locator foundation is now exposed directly through runtime evidence navigation.

- Feature Trace bounded runtime observations resolve their normalized capture table/primary key to `capture_row_locators`.
- Newly built runtime graph edges persist `capture_id`, normalized `capture_table`, and `capture_row_key` explicitly for capture events/actions.
- Existing graphs remain compatible: capture-event/action evidence locations are parsed as a conservative fallback, so source drill-down does not require an immediate graph rebuild.
- Runtime drill-down rows now display the exact source filename and physical line/block or SQLite row identity.
- A dedicated read-only source-evidence route verifies the current source SHA-256 before showing bytes. Text/CSV evidence displays only the recorded byte/line span; SQLite evidence queries only the recorded source table/rowid.
- If the original source is unavailable or its bytes changed, the stored locator remains visible but current bytes are not presented as the original evidence.
- This is presentation/navigation only; it does not promote runtime observations into server truth.


## 2026-09-28 — Row-level PacketLogger / EventView runtime graph linkage

The capture graph bridge now preserves packet evidence at observation granularity instead of only opcode summaries.

- Each `capture_raw_packets` row creates a distinct `OBSERVES_PACKET` edge from the capture to the canonical `packet:0xNNN` node.
- Raw packet evidence records capture id, normalized row key, timestamp, direction, opcode, byte length, and whether raw bytes are present; the bytes themselves remain in the capture store.
- Each `capture_eventview` row creates a distinct `OBSERVES_EVENTVIEW_PACKET` edge to the same canonical packet node while retaining packet class, GP command, entity/message fields, and decoded EventView fields.
- RAW_PACKET and EVENTVIEW_DECODE are deliberately distinct from the existing IDVIEW_EVENT bridge and from VIDEO_OCR; convergence happens only at the canonical packet node.
- `workbench_connect.py` now emits the same stable row-level raw-packet IDs when the modern `seq` schema is present, making the general and capture-specific connectors idempotent. Its legacy opcode/direction summary is retained only for schemas without row identity.
- The capture-specific connector reconciles its owned raw/EventView relationships and evidence before regenerating them, preventing stale graph observations after capture rebuilds shrink or replace normalized data.
- Feature Trace source drill-down resolves these new edges directly through their explicit normalized capture row keys to exact PacketLogger/EventView source blocks.


## 2026-09-28 — Cross-source packet correlation

Independent runtime evidence streams can now be correlated without being merged or promoted into a single synthetic observation.

- New `capture_packet_correlations` stores deterministic pairwise links between RAW_PACKET, EVENTVIEW_DECODE, IDVIEW_EVENT, and VIDEO_OCR observations.
- Raw PacketLogger ↔ EventView candidates require canonical opcode/direction agreement and bounded absolute timestamp proximity. One-to-one candidates are `MATCHED`; repeated same-window candidates remain `AMBIGUOUS`.
- IDView ↔ EventView does not invent a time axis. It requires opcode/direction plus at least one shared decoded identity field (entity id or message id), and only a unique bidirectional candidate is marked `MATCHED`.
- Video OCR correlations are generated only when an explicit fitted alignment model exists for the target logger clock. Video time is projected into that clock, then bounded opcode/direction candidates are evaluated.
- Correlations record basis, candidate counts, delta, score, and the fitted alignment model where applicable. They never replace the original source rows.
- Rebuilding correlations deletes and deterministically regenerates only that capture's correlation rows, preventing stale links after capture data changes.
- Runtime graph generation refreshes correlation state automatically before emitting packet observations.
- Capture / Video Alignment now exposes matched and ambiguous correlations and provides an explicit rebuild action.


## 2026-09-28 — Broad optional logger ingestion

Capture ingestion now accepts auxiliary logger data when present instead of requiring a fixed Assault/Nyzul addon set.

New structured evidence families:
- MissionTrack
- Captain ShopStock buy/sell SQLite
- Captain GuildStock SQLite
- SpawnTrack CSV
- WeatherTrack SQLite
- CraftTrack CSV
- CheckParam CSV
- POITrack SQLite
- ConquestTrack CSV
- historical Wiggo PriceLog/findPrice simple logs and Lua price databases

Implementation contract:
- full source row/block payload is retained in capture_structured_records
- stable common fields are promoted when proven by the source: timestamp, zone, entity/NPC id/name, item id/name, price
- unknown/source-specific fields remain in payload_json rather than being discarded
- exact sqlite-row / csv-row / text-block locators are recorded
- source SHA-256 / parser lineage / safe rebuild use the same capture-integrity machinery as existing formats
- auxiliary detection is content-first and runs only after the established core capture parsers, avoiding path-layout coupling and parser collisions
- capture detail exposes structured logger rows and capture health lists present families

Historical compatibility verified from Captain repository history:
- early GuildStock databases without NPC identity or Hidden columns
- early CheckParam CSV without syncId

Absence of any auxiliary family is not a capture-quality failure; these sources remain optional and are ingested only when the capture/tooling actually produced them.


## 2026-09-28 — Packet source adapter convergence

Capture ingestion now treats MalRD PacketDB SQLite and Ashita Packeteer text as first-class raw-packet sources alongside PacketLogger/PacketViewer. Canonical raw packet rows preserve optional zone id, packet size, sync id, injected/blocked state, source format, and source-native identity without collapsing independent evidence.

Legacy NPCLogger Lua `raw_packet` bytes are promoted into the same canonical packet store with exact line provenance. Cross-source packet correlation now records exact-byte equivalence across independent raw sources while retaining each observation separately. Safe rebuild logic preserves mixed-source captures instead of assuming PacketLogger owns the whole raw-packet table.


## 2026-09-28 — Canonical chat observations and PacketDB CHATLOG

PacketDB chat evidence is no longer discarded.

- MalRD PacketDB `CHATLOG` rows are ingested with native `CHAT_ID`, timestamp, direction, zone ID, and exact text.
- A generic `capture_chat_observations` table now stores chat/message evidence independently of any one logger.
- CapLog chat/system lines dual-write into the canonical chat store while the older `capture_caplog_chat` table remains intact for compatibility.
- Canonical rows retain `source_format` and `source_native_id`, preventing cross-tool evidence from being silently collapsed.
- PacketDB uses exact SQLite-row provenance; CapLog retains exact source-line/byte provenance.
- PacketDB and CapLog lineage declarations now include the canonical chat target, and the table participates in capture deletion safety.

The next capture evidence-loss target is preservation of whole-session EventView/simple or raw observations whose zone cannot be attributed safely.


## 2026-09-28 — Whole-session EventView evidence preservation

Whole-session EventView logs are no longer recognized-but-discarded.

- `eventview/simple.log` is normalized into decoded event evidence with the explicit `__UNKNOWN__` zone sentinel. The sentinel records that the source did not prove a zone; it is not a real zone name and is never inferred from the capture label.
- `eventview/raw.log` contributes canonical raw packet observations with exact packet bytes, direction, and opcode.
- Session raw packets retain `zone_id=NULL` and `ts=NULL` because these files do not provide trustworthy per-record zone or clock attribution.
- Per-zone EventView/simple evidence remains independent and keeps its actual source zone.
- Exact source line/block and byte provenance is retained for both decoded session events and session raw packets.
- Source manifest identities distinguish `eventview_session_simple` and `eventview_session_raw`; both are included in safe exact-source rebuild.
- Bare uploads named `simple.log` or `raw.log` are treated as session-scoped evidence instead of fabricating zones named "simple" or "raw".

Later correlation may resolve candidate zone/time context from independent entity, packet, or timeline evidence, but ingestion itself does not invent those dimensions.


## 2026-09-28 — Capturebar OCR context profile

Capturebar is now supported as a visual evidence source even though the addon itself does not write a persistent capture file.

- Added the `capturebar` OCR capture profile and built-in `capturebar_overlay` layout template using the small-overlay preprocessing preset.
- Parsing follows Wiggo32 Capturebar's default rendered format and extracts zone id/name, target/player name, X/Z/Y coordinates, rotation, main/sub jobs and levels, moon percentage, and moon phase.
- The parser explicitly records Capturebar's visual coordinate order as `x,z,y`; normalized fields remain semantically named `x`, `y`, and `z`.
- Capturebar sections bypass dialog-text fuzzy matching so coordinates, IDs, jobs, or world-state text cannot be silently replaced by a nearby dialog string.
- Successfully parsed frames materialize as `CAPTUREBAR_CONTEXT` video observations. Raw OCR text, frame id, video-relative timestamp, crop, preprocessing profile, and source URL remain in provenance.
- Unparseable or customized Capturebar display strings remain visible as raw OCR evidence rather than receiving guessed fields.
- The OCR GUI exposes Capturebar as a selectable capture profile and the reusable layout list exposes the built-in Capturebar role template.

This closes Capturebar as a known capture-support gap; it remains an OCR/video source, not a file-ingestion format.


## 2026-09-28 — Bounded PCAP / PCAPNG network evidence ingestion

Generic packet-capture containers can now be preserved without pretending encrypted/compressed FFXI wire traffic is already addon-level packet data.

- Added a dependency-free classic PCAP and PCAPNG reader with exact frame/block byte offsets.
- Common link layers are decoded conservatively: Ethernet (including VLAN), raw IP, Linux cooked v1, and Linux cooked v2.
- IPv4 and direct IPv6 UDP/TCP payloads are exposed with source/destination addresses and ports. Fragmented IPv4 and IPv6 extension-chain traffic is retained but not reassembled/guessed.
- Every captured frame is stored as a `pcap_network` structured observation with timestamp, interface id, link type, captured/original length, SHA-256, complete captured frame bytes, transport payload when available, and explicit decode status.
- A UDP payload is promoted into `capture_raw_packets` only if the complete payload validates as a stream of known four-byte-header FFXI chunks. Partial matches are rejected.
- Promoted PCAP chunks keep `direction='unknown'` because a standalone capture file does not prove which endpoint is the game client. No port-number heuristic is used to fabricate direction.
- Opaque retail/map datagrams remain preserved network evidence. The adapter does not guess Blowfish keys, zlib state, session initialization, or decompression boundaries.
- PCAP and PCAPNG participate in source manifests, exact `pcap-frame` row locators, safe source rebuilds, and ordinary capture deletion.
- The implementation uses only Python's standard library; no Scapy/libpcap dependency is required for offline ingestion.

Research basis: Windower packet documentation distinguishes UDP datagrams from the embedded four-byte-header packet chunks; current LandSandBoat map networking and independent FFXI transport implementations confirm UDP map transport with compression/encryption stages. Full retail-wire decoding remains a separate session-aware research milestone.


## 2026-09-28 — Historical Windower/Ashita/Captain capture-tool archaeology

A source-level archaeology pass separated real persisted formats from addons that merely consume packets or print/display derived state.

Findings:
- Windower's stock Logger is a real previously-unhandled persisted format. It writes daily `<player>_YYYY.MM.DD.log` files and can optionally prefix each line with a configurable clock timestamp. These files now feed canonical `capture_chat_observations` with exact line/byte provenance. If timestamps are disabled, `ts` remains NULL.
- Classic Windower PacketViewer and current Captain PacketLogger are the same compatibility family for toolkit purposes. Captain explicitly targets PVLV/VieweD compatibility and writes per-ID incoming/outgoing timestamped hexdumps; no duplicate adapter is needed.
- Windower QuestLog consumes packet 0x056 and writes results to chat only; old Windower Pricer fetches FFXIAH sale data and writes to chat only; Ashita ScanZone displays/prints entity observations. None creates a reusable capture file in the audited source, so adding fake file ingesters would be incorrect.
- Captain PacketBridge forwards packets over UDP but does not create a static log. It is a potential future live-input connector, not an ingestion format.
- Current Captain EventView v2 standalone files are a distinct compatibility question. Source inspection shows a newer full-datetime direction/type + dumped-table writer that does not match the legacy EventView header grammar. A real emitted sample is required before normalization; support is not claimed yet.
- Current Captain NPCLogger remains SQLite-backed and its packet logger remains in the existing raw-packet family.

Detailed tool-by-tool results are maintained in `docs/workbench/CAPTURE_TOOL_ARCHAEOLOGY.md`.

This closes the planned broad historical-tool search pass while keeping the inventory open for future forum/Discord/deleted-repository samples. The next major research boundary is lobby/world/non-zone traffic.


## 2026-09-28 — Lobby / search-cache / world-map stream research

The capture architecture now has a documented network-plane model instead of treating every FFXI packet source as one stream.

Confirmed boundaries:
- Retail lobby/character-service traffic is TCP and uses a lobby-specific header/MD5 command protocol. Character selection returns the information needed to reach the gameplay server and search/cache service.
- Search/cache is a separate TCP service. Current LandSandBoat source confirms player search, ID/group lists, party/linkshell lists, search comments, auction listing, and auction history request families. Its handler uses its own Blowfish/MD5 packet framing.
- World/map gameplay traffic uses UDP and contains the familiar 9-bit opcode / 7-bit size / 16-bit sync packet chunks after transport/session processing.
- Modern LandSandBoat additionally exposes loader/auth/data/profile endpoints. Those are implementation-specific private-server surfaces and are not being presented as retail socket topology.

Capture implications:
- Windower/Ashita packet hooks and Captain PacketBridge primarily expose the world/map chunk plane.
- PCAP/PCAPNG is the current evidence-preserving route for observing all socket families, but the toolkit does not yet reassemble or decode lobby/search TCP sessions.
- Search/AH/group/comment responsibilities are proven. Storage/inventory/account traffic is not being assigned to search merely from feature naming; it remains source-evidence dependent.
- Future decoding must start with generic TCP reassembly and validated structural classification rather than hard-coded port guesses.

The implementation sequence, open questions, and recommended network-flow/message evidence model are documented in `docs/workbench/LOBBY_WORLD_STREAM_RESEARCH.md`.


## 2026-09-28 — Generic PCAP TCP flow reconstruction

PCAP/PCAPNG ingestion now includes a protocol-neutral TCP reconstruction layer suitable for future lobby and search/cache decoders.

- TCP frame decoding now preserves sequence number, acknowledgement number, and individual control flags in the existing `pcap_network` frame evidence.
- New `capture_network_flows` rows identify bidirectional TCP connections using canonical endpoint ordering. Endpoint labels A/B are deterministic only; they do not claim client/server roles.
- New `capture_network_ranges` rows preserve each contiguous observed byte range independently for A→B and B→A.
- Sequence gaps remain explicit and split reconstructed ranges. Missing bytes are never synthesized or zero-filled.
- Exact duplicate retransmissions are recorded.
- Overlapping segments are recorded. If overlapping bytes conflict, the first observed byte is retained deterministically and each conflicting position/new byte/frame is preserved in anomaly metadata.
- SYN sequence-space consumption is accounted for when a SYN segment also carries payload.
- Each flow retains its contributing frame inventory. Each reconstructed range records the exact frame numbers contributing bytes plus a conservative source-file byte span and row locator.
- Reingesting the same source replaces source-owned flow/range rows rather than duplicating them.
- Source manifest row counts and ingestion lineage include flow/range observations.
- Protocol family remains `unknown_tcp`. No port-based lobby/search classification is performed in this milestone.

Known bounded limitation: 32-bit TCP sequence wrap across extremely large captured directional streams is not normalized into an extended sequence space yet. That should be addressed if a real FFXI capture demonstrates a flow large enough to cross the wrap boundary.

This completes the generic transport prerequisite for validated lobby/search-cache protocol classification.


## 2026-09-28 — Validated retail lobby TCP classifier / framing decoder

The generic TCP reconstruction layer now supports a conservative retail FFXI lobby decoder.

Validation/classification:
- TCP port numbers are never sufficient to classify a lobby flow.
- A candidate packet must be completely present inside one reconstructed contiguous range.
- The packet's little-endian header must contain the exact `IXFF` terminator and a known XiPackets lobby command.
- Fixed-size commands must match their documented packet size; variable character/world-list commands must match their count-derived layout size.
- The 16-byte identifier must match MD5 of the complete packet after bytes 12-27 are zeroed.
- Only MD5-valid messages can promote a parent flow from `unknown_tcp` to `ffxi_lobby`.
- Known command direction can infer client/server endpoint roles only if all validated messages agree. Contradiction leaves roles unresolved/conflicting.

Persistence:
- Added `capture_network_messages` for validated protocol messages, separate from raw TCP ranges.
- Each message retains source file, flow, direction, range/message index, reconstructed sequence span, command/name, full raw bytes, decoded fields, validation state, and exact contributing-frame provenance.
- Reingestion deletes/rebuilds only source-owned message evidence.

Initial field decoders cover:
- ResponseKey: lobby MD5 key, server expansion flags, feature flags including security token and Wardrobes 3-8.
- ResponseNextLogin: character identifiers/name, game-server id/address/port, and returned search/cache address/port.
- ResponseChrInfo2: character count and basic per-character ids/world/status/name flags.
- ResponseWorldList: world ids/names.
- RequestLobbyLogin: client version code and client expansion flags.
- RequestSelect/Delete/CreatePre/Rename and ResponseError/Ok: non-secret identifying/status fields where structurally documented.

Authentication tokens, hashed session password fields, and auth checksums are not promoted into normal decoded fields. They remain present only in the immutable raw packet evidence for forensic reproducibility.

Regression coverage includes a lobby request split across TCP segments, valid server responses, endpoint-role inference, feature flag decoding, next-login endpoint decoding, and an IXFF/known-command false positive with an invalid MD5 that must remain `unknown_tcp`.

The next network milestone is the search/cache TCP decoder, which requires session-aware Blowfish/MD5 handling and real capture fixtures.



## 2026-09-28 — High-volume pipeline scalability audit

The Heroines Holdfast capture exposed an O(n²) PacketViewer provenance regression at roughly 83k raw packet observations. A follow-up audit used that scale as the reference case across capture, correlation, Feature Trace, and migration-package paths.

Findings and hardening:

- PacketViewer/PacketLogger provenance now indexes line and UTF-8 byte offsets in linear passes instead of rescanning source prefixes per packet.
- Packeteer had the same UTF-8 prefix-offset pattern and now uses the same linear offset strategy.
- PacketDB/Packeteer bulk insertion now allocates source-native sequence ownership once per import instead of performing per-packet source identity/MAX(seq) lookups, leveraging the canonical raw-packet indexes already maintained by schema migration.
- Redundant flat PacketViewer/PacketLogger full/incoming/outgoing logs are recognized by path during provenance finalization so they are not decompressed a second time merely for format sniffing.
- Cross-source packet correlation no longer compares same-source exact-packet repeats pairwise. Raw/EventView and video/runtime matching now use opcode/time-window indexes, while IDView/EventView matching uses opcode/entity/message indexes.
- Migration package action ordering now uses Kahn topological sorting with reverse adjacency rather than repeatedly rescanning all remaining actions.
- Package dependency scope was confirmed already bounded by max_depth and max_nodes.
- Feature Trace runtime edges remain terminal rather than recursively expanded. Feature Trace now also has a hard max_nodes traversal budget (default 5000) and reports truncated=true when the budget is reached.
- Capture graph emission remains linear in observation count and commits as one transaction, but very large captures still produce one evidence row and one relationship row per raw packet by design; this is a storage/linear-throughput cost rather than an unbounded recursion.
- Feature Trace node presentation still performs per-node catalog metadata resolution. The traversal is now bounded, so this is a bounded N+1 cost rather than an unbounded graph explosion; batch catalog hydration remains a future optimization if real traces approach the node ceiling.

Focused high-volume regression coverage is part of the Workbench regression workflow.
