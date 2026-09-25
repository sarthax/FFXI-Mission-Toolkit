# Workbench Audit Status

Last updated: 2026-09-25

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
- [ ] General ClientCapability service.
- [ ] DAT asset resolver consolidation.
- [ ] Dialog drift service.
- [ ] Actual EXE/DLL analysis when binaries are available.

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
