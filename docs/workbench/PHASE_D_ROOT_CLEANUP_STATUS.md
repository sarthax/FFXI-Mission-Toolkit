# Phase D repository-root cleanup status

Status: **ACTIVE / BOUNDED ROOT CLEANUP**  
Aligned through: PR #300 (`f15813beec63f2ab40f4efa7691f1bc0ec305103`)  
Date: 2026-10-02

The canonical Python package migration is complete under `src/workbench`. Phase D is the separate cleanup of historical repository-root Python implementations. The rule for this phase remains: move one bounded implementation at a time, preserve root CLI/import compatibility where still required, normalize repository/vendor/runtime paths before moving code, and require both Src Layout Regression and Workbench Regression before merge.

## Recently completed bounded migrations

- PR #294 — Client Binary Inspector implementation moved to `workbench.client.binary.inspector`; root `binary_inspector.py` is compatibility-only.
- PR #295 — model schedule inspection moved to `workbench.client.models.schedule_dump`; vendor lookup uses canonical runtime paths.
- PR #296 — verified mob model-family tables moved to `workbench.client.models.mob_model_tables`; root module is compatibility-only and verified-range behavior remains fail-closed.
- PR #297 — dialog drift audit moved to `workbench.reference.dialog.audit_drift`; root script remains a compatibility entry point and vendor/repository paths use runtime path services.
- PR #298 — AltanaView index builder moved to `workbench.client.models.build_altana_index`; `altana_view_index.db` remains intentionally at repository root through `REPO_ROOT`.
- PR #299 — Client Overview/build fingerprinting moved to `workbench.client.snapshots.overview`; root `client_overview.py` is a zero-logic compatibility alias.
- PR #300 — validation pipeline CLI moved to `workbench.validation.pipeline`; root `validation_pipeline.py` is a compatibility launcher/import alias.

Earlier Phase D work also packaged C++ server analyzers, Client binary CLI entry points, engine-environment validation, package Lua/map/binding/SQL validation, legacy DSP conversion drivers, and package conversion orchestration. These are already covered by the canonical `SRC_LAYOUT_STATUS.md` history.

## Current migration guardrails

1. Do not move `gui_server.py` yet. It remains the highest-coupling application surface and should be handled near the end of root cleanup.
2. Do not move `settings.py` until all repository/database/vendor/config paths it exposes have explicit canonical ownership and launch/setup behavior is ready for the change.
3. Do not move a module that only works because the repository root is on `sys.path`. Canonical code must import through packaged namespaces and pass the editable-install smoke outside repository cwd.
4. Preserve current runtime-state locations. Moving implementation code must not silently relocate `ffxi_zone_database.db`, generated indexes, captures, edit journals, backups, addons, or other user/runtime state.
5. Root compatibility files must contain no independent business logic unless they are intentionally still operator/setup launchers waiting for a later migration.
6. Every migration slice must pass both **Src Layout Regression** and **Workbench Regression** before merge.

## Deferred because of coupling

- `build_dialog_index.py` — still coupled to root `settings.py` and root `dat_extractor_bin.py`; move only after DAT extractor path normalization and settings decoupling.
- `client_model_catalog.py` — still coupled to root `settings` / `zone_plot`; moving it now would create a package that works only from repo-root execution.
- `dat_inspector.py` — depends on DAT extractor/vendor plumbing that should be normalized first.
- `model_viewer.py` — higher GUI/static/model coupling; defer until its lower-level Client dependencies are package-safe.
- `gui_server.py` and `settings.py` — intentionally late/high-risk.

## Good next candidates

Prefer the next root implementation that is still real code, has packaged dependencies, and has no implicit `Path(__file__).parent` repository semantics. Before selecting a candidate, first verify that it is not already a compatibility shim from an earlier migration.

Near-term dependency work that unlocks more candidates:

- package/normalize `dat_extractor_bin.py` around `workbench.runtime.paths.VENDOR_ROOT`;
- then migrate `dat_inspector.py` and `build_dialog_index.py` in separate slices;
- continue reducing direct `settings.py` consumers by passing explicit paths/configuration into canonical package services;
- defer `client_model_catalog.py`, `model_viewer.py`, and the GUI application shell until those lower-level dependencies are clean.

## Validation history for the latest slices

- PR #297: Src Layout #113 / Workbench #2164 — green.
- PR #298: Src Layout #114 / Workbench #2165 — green.
- PR #299: Src Layout #116 / Workbench #2167 — green after correcting a test-harness root-import assumption.
- PR #300: Src Layout #117 / Workbench #2168 — green.

The recurring test lesson from PRs #297 and #299 is explicit: outside-repo editable-install tests must validate canonical package imports only. Root compatibility shims should be loaded explicitly from `REPO_ROOT` when identity compatibility itself is under test.

## Completion condition for Phase D

Phase D is complete when the remaining root `.py` files are limited to intentional launch/bootstrap compatibility entry points, generated/operator data is not colocated accidentally with implementation code, setup/start workflows no longer depend on implementation modules living at repository root, and the remaining compatibility shims have a documented removal path.
