## Repository structure
- Began staged repository restructuring with `workbench/` package namespaces.
- Canonical schema, graph, and provenance implementations now live under `workbench/core/`; root modules are compatibility shims.
- Lua event surface analyzer now lives under `workbench/analyzers/server/lua_events.py`; the historical root entry point is a compatibility shim.
- No repository-wide move was attempted; subsystem migrations remain independently reviewable.

# Workbench Audit Status

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

The Workbench now has a generic adapter-aware live database validation path that complements, but does not replace, the existing specialized `backport_sql_live_check.py` MariaDB tooling.

Implemented:
- `workbench.migrations.live_target_validation` compares expected adapter-normalized `LogicalRecord` records against current live target rows using target adapter physical table/column mappings;
- the live reader is DB-API based and issues SELECT-only queries;
- results distinguish VERIFIED, MISSING, CONTRADICTED, AMBIGUOUS, UNKNOWN, and FAILED live states;
- successful live comparison validates database representation only and does not imply runtime behavior;
- live results can persist as canonical `ValidationRun` and `ValidationResult` records;
- connection credentials are never persisted in canonical validation metadata;
- `python -m workbench.cli.live_target_validation` supports read-only SQLite validation and optional MySQL/MariaDB validation via `mysql-connector-python`;
- MySQL/MariaDB passwords are read from an environment variable (default `FFXI_DB_PASSWORD`) rather than accepted as a normal CLI argument.

The legacy `backport_sql_live_check.py` remains present and separate because it contains specialized package ID/content-duplication logic, including `mob_groups` live-conflict analysis. Existing admin/write tooling is not removed or absorbed into the generic validator.


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

The live `gui_server.py` route surface contains 142 FastAPI method/path registrations. Every registration now has exactly one canonical GUI home and a migration disposition. The map is regression-checked so future route additions/removals must be deliberately incorporated into the information architecture.

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
- Packages: 0 current routes (NEW GUI required)

The high Tools count is dominated by the supporting APIs/actions of the existing Zone Editor and Item Editor and does not imply those tools will be flattened into generic navigation. The Domains count currently consists of the Assault landing page plus the existing Nyzul page/data/action routes.

No existing GUI capability was removed or hidden by this milestone.


## 2026-09-25 — Shared GUI application shell

Implemented the shared GUI shell and subsequent Domains workspace expansion without redesigning existing Nyzul/Zone Editor internals. The current FastAPI surface is 142 routes.

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

`workbench.gui_shell` owns the read-only shell model and resolves active workspace ownership from `GUI_ROUTE_MAP.json`; it does not add routes, select snapshots, or mutate settings. Validation and Packages remain visible top-level workspaces while their consolidated pages remain future work. The existing Backport Package route stays available as an explicitly labeled legacy workflow.

Regression coverage in `test_fixtures/test_gui_shell.py` reruns the 142-route information-architecture check, verifies dynamic route ownership including Domains/Battle Systems, verifies configured versus unknown context semantics, and renders representative Home, Captures, and mutation-editor templates through the shared shell. The Workbench regression workflow runs this shell test.


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
