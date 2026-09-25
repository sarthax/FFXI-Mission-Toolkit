# FFXI Workbench — Architecture Audit Record

## Audit baseline
Date: 2026-09-25
Repository: sarthax/FFXI-Mission-Toolkit
Stable branch: main
Rework branch: workbench-rework/audit-foundation

## Audit objective
Establish a durable architecture for an FFXI server/client research and backport workbench. The system must support source comparison, feature/dependency analysis, migration planning, client/server synchronization, packet/capture analysis, and validation without assuming that all FFXI battle systems share the same mechanics.

## Current architectural decisions
### Universal core
The universal core is intentionally minimal and generic:
- Source
- Snapshot
- Domain/System metadata
- Feature
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

### System-specific extensions
Assault, Nyzul, Salvage, Abyssea, Einherjar, and future systems are extensions/plugins. Their mechanics do not belong in the universal schema.

### Evidence model
Evidence types include SERVER_SOURCE, SERVER_DB, SERVER_CPP, CLIENT_DAT, CLIENT_EXE, CLIENT_DLL, PACKET, CAPTURE, REFERENCE, DERIVED, and INFERRED.
Findings include VERIFIED, DERIVED, INFERRED, CONTRADICTED, and UNKNOWN. Confidence must be scoped to the specific question/field being evaluated.

### Server architecture
Use adapters rather than a universal physical SQL schema:
- TopazAdapter
- DSPAdapter
- LSBAdapter
- TopazNextAdapter
- CustomForkAdapter
Physical table/column differences map into logical entities and fields.

### Migration architecture
Existing Lua, SQL, binding, item, coverage, map, and package tools are retained and progressively promoted behind common services. The goal is evolution, not a wholesale rewrite.

### Engine architecture
Generic Implementation represents an implementation artifact. EngineChange is an engine-specific specialization carrying C++ symbol, declaration, definition, dependency, binding, enum, packet, and build information.

### Client architecture
Client capability is modeled separately from server implementation. A feature can exist server-side but remain unavailable or unusable to an older client.
Client/server field bindings distinguish SERVER authoritative, CLIENT authoritative, DUAL / REQUIRED_TO_AGREE, SERVER_ONLY, CLIENT_ONLY, DERIVED, and UNKNOWN.

## Audited areas
| Area | Status | Architecture |
|---|---|---|
| Server indexers | Audited | Adapter |
| Lua migration | Audited | Migration backend |
| SQL migration | Audited | Migration backend |
| Bindings | Audited | Compatibility engine |
| ID mapping | Audited | Universal resolver |
| Entity system | Audited | Core |
| Model resolution | Audited | Client asset resolver |
| DAT/item tooling | Audited | Client adapter |
| Packet tooling | Audited | Protocol adapter |
| Capture tooling | Audited | Runtime evidence |
| Zone tooling | Audited | World subsystem |
| Wiki tooling | Audited | Reference adapter |
| Database | Audited | Research/index cache |
| GUI | Partially audited | API/presentation |
| LLM | Existing Open WebUI/Ollama + read-only DB assistant audited; evidence-aware research/orchestration architecture defined | P1 research service |
| C++ analysis | Implemented; conservative regex/API/dependency indexing with executed regression coverage | P0 |
| Enum analysis | Implemented; enum/constant indexing, scoped resolution, and confidence boundaries covered by CI | P0/P1 |
| Client EXE/DLL | Deferred pending actual binaries | P2 |
| Feature graph | Implemented; canonical SQLite graph, Feature Trace, Feature Checker, semantic mirrors, and candidate traversal | P0 |
| Provenance | Implemented for core server/C++/build/packet analysis; broader adapter consolidation still pending | P0 |
| Package analyzer | Canonical graph import plus dependency-aware package/review pipeline implemented; broader converter coverage remains | P0 |
| System plugins | Not implemented | P1+ |

## Key findings
### 1. SQL schemas are source-specific
DSP, Topaz, and LSB differ in table names, columns, generated values, and representation conventions. Migration must use logical entities plus source/target adapters rather than hard-coded universal SQL schemas.

### 2. Physical identity differs from logical identity
Examples such as mob groups and spawn/drop relationships demonstrate that IDs alone are insufficient. Logical entity identity and physical database identity must be represented separately.

### 3. Lua binding names are not sufficient for compatibility
The existing binding index/audit can establish registration/name presence, but future compatibility analysis must include signature, class, implementation, and semantic differences.

### 4. C++ implementation must be distinguished from binding exposure
A missing Lua binding does not prove that a C++ capability is missing. Conversely, a copied source file does not prove that the implementation is compiled into the target.

### 5. Build integration is part of implementation
A source file that is present but absent from the build target must be reported separately as SOURCE_PRESENT_NOT_BUILT.

### 6. Client capability is independent
Server support and client support are separate dimensions. The Workbench must not report a feature as client-usable solely because the server has implemented it.

### 7. Existing specialized converters are valuable evidence
Assault and Nyzul converters contain real target-specific knowledge such as skip rules, semantic rewrites, and ID mappings. They should be preserved as extensions rather than flattened into generic migration rules.

### 8. Dependency discovery requires evidence levels
require() and similar references can be ambiguous. Dependency edges should record whether they are explicit, deterministic, inferred, or manually overridden.

## Generic dependency edge
Recommended fields:
- edge_id
- source_node
- target_node
- relationship
- evidence_id
- confidence
- status
- discovered_by
- source_location
- notes

## Generic Implementation
Recommended fields:
- implementation_id
- feature_id
- source_snapshot_id
- target_snapshot_id
- artifact_id
- artifact_type
- status
- language
- path
- symbol
- change_type
- scope
- requires_build
- build_target
- evidence_id
- notes

## EngineChange specialization
Additional fields:
- symbol
- symbol_kind
- source_file/source_line
- header_file/header_line
- definition_file/definition_line
- binding
- enum_dependencies
- constant_dependencies
- packet_dependencies
- build_targets
- compile_conditions
- dependencies
- behavior_change
- compatibility_notes

## Engine compatibility states
- PRESENT
- EQUIVALENT
- PARTIAL
- MISSING
- CONFLICTING
- UNKNOWN
- NOT_REQUIRED

## C++ dependency chain
Lua call -> binding -> C++ function -> declaration/implementation -> dependencies/enums/constants/packets -> build target

## Unresolved items
1. General server adapters need broader logical field coverage and Topaz-Next/custom-fork handling beyond the current Topaz/DSP/LSB profiles.
2. The general Feature Migration Engine is partially implemented: logical comparison/planning, dependency-aware package generation, package assembly, generated outputs, provenance journals, validation metadata, cohesion checks, apply-readiness gating, reversible file apply journaling, a conditional LSB→DSP Lua backend, and artifact-level conditional preflight now exist. Package contents are derived from refined MigrationActions so domain-resolved roles are excluded before conversion, and proposal-backed roles may become REVIEW_PROPOSALS actions that bypass source conversion/staging while preserving manual review. Review-only WORKBENCH_PATCH_PLAN artifacts can carry exact patch operations plus source/preview hashes for future drift-aware approval. A separate approval gate must verify target source hashes, anchor replay, and preview hashes before a plan can reach READY_FOR_APPROVAL; this state still has no write authority. A matching WORKBENCH_PATCH_APPROVAL_REQUEST must be explicitly APPROVED before deterministic apply can become eligible. Packaged approval requests must also hash-link to a packaged patch plan or package cohesion fails. An approved deterministic patch apply service now performs a final readiness recheck, creates backups and before/after hash journals, and supports rollback; it is not invoked by the Ancient Vows flagship. A unified patch lifecycle service reports the authoritative package state across cohesion, drift, approval, apply, and rollback. A unified package review summary combines that lifecycle with manifest identity, validation, cohesion, apply readiness, and artifact/action counts for UI/CLI consumers. The read-only `workbench.cli.package_review` entry point exposes the consolidated review as JSON without adding approval or write authority. The read-only `workbench.cli.patch_status` entry point exposes that state as JSON without adding approval or write authority. Remaining work is verified framework reshape coverage, broader source-to-target conversion, and safe database-level application/rollback.
3. Multi-validator ValidationRun orchestration is implemented with independent validation dimensions, canonical ValidationRun/ValidationResult persistence, and suite CLI support. Future work is richer validator registries and runtime/client validator coverage.
4. ClientCapability, DAT asset resolver consolidation, dialog drift, and client/server synchronization services remain incomplete.
5. Actual client pol.exe / FFXiMain.dll bytes are not presently available to this audit pass; exact offsets and binary patches remain unverified.
6. Repository/service migration remains staged; many mature root scripts still need package service extraction and compatibility shims.
7. GUI service extraction remains partial.
8. The LLM/research layer needs implementation of the new ResearchSession/provider/tool-registry architecture; current Open WebUI/Ollama + read-only SQLite integration remains a narrow draft assistant.
9. Domain plugins now have a generalized extension interface. The reusable battlefield framework has active migration/reshape and battlefield representation planning, and mission representation planning can decompose modular source mission behavior into target lifecycle requirements across distributed legacy scripts. Safe role-scoped plugin reshape findings can refine generic MigrationActions without moving domain semantics into the core. Verified mission gaps may emit proposal-only artifacts and exact-anchor patch previews that remain non-target-ready and force review. SQL-backed policy/membership may be generated only when safe, while callback/body mission semantics remain evidence/manual-review driven. Assault-specific analyzers and other system plugins remain future work.

## Legacy evidence integration\nLegacy entity_profile and namespace-map confidence evidence now have canonical graph bridges. Capture and packet observations were already connected. Source-specific confidence semantics are preserved rather than flattened into verified implementation truth.\n\n## Audit discipline
Every future audit pass should update:
- audited modules
- findings
- classification
- priority
- architectural decisions
- unresolved issues
- implementation recommendations
- audit milestone

No finding should be upgraded to VERIFIED without source evidence.


## Current end-to-end validation strategy

The first architecture-level end-to-end test does not require the user's local DSP installation. Use a pinned public server-source snapshot (prefer LandSandBoat and/or Topaz) as an external source fixture, run the Workbench analyzers/adapters against it, import the results into the canonical graph, and verify trace/compatibility/migration outputs with deterministic CI assertions.

This proves the Workbench pipeline and source-adapter boundaries. It does **not** prove that a generated migration works on the user's specific DSP database/server/client. That later validation requires either a representative DSP target snapshot in CI or the user's local/server environment for SQL application, server startup, instance behavior, runtime packet capture, and client capability validation.

Recommended progression:
1. External public-source integration smoke test in CI.
2. Source-to-synthetic-target migration test in CI.
3. Source-to-real DSP repository/schema snapshot validation.
4. Local/live DSP runtime validation.
5. Client DAT/EXE/DLL validation when the actual client files are available.


## LLM/research architecture

The current local-model integration is intentionally conservative and should remain so: model output is draft-only and database access is read-only. The rework expands usefulness by giving the model typed, provenance-rich Workbench tools rather than arbitrary authority.

The target architecture is documented in `docs/workbench/LLM_RESEARCH_ARCHITECTURE.md`. Key decisions:
- provider abstraction separates Open WebUI/Ollama from research logic;
- ResearchSession records preserve model/provider, snapshots, tool calls, evidence IDs, outputs, and verification state;
- typed graph/server/entity/C++/packet/capture/client/migration/validation/reference/source tools are preferred over raw SQL;
- bounded source crawling is allowed only within configured snapshot-scoped roots;
- LLM conclusions enter a FindingProposal/ResearchFinding staging layer rather than canonical truth;
- change generation is proposal-only (diffs, MigrationActions, manifests, validation plans), with deterministic services applying approved changes;
- permission profiles separate read-only research, proposal generation, and deterministic validation orchestration;
- model-independent regression fixtures must verify preservation of UNKNOWN/INFERRED/CONTRADICTED states and provenance discipline.

This is intended to make the LLM useful for deep cross-fork research, dependency discovery, root-cause analysis, migration planning, and research-gap detection without allowing the model to bypass the Workbench evidence model.
