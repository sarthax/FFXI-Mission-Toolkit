# Workbench Audit Status

Last updated: 2026-09-25

## Current milestone
Foundation preserved; engine-change workspace audited; first machine-readable engine-change index added; C++ symbol/build analysis is next.

## New work completed
- [x] Directly inspected the bundled dsp-engine-changes/_example_change scaffold.
- [x] Confirmed the engine-change convention is README + real scoped diff + verification evidence.
- [x] Added engine_change_index.py for evidence-first indexing.
- [x] Added docs/workbench/ENGINE_CHANGE_AUDIT.md.
- [x] Verified the existing project evidence for a real Lua/C++ API-shape mismatch in GetNPCByID.
- [x] Verified the existing mob_groups logical-vs-physical identity warning and content-duplication safeguard.

## Priority queue
### P0 — Core
- [x] Stable main branch identified as protected baseline for rework.
- [x] Universal/core architecture defined.
- [x] Server adapter architecture defined.
- [x] Evidence/Finding model defined.
- [x] Feature/Implementation/Dependency model defined.
- [ ] Canonical graph implementation.
- [ ] Standard machine-readable findings/results.
- [ ] Provenance service consolidation.

### P0 — Migration
- [x] Lua converter audited.
- [x] SQL converter audited.
- [x] Binding audit audited.
- [x] SQL live validation audited.
- [ ] General Feature Migration Engine.
- [ ] Dependency-aware package analyzer.
- [ ] Generalized validation pipeline.

### P0 — Engine
- [x] Generic EngineChange architecture defined.
- [x] Engine-change workspace audited.
- [x] Evidence-first engine-change indexer added.
- [ ] C++ header/declaration index.
- [ ] C++ definition/symbol index.
- [ ] Enum/constant index.
- [ ] Lua binding -> C++ resolution.
- [ ] C++ dependency graph.
- [ ] Build-system integration analyzer.
- [ ] Engine migration classifier.

### P0/P1 — Client
- [x] Item DAT architecture audited.
- [x] Client/server authority concept defined.
- [ ] General ClientCapability service.
- [ ] DAT asset resolver consolidation.
- [ ] Dialog drift service.
- [ ] Actual EXE/DLL analysis when binaries are available.

### P0/P1 — Runtime
- [x] Capture indexing audited.
- [x] Packet decoder audited.
- [ ] Packet -> handler -> feature relationships.
- [ ] ValidationRun/ValidationResult standardization.
- [ ] Automated regression fixtures.

### P1 — Architecture cleanup
- [ ] Extract GUI domain services incrementally.
- [ ] Formalize LLM evidence workflow.
- [ ] Consolidate duplicated ID/entity logic.
- [ ] Standardize source snapshot fingerprints.

### P1+ — Domain plugins
- [ ] Assault plugin.
- [ ] Nyzul plugin.
- [ ] Salvage plugin.
- [ ] Abyssea plugin.
- [ ] Einherjar plugin.

## Branch/PR policy
- main remains the stable baseline.
- Rework is developed on dedicated branches.
- Changes should be reviewed as pull requests before merging.
- Large architectural changes should be split into auditable commits.
- Do not rewrite or delete existing working tools merely to fit the new architecture.

## Evidence levels
- CLIENT_VERIFIED: directly verified against supplied client binaries/assets.
- PUBLIC_VERIFIED: verified against public source/repository/documentation.
- SERVER_VERIFIED: verified against server source/database.
- PACKET_VERIFIED: verified against packet definitions/captures.
- INFERRED: reasoned from evidence but not directly verified.
- UNKNOWN: insufficient evidence.

## Important current client limitation
The client version under investigation is 30191204_1, with testing indicating /wardrobe1-8 recognizes only wardrobes 1–4. Exact EXE/DLL patch points remain deferred until the actual binaries are available to the analysis environment.
