# Workbench src-layout migration status

Status: **CANONICAL PACKAGE MIGRATION COMPLETE**  
Last aligned: 2026-10-01

The canonical Python package is now `src/workbench`.

## Completed

- `workbench.core`, runtime/path infrastructure, services and supporting package code moved under `src/workbench`.
- `workbench.domains` moved under `src/workbench/domains`; domain JSON catalogs are packaged explicitly.
- `workbench.client` moved completely under `src/workbench/client`.
- Client EVENT and identity extraction vendor lookups use `workbench.runtime.paths` rather than physical `__file__` depth.
- `workbench.gui_shell` moved to `src/workbench/gui_shell.py`; the GUI route map remains a repository-owned document resolved through `runtime.paths`.
- Repository-owned data, vendor, GUI, database and documentation paths are centralized through `src/workbench/runtime/paths.py` where applicable.
- Legacy root compatibility modules `workbench_graph.py`, `workbench_schema.py`, and `source_snapshot.py` are retired; first-party callers now import `workbench.core.graph`, `workbench.core.schema`, and `workbench.core.provenance` directly.
- Feature-candidate traversal moved from root `feature_candidates.py` to `workbench.core.services.feature_candidates`; Capture Backtrace and regression callers now use the canonical service directly.
- Feature Checker implementation now lives in its final Development namespace at `workbench.devtools.features.checker`. `workbench.core.services.feature_checker` and root `feature_checker.py` are compatibility shims while older regressions and the monolithic `gui_server.py` caller migrate.
- Feature Trace catalog/provider services now live at `workbench.devtools.features.trace_catalog` and `workbench.devtools.features.trace_providers`; their former Core service paths remain compatibility shims while high-fan-in callers migrate.
- Feature Trace dossier/closure support now lives at `workbench.devtools.features.trace_dossier` and `workbench.devtools.features.trace_closure`; their former Core service paths remain compatibility shims.
- Feature Trace binding drill-down now lives at `workbench.devtools.features.trace_binding_drilldown` and consumes the read-only Development server binding scanner at `workbench.devtools.server.binding_index`. The Validation/Packages-owned `backport_binding_index.py` keeps its cache, diff, CLI, and package concerns unchanged.
- Root Feature Trace now enters through `workbench.devtools.features.trace`; its mature implementation is staged under `_trace_impl.py` byte-for-byte while the canonical adapter binds historical imports to the final Development catalog and the read-only Core capture-row locator contract. Root `feature_trace.py` is only a compatibility CLI/import launcher.
- Exact capture-row provenance needed by cross-component consumers is exposed through `workbench.core.contracts.capture_row_locators`; capture ingestion, lineage recording, and health logic remain Captures-owned.
- Generic conditional dependency projection, recursive obtainability closure, and dependency-map presentation now live together under `workbench.devtools.dependencies`. Their former `workbench.core.services` paths are zero-logic compatibility shims, while Development/reference callers use the canonical namespace directly.
- Acquisition catalog normalization and fail-closed acquisition identity reconciliation now live under `workbench.devtools.acquisition`; their former `workbench.core.services` paths are zero-logic compatibility shims. Existing acquisition behavior fixtures remain valid through those shims, while Src Layout validates the canonical Development modules outside repo root.
- Server catalog entity-ID synchronization now lives at `workbench.devtools.server.catalog_identity`; `workbench.core.services.server_catalog_identity` is a compatibility shim. Existing root index builders continue through that shim until their own root-to-package migrations, while Src Layout validates the canonical bridge outside repo root.
- Feature/package analysis moved from root `feature_package_analyzer.py` to `workbench.core.services.feature_package_analyzer`; its graph-import regression uses the canonical service and the root implementation is retired.
- ID Bridge implementation moved to `workbench.core.services.id_bridge`; it now resolves the primary SQLite database through `workbench.runtime.paths.DATABASE_PATH`. Root `id_bridge.py` remains only as the documented operator CLI compatibility entry point.
- Development Entity Lookup and Entity Profile now have canonical package entry points under `workbench.devtools.entities`, with root files retained only for compatibility during Phase C.
- Client model lookup dependencies used by Entity Profile (`gear_tables`, model resolver, look decoder) now live under `workbench.client.models` with root compatibility shims.
- Capture chat, spatial, integrity, packet identity, timeline/correlation, raw-packet ingestion, PCAP/lobby ingestion, and related-evidence services now live under `workbench.captures` with compatibility shims preserving existing callers.
- Capture Backtrace now lives at `workbench.captures.correlation.backtrace`; root `capture_backtrace.py` is only a compatibility CLI/import launcher, and the canonical module consumes Capture-owned packet identity directly.
- Capture Graph Connect now lives at `workbench.captures.correlation.graph_connect`; its mature implementation is staged losslessly behind the canonical adapter, root `capture_graph_connect.py` is only a compatibility launcher, and packet identity/correlation are rebound directly to Capture-owned services while Core graph remains the neutral shared substrate.
- Capture index ingestion now lives at `workbench.captures.ingestion.build_index`; the mature `build_capture_index.py` implementation is staged losslessly behind that adapter, root `build_capture_index.py` remains the operator/setup compatibility command, repository/database paths use `runtime.paths`, and Capture/Entity Profile dependencies are rebound to their canonical component owners while preserving module-global monkeypatch behavior.
- YouTube/video OCR now lives at `workbench.captures.video.ocr`; the mature `youtube_chat_ocr.py` implementation is staged losslessly behind that adapter, root `youtube_chat_ocr.py` remains the GUI/operator compatibility command, and run artifacts, OCR timing, saved layout profiles, FFmpeg and Tesseract paths are rebound to canonical repository/vendor locations while preserving mutable module-global behavior used by existing regressions.
- Packet decoding now lives at `workbench.packets.decode`; the mature `packet_decode.py` implementation is staged byte-for-byte behind the canonical adapter, root `packet_decode.py` remains the CLI/import compatibility entry point, and Packetlyzer XML/extension/lookup paths resolve through `workbench.runtime.paths.VENDOR_ROOT` rather than implementation file location.
- Packet opcode indexing now lives at `workbench.packets.opcode_index`; the implementation is relocated unchanged, root `packet_opcode_index.py` remains the CLI/import compatibility entry point, and its deterministic dispatch self-test is exercised from the editable-install migration gate.
- Salvage reconstruction CLI now lives at `workbench.captures.cli.salvage_reconstruct`; root `salvage_reconstruct.py` remains the documented compatibility command, and its default database path continues to resolve through `workbench.runtime.paths.DATABASE_PATH`.
- Addon bundle tooling now lives at `workbench.runtime.addon_tools`; root `addon_tools.py` remains the documented CLI/import compatibility command, while repository and addon locations resolve through `workbench.runtime.paths.REPO_ROOT` and `ADDONS_ROOT` rather than implementation file location.
- Workbench graph/runtime connectors now live at `workbench.runtime.connect` and `workbench.runtime.connect_server`; root connector files remain compatibility entry points while existing graph-import behavior is preserved.
- Dialog drift overview now lives at `workbench.devtools.reference.dialog.drift_overview`; root `dialog_drift_overview.py` remains an import compatibility surface.
- The FFXIclopedia offline reference adapter now lives at `workbench.devtools.reference.ffxiclopedia`; root `ffxiclopedia_adapter.py` remains its CLI/import compatibility entry point.
- Research gap detection now lives at `workbench.devtools.research.gaps`; root `research_gaps.py` remains a compatibility import while the graph continues to be opened read-only.
- Build-condition/generated-source evidence indexing now lives at `workbench.devtools.server.condition_index`; root `build_condition_index.py` remains the CLI/import compatibility surface with unchanged evidence classifications.
- Development mission tooling now has a canonical `workbench.devtools.missions` namespace. Mission event reconciliation lives at `workbench.devtools.missions.event_reconcile`, while `workbench.plugins.domain.mission_event_reconcile` and the root CLI remain compatibility surfaces.
- Mission source-to-graph projection now lives at `workbench.devtools.missions.graph_ingest`; root `mission_graph_ingest.py` remains the operator CLI and `workbench.plugins.domain.mission_graph_emit` remains a zero-logic compatibility import.
- Generic mission state-machine modeling and conservative LSB mission extraction now live at `workbench.devtools.missions.mission_state_machine` and `workbench.devtools.missions.mission_lsb_extract`; their former plugin-domain paths are zero-logic compatibility shims.
- Mission representation planning and cross-feature requirement closure now live at `workbench.devtools.missions.mission_representation` and `workbench.devtools.missions.mission_feature_closure`; their former plugin-domain paths are zero-logic compatibility shims.
- Conservative LSB quest extraction and the mission/quest source catalog now live at `workbench.devtools.missions.quest_lsb_extract` and `workbench.devtools.missions.mission_source_catalog`; their former plugin-domain paths are zero-logic compatibility shims. The source catalog can now resolve both mission and quest structure entirely through Development-owned mission services.
- Normalized branching mission truth ingestion now lives at `workbench.devtools.missions.mission_ingest`; the former `workbench.plugins.domain.mission_ingest` path is a zero-logic compatibility shim with unchanged truth-set projection semantics.
- Reusable multi-zone progression analysis, graph projection, and persistence now live at `workbench.devtools.missions.multizone_progression`; the former `workbench.plugins.domain.multizone_progression` path is a zero-logic compatibility shim. The implementation is relocated unchanged and retains existing graph/persistence semantics.
- Reusable minigame/puzzle lifecycle analysis, graph projection, and persistence now live at `workbench.devtools.missions.minigame`; the former `workbench.plugins.domain.minigame` path is a zero-logic compatibility shim. Timer, scoring, outcome, reset, graph, and persistence semantics remain unchanged.
- Mission-specific target patch proposal generation now lives at `workbench.devtools.missions.mission_dsp`; the former `workbench.plugins.domain.mission_dsp` path is a zero-logic compatibility shim. Generic `PluginFinding` remains owned by `workbench.plugins.domain.base`, while generated-output contracts remain under `workbench.migrations`.
- Read-only LSB battlefield policy, level-cap, and mob-group extraction now lives at `workbench.devtools.battlefields.lsb`; `workbench.plugins.domain.battlefield_lsb` is a zero-logic compatibility shim.
- Legacy DSP battlefield migration proposal construction, callback adaptation planning, and safe generated SQL output now live at `workbench.packages.battlefields.dsp`; `workbench.plugins.domain.battlefield_dsp` is a zero-logic compatibility shim. The generic `PluginFinding` contract remains plugin-owned and is loaded lazily to avoid cross-package initialization cycles.
- Generated DSP battlefield proposal validation now lives at `workbench.validation.battlefields`; `workbench.plugins.domain.battlefield_validation` is a zero-logic compatibility shim. Validation remains descriptive and preserves READY / NOT_REQUIRED / MANUAL_REQUIRED semantics without executing generated SQL.
- Generic scripted-entity behavior modeling, graph projection, and conservative LSB Lua extraction now live under `workbench.devtools.behavior.scripted_behavior` and `workbench.devtools.behavior.scripted_behavior_lsb_extract`; their former `workbench.plugins.domain` paths are zero-logic compatibility shims. Both mature implementations are relocated byte-for-byte, preserving the existing parser and graph semantics.
- The earlier Phase A ownership inventory entries that proposed `src/workbench/captures/packets/*` for packet decoder/index files are superseded by the landed shared packet namespace `workbench.packets` established by PRs #261-#262.
- `lua_event_index.py` remains intentionally as a CLI compatibility entry point while capture tooling still documents that producer filename; its implementation remains canonical in `workbench.analyzers.server.lua_events`.
- Editable-install CI validates that the canonical package imports from `src` outside the repository working directory.
- Broad Workbench regression continues to validate the normal repo-root execution mode.

## Intentional root compatibility artifact

`workbench/__init__.py` is intentionally retained as the **only** file under the root `workbench/` directory.

It is a bootstrap shim, not a second implementation package. It exists because current supported checkout workflows still launch root entry points such as `python gui_server.py`, while `setup.bat` installs requirements but does not install the toolkit package itself. The broad regression workflow likewise exercises `PYTHONPATH=.` repo-root imports.

No implementation module should be added under root `workbench/`.

The bridge may be removed only after all supported launch/setup and CI paths either:

1. install the project (`pip install -e .` or an equivalent packaged install), or
2. explicitly place `src` on the Python import path.

That launcher/bootstrap conversion is a separate migration decision; it is not required for the canonical package layout to be considered complete.

## CI contract

Both migration safety layers are required:

- **Src Layout Regression** — editable-install smoke outside repository cwd, including canonical Feature Trace, Development dependency/acquisition services, Development server catalog identity, Development mission reconciliation/graph projection/mission+quest extraction/planning/source catalog/truth ingestion/multi-zone progression/minigame/proposal generation, Development battlefield LSB extraction, Development scripted-behavior modeling/extraction, Packages battlefield DSP proposal generation, Validation battlefield proposal checks, Capture service migrations, Capture Backtrace, Capture Graph Connect, Capture index ingestion, Capture video/OCR, packet decoder, packet opcode index, Salvage reconstruction CLI, and runtime addon-tools imports without repository-root participation.
- **Workbench Regression** — existing repo-root application/regression behavior.

`Workbench Regression` must watch both the root compatibility path and canonical `src/workbench/**` so package-only changes cannot bypass the broad suite. Specialized workflows must likewise watch their canonical `src` service paths; the Ancient Vows cross-fork workflow tracks `src/workbench/devtools/features/checker.py` directly.

The src-layout self-test rejects reintroduction of retired root graph/schema/provenance/feature-candidate/feature-package modules or their legacy import forms. It also constrains legacy root Feature Checker importing to exactly one caller, `gui_server.py`, until that monolithic GUI surface is migrated separately, verifies the ID Bridge implementation imports from `src`, verifies root/canonical Feature Trace identity while its implementation is staged behind the Development adapter, verifies Development dependency/acquisition/server-catalog service shim identity plus outside-repo canonical imports, and validates the Capture Backtrace, Capture Graph Connect, Capture index, YouTube/video OCR, packet decoder, packet opcode-index, Salvage reconstruction, addon-tools, mission reconciliation, mission graph, mission extractor core, mission planning, quest extraction, mission source catalog, mission truth ingestion, multi-zone progression, minigame, mission proposal generation, battlefield LSB extraction, battlefield DSP proposal generation, battlefield validation, and scripted-behavior legacy/canonical paths against their canonical implementations.

## Remaining repository-root cleanup

The larger repository still contains many historical root-level application scripts and entry points (`gui_server.py`, remaining capture/protocol tools and index builders, editors, bootstrap scripts and compatibility utilities). Moving those is a separate phase from the completed `workbench` package migration and should continue only as bounded, dependency-aware slices described in `SRC_LAYOUT_MIGRATION_PLAN.md`.
