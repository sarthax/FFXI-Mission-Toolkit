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
2. Keep Assault, Nyzul, Salvage, Abyssea, Einherjar, and other game systems as optional system-specific analyzers/plugins.
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
The core should not know about Assault Rank, Assault Points, lockboxes, appraisal pools, Nyzul floors, Salvage cells, Abyssea Atma, Cruor, Einherjar chambers, or similar concepts.
Those belong in optional plugins/analyzers such as Assault, Nyzul, Salvage, Abyssea, Einherjar, and future FFXI systems.
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

## Major roadmap
### Phase 0 — Preserve and baseline
- Freeze main as the stable reference.
- Establish this audit/roadmap documentation.
- Record branch/PR workflow.
- Record current audit findings and unresolved items.

### Phase 1 — Canonical evidence and feature graph (P0)
- [x] Formalize Source/Snapshot.
- [x] Formalize Entity/Relationship.
- [x] Formalize Evidence/Finding.
- [x] Formalize Feature/Implementation/Dependency.
- [x] Add machine-readable analysis outputs.
- [x] Implement generic SQLite-backed canonical graph store.
- [ ] Connect existing entity_profile, map confidence, capture, packet, and backport reports. Initial capture graph connector is now present; broader adapters remain.
- [x] Add generic bidirectional Feature Trace over canonical graph relationships.
- [x] Add Feature Checker requirements/status evaluation on top of Feature Trace.
- [x] Add build-condition/generated-source analyzer.

### Phase 2 — Server adapters and migration engine (P0)
- [x] TopazAdapter
- [x] DSPAdapter
- [x] LSBAdapter
- [ ] TopazNextAdapter
- [ ] CustomForkAdapter
- [ ] Logical schema mapping — core equipment, instances, NPCs, mobs, spawns, drops, battlefield registry/membership, and SQL extraction are implemented; broader schema coverage remains.
- [ ] Generic FeatureSurface comparison — artifact roles, entity coverage, and behavioral capabilities are implemented; migration-rule coverage remains.
- [ ] Snapshot-specific capability observations and target-aware Feature Checker evaluation — implemented for canonical graph/flagship E2E; broader capability producers remain.
- [ ] Lua migration backend — generic backend registry is implemented; legacy Topaz→DSP Lua conversion is registered explicitly. LSB→DSP and other routes remain unsupported until dedicated converters exist.
- [ ] SQL migration backend — generic backend registry is implemented; legacy Topaz→DSP SQL conversion is registered explicitly. Broader source/target routes remain unsupported.
- [ ] Binding compatibility engine
- [ ] Live target validation
- [ ] ID/content collision analysis

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
- DAT adapters
- item DAT editing
- client/server field bindings
- client capability model
- dialog drift
- packet/client/server relationships
- EXE/DLL analysis when binaries are available

### Phase 5 — Runtime validation (P0/P1)
- capture index
- NPC logger/path/action evidence
- packet evidence
- test fixtures
- validation runs/results

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

System-specific packages compose reusable frameworks rather than reimplementing them:
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
- [x] validation package — planned Lua/SQL plus generated target SQL artifacts generate independent validation requirements.
- [x] package assembly + provenance — source and generated artifacts are staged with SHA-256 journals and review metadata.
- [x] package cohesion verification — assembled manifest, validation metadata, journals, staged files, generated outputs, and recorded hashes are checked for internal consistency before apply; the flagship Ancient Vows E2E now exercises this gate.
- [x] reversible file apply journal foundation — explicit file application can be rolled back; live SQL/database apply and rollback remain future work.
- [x] apply-readiness gate — cohesion and validation readiness are checked before a package is eligible for explicit file application; Ancient Vows currently remains MANUAL_REQUIRED because LSB→DSP conversion is not yet a supported backend.
- [x] rollback/journal foundation — staged source/generated artifacts are hashed/journaled and explicit file apply operations can be rolled back; live SQL/database rollback remains future work.
- [x] generated target-artifact foundation — safe domain reshape proposals can emit target-ready staged artifacts with provenance without applying them.

### Phase 8 — Evidence-aware LLM Research & Agent Layer (P1)
Current state is a useful draft assistant: Open WebUI/Ollama chat plus read-only SQLite tools and logging. The rework should promote this into a bounded, reproducible research/orchestration layer over the Workbench rather than a free-form chatbot.

Core architecture:
- [ ] Provider abstraction for Open WebUI, Ollama Direct, and future explicitly configured providers; the toolkit must not depend on one provider's response schema.
- [ ] ResearchSession persistence with prompt/question, provider/model, pinned source/target snapshots, selected feature/entity roots, tool policy, tool transcripts, evidence IDs, findings/proposals, outputs, verification state, timestamps, usage, budgets, and replay metadata.
- [ ] Typed Workbench tool registry covering graph, feature, server adapters, entities, C++, bindings, enums, packets, captures, build targets, client capabilities, migration, validation, references, and source inspection.
- [ ] Bounded source crawler over configured repositories/snapshots with include/exclude rules, path/type/size/depth limits, secret/key exclusions, and no arbitrary filesystem access.
- [ ] Cross-repository research over configured DSP/Topaz/LSB/Topaz-Next/custom-fork roots and pinned public source snapshots.
- [ ] Semantic search/indexing over source snapshots and canonical graph metadata, while retaining exact grep/SQL/graph/source tools for deterministic verification.
- [ ] Evidence-first retrieval that returns canonical node IDs, source snapshot IDs, Evidence IDs, source file/path/line locations when available, confidence/status, and authority/source domain with every substantive result.
- [ ] Long-context feature artifact bundles combining relevant Lua, SQL logical records, C++ functions/bindings, enums, packets, build targets, client capabilities, captures, and references.
- [ ] Research-plan execution that decomposes a question into bounded tool calls, gathers evidence, synthesizes a report, identifies contradictions/gaps, and proposes the next deterministic analyzer/capture/validator actions.
- [ ] Research gap detection for UNKNOWN/MISSING/CONTRADICTED graph endpoints and recommendations for the next analyzer/capture/validator.
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
1. Validate and extend class-aware capture → Lua event → binding/C++ resolution, adding evidence-backed local/returned-object typing without guessing.
2. Resolve real packet handlers from actual server dispatch sources when a server source root is indexed.
3. Connect bindings -> C++ symbols -> enums/constants -> packets -> build targets.
4. Extend Backport Package Analyzer to import canonical graph records.
5. Connect entity_profile/map-confidence/capture/packet outputs to the graph.
6. Add full ValidationRun orchestration and independent regression dimensions.
7. Continue GUI/service extraction without rewriting the GUI wholesale.
8. Build the evidence-aware LLM research/orchestration layer described in Phase 8; begin with typed Workbench tools and reproducible ResearchSession records rather than expanding free-form SQL access.
9. Resume client EXE/DLL analysis when the actual binaries are available.

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
