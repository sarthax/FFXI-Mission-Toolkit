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

- **Src Layout Regression** — editable-install smoke outside repository cwd, including canonical Feature Trace, Development dependency/acquisition services, and Development server catalog identity imports without repository-root participation.
- **Workbench Regression** — existing repo-root application/regression behavior.

`Workbench Regression` must watch both the root compatibility path and canonical `src/workbench/**` so package-only changes cannot bypass the broad suite. Specialized workflows must likewise watch their canonical `src` service paths; the Ancient Vows cross-fork workflow tracks `src/workbench/devtools/features/checker.py` directly.

The src-layout self-test rejects reintroduction of retired root graph/schema/provenance/feature-candidate/feature-package modules or their legacy import forms. It also constrains legacy root Feature Checker importing to exactly one caller, `gui_server.py`, until that monolithic GUI surface is migrated separately, verifies the ID Bridge implementation imports from `src`, verifies root/canonical Feature Trace identity while its implementation is staged behind the Development adapter, and verifies Development dependency/acquisition/server-catalog service shim identity plus outside-repo canonical imports.

## Remaining repository-root cleanup

The larger repository still contains many historical root-level application scripts and entry points (`gui_server.py`, capture/index builders, editors, bootstrap scripts and compatibility utilities). Moving those is a separate phase from the completed `workbench` package migration and should continue only as bounded, dependency-aware slices described in `SRC_LAYOUT_MIGRATION_PLAN.md`.
