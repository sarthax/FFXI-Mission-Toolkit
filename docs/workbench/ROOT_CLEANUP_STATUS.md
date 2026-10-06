# Root Directory Cleanup Status

Status: ACTIVE  
Started: 2026-10-06  
Current merged baseline: `main` at `416432905d9fc45ce78f0cc222dc88ad98a4b045` after PR #558  
Current work branch: `cleanup/backport-callers-phase3b1`  
Goal: reduce repository-root clutter without reintroducing import/path coupling or moving runtime state accidentally.

This document is the authoritative resume point for the post-Phase-D repository-structure cleanup. `docs/workbench/SRC_LAYOUT_MIGRATION_PLAN.md` is historical planning; this file tracks what is actually merged, in progress, and still pending.

## Target root shape

```text
.claude/
.github/
data/
docs/
gui/
scripts/
src/
tests/
vendor/
workspaces/

.gitignore
LICENSE
README.md
pyproject.toml
requirements.txt
setup.bat
start.bat
reset_install.bat
```

`addons/` and other resource roots may remain temporarily where an exact external/runtime location is still part of the supported contract.

## Safety rules

1. Never move runtime DB/config/capture/cache state merely for cosmetics.
2. Delete a compatibility shim only after active repository callers are repointed or proven unnecessary.
3. Prefer package imports / `python -m workbench...` over physical root Python filenames.
4. Preserve behavior while relocating; semantic refactors are separate work.
5. Update setup/start/reset, workflows, tests, docs/examples, subprocess callers, and GUI handlers with each removed entry point.
6. Require green Source Layout plus relevant Workbench/admin regressions before merge.
7. Tighten the root-clutter guard as each legacy family disappears.

## Completed slices

### Slice 1 — low-risk data/docs relocation

MERGED: PR #556 → `c39ea9ccdc959e79c00baec2b29035db0febcf07`

Moved out of root:

- `appraisal_item_id_xref.csv` → `data/reference/appraisal/item_id_xref.csv`
- `appraisal_pools_with_item_ids.csv` → `data/reference/appraisal/pools_with_item_ids.csv`
- `uncharted90_names.txt` → `data/reference/uncharted90_names.txt`
- `mission_toolkit_gui_artifact.html` → `docs/archive/ui/mission_toolkit_gui_artifact.html`
- `backport_coverage_report.md` → `docs/reports/backport/backport_coverage_report.md`

Validation: Workbench #2716 + Src Layout #596 green.

### Slice 2 — bootstrap and stable package entry points

MERGED: PR #557 → `26567a0fe7d3a95fe0156a8ffc77df2da2f6216a`

Completed:

- `setup.bat` installs the editable package before package commands run.
- Setup uses `scripts/bootstrap/install_xi_tinkerer.py` and `scripts/bootstrap/install_external_tools.py` directly.
- Setup writes settings through `workbench.runtime.settings_store`.
- Setup uses packaged module entry points for database/NPC/dialog/global-table/capture/SQL/LSB/BG-Wiki commands.
- `start.bat` runs `python -m workbench.app.host`.
- `reset_install.bat` runs `scripts/bootstrap/reset_install.py`.
- Canonical dialog and capture adapters support direct `python -m` execution.
- Removed root wrappers: `install_xi_tinkerer.py`, `install_external_tools.py`, `reset_install.py`.

Validation: Workbench #2717 + Src Layout #597 green.

### Slice 3a — low-coupling setup-linked index/reference shims

MERGED: PR #558 → `416432905d9fc45ce78f0cc222dc88ad98a4b045`

Removed root wrappers:

- `build_database.py` → `workbench.devtools.indexing.build_database`
- `build_npc_index.py` → `workbench.devtools.indexing.build_npc_index`
- `build_dialog_index.py` → `workbench.devtools.reference.dialog.build_index`
- `ingest_global_tables.py` → `workbench.client.dat.global_tables`
- `build_sql_index.py` → `workbench.devtools.indexing.build_sql_index`
- `build_lsb_index.py` → `workbench.devtools.indexing.build_lsb_index`
- `scrape_bg_wiki.py` → `workbench.devtools.reference.scrape_bg_wiki`

`build_capture_index.py` was deliberately retained as a zero-logic compatibility alias because exact code search found roughly 33 historical import occurrences, including capture regressions that rely on module-global monkeypatch behavior. Setup and newly touched callers already use `workbench.captures.ingestion.build_index`; final removal is deferred to the dedicated test/high-fan-in cleanup slice.

Coverage migrated in 3a includes package-migration tests for database/dialog/global-table/SQL/LSB/BG-Wiki paths, Research BG-Wiki callers, several capture callers found during CI, and Source Layout guards for the seven deleted wrappers plus the retained thin capture alias.

Validation: Workbench #2730 + Src Layout #610 green on exact PR head `18d32c588498f343c221f902f811c5eaed2bdc3e`.

## Current slice

### Slice 3b1 — remove packaged callers of root backport aliases

Status: IN PROGRESS on `cleanup/backport-callers-phase3b1`.

Completed in this small batch:

- [x] `workbench.migrations.backend_registry` now imports `workbench.packages.migration.sql_convert` directly instead of root `backport_sql_convert`.
- [x] `workbench.migrations.legacy_package_service` now imports packaged migration/validation owners directly for Lua conversion, SQL conversion, package orchestration, binding audit, and Lua sanity checks.
- [x] No `backport_*` root wrapper is deleted in this batch; this is caller decoupling only.

Remaining in this family before wrapper deletion:

- [ ] Repoint `workbench.validation.live_db._sql_check_impl` from root `backport_sql_convert` to `workbench.packages.migration.sql_convert`.
- [ ] Audit tests and operator/docs callers for each `backport_*` wrapper.
- [ ] Split wrappers into safe-to-delete vs intentionally retained CLI compatibility entry points.
- [ ] Convert alias-dependent tests to canonical package tests.
- [ ] Tighten Source Layout guard, then delete only the proven-unused wrappers.

Validation for this branch should include Workbench core regression (especially `test_migration_backend_registry.py` and `test_legacy_package_service.py`) plus Source Layout before merge.

## Remaining slices

### Slice 3b+ — remaining compatibility shim forest

PENDING after 3b1. Process in bounded logical families:

- remaining backport/package/migration wrappers;
- remaining indexing/devtools wrappers;
- capture/protocol wrappers (with `build_capture_index.py` deferred until its tests are migrated);
- client/DAT/model wrappers;
- reference/research wrappers;
- spatial/domain/runtime wrappers;
- final `gui_server.py`, `settings.py`, `feature_checker.py`, `id_bridge.py` only after their remaining actual callers are removed/repointed.

For each family: search executable/import callers, repoint, convert alias tests to canonical tests, delete wrappers, tighten guard, run CI.

### Slice 4 — standalone operator scripts

PENDING.

Target structure:

```text
scripts/
  bootstrap/
  maintenance/
  import/
  diagnostics/
```

Known candidates:

- `build_item_repair_package.py`
- `seed_auction_house.py`
- `discord_inventory.py`
- `discord_holiday_load.py`
- one-off spatial/repair utilities such as `fix_zone_door_props.py` / `pull_mob_positions.py` after caller/path audit.

### Slice 5 — tests and high-fan-in compatibility removal

PENDING.

- Move remaining root `test_*.py` under `tests/legacy/` or focused suites.
- Repoint remaining capture regressions from `import build_capture_index` to `workbench.captures.ingestion.build_index` while preserving monkeypatch behavior.
- Delete `build_capture_index.py` only after that migration is complete and green.
- Remove other root-import assumptions.
- Review `test_fixtures/` → `tests/fixtures/` only after workflow/test-discovery updates are ready.

### Slice 6 — workspace/resource normalization

PENDING.

- `backport-workspace/` → preferred `workspaces/backport/` after reference audit.
- Review `client_probe_sets/`, `plot_descriptors/`, `addons/` separately; do not move stable runtime/resource roots without value.

### Slice 7 — final root guard and closeout

PENDING.

- Root allowlist permits only intentional project/bootstrap files and approved resource directories.
- Fail CI on unexpected root `.py`, `.csv`, `.html`, `.txt`, or report `.md` additions.
- Verify editable imports outside repository CWD.
- Verify setup/start/reset behavior.
- Run Workbench, Source Layout, Character/server-admin, and focused affected suites.
- Reconcile `README.md`, `ROADMAP_CURRENT.md`, `SRC_LAYOUT_STATUS.md`, packaging docs, and component-ownership docs.

## Resume instructions

1. Read this file first.
2. Fetch current `main`; concurrent work may have advanced it.
3. Check for an open `cleanup/root-*` PR/branch before creating another.
4. Continue the first incomplete item in the current slice.
5. Keep PRs bounded by logical ownership family.
6. Update this tracker in every cleanup PR.
7. Never merge a cleanup slice with failing required CI.

## Completion definition

Cleanup is complete when reusable implementation is package-owned, supported commands no longer depend on loose root Python filenames, standalone scripts live under `scripts/`, tests live under `tests/`, reference/report artifacts are structured under `data/` or `docs/`, workspace material is under `workspaces/`, and CI prevents new unexplained root clutter.