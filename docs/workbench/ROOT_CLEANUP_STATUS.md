# Root Directory Cleanup Status

Status: ACTIVE  
Started: 2026-10-06  
Current merged baseline: `main` at `b3eb6c4ece3e4a16d452befffed20128497f3fe9` after PR #560  
Current work branch: `cleanup/backport-core-wrappers-phase3b3`  
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

Validation: Workbench #2730 + Src Layout #610 green.

### Slice 3b1 — decouple packaged backport callers

MERGED: PR #559 → `b39ea8332ecf55c944a5d3a63653f0ca2d3a6f93`

- `workbench.migrations.backend_registry` now imports packaged SQL conversion directly.
- `workbench.migrations.legacy_package_service` now imports packaged migration/validation owners directly for Lua conversion, SQL conversion, package orchestration, binding audit, and Lua sanity checks.

Validation: Workbench #2731 + Src Layout #611 green.

### Slice 3b2 — lock packaged live SQL alias

MERGED: PR #560 → `b3eb6c4ece3e4a16d452befffed20128497f3fe9`

- Confirmed `workbench.validation.live_db.sql_check` pre-binds historical `backport_sql_convert` to canonical `workbench.packages.migration.sql_convert`.
- Added regression coverage for that exact alias binding.
- No production live-DB implementation rewrite was needed.

Validation: Workbench #2732 + Src Layout #612 green.

## Current slice

### Slice 3b3 — retire low-coupling package validation wrappers

Status: IN PROGRESS on `cleanup/backport-core-wrappers-phase3b3`.

Removed on this branch:

- [x] `backport_binding_audit.py` → `workbench.validation.packages.binding_audit`
- [x] `backport_lua_sanity_check.py` → `workbench.validation.packages.lua_sanity`

Caller/test migration completed:

- [x] `test_binding_audit_method_calls.py` imports packaged binding audit directly.
- [x] `test_backport_package_plan_scope.py` imports packaged orchestrator, binding audit, and Lua sanity modules directly.
- [x] `test_binding_validation_package_migration.py` now requires the root binding-audit wrapper to be absent.
- [x] `test_lua_sanity_package_migration.py` now requires the root Lua-sanity wrapper to be absent.
- [x] `backport-workspace/README.md` and `backport-workspace/reports/README.md` use packaged `python -m` CLI commands.
- [x] Src Layout and Ancient Vows workflow path filters no longer list the retired wrappers.

Explicitly retained in this batch:

- `backport_package.py` — still has root-facing regression/operator documentation and will be handled with its CLI/test migration.
- `backport_lua_convert.py` — still has the standalone root `test_backport_lua_convert.py` regression/operator surface.
- `backport_sql_convert.py` — still has the standalone root SQL conversion regression/operator surface.
- `backport_binding_index.py` and other validation wrappers — audit separately in later small batches.

Remaining before merge:

- [ ] Run Workbench + Src Layout regression.
- [ ] Fix only regressions caused by this wrapper retirement.
- [ ] Merge only when green.

## Remaining slices

### Slice 3b+ — remaining compatibility shim forest

PENDING after 3b3. Continue in bounded families:

- remaining backport/package/migration wrappers;
- remaining indexing/devtools wrappers;
- capture/protocol wrappers (`build_capture_index.py` deferred until its tests migrate);
- client/DAT/model wrappers;
- reference/research wrappers;
- spatial/domain/runtime wrappers;
- final `gui_server.py`, `settings.py`, `feature_checker.py`, `id_bridge.py` only after remaining callers are removed/repointed.

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

Known candidates: `build_item_repair_package.py`, `seed_auction_house.py`, `discord_inventory.py`, `discord_holiday_load.py`, and one-off spatial/repair utilities after caller/path audit.

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
