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
| LLM | Partially audited | Research assistant |
| C++ analysis | Architecture defined; implementation audit pending | P0 |
| Enum analysis | Architecture defined; implementation audit pending | P0/P1 |
| Client EXE/DLL | Deferred pending actual binaries | P2 |
| Feature graph | Architecture defined; implementation pending | P0 |
| Provenance | Partially present; standardization pending | P0 |
| Package analyzer | Partially present; extension pending | P0 |
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
1. Actual dsp-engine-changes artifact contents need direct inspection.
2. C++ AST/symbol extraction implementation has not yet been added to the toolkit.
3. Build-system analyzer has not yet been implemented.
4. Actual client pol.exe / FFXiMain.dll bytes are not presently available to this audit pass; exact offsets and binary patches remain unverified.
5. Canonical schema migration from current SQLite tables into the generalized graph is not implemented yet.
6. GUI service extraction remains partial.
7. The LLM/research layer needs formal evidence/provenance integration.

## Audit discipline
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
