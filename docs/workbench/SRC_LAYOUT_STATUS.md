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
- Feature Checker lives at `workbench.core.services.feature_checker`; research tooling and regressions now use the canonical service directly and the root `feature_checker.py` compatibility wrapper is retired.
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

- **Src Layout Regression** — editable-install smoke outside repository cwd.
- **Workbench Regression** — existing repo-root application/regression behavior.

`Workbench Regression` must watch both the root compatibility path and canonical `src/workbench/**` so package-only changes cannot bypass the broad suite. Specialized workflows must likewise watch their canonical `src` service paths; the Ancient Vows cross-fork workflow tracks `src/workbench/core/services/feature_checker.py` directly.

The src-layout self-test rejects reintroduction of retired root graph/schema/provenance/feature-candidate/feature-checker modules or their legacy import forms, and verifies the canonical services are importable independently of repository-root compatibility files.

## Remaining repository-root cleanup

The larger repository still contains many historical root-level application scripts and entry points (`gui_server.py`, capture/index builders, editors, bootstrap scripts and compatibility utilities). Moving those is a separate phase from the completed `workbench` package migration and should continue only as bounded, dependency-aware slices described in `SRC_LAYOUT_MIGRATION_PLAN.md`.
