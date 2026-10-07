# Phase A Component Ownership Inventory

Status: **Phase A ownership map for the modular-monorepo migration**

This document applies the adopted `COMPONENT_BOUNDARY_PLAN.md` to the current repository before any further broad Python relocation. It is an ownership and dependency audit, not a code move.

## Scope and rules

The inventory covers:

- all **97 Python files still at repository root**;
- the existing `src/workbench` package families;
- current component-placement mismatches that should be corrected during the remaining src migration;
- known direct cross-component dependencies that need contracts or public provider APIs;
- UI/application ownership, external dependency ownership, and logical DB ownership at component level.

The seven ownership buckets are:

1. **Core** — shared graph/schema/provenance/identity/config/contracts only.
2. **Captures** — capture ingestion, protocol, evidence search, integrity, correlation, OCR/video and capture spatial reconstruction.
3. **Validation / Packages** — environment comparison, drift, compatibility, package assembly/backport/migration and live validation.
4. **Development / Research** — Entity Profile, Feature Trace, Behavior, mission/server/reference/research workflows.
5. **Editors** — intentional write/edit workflows, journals, backups and rollback.
6. **Client Shared** — reusable read-only client parsing, snapshots, identity, DAT/model/binary evidence.
7. **Bootstrap / Tests** — repository launch/install/test infrastructure and the temporary integrated application host.

`gui_server.py` is assigned to **Bootstrap / Tests / integrated app host** during decomposition because it is currently the composition root for all products. Its routes ultimately move to product-owned app modules; the final shared host should be small and product-neutral.

---

# 1. Root Python ownership map — 97 files

Every root-level Python file present at the start of Phase A has exactly one owner below.

## Core — 4

| Root file | Final ownership / intended destination | Notes |
| --- | --- | --- |
| `addon_tools.py` | Core runtime → `src/workbench/runtime/addon_tools.py` | Shared addon/resource discovery. Must remain product-neutral. |
| `settings.py` | Core config → `src/workbench/core/config/settings.py` | High fan-in. Central path/config migration before move. |
| `workbench_connect.py` | Core runtime/integration → `src/workbench/runtime/connect.py` | Shared process/integration surface; preserve stable external entry point if used. |
| `workbench_connect_server.py` | Core runtime/integration → `src/workbench/runtime/connect_server.py` | Same ownership as connect client. |

## Captures — 7

| Root file | Final ownership / intended destination | Notes |
| --- | --- | --- |
| `salvage_reconstruct.py` | Captures CLI → `src/workbench/captures/cli/salvage_reconstruct.py` | Canonical reconstruction logic already exists in packaged code; root file is mostly launcher. |
| `build_capture_index.py` | Captures ingestion → `src/workbench/captures/ingestion/build_index.py` | Large/high fan-in. Root wrapper until setup/import callers migrate. |
| `capture_backtrace.py` | Captures correlation → `src/workbench/captures/correlation/backtrace.py` | Evidence/capture-specific. |
| `capture_graph_connect.py` | Captures correlation → `src/workbench/captures/correlation/graph_connect.py` | Must depend on Core graph/provenance contracts, not product internals. |
| historical `youtube_chat_ocr.py` | Captures video → `src/workbench/captures/video/ocr.py` | Root launcher retired; external-tool/profile dependencies remain Capture optional dependencies. |
| historical `packet_decode.py` | Shared packets → `src/workbench/packets/decode.py` | Root launcher retired; Packetlyzer/vendor paths are package-owned. |
| `packet_opcode_index.py` | Captures packets → `src/workbench/captures/packets/opcode_index.py` | Protocol research belongs with Capture Workbench. |

## Validation / Packages — 18

| Root file | Final ownership / intended destination | Notes |
| --- | --- | --- |
| `id_bridge.py` | Validation drift → `src/workbench/validation/drift/id_bridge.py` | Canonical implementation is currently under Core services and should move out of Core. |
| `validation_pipeline.py` | Validation orchestration → `src/workbench/validation/pipeline.py` | Generic validation runner, not Core. |
| `backport_binding_audit.py` | Packages migration → `src/workbench/packages/migration/binding_audit.py` | Backport/package concern. |
| `backport_binding_index.py` | Packages migration → `src/workbench/packages/migration/binding_index.py` | Same. |
| `backport_convert_7_packages.py` | Packages migration → `src/workbench/packages/migration/convert_7_packages.py` | Maintenance CLI; verify long-term support. |
| `backport_convert_gm_debug_tools.py` | Packages migration → `src/workbench/packages/migration/convert_gm_debug_tools.py` | Same. |
| `backport_convert_nyzul_package.py` | Packages migration → `src/workbench/packages/migration/convert_nyzul_package.py` | Same. |
| `backport_coverage_check.py` | Validation/packages → `src/workbench/packages/validation/coverage.py` | Package completeness/coverage. |
| `backport_item_audit.py` | Validation/packages → `src/workbench/packages/validation/item_audit.py` | Package/item compatibility. |
| `backport_lua_convert.py` | Packages migration → `src/workbench/packages/migration/lua_convert.py` | Root compatibility entry point initially. |
| `backport_lua_sanity_check.py` | Validation/packages → `src/workbench/packages/validation/lua_sanity.py` | Validation responsibility. |
| `backport_map_confidence_check.py` | Validation/packages → `src/workbench/packages/validation/map_confidence.py` | Validation responsibility. |
| `backport_map_lint.py` | Validation/packages → `src/workbench/packages/validation/map_lint.py` | Validation responsibility. |
| `backport_package.py` | Packages migration → `src/workbench/packages/migration/package.py` | Package core; high regression coverage. |
| `backport_sql_convert.py` | Packages migration → `src/workbench/packages/migration/sql_convert.py` | Root compatibility entry point initially. |
| `backport_sql_live_check.py` | Validation live DB → `src/workbench/validation/live_db/sql_check.py` | Live environment validation, not package assembly. |
| `engine_change_index.py` | Validation environments → `src/workbench/validation/environments/engine_change_index.py` | Cross-environment engine comparison. |
| `engine_migration_compare.py` | Validation environments → `src/workbench/validation/environments/engine_compare.py` | Same. |

## Development / Research — 39

| Root file | Final ownership / intended destination | Notes |
| --- | --- | --- |
| `mission_toolkit.py` | Development CLI → `src/workbench/devtools/app/mission_toolkit.py` | Legacy/stable developer CLI. |
| `entity_profile.py` | Development entities → `src/workbench/devtools/entities/profile.py` | Path/root dependencies must be decoupled first. |
| `feature_checker.py` | Development features → `src/workbench/devtools/features/checker.py` | Canonical implementation currently under Core services; root wrapper remains for GUI. |
| `feature_trace.py` | Development features → `src/workbench/devtools/features/trace.py` | High fan-in and currently directly imports Capture services. |
| `lookup_entity.py` | Development entities → `src/workbench/devtools/entities/lookup.py` | Entity research/lookup, not Client Shared identity parsing. |
| `lua_event_index.py` | Development server analysis → `src/workbench/devtools/server/lua_events.py` | Canonical implementation already packaged; preserve CLI while documented. |
| `explore_event.py` | Development server analysis → `src/workbench/devtools/server/explore_event.py` | Server/event analysis. |
| `mission_event_reconcile.py` | Development missions → `src/workbench/devtools/missions/event_reconcile.py` | Mission implementation research. |
| `mission_graph_ingest.py` | Development missions → `src/workbench/devtools/missions/graph_ingest.py` | Mission graph research. |
| `build_condition_index.py` | Development server analysis → `src/workbench/devtools/server/condition_index.py` | Server implementation index. |
| `audit_dialog_drift.py` | Development reference → `src/workbench/devtools/reference/dialog/audit_drift.py` | Research/reference evidence. |
| `dialog_drift_overview.py` | Development reference → `src/workbench/devtools/reference/dialog/drift_overview.py` | Same. |
| `ffxiclopedia_adapter.py` | Development reference → `src/workbench/devtools/reference/ffxiclopedia.py` | Reference provider implementation. |
| `wiki_claim_compare.py` | Development reference → `src/workbench/devtools/reference/wiki_claim_compare.py` | Evidence comparison. |
| `wiki_compile.py` | Development reference → `src/workbench/devtools/reference/wiki_compile.py` | Evidence compilation. |
| `wiki_evidence.py` | Development reference → `src/workbench/devtools/reference/wiki_evidence.py` | Reference evidence provider. |
| `wiki_lookup.py` | Development reference → `src/workbench/devtools/reference/wiki_lookup.py` | Normalize dump path first. |
| `scrape_bg_wiki.py` | Development reference → `src/workbench/devtools/reference/scrape_bg_wiki.py` | Network/reference acquisition. |
| `build_wiki_index.py` | Development reference/indexing → `src/workbench/devtools/reference/build_wiki_index.py` | Setup wrapper may remain temporarily. |
| `llm_client.py` | Development research → `src/workbench/devtools/research/legacy_llm/client.py` | Legacy research provider. |
| `llm_db_tools.py` | Development research → `src/workbench/devtools/research/legacy_llm/db_tools.py` | DB/path audit. |
| `llm_log.py` | Development research → `src/workbench/devtools/research/legacy_llm/log.py` | Normalize DB path. |
| `research_gaps.py` | Development research → `src/workbench/devtools/research/gaps.py` | Research workflow. |
| `zone_plot.py` | Development spatial/viewer → `src/workbench/devtools/spatial/zone_plot.py` | Read-only viewer belongs in Devtools; editing remains Editors. |
| `zmesh.py` | Development spatial/viewer → `src/workbench/devtools/spatial/zmesh.py` | Visual mesh/cache consumer; GUI path normalization first. |
| `build_zone_topdown.py` | Development spatial → `src/workbench/devtools/spatial/build_topdown.py` | Read-only derived visualization output. |
| historical `build_zone_visual_cache.py` | Development spatial → `src/workbench/devtools/spatial/build_visual_cache.py` | Root launcher retired; read-only visualization/cache builder is package-owned. |
| `build_plot_descriptors.py` | Development spatial → `src/workbench/devtools/spatial/build_plot_descriptors.py` | Plot/reference descriptors. |
| `pull_mob_positions.py` | Development spatial/server evidence → `src/workbench/devtools/spatial/pull_mob_positions.py` | Read-only source extraction. |
| `nyzul_plot.py` | Development domain tooling → `src/workbench/devtools/domains/nyzul_plot.py` | Domain visualization/research. |
| `build_database.py` | Development indexing → `src/workbench/devtools/indexing/build_database.py` | Setup invokes it; root wrapper until bootstrap conversion. |
| `build_dialog_index.py` | Development indexing → `src/workbench/devtools/indexing/build_dialog_index.py` | Same. |
| `build_dsp_index.py` | Development indexing → `src/workbench/devtools/indexing/build_dsp_index.py` | Server/reference index. |
| `build_integration_index.py` | Development indexing → `src/workbench/devtools/indexing/build_integration_index.py` | Implementation integration index. |
| `build_lsb_index.py` | Development indexing → `src/workbench/devtools/indexing/build_lsb_index.py` | Server source index. |
| `build_npc_index.py` | Development indexing → `src/workbench/devtools/indexing/build_npc_index.py` | Server/entity index. |
| `build_sql_index.py` | Development indexing → `src/workbench/devtools/indexing/build_sql_index.py` | High fan-in; migrate imports carefully. |
| `build_topaz_index.py` | Development indexing → `src/workbench/devtools/indexing/build_topaz_index.py` | Historical/server source index. |
| `ingest_global_tables.py` | Development indexing → `src/workbench/devtools/indexing/ingest_global_tables.py` | Setup wrapper until bootstrap conversion. |

## Editors — 4

| Root file | Final ownership / intended destination | Notes |
| --- | --- | --- |
| `item_dat_tools.py` | Editors items/client → `src/workbench/editors/items/dat_tools.py` | Contains write/backup/journal behavior; not Client Shared. |
| `item_edit.py` | Editors items → `src/workbench/editors/items/editor.py` | Large write workflow. |
| `zone_edit.py` | Editors zone → `src/workbench/editors/zone/editor.py` | Write workflow and journals/backups. |
| `fix_zone_door_props.py` | Editors zone/maintenance → `src/workbench/editors/zone/fix_door_props.py` | Intentional data modification. |

## Client Shared — 18

| Root file | Final ownership / intended destination | Notes |
| --- | --- | --- |
| `binary_inspector.py` | Client Shared binary → `src/workbench/client/binary/inspector.py` | Read-only. |
| `client_binary_analyze.py` | Client Shared binary → `src/workbench/client/binary/analyze.py` | Read-only. |
| `client_binary_diff.py` | Client Shared binary → `src/workbench/client/binary/diff.py` | Read-only. |
| `client_binary_index.py` | Client Shared binary → `src/workbench/client/binary/index_cli.py` | CLI delegates to packaged read-only services. |
| `cpp_api_index.py` | Client Shared binary → `src/workbench/client/binary/cpp_api_index.py` | Read-only source/binary evidence. |
| `cpp_dependency_index.py` | Client Shared binary → `src/workbench/client/binary/cpp_dependency_index.py` | Same. |
| `dat_extractor_bin.py` | Client Shared DAT → `src/workbench/client/dat/extractor_bin.py` | Read-only extraction; normalize vendor path. |
| `dat_inspector.py` | Client Shared DAT → `src/workbench/client/dat/inspector.py` | Read-only inspection. |
| `client_model_catalog.py` | Client Shared models → `src/workbench/client/models/catalog.py` | Reusable by Devtools and Editors. |
| `client_model_resolver.py` | Client Shared models → `src/workbench/client/models/resolver.py` | Reusable resolution primitive. |
| `client_overview.py` | Client Shared snapshots → `src/workbench/client/snapshots/overview.py` | Build/snapshot evidence. |
| `model_schedule_dump.py` | Client Shared models → `src/workbench/client/models/schedule_dump.py` | Read-only client model/animation evidence. |
| `model_viewer.py` | Client Shared models → `src/workbench/client/models/viewer.py` | Read-only renderer/service; product UI can be exposed by Devtools/Editors. |
| `mob_look_decode.py` | Client Shared models → `src/workbench/client/models/mob_look_decode.py` | Read-only decoder. |
| `mob_model_tables.py` | Client Shared models → `src/workbench/client/models/mob_model_tables.py` | Read-only tables. |
| `gear_tables.py` | Client Shared item reference → `src/workbench/client/items/gear_tables.py` | Read-only item reference data. |
| `build_altana_index.py` | Client Shared models/indexing → `src/workbench/client/models/build_altana_index.py` | Read-only index generation; state path must be explicit. |
| `zone_animation_meta.py` | Client Shared models/animation → `src/workbench/client/models/zone_animation_meta.py` | Read-only animation metadata shared by viewers/editors. |

## Bootstrap / Tests / integrated host — 7

| Root file | Final ownership / intended destination | Notes |
| --- | --- | --- |
| `gui_server.py` | Integrated app host → eventually small `src/workbench/app/host.py`; product routes move to component `app/` modules | Temporary composition root, **move/decompose last**. |
| `install_external_tools.py` | Bootstrap → `scripts/bootstrap/install_external_tools.py` | Update setup wrapper atomically. |
| `install_xi_tinkerer.py` | Bootstrap → `scripts/bootstrap/install_xi_tinkerer.py` | Same. |
| `reset_install.py` | Bootstrap → `scripts/bootstrap/reset_install.py` | Update `reset_install.bat` atomically. |
| `tests/legacy/test_backport_lua_convert.py` | Tests → `tests/regression/packages/tests/legacy/test_backport_lua_convert.py` | Validation/Packages regression. |
| `tests/legacy/test_backport_sql_convert.py` | Tests → `tests/regression/packages/tests/legacy/test_backport_sql_convert.py` | Validation/Packages regression. |
| `tests/legacy/test_capture_ingestion.py` | Tests → `tests/regression/captures/tests/legacy/test_capture_ingestion.py` | Capture regression. |

Root total check: **4 + 7 + 18 + 39 + 4 + 18 + 7 = 97**.

---

# 2. Existing `src/workbench` ownership

Existing folder names are not automatically treated as component boundaries. The following ownership rules supersede current placement.

## Remains Core/shared

- `src/workbench/core/graph.py`
- `src/workbench/core/schema.py`
- `src/workbench/core/provenance.py`
- `src/workbench/runtime/*` when product-neutral
- future `src/workbench/core/contracts/*`
- future `src/workbench/core/identity/*` only for universal cross-source identity contracts, not product-specific resolution workflows

`Core` should end the segregation with very little product behavior.

## Existing Client package → Client Shared

`src/workbench/client/*` is owned by **Client Shared** when the module is read-only. This includes current snapshot/fingerprint, event/entity identity, DAT adapter and binary/model readers.

Any write-capable client module encountered during later audit moves to **Editors**, even if it currently resides under `workbench.client`.

## Existing migrations package → split Validation / Packages

`src/workbench/migrations/*` is currently a mixed namespace and is not a final component name.

Move toward:

- environment/logical comparison, identity drift, collision detection, live target validation → `workbench.validation.*`;
- package plan/manifest/assembly/review/cohesion/apply gates → `workbench.packages.*`;
- patch/package generation/apply/approval/backends → `workbench.packages.migration.*`;
- client DAT migration that performs writes → `workbench.editors.client.*` or `workbench.packages.migration.*` based on whether it is an interactive editor action or package migration operation.

Observed current coupling: `workbench.migrations.backend_registry` still imports root `backport_lua_convert` and `backport_sql_convert`; those are same-component legacy dependencies but must be converted to packaged imports during the Packages move.

## Existing reference and research packages → Development / Research

- `src/workbench/reference/*` → `src/workbench/devtools/reference/*` unless a tiny provider contract belongs in Core.
- `src/workbench/research/*` → `src/workbench/devtools/research/*`.

Research Sessions remain a Development/Research product capability. Other products may consume research evidence through Core contracts, but do not own the research runner.

## Existing analyzers and server adapters → Development / Research

- `src/workbench/analyzers/server/*` → `src/workbench/devtools/server/*`.
- `src/workbench/adapters/servers/*` → Development server provider implementation, with shared interfaces defined in Core contracts.

Validation is allowed to consume a server provider contract; it should not depend directly on Development-internal adapter implementations long term.

## Existing domains package → split by workflow

- `src/workbench/domains/service.py` and generic domain definitions → Development/Research domain catalog.
- `src/workbench/domains/salvage_reconstruction.py` → Captures spatial/reconstruction because its primary input/output is capture evidence reconstruction.
- future mission/domain extraction logic independent of capture observations → Development/Research.

## Existing CLI package → CLI owner follows the product

Current `src/workbench/cli` must be split rather than remain a generic dumping ground:

- `binding_compatibility.py` → Validation / Packages;
- `live_target_validation.py` → Validation;
- `package_review.py`, `patch_status.py` → Packages;
- `client_identity_snapshot.py` → Client Shared;
- `event_identity_compare.py` → Client Shared if comparing client builds only; Validation if it becomes cross-environment policy/reporting. Current classification: **Client Shared** primitive CLI.

Product-specific launchers should eventually live under the product's `app/` or `cli/` package.

## Existing plugins package → Development first, contracts later

Current domain plugins are Development/Research implementation unless they are reduced to neutral provider contracts. A current hotspot is `plugins/domain/*` importing `workbench.migrations.*`; package/migration artifact types used by domain plugins should become Core contracts or explicit Packages APIs rather than Development importing Packages internals.

---

# 3. `src/workbench/core/services` reclassification

This directory is currently the clearest source of accidental product coupling. Existing placement under `core/services` does **not** mean the modules belong to Core.

## Move to Captures

- `capture_chat.py`
- `capture_integrity.py`
- `capture_related_evidence.py`
- `capture_spatial.py`
- `lobby_ingest.py`
- `packet_correlation.py`
- `packet_identity.py`
- `pcap_ingest.py`
- `raw_packet_ingest.py`
- `timeline_alignment.py`

These should become `workbench.captures.*` services. Capture-internal imports among them are valid after the move.

## Move to Client Shared

- `client_binary_graph.py`
- `client_entity_graph.py`

These are client evidence/graph integration services. They may write shared graph evidence through Core graph APIs but are owned by Client Shared.

## Move to Development / Research

- `acquisition_catalog.py`
- `acquisition_identity.py`
- `conditional_dependencies.py`
- `dependency_map_presentation.py`
- `entity_profile_graph.py`
- `feature_candidates.py`
- `feature_checker.py`
- `feature_surface_graph.py`
- `feature_trace_binding_drilldown.py`
- `feature_trace_catalog.py`
- `feature_trace_closure.py`
- `feature_trace_dossier.py`
- `feature_trace_providers.py`
- `map_confidence_graph.py` when used as implementation/reference evidence presentation
- `obtainability_closure.py`
- `scripted_behavior_visualizer.py`
- `server_catalog_identity.py`
- `wiki_evidence_graph.py`

`feature_surface_validation.py` is assigned to **Validation / Packages** if it decides migration/package readiness; presentation-only feature surface analysis belongs Development. Current classification: **Validation / Packages**.

## Move to Validation / Packages

- `feature_package_analyzer.py`
- `feature_surface_validation.py`
- `id_bridge.py`
- `validation_run.py`

`capability_producers.py` remains a **Core contracts/registry candidate** only if it is product-neutral. If it encodes concrete product implementations, split the registry contract into Core and move registrations into their owning components during Phase B.

`identity_resolver.py` requires a deliberate split audit: universal identity contracts/resolution primitives may remain Core, while client/capture/server-specific lookup providers belong to their respective components. Phase B should extract provider interfaces before moving provider-specific branches.

---

# 4. Direct cross-component dependency hotspots observed

Phase A does not change imports yet; it records where Phase B contracts are needed.

| Current dependency | Classification | Required outcome |
| --- | --- | --- |
| root `feature_trace.py` → `workbench.core.services.capture_integrity` | Development → Capture direct implementation import | Replace with Capture evidence/provider contract. Capture dependency is optional for Development. |
| `core/services/pcap_ingest.py` → capture integrity/raw packet/lobby services | Capture → Capture, currently mislabeled Core | Move together under Captures; no contract needed internally. |
| `core/services/raw_packet_ingest.py` → capture integrity/chat | Capture → Capture, currently mislabeled Core | Move together. |
| `plugins/domain/*` → `workbench.migrations.*` | Development → Validation/Packages internals | Replace shared artifact types with Core contract or explicit Packages public API. |
| `cli/live_target_validation.py` → server adapter implementation + migrations | Validation → Development adapter internals | Introduce server-source provider contract; Validation consumes interface. |
| `migrations/backend_registry.py` → root `backport_*` modules | Packages → legacy root same-component code | Package the implementations and remove root-to-src dependency. |
| `gui_server.py` → nearly every product area | integrated host → all components | Decompose routes late; host only registers component apps. |
| tests importing root builders/services | Tests → physical filenames | Update to canonical product APIs during each component move. |

The current Capture service graph already shows a coherent internal cluster: capture chat/related evidence/raw packet/PCAP modules all depend on Capture integrity. This should move as one component rather than be exposed through Core.

---

# 5. UI, routes, templates and navigation ownership

Until `gui_server.py` is decomposed, route ownership is logical rather than physical.

## Captures app

Owns routes/templates/navigation for:

- capture list/detail/import
- Capture Data Explorer
- Evidence Search modules
- packet decoder/opcode tools presented as capture/protocol research
- capture 2D/3D/path visualization
- OCR/video/screenshot capture alignment
- capture integrity/provenance/correlation diagnostics
- Salvage reconstruction when driven by capture evidence

## Validation / Packages app

Owns:

- environment/source/client/server comparison reports
- ID drift/logical schema comparison
- package assembly/review/inclusion/exclusion
- migration/backport validation
- live-target validation
- package readiness/apply/rollback status

## Development / Research app

Owns:

- Entity Profile
- Feature Trace / Implementation Path / dossiers
- Behavior Inspector
- mission/quest extraction
- server/Lua/SQL implementation research
- wiki/reference research
- Research Sessions
- read-only spatial/reference visualizations not tied to capture sessions

## Editors app

Owns:

- Zone Editor
- Item Editor
- client write/edit surfaces
- write journals/backups/rollback
- editor-specific model selection/preview surfaces

## Client Shared

Does **not** need a standalone top-level product shell. It may provide reusable route/view fragments for client snapshot/build inspection, DAT/model/binary readers, but those are surfaced through Development, Validation or Editors profiles as appropriate.

## Integrated host

The final shared application host owns only:

- app creation;
- common auth/config/session behavior if any;
- common shell/theme assets;
- capability registry;
- component route registration;
- profile selection.

It should not contain product business logic.

---

# 6. Optional dependency / external-tool ownership

| Dependency/tool family | Owner |
| --- | --- |
| Packetlyzer / packet decoder vendor integration | Captures |
| PCAP parsing dependencies | Captures |
| OCR/video tooling | Captures |
| capture format adapters | Captures |
| client DAT readers / xi-tinkerer read path | Client Shared |
| client DAT write helpers | Editors |
| model parsing/view read libraries | Client Shared |
| MariaDB/live target connectors used for validation | Validation |
| backport/package conversion helpers | Packages |
| wiki dumps/scrapers/reference adapters | Development / Research |
| LLM/research provider dependencies | Development / Research |
| pytest/regression-only dependencies | Bootstrap / Tests |

Phase D can convert these into optional install extras/profiles after isolation is proven.

---

# 7. Logical DB ownership

The physical SQLite database remains shared during segregation. Ownership is logical:

| Table/data family | Owner |
| --- | --- |
| graph/evidence/provenance/source identity primitives | Core |
| `capture_*`, capture manifests, packet/chat/runtime observations, capture diagnostics | Captures |
| client snapshots/builds/identity/DAT/model/binary evidence | Client Shared |
| validation results, drift/comparison reports, live-target validation | Validation |
| package plans/manifests/review/apply state | Packages |
| implementation indexes, feature/entity/mission/research/reference evidence | Development / Research |
| editor journals/rollback/write metadata | Editors |

Cross-component reads are permitted through documented APIs. Cross-component writes require an owning service/API rather than direct table mutation.

---

# 8. Phase A conclusions

1. **No additional broad root-file moves should target `core/services`.** Final component ownership is now known for the remaining migration.
2. `src/workbench/core/services` is the largest existing misclassification and should be drained during component moves.
3. Capture is already a coherent service cluster and is a strong early isolation candidate after contracts exist.
4. `src/workbench/migrations` should become two explicit product namespaces: Validation and Packages.
5. Development/Research currently owns most of the historical lookup/index/reference/server-analysis surface.
6. Client Shared remains strictly read-only; write-capable client tooling moves to Editors.
7. `gui_server.py` is a temporary integrated composition root and must be decomposed only after services/routes have owners.
8. Bootstrap/Tests remains non-product infrastructure and will eventually contain component-isolation regressions in addition to the full-tool regression suite.

---

# 9. Phase B input / enforcement backlog

Before the next broad physical relocation, Phase B should introduce enough structure to prevent new coupling:

1. Core provider contracts for:
   - Capture evidence access;
   - Client evidence/identity access;
   - Server/source evidence access;
   - Reference evidence access;
   - component capability registration.
2. Architecture tests for forbidden import directions.
3. Component ownership/path classifier used by tests.
4. Isolation import smokes for Captures, Validation/Packages, Development, Editors and Client Shared.
5. Public component API rule: cross-component imports target only documented package entry modules/contracts.
6. Initial component package scaffolds:
   - `workbench.captures`
   - `workbench.validation`
   - `workbench.packages`
   - `workbench.devtools`
   - `workbench.editors`
7. Keep `workbench.client`, `workbench.core`, and `workbench.runtime` as shared layers with the ownership restrictions above.

Once those gates exist, resume root migration **by component**, beginning with the Development entity chain or a small Capture cluster rather than continuing file-by-file into temporary namespaces.
