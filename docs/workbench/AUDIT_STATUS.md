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
