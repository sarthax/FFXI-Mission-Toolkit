# Root Directory Cleanup Status

Status: ACTIVE  
Started: 2026-10-06  
Current merged baseline: `main` at `0601134a3a845342626ede2ea4c9ea9d855c8162` after PR #564  
Current work branch: `cleanup/engine-validation-wrappers-phase3b7`  
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

Moved root reference/report artifacts into `data/reference/`, `docs/archive/`, and `docs/reports/`.

Validation: Workbench #2716 + Src Layout #596 green.

### Slice 2 — bootstrap and stable package entry points

MERGED: PR #557 → `26567a0fe7d3a95fe0156a8ffc77df2da2f6216a`

- setup/start/reset use structured bootstrap scripts or `python -m workbench...` entry points.
- Removed root `install_xi_tinkerer.py`, `install_external_tools.py`, `reset_install.py`.

Validation: Workbench #2717 + Src Layout #597 green.

### Slice 3a — low-coupling setup-linked index/reference shims

MERGED: PR #558 → `416432905d9fc45ce78f0cc222dc88ad98a4b045`

Removed root `build_database.py`, `build_npc_index.py`, `build_dialog_index.py`, `ingest_global_tables.py`, `build_sql_index.py`, `build_lsb_index.py`, and `scrape_bg_wiki.py`.

`build_capture_index.py` remains a thin transitional alias because it still has high regression fan-in; remove it only during the dedicated test migration slice.

Validation: Workbench #2730 + Src Layout #610 green.

### Slice 3b1 — decouple packaged backport callers

MERGED: PR #559 → `b39ea8332ecf55c944a5d3a63653f0ca2d3a6f93`

Packaged migration services now import canonical package owners rather than root `backport_*` aliases.

Validation: Workbench #2731 + Src Layout #611 green.

### Slice 3b2 — lock packaged live SQL alias

MERGED: PR #560 → `b3eb6c4ece3e4a16d452befffed20128497f3fe9`

Confirmed live SQL validation is package-contained and only preserves `backport_sql_convert` internally through `sys.modules` compatibility.

Validation: Workbench #2732 + Src Layout #612 green.

### Slice 3b3 — retire first validation wrappers

MERGED: PR #561 → `ec457df9faf735cbee208b21cf81874146077f73`

Removed root:
- `backport_binding_audit.py` → `workbench.validation.packages.binding_audit`
- `backport_lua_sanity_check.py` → `workbench.validation.packages.lua_sanity`

Validation: Workbench #2734 + Src Layout #614 green.

### Slice 3b4 — retire binding-index and item-audit wrappers

MERGED: PR #562 → `66374fb022f5e94b1fa9a53d0e12ed521f73f36f`

Removed root:
- `backport_binding_index.py` → `workbench.validation.packages.binding_index`
- `backport_item_audit.py` → `workbench.validation.packages.item_audit`

Tests now import canonical validation modules directly; Ancient Vows no longer watches the retired binding-index root filename.

Validation: Workbench #2735 + Src Layout #615 green.

### Slice 3b5 — retire coverage and map-confidence validation wrappers

MERGED: PR #563 → `6b7d677af0755ff9fb24743e3b11b22cdc742d37`

Removed root:
- `backport_coverage_check.py` → `workbench.validation.packages.coverage`
- `backport_map_confidence_check.py` → `workbench.validation.packages.map_confidence`

`test_package_coverage_confidence_migration.py` now exercises canonical modules directly and requires both root wrappers to remain absent.

Validation: Workbench #2736 + Src Layout #616 green.

### Slice 3b6 — retire namespace-map lint wrapper

MERGED: PR #564 → `0601134a3a845342626ede2ea4c9ea9d855c8162`

Removed root:
- `backport_map_lint.py` → `workbench.validation.packages.map_lint`

`test_lua_converter_map_lint_package_migration.py` now exercises the canonical module and direct `python -m` CLI outside repo CWD. Src-layout retirement guards now include all seven removed backport validation wrappers.

Validation: Workbench #2738 + Src Layout #617 green.

## Current slice

### Slice 3b7 — retire engine-validation wrappers

Status: IN PROGRESS on `cleanup/engine-validation-wrappers-phase3b7`.

Removed on this branch:
- [x] `engine_change_index.py` → `workbench.validation.environments.engine_change_index`
- [x] `engine_migration_compare.py` → `workbench.validation.environments.engine_compare`

Caller/test migration completed:
- [x] `test_engine_validation_package_migration.py` no longer loads either root wrapper.
- [x] The regression requires both root wrappers to remain absent.
- [x] Both canonical `python -m` CLIs are exercised from outside the repository CWD.

Classification decisions:
- [x] `backport_convert_7_packages.py`, `backport_convert_gm_debug_tools.py`, and `backport_convert_nyzul_package.py` are retained for now because their root wrappers seed Settings-derived operator defaults into canonical drivers; deleting them would remove behavior rather than just aliases.
- [x] `backport_sql_live_check.py` remains retained because active GUI/package/runtime operator guidance still names it.
- [x] `backport_package.py`, `backport_lua_convert.py`, and `backport_sql_convert.py` remain dedicated higher-fan-in CLI/test migration work.

Known harmless cleanup debt:
- `.github/workflows/src-layout-regression.yml` still contains deleted root filenames in its broad path trigger. These inert entries will be removed in a dedicated workflow-filter sweep.
- historical roadmap/source-layout prose may still name retired wrappers as historical feature names; executable coupling is the deletion gate for these small batches, with documentation reconciliation reserved for closeout.

Remaining before merge:
- [ ] Run Workbench + Src Layout regression.
- [ ] Fix only regressions caused by the engine-wrapper removals.
- [ ] Merge only when green.

## Remaining slices

### Slice 3b+ — remaining compatibility shim forest

Continue in small logical families:
- remaining backport/package/migration wrappers;
- remaining indexing/devtools wrappers;
- capture/protocol wrappers (`build_capture_index.py` deferred until its tests migrate);
- client/DAT/model wrappers;
- reference/research wrappers;
- spatial/domain/runtime wrappers;
- final compatibility launchers such as `gui_server.py`, `settings.py`, `feature_checker.py`, `id_bridge.py` only after remaining caller/CLI contracts are intentionally retired or replaced.

### Slice 4 — standalone operator scripts

PENDING. Move appropriate one-off commands under `scripts/{maintenance,import,diagnostics}` after caller/path audit. Known candidates include `build_item_repair_package.py`, `seed_auction_house.py`, `discord_inventory.py`, and `discord_holiday_load.py`.

### Slice 5 — tests and high-fan-in compatibility removal

PENDING.
- Move remaining root `test_*.py` under `tests/legacy/` or focused suites.
- Repoint remaining capture regressions from `import build_capture_index` to `workbench.captures.ingestion.build_index` while preserving monkeypatch behavior.
- Delete `build_capture_index.py` only after that migration is green.
- Review `test_fixtures/` → `tests/fixtures/` only after workflow/test-discovery changes are ready.

### Slice 6 — workspace/resource normalization

PENDING.
- `backport-workspace/` → preferred `workspaces/backport/` after reference audit.
- Review `client_probe_sets/`, `plot_descriptors/`, and `addons/` separately; do not move stable runtime/resource roots only for cosmetics.

### Slice 7 — final root guard and closeout

PENDING.
- Root allowlist permits only intentional project/bootstrap files and approved resource directories.
- Fail CI on unexpected root `.py`, `.csv`, `.html`, `.txt`, or report `.md` additions.
- Verify editable imports outside repository CWD and setup/start/reset behavior.
- Run Workbench, Source Layout, Character/server-admin, and focused affected suites.
- Reconcile README, roadmap, src-layout status, workflows, and component-ownership docs.

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
