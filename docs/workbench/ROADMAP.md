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
- TopazAdapter
- DSPAdapter
- LSBAdapter
- TopazNextAdapter
- CustomForkAdapter
- logical schema mapping
- Lua migration backend
- SQL migration backend
- binding compatibility engine
- live target validation
- ID/content collision analysis

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

### Phase 6 — Domain plugins (P1+)
- Assault analyzer
- Nyzul analyzer
- Salvage analyzer
- future Abyssea/Einherjar/etc.
Domain plugins may introduce system-specific dependency rules without contaminating the universal core.

### Phase 7 — Automated migration packages (P1+)
- feature manifests
- dependency-aware package generation
- migration action plans
- target-specific conversion
- validation package
- rollback/journal support

### Phase 8 — Evidence-aware LLM research and analysis workspace (P1)
Current state is a useful draft assistant: Open WebUI/Ollama chat plus read-only SQLite tools and logging. The rework should promote this into a bounded research/orchestration layer over the Workbench rather than a free-form chatbot.

Goals:
- [ ] Introduce an LLMProvider interface so Open WebUI/Ollama is one provider rather than the architecture.
- [ ] Add an LLM Research Session model with prompt, model/provider, source snapshots, tool calls, evidence references, outputs, and verification state.
- [ ] Replace raw-table-only research with typed tools over Feature Trace, Feature Checker, server adapters, entity lookup, packet/capture indexes, client capability, wiki/reference adapters, migration plans, and validation results.
- [ ] Allow bounded repository/source crawling over configured server/client/reference roots with explicit scope, depth, file-type, and size limits.
- [ ] Add cross-source comparison tools so an LLM can ask for LSB vs Topaz vs DSP implementations of the same logical feature/entity.
- [ ] Add evidence retrieval that returns canonical node IDs, Evidence IDs, source snapshots, file paths/lines, confidence, and authority with every research result.
- [ ] Add research-plan execution: decompose a question into tool calls, gather evidence, synthesize a report, identify contradictions/gaps, and propose next deterministic analyzer/tool actions.
- [ ] Add a FindingProposal/ResearchFinding staging layer. LLM conclusions remain DRAFT/PROPOSED until deterministic evidence or a human/validator promotes them.
- [ ] Permit write actions only through explicit generated proposals/patch plans; never grant an LLM arbitrary filesystem/SQL mutation.
- [ ] Add patch/package proposal generation that emits diffs or MigrationAction proposals for human review and later deterministic application.
- [ ] Add long-context artifact bundles for a feature: relevant Lua, SQL logical records, C++ functions/bindings, packets, build targets, client capabilities, captures, and references.
- [ ] Add semantic search/indexing over source snapshots and canonical graph metadata while retaining exact grep/SQL/graph tools for verification.
- [ ] Add contradiction detection across server forks, client evidence, captures, and reference sites.
- [ ] Add research notebooks/reports that can be reopened and reproduced against the same pinned snapshots.
- [ ] Add permission profiles such as READ_ONLY_RESEARCH, PROPOSE_CHANGES, and VALIDATION_ORCHESTRATOR.
- [ ] Add budget/timeout/tool-call limits and complete audit logging for every autonomous research run.
- [ ] Add LLM regression/evaluation fixtures using canned tool responses so provider/model changes cannot silently weaken evidence discipline.

Recommended LLM tool surface:
- graph.trace / graph.search
- feature.check / feature.candidates
- server.logical_record / server.compare / server.schema
- entity.lookup / entity.relationships
- packet.lookup / packet.handlers / capture.backtrace
- cpp.symbol / binding.lookup / build.target
- client.capability / dat.lookup
- migration.plan / migration.explain
- validation.status / validation.run-plan
- reference.search / reference.compare
- source.search / source.read (bounded, snapshot-scoped)
- report.create_research_draft

The LLM layer must never convert graph reachability into proof, must preserve UNKNOWN/INFERRED states, and must carry canonical evidence/provenance into every substantive claim.

## Feature Trace architecture
Feature Trace is the central navigation layer between indexed sources. It is deliberately separate from the Feature Checker: a trace answers “what is connected to this subject?” while the checker answers “which declared requirements/capabilities have evidence?” without treating graph connectivity as proof of implementation.

A trace may start from any canonical node ID, or from an unambiguous partial name/identifier search. Traversal supports outgoing, incoming, or bidirectional relationships and a bounded depth. Each edge retains relationship type, status, confidence, evidence ID, source snapshot, and metadata. This allows a client/DAT/packet/C++/Lua/SQL subject to be a launch point as soon as its adapter has populated the canonical graph.

Wiki/reference indexing is intentionally a **launch/navigation layer**, not a source of truth. A future ReferenceAdapter should resolve a wiki result to a canonical entity/feature ID and then invoke Feature Trace. Reference facts remain reference evidence and are never silently promoted to server/client truth.

## Repository structure rework
A staged package-layout migration is now part of the rework. Package namespaces have been introduced without moving mature root scripts yet. The mass move is intentionally deferred until shared service boundaries stabilize; root compatibility wrappers will preserve existing workflows during each subsystem migration. See `docs/workbench/REPOSITORY_STRUCTURE.md`.

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
