## Repository structure
- Began staged repository restructuring with `workbench/` package namespaces.
- Canonical schema, graph, and provenance implementations now live under `workbench/core/`; root modules are compatibility shims.
- Lua event surface analyzer now lives under `workbench/analyzers/server/lua_events.py`; the historical root entry point is a compatibility shim.
- No repository-wide move was attempted; subsystem migrations remain independently reviewable.

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
