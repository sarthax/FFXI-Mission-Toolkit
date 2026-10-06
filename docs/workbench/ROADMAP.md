## 2026-09-30 Evidence Search module completion

- [x] Add Spatial & Movement search over entity snapshots, aggregated entity paths, POI and SpawnTrack evidence.
- [x] Prevent path-heavy evidence from flooding results by aggregating path observations per capture/zone/entity.
- [x] Add Environment & World State search over WeatherTrack and ConquestTrack observations.
- [~] Add provenance-safe related-packet correlation to evidence result cards where an explicit correlation exists. Related Evidence now combines exact source-span/SQLite-row provenance with unique non-temporal packet correlations (exact raw-byte equivalence and unique shared decoded-field matches). Temporal/alignment-only and ambiguous correlations remain excluded from the verified panel.
- [~] Add cross-module “related evidence” expansion without timestamp-only guessing. Evidence Search now separates provenance-overlap, explicit packet-correlation, deterministic entity-identity evidence, and ordinary-item identity evidence across structured item/vendor/crafting observations. Key-item IDs remain isolated in their own namespace. Richer normalized summaries and deterministic chat/native-source relationships remain.

## 2026-09-30 Zone / packet usability fixes

- [x] Remove the legacy Zone Editor page from navigation and redirect old /zoneplot bookmarks to /zoneplot2.
- [x] Fix Server 3D Viewer template compilation crash.
- [x] Add packet/capture file uploads to Bulk Packet Decode using the existing capture adapters.
- [x] Expand manual packet input to a large multiline textarea submitted via POST.
- [x] Accept full PacketLogger/PacketViewer hex-grid blocks directly.
- [x] Add regression coverage for the provided multiline 0x037-style packet sample.

## 2026-09-30 Capture discovery / forensics redesign

- [x] Reframe Capture Query as Capture Data Explorer rather than a raw-table dump.
- [x] Group existing capture datasets by investigative domain.
- [x] Add human-readable dataset labels/descriptions and curated summary columns.
- [x] Preserve complete physical rows behind Raw row / provenance drill-down.
- [x] Keep direct Packet Viewer, Entity Profile, Capture and Timeline drill-downs.
- [x] Rename Capture navigation to Evidence Search vs Data Explorer.
- [x] Build modular Evidence Search framework.
- [x] Migrate Events / Dialogue and Raw Packets into search modules.
- [x] Add Entity, Battle, Items/KIs, Vendor, Crafting, Spatial, Environment and Chat search modules.
- [~] Let modules return related evidence families and drill-down handoffs rather than one-table results. Multi-family Battle, Items/KIs, Vendor, Chat and Spatial modules are implemented; richer explicit related-packet joins remain.

## 2026-09-30 Configurable shell branding

- [x] Replace hard-coded ValhallaXI shell logo/text with settings-backed branding.
- [x] Add show/hide branding toggle.
- [x] Add user-defined brand text.
- [x] Add validated custom icon upload and default-icon reset.
- [x] Keep uploaded branding as local runtime data outside Git.
- [x] Preserve ValhallaXI logo/text as the default for existing installs.
- [x] Add shell rendering regressions for default/custom/hidden branding.

## 2026-09-30 Unified acquisition catalog foundation

- [x] Normalize existing mob-drop logical records into DROP_POOL acquisition paths.
- [x] Normalize synthesis and synergy recipe records into source-neutral acquisition paths.
- [x] Adapt scripted-behavior GRANT_ITEM / GRANT_KEY_ITEM reward evidence without changing its canonical graph IDs.
- [x] Feed VERIFIED non-crafting ITEM acquisition evidence into the existing recursive crafting closure.
- [x] Keep source literals/provenance intact instead of inventing cross-source item identity.
- [x] Add audited static Lua shop extraction across DSP/Topaz/LSB general/nation shops plus modern LSB guild shops and emit SOLD_BY acquisition paths. Detection is based on stock/call shape, not NPC-only paths, so zone/instance Lua can participate too.
- [x] Profile special/dynamic shop families separately; Curio Vendor Moogle is now represented as conditional CURIO_VENDOR acquisition evidence rather than flattened into static SOLD_BY stock.
- [x] Add explicit canonical item/key-item identity reconciliation before projecting the unified catalog into shared graph nodes. ITEM and KEY_ITEM remain namespace-isolated, LSB identities resolve only through authoritative enum evidence, and cross-provider numeric IDs require VERIFIED snapshot bridges.

## 2026-09-30 Package Scope / Create / Review workflow UX

- [x] Add a shared Scope → Create → Review workflow bar.
- [x] Redesign Scope Review around closure/gate state and compact dependency decisions.
- [x] Redesign Create Package as a compact assembly form.
- [x] Group package creation result artifacts by materialized / missing / skipped.
- [x] Redesign Review & Readiness around package summary, dependency scope, execution plan, and validation sections.
- [x] Preserve scope ledger, package gating, assembly, validation, and apply-readiness semantics.

## 2026-09-30 Client Overview build-comparison UX refresh

- [x] Convert Client Overview into a dense build-comparison workspace.
- [x] Keep installed fingerprint and imported snapshots immediately visible.
- [x] Collapse binary/probe/import detail behind focused sections.
- [x] Promote cross-build EVENT/ENTITY comparison as the primary workflow.
- [x] Add compact comparison KPI cards and inspector/model-viewer handoffs.
- [x] Preserve snapshot import, Feature Trace mirroring, confidence, and CSV semantics.
- [x] Package Scope / Review / Create received their dedicated workflow redesign in the completed section above.

## 2026-09-30 Wiki Compiler and Research Session workflow UX

- [x] Redesign Wiki Compiler as an evidence-review workspace with progressive disclosure.
- [x] Keep claim mapping/review primary and dual-wiki comparison secondary/on-demand.
- [x] Add compact linked-entity KPI summaries and expandable per-kind results.
- [x] Redesign Research Session Detail as a session console.
- [x] Separate run/replay, metadata, budgets, transcript, proposals, and final report into focused sections.
- [x] Preserve research execution, evidence, proposal, permission, and wiki mapping semantics.
- [x] Extend GUI/research/wiki regressions for the new workflow contracts.

## 2026-09-30 Library and search workspace UX refresh

- [x] Compact Item Browser, Key Items, Dialog, SQL Index, Zone Browser, Missions, and Binding Reference.
- [x] Compact Dialog Drift, Data Gaps, Domains, and Feature Checker.
- [x] Compact Research Sessions, Contradictions, Evidence Detail, and Research Gaps.
- [x] Collapse full mission text/rollups into on-demand mission cards.
- [x] Add template compilation/layout regression contracts and canonical Research Gaps route checks.
- [x] Redesign Wiki Compiler as a dedicated evidence-review workspace; completed in the dedicated Wiki Compiler / Research Session workflow pass above.
- [x] Redesign Research Session Detail around run/replay, evidence transcript, proposals, budgets, and report sections; completed in the dedicated workflow pass above.

# FFXI Server/Client Development & Backport Workbench

Status: ACTIVE REWORK
Baseline: 2026-09-25
Repository: sarthax/FFXI-Mission-Toolkit
Working branch: workbench-rework/audit-foundation

## Purpose
Turn FFXI-Mission-Toolkit into a durable, auditable workbench for researching, comparing, migrating, and validating FFXI server/client features across DSP, Topaz, Topaz-Next, LandSandBoat (LSB), custom forks, client DAT/EXE/DLL assets, packets, captures, and reference material.

The workbench must preserve evidence and provenance so that a future session can understand why a migration was proposed, what was actually changed, and what remains unverified.

## Safety rule for this rework
The main branch is the stable/original version. Rework happens on dedicated branches and is reviewed through pull requests. No destructive rewrite of main is part of this project plan.

## Architecture principles
1. Generalize relationships, not domain assumptions.
2. Keep FFXI domain categories and named systems as optional domain analyzers/plugins. UI taxonomy must not promote domain-specific mechanics into the universal core.
3. Do not encode system-specific gameplay concepts into the universal schema.
4. Treat server, client, packet, capture, and reference evidence as separate evidence domains.
5. Make confidence and authority field/question scoped rather than globally ranking sources.
6. Preserve existing specialized converters and analyzers; evolve them behind common interfaces instead of replacing working code prematurely.
7. Distinguish implementation from validation.
8. Distinguish physical source representation from logical entity identity.
9. Never infer that a feature is absent merely because one API/binding/schema representation differs.
10. Prefer machine-readable audit results alongside human-readable reports.

## Universal model
Core concepts:
- Source
- Snapshot
- Feature
- Domain/System
- Artifact
- Entity
- Relationship
- Capability
- Implementation
- Dependency
- Evidence
- Finding
- Migration
- MigrationAction
- Validation
- AnalysisResult

Generic dependency relationships include IMPORTS, REQUIRES, REFERENCES, DEFINES, IMPLEMENTS, BINDS, GENERATES, GENERATED_FROM, MAPS_TO, USES_ID, USES_PACKET, USES_ENUM, USES_CLIENT_CAPABILITY, BUILDS_INTO, and VALIDATED_BY. Relationship types remain extensible.

## Feature vs package
A Feature is the thing being implemented or compared.
A Package is a delivery/migration artifact containing files and actions.
They must not be conflated. Existing mission-package/backport-package tooling remains the artifact layer.

## Domain plugins
The core should not know about Assault Rank, Assault Points, lockboxes, appraisal pools, Nyzul floors, Abyssea Atma, Cruor, battlefield families, Trust mechanics, Records of Eminence objectives, or similar concepts.
Those belong in optional domain plugins/analyzers and named system packages. The GUI now exposes a first-class **Domains** workspace as the organizational home for these system-specific development/admin workflows; that navigation taxonomy is presentation metadata, not universal schema.

Current high-level UI domain categories are:
- Abyssea
- Battlefields
- Battle Systems
- Conflict / Battle
- Combat
- Dynamis
- Escha
- Hobbies
- HELM
- Events
- Missions
- Quests
- Records of Eminence
- Trust
- Other

Assault and Nyzul Isle are currently grouped under **Battle Systems**. Additional subsections are placeholders until their analyzers, pipelines, validators, or admin tools exist.
A future plugin interface may expose identify(), analyze(), discover_dependencies(), generate_migration_rules(), validate(), and report().

## Migration states
DISCOVERED -> ANALYZED -> COMPATIBLE -> AUTO_MIGRATABLE / MANUAL_REQUIRED -> MIGRATED / IMPLEMENTED -> VALIDATING -> VERIFIED
Alternate terminal/blocking states include FAILED, UNKNOWN, CONTRADICTED, and BLOCKED.

## Migration actions
Universal actions are limited to generic operations such as COPY, CONVERT, RENAME, RESHAPE, MERGE, SPLIT, RENUMBER, IMPLEMENT, PATCH, MANUAL_REVIEW, and NOT_REQUIRED.

## Coverage
Do not collapse the audit into a single percentage. Track dimensions independently:
- Lua
- SQL/data
- bindings
- C++ engine
- enums/constants
- IDs/entities
- packets/protocol
- client DAT
- client EXE/DLL
- build integration
- runtime/capture validation
- reference evidence

## Current direction — 2026-09-29

The Workbench foundation is now largely established. Forward work is organized by the newer
direction roadmap rather than treating Phases 0-8 as a strictly sequential implementation plan.

Current priority order:

1. **Behavioral dependency closure** — conditional/cross-zone/system-state dependencies, scripted
   entity/combat behavior, unified acquisition/obtainability, and deeper mission/quest closure.
2. **Client/server synchronization** — packet ↔ DAT/EXE/DLL ↔ server relationships, richer client
   capability validation, and new-item client/server write orchestration.
3. **Protocol/capture research** — search/cache TCP and cross-plane correlation after the lobby/TCP
   foundation completed.
4. **Named delivery systems** — Assault, Nyzul, Salvage, then Abyssea/Einherjar/Limbus using generic
   Workbench capabilities rather than core hard-coding.
5. **Migration completion** — database apply/rollback, approval/apply GUI, and broader proven
   conversion backends.
6. **Product workflow** — live ingestion, annotations, capture requests/completeness, hosted access,
   and capture-to-development export.

First active foundation milestone:
- [x] Mission/quest source state machines already project canonical graph evidence.
- [x] Generic conditional/cross-zone/system-state dependency representation and Package Scope
      traversal are implemented; conditional nodes remain QUESTIONABLE until explicitly reviewed.
- [~] Discover conditional system coupling automatically from source-family implementation evidence. LSB mob-script discovery now recognizes alternate-zone variants that explicitly delegate multiple lifecycle hooks to the same shared `xi.<system>` module; broader system-state patterns remain.
- [~] Implement generic scripted-entity/combat behavior representation and graph projection. The generic model and canonical projection are implemented, and a bounded LSB Lua extractor now emits source-backed rules with exact line provenance; helper-function expansion and more dynamic source patterns remain.
- [x] Unify acquisition/obtainability across the currently audited producer families. The source-neutral acquisition catalog covers mob drops, static Lua shops, Curio Vendor Moogle conditional stock, synthesis, synergy, and scripted rewards; VERIFIED canonical ITEM/KEY_ITEM reconciliation now gates shared identity. Additional acquisition families such as HELM, gardening, exchange, and appraisal remain separate future extensions rather than blockers for the completed foundation.

## Major roadmap
### Phase 0 — Preserve and baseline
- Freeze main as the stable reference.
- Establish this audit/roadmap documentation.
- Record branch/PR workflow.
- Record current audit findings and unresolved items.

### 2026-09-30 Captures workspace UX refresh

- [x] Rework Capture Detail into a compact evidence-first workspace.
- [x] Consolidate capture navigation/actions and add at-a-glance evidence counts.
- [x] Collapse healthy integrity/provenance and secondary datasets while keeping warnings visible.
- [x] Add quick NPC/entity filtering on Capture Detail.
- [x] Refresh Timeline, Packet Browser/Viewer, Search, Query, New/Add, Alignment, Source Evidence, delete confirmation, and Help.
- [x] Expand capture 2D plot workspaces to use available screen width.
- [x] Add template compilation/layout regression contracts.
- [ ] Follow up from real-user testing on which capture panels should default open/closed and whether any high-frequency actions should be promoted further.

## 2026-09-30 Compact Workbench shell / UX alignment
- [x] Replace the three permanently stacked global header rows with a single compact shared shell while preserving existing workspace/route ownership.
- [x] Move active-workspace subsections and snapshot/project context into bounded dropdown/popover surfaces.
- [x] Add shared dense-workstation primitives for toolbars, panels, tabs, drawers, cards, control sizing, and common panel widths.
- [x] Migrate Zone Editor New Layout (`/zoneplot2`) onto the shared dense shell and remove its page-local hidden-header/site-menu workaround.
- [x] Roll the compact/dense shell into Model Viewer and 3D Viewer after validation.
- [x] Roll shared dense patterns into Item Editor, Feature Trace, Entity/Events/Packets, then selectively into standard list/admin pages. Captures, Validation lists, and Package Library migrated; workflow-heavy Scope/Review/Create and Client Overview remain intentionally roomier pending dedicated UX passes.
- [ ] Keep prose/help/report pages on a roomier reading layout instead of forcing workstation density everywhere.

### 2026-09-30 Feature Trace implementation path
- [x] Resolve exact entity IDs and unique entity-name matches across SQL/LSB/Topaz/DSP/client catalog representations instead of treating normal multi-source identity as unresolved search ambiguity.
- [x] Add an Implementation Path view that preserves each source/provider branch and recursively follows exact provider-native wiring such as instance membership and mob spawn → group → pool without manufacturing canonical graph edges.
- [x] Automatically use an explicit canonical entity mapping when entity_identifiers resolves one unique graph root, preserving runtime/semantic traversal where available.
- [x] Remove the silent Absolute Virtue dependency-map fallback from the normal Feature Trace page; canonical dependency visualization now waits for a real mapped root and clearly distinguishes canonical graph coverage from catalog-backed implementation wiring.
- [x] Broaden canonical identity ingestion/bridging across server catalogs, captures, and client ENTITY snapshots without relying on presentation-time identity guesses. Server SQL/LSB/Topaz/DSP IDs are synchronized at rebuild time; capture observations bridge only through one explicit canonical mapping; client ENTITY snapshots mirror snapshot-scoped numeric representations through semantic identities, fail closed on ambiguous/reused IDs, and expose provenance drill-down back to exact identity records.
- [x] Strengthen Implementation Path diagnostics/presentation with explicit mapping-state reasons, canonical identifier/evidence summaries, provider/domain/native-link counts, source inspect links, drift-aware multi-ID display, runtime coverage summary, bounded direct provenance drill-down, and a read-only `/features/trace/path.json` troubleshooting endpoint.
- [x] Improve entity-workflow usability across Feature Trace and Entity Dossier: direct Entity/Behavior/Event/Capture/diagnostics handoffs, runtime-capture links, evidence-coverage cues that do not infer absence, provider/domain/text/native-link branch filtering, expandable source branches with indexed source facts, and a compact Feature Trace path-health card on Entity Dossier.
- [x] Add source-level implementation drill-down to Feature Trace: exact-provider Lua resolution through Behavior Inspector, bounded 40-line source previews without persisting source text, literal CSID links from parsed behavior, SQL row drill-through for root and downstream provider-native records, Behavior/Event/SQL reverse links back to Feature Trace, and explicit ambiguous/fuzzy source candidates instead of automatic source selection.
- [x] Add Lua-to-engine implementation tracing under resolved Feature Trace branches: syntax-level direct API calls, provider binding-index lookup, exact/case-only/unindexed status, C++ registration and bounded implementation excerpts, shared-helper API binding lookup, callback ownership, Binding Reference/JSON handoffs, Behavior API-node binding links, and return navigation from Binding Reference to the originating entity trace.
- [x] Harden binding evidence semantics: separate index-build failure from true unindexed methods, preserve case-fold collisions and multi-location registrations, retain bounded implementation candidates, expose source-read/index status, and regression-test both SOL and LUNAR provider surfaces.

### 2026-09-30 Entity implementation dossier
- [x] Preserve Entity Profile as the canonical cross-source evidence bridge while adding a synthesized dossier layer: evidence-presence summary, concrete needs-attention signals, instance memberships, SQL/Lua wiring chain, direct Behavior Inspector handoff, Feature Trace/Capture/Dialog/Event links, and unified client-defined + runtime-observed CSID/dialog wiring.
- [x] Keep the existing detailed model, mob/group/pool, drops, capture observations, SQL references, Lua references, wiki references, and field-provenance tables intact below the summary instead of replacing them with an aggregate score.
- [x] Reuse Behavior Inspector inline for a bounded callback/effect/API/event/state/helper summary, resolving the actual configured LSB source before analysis; keep the full causal graph in Behavior Inspector.
- [x] Add depth-1 canonical Used By / direct relationship projection from the Workbench graph, preserving direction, confidence, status, evidence IDs, and provider-native links; leave transitive closure to Feature Trace / Package Scope.
- [ ] Follow-up: consolidate source excerpts/callback ownership where useful and add richer implementation-gap actions only where backed by existing evidence rather than inferred absence.

### 2026-09-30 Capture Timeline interaction reconstruction
- [x] Add presentation-only interaction candidates over real `capture_events` sequence evidence, grouping only contiguous rows with compatible zone/entity/CSID context.
- [x] Split candidates on zone changes, large sequence gaps, conflicting explicit entities, or a new explicit CSID rather than fabricating cross-row transactions.
- [x] Surface source rows, observed options/messages, entity links, and partial-evidence state in the Capture Timeline while explicitly labeling the grouping as non-canonical.

### 2026-09-30 Events / CSID wiring dossier
- [x] Upgrade Events / CSID from a client-only decompile view into a runtime-to-implementation dossier: decimal/hex CSID browsing, direct entity links, actor-specific server-reference counts, exact capture observation counts, full dialog/message drill-down, server source excerpts, Lua handler/API-call inventory with Binding Reference links, and explicitly non-authoritative copyable Lua scaffolding derived from the selected CSID plus observed option/parameter evidence.
- [x] Follow-up QOL: parameter/work-variable and eventUpdate/option flow visualization is implemented as evidence-only inventory: literal client work-area references, literal update markers, observed option values, positional captured parameter values, and server callback stages. Work-variable and parameter semantics remain explicitly uninterpreted.

### Phase 1 — Canonical evidence and feature graph (P0)
- [x] Formalize Source/Snapshot.
- [x] Formalize Entity/Relationship.
- [x] Formalize Evidence/Finding.
- [x] Formalize Feature/Implementation/Dependency.
- [x] Add machine-readable analysis outputs.
- [x] Implement generic SQLite-backed canonical graph store.
- [x] Connect existing entity_profile, map confidence, capture, packet, and backport reports — all five now bridge into canonical graph/evidence records with dedicated regressions.
- [x] Add generic bidirectional Feature Trace over canonical graph relationships.
- [x] Add Feature Checker requirements/status evaluation on top of Feature Trace.
- [x] Add build-condition/generated-source analyzer.

### Phase 2 — Server adapters and migration engine (P0)
- [x] TopazAdapter
- [x] DSPAdapter
- [x] LSBAdapter
- [x] TopazNextAdapter
- [x] CustomForkAdapter
- [x] Logical schema mapping (P0 core) — item_basic/equipment/weapon/usable, spells, traits, instances, NPCs, mobs, spawns, drops, battlefield registry/membership, and SQL extraction are implemented with cross-profile coverage auditing. Additional system tables are P1 expansion rather than P0 blockers.
- [x] Generic FeatureSurface comparison — artifact roles, entity coverage, behavioral capabilities, path drift, capability status drift, and explicit migration actions for entity/capability/representation gaps are implemented.
- [x] Snapshot-specific capability observations and target-aware Feature Checker evaluation — FeatureSurface, server-schema coverage, binding compatibility, and live-target DB validators now emit snapshot observations; client-specific producers remain in the client phase.
- [x] Lua migration backend (P0) — route registry/support matrix is explicit: Topaz→DSP is SUPPORTED, LSB→DSP is CONDITIONAL/content-gated, and all other unproven routes are UNSUPPORTED rather than guessed.
- [x] SQL migration backend (P0) — Topaz→DSP is the only registered SUPPORTED SQL route; every other source/target combination is explicitly UNSUPPORTED until a deterministic backend is added.
- [x] Binding compatibility engine — generic snapshot-aware comparison now distinguishes exact,
  representation drift, renamed/class-drift candidate, implementation drift, missing indexed,
  unresolved, and ambiguous outcomes while preserving binding/function evidence.
- [x] Live target validation — generic adapter-aware read-only DB validation, canonical ValidationRun/ValidationResult persistence, and safe CLI are implemented; specialized live MariaDB health/admin tools remain separate.
- [x] ID/content collision analysis — normalized-record collision engine, migration-planner blocking/review integration, typed research-tool exposure, and public cross-fork regression fixtures are implemented.

Current public flagship E2E: pinned LSB → legacy DSP Chains of Promathia 2-5 (Ancient Vows) reaches adapters, logical comparison, FeatureSurface capability alignment, canonical graph persistence, target-snapshot capability requirements, ValidationRun/ValidationResult, and Feature Checker.

### Phase 3 — C++/engine analyzer (P0)
- [x] header declarations
- [x] definitions
- [x] classes/functions/methods
- [x] enums/constants/macros
- [x] Lua bindings
- [x] C++ dependency graph (conservative)
- [x] packet dispatch pattern extraction (deterministic switch/registration evidence; full handler resolution remains source-dependent)
- [x] build-system inclusion (conservative)
- [x] build-target records and explicit CMake source-to-target relationships
- [x] compile conditions/generated-source syntax analyzer (conservative; no environment evaluation)
- [x] engine migration classification

### Phase 4 — Client capability and synchronization (P0/P1)
- [x] DAT adapters (P0 read-only foundation) — generic item DAT records normalize the existing audited item_dat_tools reader without replacing its low-level implementation.
- [ ] item DAT editing (P1) — existing specialized item_dat_tools editing remains available; generalized Workbench migration/write orchestration remains future work.
- [x] client/server field bindings (P0) — explicit core item field relationships are modeled and compared conservatively.
- [x] client capability model (P0) — readable client DAT records emit snapshot-scoped capability observations/evidence.
- [x] dialog drift (P1) — read-only cross-zone overview at `/dialogdrift` (`dialog_drift_overview.py`) over the existing `dialog_drift_report`; infers a per-zone constant id offset (most zones: -1). Inferred hint only, nothing applied; report data was last built 2026-09-06.
- [ ] packet/client/server relationships (P1 beyond the existing packet/server graph foundation)
- [x] generic EXE/DLL static research foundation — PE metadata/hash/section/import/export/string indexing, canonical evidence ingestion, typed research tools, and cross-binary index diffing are implemented; deeper disassembly/xref/function-recovery analyzers remain future work.
- [x] Client DAT/Binary Inspector GUI pages and feature-presence probes (`binary_probes.py`) emitting capability observations/requirements — see CLIENT_BINARY_RESEARCH.md; probe-set JSON files + read-only GUI runner (PoC); GUI save-to-graph; [ ] probe-set editor; [x] Client Overview/Build fingerprint page.

### Phase 5 — Runtime validation (P0/P1)
- [x] capture index (P0) — current/last-state, history, paths, actions, HP/events/raw packets are ingestible with provenance.
- [x] NPC logger/path/action evidence (P0) — runtime entity/path/action observations are indexed and backtraceable without promotion to server truth.
- [x] packet evidence (P0) — capture packet observations connect to canonical packet nodes and existing server handler/dependency edges.
- [x] test fixtures (P0) — focused capture/packet/event/backtrace fixtures plus an integrated runtime-validation fixture are in CI.
- [x] validation runs/results (P0) — deterministic ValidationRun/ValidationResult orchestration and graph persistence are implemented.
- [x] Exact runtime source drill-down — Feature Trace runtime observations resolve normalized capture rows through capture_row_locators and can open the precise original text/CSV span or SQLite row when source bytes remain hash-identical; older graph evidence-location strings remain supported as a compatibility fallback.
- [x] Row-level PacketLogger/EventView runtime graph linkage — raw PacketLogger/PacketViewer rows and EventView decoded blocks now create distinct per-observation runtime edges to the same canonical packet node, with exact normalized row identity and source provenance; general and capture-specific graph bridges are idempotent and stale bridge-owned observations are reconciled on rerun.
- [x] Cross-source packet correlation — preserve Raw PacketLogger, EventView, IDView, and video OCR as independent observations while recording conservative pairwise MATCHED/AMBIGUOUS correlations using packet dimensions, direct logger timestamps, decoded entity/message fields, and explicit video/capture alignment models. Correlation state rebuilds deterministically and is reviewable from Capture / Video Alignment.
- [ ] richer runtime probes/capture producers (P1) — expand only as specific systems need them.
  - [x] Broad optional logger ingestion — capture ingestion now accepts MissionTrack, ShopStock/GuildStock, SpawnTrack, WeatherTrack, PriceLog/findPrice, CraftTrack, CheckParam, POITrack, and ConquestTrack when those source files are supplied, preserving full payloads plus promoted searchable fields and exact source provenance. Historical Captain GuildStock and CheckParam schemas are explicitly supported.
  - [x] PacketDB CHATLOG canonicalization — PacketDB chat rows and CapLog text observations converge into `capture_chat_observations` while preserving source identity, direction/zone context, and exact SQLite-row or physical-line provenance; legacy CapLog storage remains for compatibility.
  - [x] Whole-session EventView preservation — session-wide `simple.log` decoded events are retained with explicit `__UNKNOWN__` zone attribution, while `raw.log` contributes canonical raw packet bytes with NULL zone/time where the source cannot prove them; per-zone evidence remains separate with exact provenance.
  - [x] Capturebar OCR context profile — built-in Capturebar layout/preprocess role plus structured parsing of the default Wiggo32 HUD into zone, target, X/Z/Y, rotation, job/level, and moon context; observations remain VIDEO_OCR-derived and retain frame/timestamp/crop provenance.
  - [x] Bounded PCAP/PCAPNG ingestion — preserve exact network frames plus link/IP/UDP/TCP metadata and frame offsets; promote UDP bytes to canonical FFXI chunks only when the complete payload validates as an already-plaintext known chunk stream. Session decryption/decompression and endpoint-role inference remain explicit future work rather than guessed ingestion behavior.
  - [x] Historical logger archaeology pass — audit Windower/Ashita/Captain/community packet/logging tools for actual persisted evidence vs. display-only/runtime-only behavior; add Windower Logger daily chat ingestion and maintain `CAPTURE_TOOL_ARCHAEOLOGY.md` as the source inventory. Captain EventView v2 standalone output is explicitly tracked as a sample-required parser gap rather than assumed compatible.
  - [x] Lobby/search/world stream research map — separate retail lobby/character-service TCP, search/cache TCP, world/map UDP, and private-server loader/auth/profile transports; document confirmed responsibilities, framing/encryption boundaries, capture visibility, and a no-guess implementation sequence in `LOBBY_WORLD_STREAM_RESEARCH.md`.
  - [x] Generic PCAP TCP flow reconstruction — canonical bidirectional A/B flows with TCP sequence/ACK/flags, deterministic contiguous byte ranges, explicit gap/retransmit/overlap/conflicting-overlap diagnostics, and contributing-frame provenance. Missing bytes are never fabricated and endpoint roles remain unassigned until independently proven.
  - [x] Validated lobby TCP protocol classifier/decoder — complete reconstructed ranges are scanned for known lobby frames; classification requires IXFF, exact declared size/layout, known command, and valid zero-identifier MD5. Endpoint roles come only from consistent known command directions; decoded messages retain raw evidence/provenance while omitting authentication/password material from promoted fields.
  - [ ] Search/cache TCP decoder — session-aware Blowfish/MD5 decode only after real capture fixtures validate the target protocol generation.
  - [ ] Cross-plane correlation — connect lobby-selected character/world/search endpoints to subsequent TCP/UDP flows while retaining each source observation independently.
  - [~] Unified packet inspection surface — standalone manual decode and capture-native Packet Viewer now share the canonical byte-layout analyzer; Capture retains timestamp, neighboring packets, source provenance, and correlation evidence while field rows coordinate directly with raw bytes. UI terminology is explicit: Capture → Packet Browser → Packet Viewer, while /packets is Packet Tools / Manual Packet Viewer & Decoder. Continue wiring packet-derived tools to contextual packet detail instead of duplicating decoder logic.
  - [ ] Live world-session packet producer — ingest timestamped live FFXI packet observations into the same canonical <code>capture_raw_packets</code> path used by persisted logs, preserving source identity, direction certainty, packet header metadata, and capture/session provenance; feed the existing decoder/correlation surfaces rather than creating a parallel live-only decoder.
  - [ ] Keep persistent global telemetry (WeatherTrack, POITrack, ConquestTrack) source-scoped rather than forcing it into capture_id.
  - [ ] Regression-test Captain EventViewV2/HPTrackV2/NPCLoggerV2/PathLogV2 samples against existing parser families before declaring compatibility.



### Capture integrity and provenance hardening (P1)

Purpose: make capture evidence reproducible, deletion-safe, content-addressed, and auditable before additional runtime-research automation depends on it.

- [x] Make capture deletion orphan-safe by reconciling the explicit child-table registry with live-schema discovery of every table containing `capture_id`; include VIDEO_OCR, timeline anchors, key evidence, source manifests/lineage, and future capture-owned tables automatically.
- [x] Remove persisted per-capture screenshot/key-evidence files when the capture itself is deleted.
- [x] Add a content-addressed source manifest for every ingested source file with SHA-256, byte size, detected format, parser identity/version, row count, ingest status/error, and ingestion time.
- [x] Apply source hashing to both individual-file ingestion and folder/archive bundle ingestion, so renamed/moved copies can be recognized by content rather than only `source_path`.
- [x] Add explicit ingestion lineage from source file/hash → parser/version → normalized table family with locator basis (`line`, `block`, `sqlite-row`, `csv-row`, etc.) and row-count provenance.
- [x] Add a dimensioned capture-health report covering source integrity, parser coverage, lineage, client context, packet evidence, entity evidence, timeline alignment, and duplicate-source detection; do not collapse these dimensions into one numeric score.
- [x] Expose capture integrity dimensions plus the source manifest/parser provenance on the capture detail GUI.
- [x] Add a path-independent whole-capture content fingerprint over the current non-auxiliary source set so renamed/moved/re-zipped copies can be recognized as exact capture duplicates.
- [x] Preserve changed same-name source files in an append-safe content-addressed source-artifact history while keeping the per-filename manifest as the current/latest view.
- [x] Hash failed archive uploads too, preserving failed ingestion provenance without treating the archive wrapper as successfully parsed capture evidence.
- [x] Refine recognized capture parsers to emit exact per-normalized-row source locators where the original format supports them; do not infer precision the source format does not expose. **All currently registered normalized capture parsers now participate: EventView, PacketLogger/PacketViewer, CapLog, KITrack, both IDView/simple formats, HPTrack, ActionView/simple, NPCLogger.db, ActionView.db, LevelRangeTrack.db, NPCLogger Lua tables/database, NPC/PC PathLog CSV, Widescan, and AttackDelay. Text/CSV formats retain real line/block/UTF-8 byte spans when trustworthy; SQLite formats retain source table + SQLite rowid/source key identity. Future parser families must meet the same provenance contract when added.**
- [x] Add session-overlap/fingerprint detection beyond exact source-file hashes for partial/overlapping captures — conservative normalized-runtime-evidence containment now surfaces review candidates without classifying them as duplicates.
- [x] Add clock discontinuity diagnostics and parser-specific rebuild/reingestion orchestration while preserving capture identity and annotations. **Clock continuity diagnostics use timestamp-bearing exact locators in physical source order; safe parser rebuild now requires accessible hash-identical original bytes plus exact row ownership, rebuilds PacketLogger/Viewer as a merged family, and preserves capture identity/metadata/tags/alignment/key evidence. Unsupported/unavailable sources are refused with an explicit reason.**
- [x] Modernize capture 2D/3D spatial viewers to share capture-observed entity metadata: all positioned entities (not path-only), name/ID/XYZ display, name/ID search, fixed/snapshot-only visibility, path presence, and capture-aware 3D marker hover/focus/proximity labels while retaining normal zone mesh/navmesh behavior.

### Video OCR evidence alignment and packet reconstruction (P1)

Purpose: treat gameplay video and screenshots as time-addressable runtime evidence that can be aligned with real capture sessions, packet observations, NPC/dialog events, and later screenshot/key-event evidence without promoting OCR guesses to authoritative packet truth.

- [x] Timestamp every OCR observation with video-relative time, frame identity, section/crop provenance, sampling rate, source URL, confidence, and sampling-resolution uncertainty.
- [x] Ingest parsed on-screen packet observations into the capture/evidence model as explicit `VIDEO_OCR` observations, separate from binary/raw packet captures.
- [x] Connect OCR packet observations to canonical packet nodes with conservative `INFERRED` confidence/provenance so Feature Trace can correlate video evidence with server/client packet knowledge.
- [x] Harden OCR run/section filesystem access against traversal or malformed route parameters.
- [x] Add video/capture alignment anchors so a real logger/capture session can be synchronized to a video using explicit clock-scoped anchors, shared packet landmark candidates, offset/drift fitting, and residual diagnostics.
- [x] Add screenshot/key-event evidence records that can attach to exact video/capture timestamps or an existing alignment anchor, derive the opposite timeline coordinate from fitted alignment without overwriting observed values, persist validated screenshot files, and bridge curated evidence into the canonical capture graph.
- [x] Add cross-frame OCR consensus and packet-symbol-assisted correction while retaining raw OCR/parsed values, correction candidates/scores, source packet definitions, vote provenance, and unresolved ties.
- [x] Add saved screen-layout/preprocessing profiles for chat, EView/packet overlays, NPCLogger, and other recurring capture layouts, including named OCR preprocessing presets, per-region provenance, reusable multi-region coordinate layouts, and GUI save/apply/delete workflows.

### Phase 6 — Domain plugins & reusable content frameworks (P1+)
Domain plugins should model both **content archetypes** and **named game systems**. The core graph/migration engine stays domain-neutral; this layer explains how different kinds of FFXI content are assembled, discovered, compared, migrated, and validated.

Reusable content archetypes/frameworks:
- [ ] Simple NPC/turn-in content — one or a few NPCs, dialog/events, key item/item/reward checks, minimal zone scope.
- [ ] Multi-zone hunt/progression content — multiple zones, NPC gates, monster kills, variables/key items, staged progression.
- [ ] Battlefield-instance content — reusable framework for BCNM/KSNM/ISNM/ENM/mission battlefields and similar arena content: registry, entry/exit, party/level/time policy, battlefield groups, mob scripts, rewards, mission/quest hooks.
- [ ] Multi-stage mission/quest content — state machine across multiple zones/NPCs/events with optional battlefield stages.
- [ ] Minigame/puzzle content — temporary state, timers, interactables, scoring/win-loss conditions, event-driven scripts.
- [ ] Repeatable/system-container content — currency/points/rank/entry resources/rewards plus many child features.
- [ ] Legacy-distributed implementation profile — recognizes DSP-style systems whose implementation is spread across zone scripts, SQL, globals, C++, and IDs rather than one central module.
- [ ] Modular-framework implementation profile — recognizes LSB-style reusable globals/classes/modules and maps them back to semantic roles without treating structural centralization as feature completeness.

Plugin contract:
- [ ] `identify()` / `classify_archetypes()` — determine which content archetype(s) fit a feature using evidence, not path names alone.
- [ ] `discover_surfaces()` — emit semantic FeatureSurface roles across Lua/SQL/YAML/C++/client/runtime evidence.
- [ ] `discover_dependencies()` — declare domain-specific dependency rules on top of generic graph edges.
- [ ] `compare()` — compare equivalent behaviors even when one fork centralizes a framework and another distributes logic across zones/files.
- [ ] `generate_migration_rules()` — contribution path is implemented and the battlefield framework now emits conservative migration guidance; broader plugin-specific rules remain.
- [ ] `validate()` — attach archetype/system-specific validation checks to ValidationRun.
- [ ] `report()` — expose a user-facing navigation model: stages, zones, NPCs, mobs, battlefields, rewards, variables, and unresolved gaps.
- [ ] Plugin registry/version/capability metadata so custom/community plugins can be added without editing core dispatch logic.

Reusable framework plugins:
- [x] Battlefield family plugin foundation for BCNM/KSNM/ISNM/ENM/mission battlefields — LSB policy/group extraction, DSP policy/membership reshape proposals, legacy callback-surface analysis, and conservative migration guidance are implemented; broader battlefield families still need additional fixtures.
- [ ] Generic quest/mission state-machine plugin.
- [ ] Generic multi-zone progression/hunt plugin.
- [ ] Generic minigame/puzzle plugin.

System-specific packages compose reusable frameworks rather than reimplementing them. Package identity is independent of the GUI taxonomy; for example, Assault and Nyzul Isle are grouped under the Battle Systems domain while remaining distinct system packages:
- [ ] Assault package — framework composition exists, but Assault-specific analyzers/migration rules for ranks/AP/tags/appraisal/lockboxes/instance conventions remain incomplete.
- [ ] Nyzul package — floor progression, objectives, lamps, tokens, boss floors, randomized objective framework.
- [ ] Salvage package — cells, path/room progression, restrictions, NM/boss structures, rewards.
- [ ] Abyssea package — Atma/Cruor/visitant/time extensions/triggers and zone-system rules.
- [ ] Einherjar package — chambers, reservations, waves, ampoules/rewards.
- [ ] Limbus legacy-preservation package when an appropriate implementation/client snapshot is selected.

Design requirements:
- A feature may compose multiple archetypes (for example a multi-stage mission containing a battlefield and a minigame).
- Named systems never become universal schema concepts.
- A centralized LSB framework and a distributed DSP implementation may be semantically equivalent; path/layout differences alone are representation drift.
- Plugins may add semantic roles and validators, but canonical Evidence/Finding/Feature/Relationship/Migration/Validation records remain the persistence boundary.
- Public-repo fixtures should include at least one reusable battlefield case (Ancient Vows) and one distributed-vs-modular comparison before system-specific packages are considered stable.

### Phase 7 — Automated migration packages (P1+)
- feature manifests
- [x] dependency-aware package-plan foundation — explicit canonical dependency edges now produce a deterministic, cycle-detecting MigrationAction order without applying changes.
- [x] migration action plans — ordered generic actions are emitted into a machine-readable package manifest.
- [x] target-specific conversion bridge — existing Lua/SQL package conversion can be scoped by a Workbench plan while preserving legacy full-folder behavior.
- [x] conditional LSB→DSP Lua backend — route recognition and conservative content gating exist; modern `xi.*` and framework-object rewrites remain manual until verified rules are added.
- [x] artifact-level converter preflight — individual conditional artifacts can be promoted to SUPPORTED only after deterministic source-text preflight passes; Ancient Vows confirms both framework-heavy Lua artifacts remain MANUAL_REQUIRED.
- [x] battlefield representation planner — combines DSP SQL policy/membership reshapes with callback-surface coverage while refusing to invent callback bodies.
- [x] plugin reshape action refinement — safe role-scoped domain findings can suppress generic migration actions without leaking domain semantics into the core.
- [x] refined actions drive package contents — resolved roles are excluded before converter/preflight/package staging; Ancient Vows now queues only its unresolved mission script.
- [x] mission representation planning — modern mission-script behavior can be decomposed into lifecycle requirements and checked against distributed legacy target scripts; Ancient Vows currently has two verified and two missing lifecycle requirements.
- [x] mission gap proposal artifacts — verified missing lifecycle requirements can emit proposal-only patch artifacts that remain review-only and are included in package provenance/validation.
- [x] deterministic patch-operation previews — exact-anchor patch operations can be validated in memory against pinned target files without writing them.
- [x] proposal-backed package actions — decomposed source roles can become REVIEW_PROPOSALS actions so the original source artifact bypasses conversion/staging while review artifacts remain in the package.
- [x] machine-readable patch plans — review-only exact-anchor operations carry source/preview hashes for later drift-aware approval and application.
- [x] drift-aware patch approval gate — target source hashes, anchors, and preview hashes must still match before a patch plan can reach READY_FOR_APPROVAL.
- [x] explicit human patch approval state — READY_FOR_APPROVAL remains non-executable until a matching approval record is explicitly APPROVED.
- [x] patch-plan approval linkage integrity — packaged approval requests must hash-link to a packaged patch plan or package cohesion fails.
- [x] approved deterministic patch apply — approved patch plans can be applied with backups, before/after hashes, apply journaling, and rollback; regression coverage is temporary-file only.
- [x] unified patch lifecycle status — package/UI consumers can read one authoritative lifecycle state across cohesion, drift, approval, apply, and rollback.
- [x] read-only patch lifecycle CLI — package lifecycle can be queried as JSON without granting approval or write authority.
- [x] unified package review summary — manifest, validation, cohesion, readiness, generated artifacts, and patch lifecycle are collapsed into one review result.
- [x] read-only package review CLI — consolidated package review state is available as JSON without approval or write authority.
- [x] validation package — planned Lua/SQL plus generated target SQL artifacts generate independent validation requirements.
- [x] package assembly + provenance — source and generated artifacts are staged with SHA-256 journals and review metadata.
- [x] package cohesion verification — assembled manifest, validation metadata, journals, staged files, generated outputs, and recorded hashes are checked for internal consistency before apply; the flagship Ancient Vows E2E now exercises this gate.
- [x] reversible file apply journal foundation — explicit file application can be rolled back; live SQL/database apply and rollback remain future work.
- [x] apply-readiness gate — cohesion and validation readiness are checked before a package is eligible for explicit file application; Ancient Vows currently remains MANUAL_REQUIRED because LSB→DSP conversion is not yet a supported backend.
- [x] rollback/journal foundation — staged source/generated artifacts are hashed/journaled and explicit file apply operations can be rolled back; live SQL/database rollback remains future work.
- [x] generated target-artifact foundation — safe domain reshape proposals can emit target-ready staged artifacts with provenance without applying them.


### Reference wiki evidence mapping (P1)

Purpose: use BG Wiki and FFXIclopedia as reproducible, revision-stamped reference evidence without allowing community documentation to become implementation truth.

- [x] Preserve claim-level wiki evidence with source/page/revision/section/excerpt provenance and explicit `REFERENCE_ONLY` authority.
- [x] Extract explicit entity-reference claims from MediaWiki links and retain useful Walkthrough/Strategy/Notes/etc. list statements even when they cannot yet be semantically mapped.
- [x] Resolve wiki entity references conservatively against indexed zones, NPCs/mobs, key items, and items; preserve MAPPED / AMBIGUOUS / UNRESOLVED / UNMAPPED states.
- [x] Add human mapping review with CONFIRMED / REJECTED decisions that never alter the underlying wiki claim.
- [x] Bridge wiki claims into the canonical graph as REFERENCE evidence and MENTIONS / MAY_MENTION relationships; confirmed identity mappings may verify identity only while the claim authority stays reference-only.
- [x] Expose claims, mappings, and reviews through Feature Trace catalog navigation and the Wiki Compiler GUI.
- [x] Add dual-source BG Wiki ↔ FFXIclopedia claim alignment with agreement/divergence/one-sided states and explicit `REFERENCE_CONFLICT` findings for deterministic numeric/negation disagreements, without selecting a winning source.
- [ ] Add semantic claim typing for progression requirements, rewards, coordinates, event/CSID hints, drops/acquisition, and behavioral mechanics without free-form truth promotion.
- [ ] Add deterministic corroboration summaries against server/client/runtime evidence so a claim can show SUPPORTED / CONTRADICTED / UNVERIFIED by evidence domain.
- [ ] Add mission/quest dependency extraction from typed wiki claims as reference guidance only, keeping executable/source-derived dependency gates separate.
- [ ] Add bulk/rebuild tooling for selected wiki categories/features so evidence maps can be refreshed reproducibly from pinned wiki snapshots.

### Phase 8 — Evidence-aware LLM Research & Agent Layer (P1)
Current state is a useful draft assistant: Open WebUI/Ollama chat plus read-only SQLite tools and logging. The rework should promote this into a bounded, reproducible research/orchestration layer over the Workbench rather than a free-form chatbot.

Core architecture:
- [x] Provider abstraction for Open WebUI and Ollama Direct with a provider-neutral contract/factory; future explicitly configured providers can extend the same interface without changing ResearchRunner.
- [ ] ResearchSession persistence with prompt/question, provider/model, pinned source/target snapshots, selected feature/entity roots, tool policy, tool transcripts, evidence IDs, findings/proposals, outputs, verification state, timestamps, usage, budgets, and replay metadata.
- [ ] Typed Workbench tool registry covering graph, feature, server adapters, entities, C++, bindings, enums, packets, captures, build targets, client capabilities, migration, validation, references, and source inspection.
- [ ] Bounded source crawler over configured repositories/snapshots with include/exclude rules, path/type/size/depth limits, secret/key exclusions, and no arbitrary filesystem access.
- [ ] Cross-repository research over configured DSP/Topaz/LSB/Topaz-Next/custom-fork roots and pinned public source snapshots.
- [ ] Semantic search/indexing over source snapshots and canonical graph metadata, while retaining exact grep/SQL/graph/source tools for deterministic verification.
- [ ] Evidence-first retrieval that returns canonical node IDs, source snapshot IDs, Evidence IDs, source file/path/line locations when available, confidence/status, and authority/source domain with every substantive result.
- [ ] Long-context feature artifact bundles combining relevant Lua, SQL logical records, C++ functions/bindings, enums, packets, build targets, client capabilities, captures, and references.
- [ ] Research-plan execution that decomposes a question into bounded tool calls, gathers evidence, synthesizes a report, identifies contradictions/gaps, and proposes the next deterministic analyzer/capture/validator actions.
- [x] Research gap detection for UNKNOWN/MISSING/CONTRADICTED graph endpoints and recommendations for the next analyzer/capture/validator — read-only `/researchgaps` (`research_gaps.py`): unresolved requirements, orphan entities, unverified relationships, empty analysis tables.
- [ ] Contradiction detection across server forks, client evidence, captures, runtime evidence, and reference sources.
- [ ] Reproducible research notebooks/reports that can be reopened and replayed against the same pinned snapshots.

Proposal and action boundaries:
- [ ] FindingProposal/ResearchFinding staging so model conclusions remain PROPOSED/DRAFT until deterministic verification or explicit human review.
- [ ] ChangeProposal support for MigrationAction proposals, patch/diff drafts, analyzer recommendations, validation plans, and package manifests.
- [ ] Patch/package proposal generation may emit diffs or migration plans for review, but deterministic migration services remain the only source-tree/database/DAT/package write/apply path.
- [ ] Permission profiles: READ_ONLY_RESEARCH, PROPOSE_CHANGES, VALIDATION_ORCHESTRATOR.
- [ ] Validation orchestration tools may invoke approved deterministic validators and attach ValidationResult records, but not arbitrary code/SQL mutation.

Recommended typed tool surface:
- graph.trace / graph.search
- feature.check / feature.candidates
- server.schema / server.logical_record / server.compare
- entity.lookup / entity.relationships
- cpp.symbol / binding.lookup / enum.lookup / build.target
- packet.lookup / packet.handlers / capture.backtrace
- client.capability / dat.lookup
- migration.plan / migration.explain
- validation.status / validation.plan
- reference.search / reference.compare
- source.search / source.read (bounded, snapshot-scoped)
- report.create_research_draft

GUI, auditability, and evaluation:
- [ ] GUI evidence trail showing tool calls, cited evidence, contradictions, proposal state, verification state, budgets, and replay metadata.
- [ ] Budget/timeout/tool-call limits and complete audit logging for every autonomous research run.
- [ ] Model-independent regression/evaluation fixtures using canned tool results to verify evidence citation, UNKNOWN/INFERRED preservation, contradiction handling, source authority, correct typed-tool selection, and no-direct-write guarantees.
- [ ] Provider/model quality evaluation remains separate from Workbench evidence/safety evaluation.
- [ ] Keep `llm_client.py`, `llm_db_tools.py`, `llm_log.py`, and existing GUI routes as compatibility entry points while moving provider/tool/research orchestration into `workbench/research/`.

Evidence rules:
- Graph reachability is never proof by itself.
- UNKNOWN and INFERRED states must be preserved rather than rounded up to certainty.
- Reference/wiki evidence is not silently promoted to server/client truth.
- LLM-generated conclusions never become canonical Findings without deterministic verification or explicit review.
- Every substantive LLM research claim should be traceable back to canonical evidence/provenance.

## Feature Trace architecture
Feature Trace is the central navigation layer between indexed sources. It is deliberately separate from the Feature Checker: a trace answers “what is connected to this subject?” while the checker answers “which declared requirements/capabilities have evidence?” without treating graph connectivity as proof of implementation.

A trace may start from any canonical node ID, or from an unambiguous partial name/identifier search. Traversal supports outgoing, incoming, or bidirectional relationships and a bounded depth. Each edge retains relationship type, status, confidence, evidence ID, source snapshot, and metadata. This allows a client/DAT/packet/C++/Lua/SQL subject to be a launch point as soon as its adapter has populated the canonical graph.

Wiki/reference indexing is intentionally a **launch/navigation layer**, not a source of truth. A future ReferenceAdapter should resolve a wiki result to a canonical entity/feature ID and then invoke Feature Trace. Reference facts remain reference evidence and are never silently promoted to server/client truth.

## Repository structure rework
A staged package-layout migration is now part of the rework. Package namespaces have been introduced without moving mature root scripts yet. The mass move is intentionally deferred until shared service boundaries stabilize; root compatibility wrappers will preserve existing workflows during each subsystem migration. See `docs/workbench/REPOSITORY_STRUCTURE.md`.

## End-to-end integration test strategy
Use different fixtures for different architectural questions rather than treating one content family as the universal proof case.

- **Flagship completeness E2E:** choose a feature substantially implemented in both public source and target snapshots. Prefer a main-story mission/battlefield or similarly mature system with Lua, SQL/entities, bindings/C++, packets/build dependencies, and validation surfaces.
- **Assault drift E2E:** retain Excavation Duty and later Assault missions as schema/ID/path/incomplete-content stress tests. Public LSB Assault coverage is not assumed complete and must not be used as proof that the full backport pipeline handles a complete feature.
- **Legacy-system audit:** Limbus is useful for testing legacy DSP discovery and preservation, but current LSB keeps legacy Limbus primarily as documentation because modern client data changed. Treat it as a preservation/audit case unless a compatible implementation snapshot is selected.
- **Reverse-pipeline E2E:** when the user's local Topaz/DSP Assault backport repositories are available, use them to test target/newer-feature → source/audit/reconciliation paths, including functionality absent from public LSB.
- **Local/live validation:** reserve the user's running server/client for generated-package application, startup/runtime behavior, packet/capture checks, and client capability validation after public-repository CI has proven the deterministic pipeline.

## Immediate audit queue
1. [x] Validate and extend class-aware capture → Lua event → binding/C++ resolution, adding evidence-backed local/returned-object typing without guessing. Flow-sensitive alias/API-return propagation, ambiguity rejection, reassignment invalidation, and provenance-preserving graph metadata are implemented.
2. [x] Resolve legacy DSP PacketParser opcode assignments to real handler symbols when a server source root is indexed; additional fork-specific dispatch patterns can extend the same evidence path.
3. [x] Connect bindings -> C++ symbols -> enums/constants -> packets -> build targets in the canonical graph, with confidence preserved per edge.
4. [x] Extend Backport Package Analyzer to emit/import canonical Feature, Artifact, DependencyEdge, Migration, and MigrationAction graph records.
5. [x] Connect entity_profile/map-confidence/capture/packet outputs to the canonical graph with evidence/confidence preserved.
6. [x] Add ValidationRun suite orchestration with independent dimensions, canonical ValidationResult persistence, and CLI/graph support.
7. Continue GUI/service extraction without rewriting the GUI wholesale. [in progress: `/backport/package` orchestration extracted behind `workbench.migrations.legacy_package_service` with regression coverage.]
8. Build the evidence-aware LLM research/orchestration layer described in Phase 8; begin with typed Workbench tools and reproducible ResearchSession records rather than expanding free-form SQL access.
9. [x] Validate the generic client EXE/DLL pipeline against supplied real FFXI binaries and add dependency-free bounded byte/xref/function-candidate analysis; next binary milestone is optional decoder-backed disassembly/CFG evidence and cross-build validation without introducing feature-specific logic into the core.

## Definition of done
The workbench is structurally ready when a feature can be traced from source/version through implementation dependencies, migration actions, client/server requirements, and validation evidence, with every conclusion carrying provenance and an explicit status.


## Capture-rooted reverse validation

The canonical graph must support both directions:

- feature/entity → client/server/runtime evidence
- capture observation → entity/event/packet → server/client implementation

Capture backtracing is another traversal root using the same evidence, capability, implementation, and dependency relationships. Numeric capture identifiers remain semantically neutral until their CSID/event meaning is verified.

## Reference-source expansion

Add FFXIclopedia as an independent reference adapter alongside BG Wiki. Prefer reproducible MediaWiki XML snapshots when available. Preserve source/revision/content hashes and expose reference conflicts rather than choosing a source globally.


### 2026-09-25 continuation milestone
The server graph connector now accepts the Lua event-surface index and independently verifies event identity against `npc_event_refs` before creating event → Lua function relationships. Lua method calls are preserved as inferred binding candidates rather than asserted class resolutions.


### Class-aware Lua candidate milestone
Lua event indexing now carries conservative callback-parameter class hints, and graph connectors use those hints to narrow binding candidates. The hint does not upgrade a call to VERIFIED; semantic typing of locals/returned objects remains future work.


### 2026-09-25 Lua typing continuation
- [x] local alias type propagation for callback-scoped Lua analysis.
- [x] explicit returned-object hint support without method-name guessing.
- [x] derive returned-object hints from indexed C++ API signatures and preserve evidence provenance.
- [x] reject conflicting API return-class hints instead of selecting one.
- [x] invalidate stale receiver hints after unknown local reassignment.
- [x] preserve parameter/alias/API-return trace and evidence metadata through capture/server graph CALLS edges while keeping them INFERRED.


### 2026-09-25 ID/content collision foundation
- [x] compare adapter-normalized LogicalRecord identities without assuming physical SQL schemas.
- [x] detect same-identity/same-content compatibility versus same-identity/different-content collision.
- [x] identify same-content/different-identity renumber candidates without treating them as proven semantic equivalence.
- [x] preserve composite identity namespaces so reused numeric components in different logical scopes do not become false collisions.
- [x] surface duplicate and unresolved identities explicitly.
- [x] feed collision findings into migration planning; hard same-ID/different-content conflicts now BLOCK package planning, while renumber candidates remain MANUAL_REQUIRED.
- [x] expose collision analysis through typed read-only research tools (`collision.inspect`, `migration.collisions`).
- [x] add broader real cross-fork collision fixtures.


### 2026-09-25 Logical schema / FeatureSurface coverage
- [x] add cross-profile logical schema coverage audit for Topaz, Topaz-Next, DSP, and LSB.
- [x] report unmapped parsed physical fields and identity mapping gaps per logical table.
- [x] expose physical-table drift (for example DSP item_armor vs logical item_equipment) without collapsing lineage differences.
- [x] expand FeatureSurface migration planning for entity coverage drift, capability status drift, and role-path drift.
- [x] audit and map item_weapon, item_usable, spells, and traits with lineage-specific drift retained.
- [x] audit item_basic with explicit legacy Topaz/DSP versus LSB representation drift.
- [ ] audit additional system tables as P1 schema expansion; P0 core schema coverage is complete.


## P0 closure status

P0 architecture is closed on the `workbench-rework/audit-foundation` branch.

Closed P0 scope:
- canonical evidence/feature graph and report connectors;
- Topaz, Topaz-Next, DSP, LSB, and explicit custom-fork adapters;
- core logical schema coverage for items, entities, instances, battlefields, spells, traits, and SQL extraction;
- FeatureSurface comparison and target-snapshot capability evaluation;
- explicit migration backend support matrix and conservative unsupported-route behavior;
- binding compatibility, live-target validation, and ID/content collision handling;
- C++/enum/binding/packet/build analysis foundation;
- read-only client DAT normalization, core client/server field bindings, and client capability observations;
- EXE/DLL static research foundation;
- runtime capture ingestion/backtrace/packet evidence and canonical validation orchestration.

Explicitly deferred to P1+:
- generalized Workbench DAT write orchestration and richer client synchronization/dialog drift;
- broader non-core server table mappings;
- richer runtime capture/probe producers;
- domain/plugin expansion and named-system packages;
- broader migration automation/live SQL apply;
- GUI exposure of the new architecture and evidence-aware research/agent UX.

Current proof:
- Workbench Regression remains green through the P0 closure sequence.
- Workbench Ancient Vows Cross-Fork #129 passes on the current branch head against pinned public LSB and legacy DSP snapshots.


## GUI information architecture mapping

- [x] Inventory all current FastAPI GUI routes and assign each route exactly one canonical workspace.
- [x] Preserve contextual entry points for dual-purpose tools without duplicating backend implementations.
- [x] Keep Captures as a first-class top-level workspace.
- [x] Preserve Item Editor and Zone Editor as mutation-focused tools under Tools > Editors.
- [x] Define canonical homes for backend-first capabilities that still need GUI exposure: Feature Checker/Trace, migration/collision/schema analysis, client binary research, validation runs/results, and package review/apply.
- [x] Add machine-readable `GUI_ROUTE_MAP.json` and CI regression coverage for the current FastAPI route surface (149 routes after Package Scope Review exposure).
- [x] Implement the shared navigation shell and persistent project/source/target/client context. The shell uses the approved route map for active workspace ownership, supports workspace subsections, keeps mutation editors visually distinct, and reports UNKNOWN / Not configured when current settings cannot establish snapshot or build identity. Existing routes and page internals remain unchanged.
- [x] Expose Feature Trace and Feature Checker as read-only Features workspace pages over the canonical Workbench graph.
- [x] Expose Validation dashboard and ValidationRun/ValidationResult browsing as read-only views over the canonical Workbench graph.
- [x] Expose Live Target Validation as an adapter-aware SELECT-only GUI using the existing CLI/service contract, with credentials kept transient and optional canonical persistence.
- [x] Expose Package Library and consolidated Review & Readiness as read-only Packages workspace pages over assembled migration packages.
- [x] Add Package Dependency Closure / Scope Review: bounded transitive graph discovery, per-dependency evidence/path visibility, user decisions/reasons/tags, reviewed-scope fingerprints, stale-review invalidation, and package-creation gating.
- [x] Expose canonical package creation from existing Migration/MigrationAction/Artifact/dependency records; creation consumes reviewed scope, embeds the full dependency decision ledger, and assembles a reviewable package workspace only.
- [~] Prove dependency-discovery completeness against a complex mob and representative instance/mission before adding approval/apply UI.
  - [x] Establish Arrapago Reef Medusa as the first machine-readable manual truth set, including helpers, skill/spell chains, job-special mixin, loot/items, title/text, Lua/engine requirements, and related-but-out-of-scope Besieged variants.
  - [~] Close the generic discovery gaps exposed by the Medusa proof and rerun the truth-set comparison.
    - [x] Promote mob skills, mob skill-list membership, and mob spell-list membership to generic logical schema surfaces.
    - [x] Discover literal Lua `require()`/mixin artifact dependencies with evidence.
    - [x] Resolve safe `ID.mob.SYMBOL + N` entity arithmetic/ranges through `IDs.lua` + zone `mobs.yaml`, including Medusa's four Lamia Exon helpers.
    - [x] Normalize modern LSB zone YAML templates/entities into entity→template→species/skill/spell closure.
    - [x] Link skill-list members to normalized mob-skill definitions and conventional Lua implementations, preserving missing scripts as explicit findings.
    - [x] Link zone-YAML loot symbols uniquely through normalized item identities to canonical ITEM dependency nodes.
    - [~] Promote zone text/title references and cross-zone Besieged coupling into package dependency edges.\n      - [x] Resolve zone `ID.text.*` and global `xi.title.*` symbols into dependency nodes.\n      - [x] Add cross-zone Besieged coupling as an explicit conditional/system dependency; conservative LSB shared-lifecycle source discovery can now surface the Besieged module and alternate-zone variants without treating name matching alone as proof.
  - [x] Establish Coiler automaton attachment as a second truth set covering item/internal identity mapping, dynamic Lua dispatch, shared automaton behavior, C++ puppet runtime, persistence, downstream weapon-skill consumers, conditional interactions, and reviewer-controlled acquisition paths.
  - [x] Add recursive crafting/producibility closure for synth/synergy recipe prerequisites; Heat Seeker→Glass Sheet now proves multi-level recipe recursion, key-item gating, leaf obtainability, and Synergy client/runtime gating.
  - [ ] Unify shop/drop/reward/HELM/gardening/exchange/appraisal acquisition analyzers so every crafting leaf can resolve against the same obtainability graph.
  - [x] Establish WotG25 branching mission truth set covering nation OR-branches, NPC/zone/CSID state transitions, key-item lifecycle, trades, timers, dialog/default actions, expected missing content, and placeholder battlefield gaps.
  - [ ] Build generic mission/quest state-machine and CSID/event analyzers against the WotG25 proof.
  - [ ] Repeat with an additional instance-heavy mission after state-machine closure is implemented.
- [ ] Add approval/apply/rollback UI only after preserving the existing readiness, approval, drift, backup, journal, and rollback gates end to end.
- [ ] Migrate remaining workspace pages incrementally while preserving current routes until feature parity is verified.


## 2026-09-25 — Real packed-DLL deeper pass

Completed a real `FFXiMain.dll` deeper pass and PE32 import-thunk candidate lookup. Future decoder/CFG work should prove reachable instruction boundaries and explicitly version its decoder; virtual `.text` requires an unpacked or runtime snapshot.


### 2026-09-26 Research Sessions GUI milestone
- [x] Expose persistent ResearchSession history in the shared GUI under Tools > Research: Sessions.
- [x] Show pinned source/target context, provider/model, permission profile, budgets, usage, replay metadata, verification state, final report, typed tool transcript, and evidence IDs.
- [x] Show staged research proposals with supporting/contradicting evidence and verification requirements.
- [x] Allow creation of session metadata without implicitly running a provider or granting source/database write authority.
- [x] Add focused GUI/session regressions and route-map coverage.
- [x] Add explicit provider-run/replay actions with provider/model, timeout, tool/provider-call budgets, temperature, run-state UX, and immutable replay cloning through the bounded ResearchRunner.
- [ ] Add contradiction-focused filtering and canonical evidence drill-through from the session detail page.

### 2026-09-26 Ollama Direct provider milestone
- [x] Add direct Ollama `/api/tags`, `/api/show`, and non-streaming `/api/chat` provider support.
- [x] Normalize Ollama models to the provider-neutral `id` shape used by ResearchRunner.
- [x] Preserve capability evidence (vision/thinking/tools), model details, usage counters, and provider metadata.
- [x] Add a provider factory for Open WebUI vs Ollama Direct selection.
- [x] Keep provider failures explicit; no silent fallback from one provider to another.
- [x] Add no-network regression coverage for both provider implementations and provider selection.


### 2026-09-26 — Revised next-work priority
Current ordered backlog after client snapshot GUI, Research Sessions GUI, direct Ollama provider, DAT Inspector UX cleanup, and CI stabilization:

1. [x] Safer variable-length EVENT opcode decoding to reduce `RAW_ONLY` fingerprints and improve cross-client EVENT identity matching.
2. [x] Research Session Run / Replay controls using the bounded `ResearchRunner` with explicit provider/model/budget/timeout/run-state handling.
3. [x] Improve cross-client ENTITY equivalence coverage and diagnostics, including portable client ENTITY-name ingestion, ambiguous/unresolved target-actor diagnostics, and actor-constraint visibility in EVENT comparison.
4. [x] Research contradiction filtering and canonical evidence drill-down across server/client/capture/runtime/reference evidence.
5. [x] Continue P1 logical schema expansion beyond the completed P0 core mappings — completed through combat registries, item modifiers/latents, progression, and combat-support tables; further schema additions are opportunistic rather than a blocker.

Completed/retired from the prior queue:
- [x] Automatic client ENTITY ingestion/actor-aware EVENT comparison foundation exists; remaining work is equivalence quality/diagnostics rather than basic ingestion.
- [x] Coiler/core-regression cleanup is complete; the full Workbench Regression suite is green.

### 2026-09-26 Client ENTITY equivalence milestone
- [x] Export per-zone client ENTITY resources into portable client snapshots.
- [x] Ingest ENTITY name-table rows as zone-scoped snapshot identities.
- [x] Preserve duplicate entity names as ambiguous rather than selecting an arbitrary target actor.
- [x] Add source/target ENTITY diagnostic payloads with evidence basis, confidence, target candidates, reason, and next-action guidance.
- [x] Feed ENTITY diagnostics into EVENT comparison and expose whether actor constraints were actually applied.
- [x] Show actor identity coverage and diagnostics in Client Overview and comparison CSV.
- [x] Correct Client Overview dialog counts to include the stored `DIALOG_TEXT_ID` namespace.

### 2026-09-26 Research contradiction / evidence drill-down milestone
- [x] Add read-only contradiction discovery over explicit CONTRADICTED findings, conflicting finding values, cross-snapshot capability observations, and ResearchSession proposal contradictions.
- [x] Filter contradictions by ResearchSession, canonical subject, and Evidence type.
- [x] Add canonical Evidence detail with backlinks to findings, relationships, validations, capabilities, implementations, typed research tool calls, and proposals.
- [x] Make ResearchSession supporting/contradicting/tool-call evidence IDs clickable.
- [x] Add Tools > Research: Contradictions navigation and route-map ownership.
- [x] Preserve source disagreement without selecting a winner or promoting one record to truth.


### 2026-09-26 P1 logical schema — combat registry tranche
- [x] Add source-neutral logical mappings for job abilities across Topaz, Topaz-Next, DSP, and LSB.
- [x] Add source-neutral logical mappings for weapon skills across all four server profiles.
- [x] Add source-neutral logical mappings for mob skills and mob skill-list membership.
- [x] Preserve modern LSB-only ability/weapon-skill radius and mob-skill AOE radius as explicit schema drift rather than projecting those fields onto legacy forks.
- [x] Keep runtime Lua/C++ effect behavior outside the SQL registry record; registry presence is not proof that the behavior implementation exists.
- [x] Continue P1 with generic item modifier/latent and character progression tables after this tranche.


### 2026-09-26 P1 logical schema — item modifier tranche
- [x] Add source-neutral logical mappings for direct item modifiers.
- [x] Add source-neutral logical mappings for pet-scoped item modifiers.
- [x] Add source-neutral logical mappings for conditional item latents.
- [x] Preserve physical uniqueness for item latents with the full `(item_id, modifier_id, value, latent_id, latent_parameter)` identity.
- [x] Keep modifier and latent semantics tied to separate enum/engine evidence rather than treating numeric IDs as self-describing.
- [x] Continue P1 with character progression tables such as merits/job points after this tranche.


### 2026-09-26 P1 logical schema — progression tranche
- [x] Add source-neutral job-point registry mappings across Topaz, Topaz-Next, DSP, and LSB.
- [x] Use semantic job-point identity `(job_id, name)` so numeric `job_pointid` drift is visible instead of becoming identity failure.
- [x] Add legacy SQL merit mappings for Topaz, Topaz-Next, and DSP.
- [x] Add an LSB `data/merits.yaml` producer that emits the same logical merit record type without inventing a removed SQL table.
- [x] Preserve legacy-only and LSB-only merit representation fields as explicit missing-field drift.
- [x] Continue P1 with additional generic server surfaces only where cross-lineage representation can be proven.


### 2026-09-26 P1 logical schema — combat support tranche
- [x] Add source-neutral mob pool modifier mappings across Topaz, Topaz-Next, DSP, and LSB.
- [x] Add mob spell-list membership with min/max level gates.
- [x] Add level-indexed skill-cap curves for rank buckets r0-r13.
- [x] Add per-job skill-rank mappings for all supported jobs in the audited schemas.
- [x] Preserve modifier namespace semantics as an enum/engine dependency rather than inferring meaning from numeric IDs alone.
- [x] Current prioritized P1 expansion is complete; future generic cross-lineage surfaces may be added opportunistically when they materially improve dependency tracing.

### 2026-09-26 Revised priority queue completion
- [x] All five items in the 2026-09-26 revised next-work priority are complete.
- [x] P1 logical schema expansion is no longer a blocking queue item after four evidence-backed tranches.
- [x] Future schema additions remain allowed when a concrete feature/package exposes a missing generic dependency surface.
- [x] Resume subsequent roadmap work from the next open phase item rather than treating schema breadth as an unbounded prerequisite.


### 2026-09-26 Generalized item DAT migration orchestration
- [x] Add proposal-only client DAT patch plans for existing item records.
- [x] Fingerprint the reviewed client record and block approval if the live/pivot record drifts before apply.
- [x] Require a matching explicit human approval record before any DAT writer is invoked.
- [x] Journal low-level DAT target/backup metadata and support deterministic rollback of the applied file.
- [x] Include client DAT plans/approvals in generated-output package integrity checks.
- [ ] Extend generalized orchestration to new-item allocation/injection and coordinated server SQL/client-index changes.

## 2026-09-27 — Audit reconciliation and sample-name neutrality

Architecture naming rule: concrete FFXI content used as a proof case or regression fixture must not name generic Workbench services, framework concepts, or reusable test roles. Content names remain valid inside evidence payloads where they identify the actual game subject.

Reconciled work discovered on current `main`:
- [x] Variable-length EVENT decoding: `workbench/client/event_fingerprint.py` now performs conservative variable-length rule extraction and fail-closed decoding; focused coverage lives in `test_fixtures/test_event_fingerprint.py`.
- [x] Automatic client ENTITY identity ingestion: `workbench/client/identity_extract.py`, `workbench/client/identity_snapshot.py`, and identity/event regressions automatically ingest per-zone client ENTITY evidence. Duplicate-name enrichment remains a refinement, not a blocker.
- [x] Broader P1 logical schema expansion: `workbench/adapters/servers/profiles.py`, `progression.py`, `schema_coverage.py`, and their regressions cover combat abilities/skills, item modifiers/latents, job points/merits, mob support tables, skill caps/ranks, synthesis, and synergy in addition to the P0 core.
- [x] Proof-case naming cleanup: generic artifact/test names now describe the dependency pattern rather than the sampled FFXI subject. The attachment/shared-runtime and cross-zone/system-coupling truth sets retain their concrete subjects only inside evidence content.

Files changed by the naming cleanup:
- `docs/workbench/DEPENDENCY_PROOF_CASE_ATTACHMENT.md` (renamed from `COILER_PACKAGE_PROOF.md`)
- `docs/workbench/DEPENDENCY_PROOF_CASE_CROSS_ZONE_ENTITY.md` (renamed from `MEDUSA_PACKAGE_PROOF.md`)
- `test_fixtures/fixtures/dependency_truth_attachment_runtime.json`
- `test_fixtures/fixtures/dependency_truth_cross_zone_entity.json`
- `test_fixtures/test_dependency_truth_attachment_runtime.py`
- `test_fixtures/test_dependency_truth_cross_zone_entity.py`
- `docs/workbench/ROADMAP.md`
- `docs/workbench/AUDIT_STATUS.md`

This naming rule applies to future proof cases as well: sample content demonstrates architecture; it does not define architecture.


## 2026-09-27 — Unified remaining-feature inventory

The Workbench roadmap and the older Toolkit product roadmap were reconciled. The following open capabilities were either absent from the recent scoped queue or were obscured by stale historical status.

### Core architecture / evidence
- [x] Generic conditional and cross-zone/system-state dependency relationship contract and Package Scope review semantics; Besieged-style coupling is now represented explicitly and remains reviewer-controlled.
- [ ] Unified acquisition/obtainability graph across shops, drops, rewards, HELM, gardening, exchange, appraisal, synthesis, and synergy.
- [ ] Broader packet ↔ client DAT/EXE/DLL ↔ server relationship coverage.
- [ ] Richer runtime probe/capture producers and repeatable live validation recipes.
- [ ] Optional decoder-backed binary instruction/CFG/xref/function recovery with explicit decoder/version provenance.

### Reusable content frameworks
- [ ] Generic mission/quest state-machine and CSID/event analyzer.
- [ ] Generic multi-zone progression/hunt framework.
- [ ] Generic minigame/puzzle framework.
- [ ] Generic repeatable/system-container framework.
- [ ] Additional instance-heavy proof after mission state-machine closure.

### Named system packages
- [ ] Assault.
- [ ] Nyzul Isle.
- [ ] Salvage.
- [ ] Abyssea.
- [ ] Einherjar.
- [ ] Limbus preservation package when a compatible implementation/client snapshot is selected.

### Migration / application
- [ ] Safe database-level apply and rollback; current deterministic rollback coverage is file-oriented.
- [ ] Approval/apply/rollback GUI after dependency-completeness gates are satisfied.
- [ ] Broader verified source→target conversion backends without guessing unsupported routes.
- [ ] Finish generalized client DAT write orchestration; active PR work remains incomplete until merged.

### Toolkit product features outside the recent Workbench queue
- [ ] Video/capture timestamp alignment and optional transcription.
- [ ] Authenticated remote/hosted access.
- [ ] Watched-folder or live Windower/Ashita auto-ingestion.
- [ ] Capture-data requests and fulfillment tracking.
- [ ] Capture annotations / invalid-data flags.
- [ ] Tag/category completeness checklists.
- [ ] Capture→server drafting/export through canonical evidence and migration review.
- [ ] Discord history/link catalog integration.

Roadmap authority rule: `docs/workbench/ROADMAP.md` is the detailed rework backlog; `docs/guides/ROADMAP.md` and the in-app `/roadmap` summarize both the Workbench and older Toolkit product backlog. Historical phase text may remain for provenance, but a newer reconciled status section supersedes stale labels.


### 2026-09-27 Generic mission/quest state-machine foundation
- [x] Add content-neutral state, guarded transition, zone-scoped event identity, transition-effect, and AND/OR dependency-gate models.
- [x] Distinguish branch viability from full machine completeness and keep expected implementation gaps visible.
- [x] Model lifecycle effects generically (grant/require/consume/remove/reissue) without adding mission-specific columns to the core graph.
- [x] Bridge behavioral transitions/lifecycles into the existing mission representation planner.
- [~] Add source-family extractors that populate the model from Lua mission/quest scripts. Conservative LSB literal extraction and handler-level guard/CSID/effect correlation are implemented; broader nested/dynamic helper resolution and cross-handler event-to-state chaining remain.
  - Required by stress probes: named mission-status channels, persistent/local vars, temporal guards, spawned-entity/death transitions, spatial guards, battlefield-result guards, trade semantics, default-action replacement/priority, and client-handled effects.
- [ ] Emit canonical graph dependency edges and evidence records from extracted machines.
- [ ] Add DefaultActions/fallback conflict analysis and client dialog/event-resource closure.
- [ ] Run the branching-mission truth set as the first large stress validation after the generic extractor exists.


### 2026-09-27 Scripted-NM behavior-map discovery

- [x] Stress a non-mission scripted NM with Absolute Virtue + Jailer of Love spawn closure.
- [x] Confirm mission state machines are not the universal behavioral representation.
- [x] Identify generic combat-map requirements: hooks, probabilistic/delayed spawn, runtime state transfer, cross-entity state, HP thresholds, random timers, ability responses/sets, combat modifiers, spell/magic responses, cleanup, loot overrides.
- [~] Implement the generic scripted-entity/combat behavior representation and source extractor. Generic behavior-map representation and canonical projection now cover mobs/NPCs/objects/escorts plus zone/instance hook owners. LSB extraction follows bounded local/entity helpers, recognizes common semantic effects, and preserves unfamiliar bound calls through generic API_CALL evidence. Remaining work is dynamic alias/data-flow resolution, imported helpers, richer instance/environment semantics, dynamic/computed entity resolution beyond direct literal offsets, and broader non-combat stress cases.
- [x] Add a bounded non-combat mission/NPC behavior stress regression covering char-state reads/writes, multiple event/CSID starts, key-item grant/removal, symbolic door identity, and world-state door effects using only generic behavior primitives. This is extractor stress coverage, not a claim that full branching mission closure is complete.
- [x] Add a GUI Behavior Inspector for direct source auditing: search LSB Lua, render upstream guards/state, hooks/helpers/rules, downstream effects/API calls and affected targets, and list same-zone controller/instance context separately from proven dependencies.
- [x] Promote named Lua state into first-class behavior evidence: entity-local, player-local/char, instance-local, zone-local, and server-global state reads/writes now produce canonical state identities with source-line provenance and visual read/write flow.
- [x] Promote anonymous timer/queue/addListener closures into explicit callback nodes with delay/listener trigger provenance; nested callback API/state behavior is extracted under that callback branch instead of being visible only as undifferentiated hook code.
- [x] Promote literal switch/case phase machines into verified named-state transitions when the selector is a direct state alias and the case writes back to the same state; unrelated writes remain generic state flow.
- [x] Emit modeled scripted-NM behavior/dependency evidence into the canonical graph, including cross-entity actor requirements; runtime/source verification remains distinct from proof-derived EXPECTED evidence.
- [x] Stress the behavior representation with King Vinegarroon as a mechanically different NM: weather listener, helper-driven Vana'diel-hour behavior, respawn timing, immunities/modifiers, alliance draw-in, dynamic TP-skill selection, title reward, and weather-driven despawn all remain traceable with source provenance. Literal weather-element, Vana’diel-hour-range, position/distance, and party/alliance access conditions are now promoted into structured behavior conditions; more dynamic environmental predicates remain.

- [x] Resolve direct symbolic Lua entity references (`ID.npc.*` / `ID.mob.*`) with optional literal integer offsets in `GetNPCByID`, `GetMobByID`, `SpawnMob`, and `DespawnMob` calls, preserving source provenance and projecting concrete `entity-symbol:*` targets. Dynamic aliases/loop offsets remain open.

- [x] Propagate literal local aliases of `ID.npc.*` / `ID.mob.*` through direct entity calls, combining literal base/call offsets while preserving alias provenance. Dynamic loop/index offsets remain open.

- [x] Expand bounded literal numeric `for` loops that reference entity symbols (`ID.* + i` or literal symbol aliases `+/- i`) when the full iteration set is statically known and <=64; oversized/dynamic loops remain raw evidence. Direct-symbol matching now rejects dynamic suffixes rather than emitting false base targets.

- [x] Expand bounded symbolic entity ranges where loop bounds are the same `ID.npc.*` / `ID.mob.*` base plus literal offsets (for example Nyzul lamp ranges), resolving each loop variable use into concrete `entity-symbol:*` targets with source/loop provenance. Oversized or mixed-base ranges remain unresolved.

- [x] Resolve `xi.<module>.<function>` calls in Behavior Inspector to exact module-scoped LSB global Lua definition candidates. One candidate is marked RESOLVED, multiple candidates AMBIGUOUS, and none UNRESOLVED; no body inlining or arbitrary candidate selection is performed yet.

- [x] Capture balanced source spans for uniquely or ambiguously resolved shared `xi.<module>.<function>` definitions and expose bounded source previews in Behavior Inspector; helper bodies are still not recursively interpreted into parent behavior.

- [x] Run one-level conservative semantic analysis for uniquely resolved shared `xi.<module>.<function>` bodies in Behavior Inspector (direct API calls, named state, literal context conditions, and entity references). Ambiguous/unresolved helpers are never expanded, and recursive shared-helper expansion remains disabled.

- [x] Present uniquely resolved shared-helper one-level analysis as separate upstream inputs (state/context), downstream effects (state/entity), and raw direct calls in Behavior Inspector; ambiguous/unresolved helpers remain unexpanded.
- [x] Model literal-offset runtime-relative entity identities such as `local mobId = mob:getID(); GetMobByID(mobId + 1)` as `RUNTIME_RELATIVE_ID` evidence with receiver/alias/source provenance, without fabricating static `ID.mob.*` symbols; dynamic offsets remain unresolved.
- [x] Promote bounded server-global lifecycle transitions for direct `GetServerVariable` aliases guarded by literal equality and written back through `SetServerVariable` to the same canonical global state identity; computed predicates and cross-global writes remain ordinary evidence.
- [x] Promote bounded instance lifecycle transitions for direct `instance:getStage()` / `instance:getProgress()` aliases guarded by literal equality and written back through the matching `setStage` / `setProgress` canonical state identity; cross-lifecycle writes, computed predicates, and non-equality guards remain ordinary evidence.
- [x] Recognize the same bounded literal lifecycle transitions when server-global or instance stage/progress getters are used directly in the `if` predicate without a local alias; exact same-state writes are required, and cross-state writes remain generic evidence.
- [x] Surface cross-hook shared-state evidence in Behavior Inspector when the same canonical state identity is written in one hook and read in another, including literal `STATE_EQUALS` guards. These links are explicitly non-causal (`ordering: UNPROVEN`) unless another analyzer establishes execution order.
- [x] Surface cross-hook event identity evidence when a literal CSID is started in one hook and guarded in another (for example `onTrigger` → `onEventFinish`). Correlation requires the exact same literal event ID, leaves unmatched starts/guards unlinked, and records ordering/causality as `UNPROVEN`.
- [x] Bind literal CSID branches to branch-local canonical state writes, then surface downstream cross-hook readers separately. CSID→state writes are source-local evidence; state→other-hook reads remain `UNPROVEN` ordering unless execution sequencing is independently established.
- [x] Preserve broader branch-local CSID effect bundles in Behavior Inspector: key-item grant/removal, item/gil rewards, event updates, world-state changes, and direct entity reference/spawn/despawn effects remain attached to the exact literal branch that contains them; unsupported/dynamic effects are not reassigned.
- [x] Split literal `option == ...` / `result == ...` event outcomes into outcome-specific effect bundles, including `onEventUpdate` handling. Dynamic predicates and `else` fallback arms are excluded from parent CSID attribution rather than guessed; event guard hooks preserve finish/update handler roles.
- [x] Model literal canonical-state guards nested inside literal event outcomes as a third condition layer (`CSID + option/result + state == literal`) with branch-local effects and cross-hook state-reader correlation. Unsupported nested predicates are masked from the parent outcome bundle rather than promoted.
- [x] Model source-literal resource guards nested inside literal event outcomes: direct `player:hasKeyItem(xi.keyItem.*)`, negated key-item possession, and simple `npcUtil.tradeHas` / `tradeHasExactly` requirements over literal item symbols or numeric ids. Deeper dynamic/compound predicates stay unpromoted, and cross-hook state sequencing remains `UNPROVEN`.


### 2026-09-29 Zone Editor quality-of-life backlog

Priority stack:
- [x] Undo / redo for position/rotation, animation, add/delete, and drop-table edits; backups remain the hard recovery layer.
- [x] Keyboard transform controls for selected entities, with configurable movement/rotation increments and precision/large-step modifiers.
- [x] Strong selected-object highlighting plus Frame Selected / Frame All camera controls.
- [x] Dirty / unsaved-change state with original-vs-preview values, save-state emphasis, and protection when switching entities.
- [x] Rotation presets and quick-turn controls using the verified FFXI heading convention (0=E, 64=N, 128=W, 192=S).
- [x] Camera presets (Top/North/South/East/West/Perspective) and remembered camera/UI state.
- [x] Three.js transform gizmo for direct XYZ/rotation manipulation without auto-saving.
- [x] Explicit live-DB vs checked-in SQL synchronization state per edited entity.
- [x] Orthographic/top-down editing mode using the same selection/transform tools.
- [x] Multi-select / bulk transform workflow with conservative edit scope.

Additional QOL backlog:
- [x] Double-click entity to select, frame, and enter edit-ready camera distance.
- [x] Improved sortable/filterable entity list with type/id/name/group/level/rotation/reachability/instance columns and dedicated filters.
- [x] Keep map selection and list selection synchronized, including highlighted/auto-scrolled list rows.
- [x] Optional heading text on labels.
- [x] Click/drag facing-direction control from the selected entity's heading arrow.
- [x] Snap controls for coordinate grid, navmesh Y, selected entity, and nearest floor; snapping is always explicit/user-triggered.
- [x] Copy/paste full or partial transforms (position, X/Z, rotation).
- [x] Distance/bearing measurement tool with horizontal/3D distance and delta coordinates.
- [x] Change-history panel for selected entity using the existing edit log/backups.
- [x] One-click restore selected entity to its previous saved state.
- [x] Navmesh diagnostics mode: nearest polygon, component, bounds, distance-to-navmesh, and invalid-placement highlighting.
- [x] Height/elevation coloring.
- [x] Door/prop orientation markers that remain visible without selection.
- [x] Spawn/roam-radius visualization where values genuinely exist: Zone Editor draws explicit `ROAM_DISTANCE` and `SPAWN_LEASH` circles from `mob_pool_mods` or direct literal per-mob Lua overrides, records provenance in the selected-entity panel, supports selected-only or all-explicit overlays, and deliberately omits engine defaults/dynamic conditional values that cannot be resolved safely.
- [x] Clone-selected shortcut in Add workflow.
- [x] Repeated placement mode for multiple copies.
- [x] Ghost preview before add, including heading and instance linkage.


### 2026-09-29 Animation evidence correlation backlog

- [ ] Correlate actual model DAT animation schedules + capture/runtime evidence + LSB script usage into model-specific animation/subanimation labels with provenance and explicit observed/correlated/verified states; do not promote global numeric labels without model-family evidence.

### 2026-09-29 Item Editor strengthening / quality-of-life backlog

Priority stack:
- [x] Unified dirty-state and field-level change summary across item tables, masks, client-relevant fields, mods, pet mods, and latents; navigation discard warnings are enforced.
- [x] Atomic whole-item save covers the core item_* tables plus staged mods/pet-mods/latents: validate first, capture one coherent backup, update all SQL rows in one DB transaction, validate/patch the DAT once, and restore the DAT snapshot if DB commit fails.
- [x] Session undo / redo covers Save Item, create, and delete actions with Ctrl+Z / Ctrl+Y; exact client-record snapshots keep SQL and DAT state synchronized across undo/redo.
- [x] Expanded server-vs-client DAT comparison across every decoded overlapping field, with explicit per-field mismatches rather than level-only comparison.
- [x] Centralized item validation panel with source-proven errors/warnings/info; errors block save, warnings require explicit confirmation.
- [~] Improved item search/results grid: exact ID lookup, name search, level/job/skill/client-state filters, sortable columns, synced/mismatch/server-only state, and recent-item navigation are complete. True DAT-only discovery remains because it requires scanning/indexing client DAT ranges rather than the server-backed search.

Editing / presentation:
- [x] Basic vs Advanced field modes while retaining raw values; mode is persisted locally, all existing-item fields remain mounted so unsaved Advanced values survive mode toggles, and create/clone drafts remain lossless.
- [x] Group fields into logical presentation sections across identity/economy, equip requirements/placement, combat/item-level, usable targeting/timing/charges, puppet, furnishing, client/DAT, and effects.
- [~] Human-readable decoded summary now resolves known bitmasks/enums plus common weapon/use/effect metadata while preserving raw values; richer unit conversions/confirmed semantics remain.
- [x] Inline field descriptions/tooltips added for the editable item schema; descriptions stay conservative where semantics are only partially established.
- [x] Copy/paste individual values and logical field groups with schema-identity guards: fields only paste to the same table.field and groups only to the same table/group.

Create / clone:
- [x] One-click Clone This Item from the open editor.
- [~] Clone effect scopes support template-only, +mods, +mods/pet-mods, and +all latents in the same creation transaction. A distinct pure SQL-only/no-client template mode remains.
- [~] Pre-create summary shows the current verified free-slot candidate ID, DAT category/record/destination, SQL rows, copied effect counts, and write target. The candidate is intentionally not reserved and is revalidated at Save.
- [x] Free ID / DAT-slot browser showing server occupancy, DAT occupancy, used-both/server-only/DAT-only/free states, and only verified reservation rules (item id 0 sentinel).
- [x] After creation, open the new item automatically with Server/DAT synchronization status and undo-create support.

Mods / pet mods / latents:
- [x] Stage mod/pet-mod/latent edits instead of immediately writing each row; include them in unified Save Item.
- [x] Multi-add and copy-all-effects from another item into staging, with scope controls and strict integer/composite-key parsing; nothing writes until Save Item.
- [~] Duplicate mod/pet-mod/latent composite-key detection is enforced in UI staging, batch parsing, and backend validation; effect lists render in normalized key order, while richer filtering remains.
- [x] Surface known mod units/comments and latent-condition parameter semantics only where confirmed; Item Editor now shows verbatim source comments plus conservative structured unit/parameter hints, leaving ambiguous values raw.
- [x] Item-to-item staged-vs-saved comparison now includes editable server fields plus added/removed/changed mods, pet mods, and latents with resolved names where available.

DAT workflow:
- [x] Full Item DAT Record Inspector shows the embedded live item icon, client-facing EN/JP text, singular/plural/article metadata, confirmed common/equipment/weapon/puppet fields, record location/format/stride/hash, explicit unresolved-byte status, authoritative furniture FUD correlation (ROM/74/21.DAT), and a documented legacy 0xC00 vs retail 0x1400 structural audit.
- [x] Embedded item icons are extracted in real time from the same item DAT record (BitmapA payload at 0x280) and rendered as PNG; no separate icon library/index is required.
- [x] Persistent item status header showing Server state, Client DAT state, mismatch count, exact DAT record location, and current Live/Xi-Pivot target.
- [x] Strong visual distinction for LIVE CLIENT WRITE target.
- [x] Always show exact DAT ROM path/category/record and latest backup timestamp.
- [x] Compare the active write target's decoded DAT record against the permanent pristine backup and show changed fields.
- [x] Explicit reconcile actions: use server values or use client values per confirmed overlapping field; structural item-type mismatches remain diagnostic-only and never guess authority.
- [x] Safe record-level restore from exact item backup snapshots, replacing only the selected item's DAT record and enrolling the action in session undo/redo.
- [x] Compare Live DAT vs Xi-Pivot at the selected item-record level and explicitly copy only that record Live→Pivot or Pivot→Live with destination backup.

Search / discovery:
- [x] DAT-only item discovery: opt-in client-record search by name or ID finds populated DAT records with no active-server item_basic row and provides a decoded client-record/icon preview without requiring a server-backed editor load.

History / audit / safety:
- [x] Selected-item change-history panel with field-level summaries, comments, SQL/DAT/effect action types, legacy-backup fallback metadata, and one-click previous-state restore that backs up the current state first.
- [x] Whole-item delete/create/edit history integrates with session undo/redo using exact client-record snapshots.
- [x] Dependency/usage view before destructive changes combines exact active-server content-table references, canonical Workbench graph/catalog relationships, item-scoped client-index identities when present, and opt-in Lua source-text evidence. Exact DB references drive destructive-action warnings; lower-authority evidence stays visibly distinct.
- [x] Constrained batch editor with mandatory dry-run preview, proven-safe dual-authority field whitelist (flags/stack/level/jobs/slots/damage/delay/skill), all-item validation before write, one SQL transaction, one multi-item backup envelope, client-DAT rollback, and batch restore.
- [x] Item comparison mode for SQL, DAT, mods, pet mods, and latents side-by-side, preserving a concise diff summary while showing staged-vs-saved SQL/effect values and saved client DAT records with highlighted differences.


### 2026-09-29 Client Model Viewer integration
- [x] Keep the existing lightweight Three.js/MIT DAT renderer rather than importing the GPL-3.0 `xi-model-viewer` application wholesale.
- [x] Separate server `look_t` model IDs, client FTABLE file IDs, and physical ROM DAT paths instead of treating them as one offset namespace.
- [x] Implement the four-band FFXiMain monster-model lookup documented from VA `0x100C513D`: `+1300`, `+50295`, `+96907`, then `+98239` from model ID 3500 upward.
- [x] Validate the mapped file ID through the configured client's FTABLE/VTABLE before treating it as registered.
- [x] Preserve older hand-verified per-family visible mesh DATs as explicit render hints where available; do not treat those mesh anchors as competing model-ID formulas.
- [x] Add direct raw `look_t` model-ID loading to Client > Model Viewer with mapping/render provenance.
- [x] Add query-string autoload/embed support and a lazy selected-entity model preview inside Zone Editor.
- [x] Build a searchable local-client model catalog from actual Topaz/DSP mob/NPC references plus the configured client's FTABLE/VTABLE: names/aliases, model IDs, resource/render file IDs and DAT paths, family IDs, pool IDs, reference counts, verified visual hints, reverse DAT correlation, Model Viewer picker/direct-DAT lookup, and read-only Zone Editor candidate preview. Resource/skeleton identity stays distinct from visible render hints.
- [x] Add safe Zone Editor flat-model editing: candidate preview is read-only; Apply requires a fresh impact preview. NPC changes are row-local; mob changes resolve spawn → group → shared mob_pools row and show affected spawn/group/zone counts before write. Changes are backup-backed, undoable, and have explicit model-row SQL sync.
- [~] Expand multi-DAT actor composition/animation fidelity only where it materially helps validation; do not reproduce the full external viewer. Humanoid composition now resolves the separate race face DAT in addition to the race skeleton and equipped slot DATs, exposes an ordered composition manifest with resolved/missing provenance, and renders the face as part of the shared-skeleton composite. Model-specific animation schedule/capture correlation remains deferred in the dedicated animation-evidence backlog.


### 2026-09-29 Client model catalog milestone
- [x] Correlate flat creature model IDs from live `mob_pools` and `npc_list` rather than inventing labels from DAT filenames.
- [x] Aggregate server aliases, mob/NPC source kind, family IDs, pool IDs, and reference counts per model ID.
- [x] Resolve FFXiMain resource file IDs and verified family visual hints to the configured client's real DAT paths in bounded batches.
- [x] Search by name/alias, model ID, file ID, family ID, pool ID, or ROM path.
- [x] Reverse-correlate a model ID, file ID, or DAT path back to known model names and server evidence.
- [x] Add Client > Model Viewer catalog picker plus direct DAT/file-ID correlation and rendering.
- [x] Add read-only Zone Editor candidate model search/preview without mutating server data.
- [x] Refuse ambiguous family-specific visual hints for context-free catalog loads; entity-specific loads may still use their exact verified family hint.
- [x] Constrain direct DAT loads to the configured FFXI client root.
- [ ] Next: safe model mutation with impact preview. NPC flat looks can be row-local; mob model changes may affect every spawn/group sharing a `mob_pools` row and must show that blast radius before write.


### 2026-09-29 Zone Editor model / help / animation hardening
- [x] Reset TransformControls to Move/translate whenever a model/entity is clicked or selected, so a previous Rotate mode does not carry into the next selection.
- [x] Add a dedicated Zone Editor Help tab covering selection, camera, transform shortcuts, move/rotate/snap, nav diagnostics, roam/leash overlays, model preview/catalog, animation/subanimation, add/delete/drop editing, backups, and live-DB vs SQL synchronization.
- [x] Add impact-gated model replacement from the shared Client Model Catalog. NPC flat looks mutate only the selected npc_list row; mob flat looks mutate the owning mob_pools row and report all groups/spawns/zones sharing it.
- [x] Store model changes as proper 20-byte MODEL_STANDARD look_t blobs rather than writing raw scalar model IDs into look/modelid columns.
- [x] Back up the actual owning row (npc_list or mob_pools), journal exact SQL, support undo through Zone Editor restore, and provide explicit checked-in SQL sync for the model owner row.
- [x] Replace the sparse hardcoded animation dropdown with current bundled LSB data/enums/animation.yaml values.
- [x] Scan bundled LSB scripts for literal setAnimationSub(N) uses and show counts, nearby literal setModelId values, and source-line samples as model-dependent evidence.
- [x] Expose LSB animationString FOURCC values separately so transient entityAnimationPacket effects are not confused with persistent npc_list animation/animationsub bytes.
- [ ] Future animation work: correlate captures/client model schedules with specific model IDs so subanimation meanings can be promoted from observed script evidence to model-specific verified labels where evidence is sufficient.

### 2026-10-05 Auction House Economy BI and seeding
- [x] Economy Intelligence trends (KPI deltas, activity chart, price movers), queues, category sell-through, supply snapshots, baselines, admin-impact overlay.
- [x] Seeder-tab market history/scenario/clear tool (Test only, fake-seller range 990000-990024); `seed_auction_house.py` now exposes `column_map` for reuse.
- [x] Drawer Close button no longer hidden under the site header (z-index 2000, backdrop click closes).
- [ ] Items/Sellers strengthening pass; supply/sell-through KPI deltas; anomaly detection and forecasting.
