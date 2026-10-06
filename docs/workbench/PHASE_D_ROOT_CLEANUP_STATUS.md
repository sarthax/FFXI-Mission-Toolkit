# Phase D repository-root cleanup status

Status: **COMPLETE — IMPLEMENTATION OWNERSHIP PACKAGED**  
Aligned through: PR #552 (`fbd6e844b40a1608a0e66b76910b254e6a03d3fc`)  
Date: 2026-10-06

Phase D is complete at the source-layout / implementation-ownership boundary. Canonical Workbench Python implementation lives under `src/workbench`; repository-root Python files that remain are intentional compatibility imports, operator/setup launchers, or historical command entry points whose implementations live in the canonical package.

This closeout does **not** mean every compatibility file should be deleted. Removing checkout-local launchers and the root `workbench/__init__.py` bootstrap requires a separate distribution/bootstrap decision in which supported setup/start paths install the project or otherwise place `src` on the import path.

## Final closeout migrations

- PR #549 — the settings store moved to `workbench.runtime.settings_store`; root `settings.py` is now a zero-logic compatibility alias and `workbench.runtime.legacy_settings` no longer filesystem-loads root implementation code.
- PR #552 — the monolithic GUI application host moved under `workbench.app`; root `gui_server.py` is now a thin launcher/import alias. The mature route implementation was relocated without an intentional route/body rewrite.
- PR #552 also moved static route/source regressions to the canonical packaged host and expanded Character Editor regression path coverage so future app-host/settings changes cannot bypass the server-admin integration suite.

Earlier Phase D work packaged the remaining mature server analyzers, client tooling, DAT/model tooling, capture ingestion/correlation, packet tooling, mission/research services, validation/package conversion services, index builders, and other reusable root implementations while retaining compatibility entry points where operator workflows still use them.

## Closeout guardrails that remain in force

1. New reusable implementation code belongs under `src/workbench`, not repository root.
2. Root compatibility files must remain zero-logic aliases/launchers unless a file is explicitly documented as an operator/setup command surface.
3. Repository/runtime state locations must not move merely because implementation code moved. Existing database, capture, backup, addon, generated-index, vendor, and edit-journal locations remain governed by `workbench.runtime.paths` and current product contracts.
4. Canonical package code must not rely on repository root being on `sys.path`; Src Layout Regression continues to exercise editable-install imports outside repository cwd.
5. Broad Workbench Regression continues to protect the supported checkout-local/root-launch workflow.
6. Application-host or runtime-settings changes must also run Character Editor/server-admin regression because router composition and active-environment behavior cross those boundaries.

## Intentional compatibility/bootstrap surfaces

- `gui_server.py` — supported checkout-local launcher/import alias for `workbench.app.host`.
- `settings.py` — compatibility import alias for `workbench.runtime.settings_store`.
- root `workbench/__init__.py` — bootstrap bridge that exposes `src/workbench` when the repository is run directly without installing the project.
- historical root CLI/import files — retained where user/operator documentation or compatibility callers still invoke the root command; their reusable implementation is package-owned.

These surfaces are not Phase D implementation debt. Their eventual retirement belongs to a separate packaging/distribution/bootstrap phase and should happen only after setup/start/CI paths no longer require them.

## Validation at closeout

PR #552 final head `e356a780d1b50787c5cc1cd7deccfd48ce2a27d3` passed:

- **Workbench Regression #2713**, including the full core regression sequence;
- **Src Layout Regression #593**;
- **Character Editor Regression #190**, including pytest-style and script-style server-admin regressions.

The closeout regression sweep also removed the old assumption that static route tests should inspect root `gui_server.py`; those tests now inspect the canonical packaged application host while a dedicated migration regression verifies that the root launcher remains thin.

## Completion condition

Phase D is considered complete because reusable implementation ownership is under `src/workbench`, the two intentionally late/high-coupling root implementations (`settings.py` and `gui_server.py`) have been packaged, compatibility behavior is regression-covered, and remaining root entry points are intentional launch/bootstrap surfaces rather than duplicate implementation homes.

Future work should not reopen Phase D merely to remove compatibility launchers. Create a distinct bootstrap/distribution cleanup item when the project is ready to require an installed package or an explicit `src` import path for every supported execution mode.
