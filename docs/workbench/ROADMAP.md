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
- [ ] Connect existing entity_profile, map confidence, capture, packet, and backport reports.

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
- [x] compile conditions/generated sources (conservative)
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

## Immediate audit queue
1. Resolve real packet handlers from actual server dispatch sources when a server source root is indexed.
2. Connect bindings -> C++ symbols -> enums/constants -> packets -> build targets.
3. Extend Backport Package Analyzer to import canonical graph records.
4. Connect entity_profile/map-confidence/capture/packet outputs to the graph.
5. Add full ValidationRun orchestration and independent regression dimensions.
6. Continue GUI/service extraction without rewriting the GUI wholesale.
7. Audit LLM/research tooling and make it evidence-aware.
8. Resume client EXE/DLL analysis when the actual binaries are available.

## Definition of done
The workbench is structurally ready when a feature can be traced from source/version through implementation dependencies, migration actions, client/server requirements, and validation evidence, with every conclusion carrying provenance and an explicit status.
