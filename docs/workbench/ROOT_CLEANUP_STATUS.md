# Root Directory Cleanup Status

Status: ACTIVE  
Started: 2026-10-06  
Current merged baseline: `main` at `26567a0fe7d3a95fe0156a8ffc77df2da2f6216a` after PR #557  
Current work branch: `cleanup/root-shims-indexing-phase3a`  
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
- Removed root wrappers:
  - `install_xi_tinkerer.py`
  - `install_external_tools.py`
  - `reset_install.py`
- Regressions enforce the structured bootstrap contract.

Validation: Workbench #2717 + Src Layout #597 green.

## Current slice

### Slice 3a — setup-linked indexing/capture/reference shims

Status: IN PROGRESS on `cleanup/root-shims-indexing-phase3a`

Root wrappers removed on this branch:

- [x] `build_database.py` → `workbench.devtools.indexing.build_database`
- [x] `build_npc_index.py` → `workbench.devtools.indexing.build_npc_index`
- [x] `build_dialog_index.py` → `workbench.devtools.reference.dialog.build_index`
- [x] `ingest_global_tables.py` → `workbench.client.dat.global_tables`
- [x] `build_capture_index.py` → `workbench.captures.ingestion.build_index`
- [x] `build_sql_index.py` → `workbench.devtools.indexing.build_sql_index`
- [x] `build_lsb_index.py` → `workbench.devtools.indexing.build_lsb_index`
- [x] `scrape_bg_wiki.py` → `workbench.devtools.reference.scrape_bg_wiki`

Coverage migrated on this branch:

- [x] Database index package migration test now validates canonical behavior/paths and root-shim absence.
- [x] Capture index migration test now validates canonical dependencies/paths and root-shim absence.
- [x] Global tables migration test now validates canonical behavior and root-shim absence.
- [x] SQL index migration test now validates canonical parser/paths and root-shim absence.
- [x] LSB index migration test now validates packaged foundations/paths and root-shim absence.
- [x] BG Wiki scraper migration test now validates canonical dump behavior and root-shim absence.
- [x] Source Layout regression explicitly guards all eight retired root filenames.

Important compatibility note:

The staged `_impl.py` files may still contain historical absolute-import names such as `import build_database` or `import build_sql_index`. Their canonical adapters inject the packaged modules into `sys.modules` while loading those mature implementations. Those strings are therefore internal implementation compatibility, **not** a reason to retain root files.

Remaining before merge:

- [ ] Run Workbench + Src Layout regression and fix any overlooked test-only dependency.
- [ ] Remove obsolete workflow path-filter references to deleted root shims when encountered.
- [ ] Merge only when green.

## Remaining slices

### Slice 3b+ — remaining compatibility shim forest

PENDING. Process in bounded logical families:

- indexing/devtools wrappers not covered by 3a;
- capture/protocol wrappers;
- backport/package/migration wrappers;
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

` scripts/bootstrap/ ` implementations are already structured; obsolete root bootstrap wrappers were removed in Slice 2.

### Slice 5 — tests

PENDING.

- Move remaining root `test_*.py` under `tests/legacy/` or focused suites.
- Remove root-import assumptions.
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