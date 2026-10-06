# Root Directory Cleanup Status

Status: ACTIVE  
Started: 2026-10-06  
Current merged baseline: `main` at `aa31f4156c8903b95e681336ede379a017e6cd90` after PR #568  
Current work branch: none  
Goal: reduce repository-root clutter without reintroducing import/path coupling or moving runtime state accidentally.

This file is the authoritative resume point for post-Phase-D root cleanup. `SRC_LAYOUT_MIGRATION_PLAN.md` is historical planning only.

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

1. Do not move runtime DB/config/capture/cache state for cosmetics.
2. Delete a root compatibility shim only after active callers are repointed or proven unnecessary.
3. Prefer package imports and `python -m workbench...` over physical root Python filenames.
4. Preserve behavior while relocating; semantic refactors are separate work.
5. Update tests, workflows, docs/examples, subprocess callers, setup/start/reset, and GUI handlers as required by each removal.
6. Require green Workbench plus Src Layout for each cleanup slice that changes executable/import surfaces.
7. Keep cleanup PRs bounded by one logical ownership family.

## Completed slices

- **PR #556 / Slice 1** → `c39ea9ccdc959e79c00baec2b29035db0febcf07`
  - moved root reference/report artifacts under `data/reference/`, `docs/archive/`, and `docs/reports/`.
  - Workbench #2716 + Src Layout #596 green.
- **PR #557 / Slice 2** → `26567a0fe7d3a95fe0156a8ffc77df2da2f6216a`
  - setup/start/reset use structured bootstrap scripts or packaged module entry points.
  - removed root `install_xi_tinkerer.py`, `install_external_tools.py`, `reset_install.py`.
  - Workbench #2717 + Src Layout #597 green.
- **PR #558 / Slice 3a** → `416432905d9fc45ce78f0cc222dc88ad98a4b045`
  - removed setup-linked index/reference shims except intentionally deferred `build_capture_index.py`.
  - Workbench #2730 + Src Layout #610 green.
- **PR #559 / Slice 3b1** → `b39ea8332ecf55c944a5d3a63653f0ca2d3a6f93`
  - packaged migration services no longer depend on root `backport_*` imports.
  - Workbench #2731 + Src Layout #611 green.
- **PR #560 / Slice 3b2** → `b3eb6c4ece3e4a16d452befffed20128497f3fe9`
  - verified live SQL checker is package-contained.
  - Workbench #2732 + Src Layout #612 green.
- **PR #561 / Slice 3b3** → `ec457df9faf735cbee208b21cf81874146077f73`
  - removed `backport_binding_audit.py`, `backport_lua_sanity_check.py`.
  - Workbench #2734 + Src Layout #614 green.
- **PR #562 / Slice 3b4** → `66374fb022f5e94b1fa9a53d0e12ed521f73f36f`
  - removed `backport_binding_index.py`, `backport_item_audit.py`.
  - Workbench #2735 + Src Layout #615 green.
- **PR #563 / Slice 3b5** → `6b7d677af0755ff9fb24743e3b11b22cdc742d37`
  - removed `backport_coverage_check.py`, `backport_map_confidence_check.py`.
  - Workbench #2736 + Src Layout #616 green.
- **PR #564 / Slice 3b6** → `0601134a3a845342626ede2ea4c9ea9d855c8162`
  - removed `backport_map_lint.py`.
  - Workbench #2738 + Src Layout #617 green.
- **PR #565 / Slice 3b7** → `05bfeea999e31d58658d2fb99d1c46af5cfc30b9`
  - removed `engine_change_index.py`, `engine_migration_compare.py`.
  - Workbench #2739 + Src Layout #618 green.
- **PR #566 / Slice 3c1** → `2922596de81acecef198c5b34770bbd81b69959b`
  - removed `dialog_drift_overview.py`, `research_gaps.py`.
  - Workbench #2740 + Src Layout #619 green.
- **PR #567 / Slice 3c2** → `2b7f4d795f2ff5f1ae26002201362094dd54e55c`
  - removed `ffxiclopedia_adapter.py`.
  - canonical FFXIclopedia CLI/import coverage retained.
  - Workbench #2741 + Src Layout #620 green.
- **PR #568 / Slice 3c3** → `aa31f4156c8903b95e681336ede379a017e6cd90`
  - moved dialog audit implementation to `workbench.devtools.reference.dialog.audit_drift`.
  - reduced `workbench.reference.dialog.audit_drift` to a compatibility alias.
  - removed root `audit_dialog_drift.py`.
  - canonical CLI/import coverage plus old packaged-namespace compatibility retained.
  - Workbench #2742 + Src Layout #621 green.

## Next recommended slice

### Slice 3c4 — Client binary CLI-doc migration

The three Client binary root files are already pure aliases:
- `client_binary_analyze.py`
- `client_binary_index.py`
- `client_binary_diff.py`

Do **not** delete them until active docs/examples are repointed from physical root filenames to:
- `python -m workbench.client.cli.binary_analyze`
- `python -m workbench.client.cli.binary_index`
- `python -m workbench.client.cli.binary_diff`

Then migrate `test_client_binary_cli_package_migration.py` to canonical imports/direct module CLI smoke, delete the three root launchers, and validate Workbench + Src Layout.

## Explicitly retained / deferred

These are **not** deletion candidates yet:

- `build_capture_index.py` — high regression fan-in; dedicated test migration required.
- `backport_convert_7_packages.py`, `backport_convert_gm_debug_tools.py`, `backport_convert_nyzul_package.py` — wrappers seed Settings-derived operator defaults.
- `backport_sql_live_check.py` — active GUI/package/runtime operator guidance still names it.
- `backport_package.py`, `backport_lua_convert.py`, `backport_sql_convert.py` — higher-fan-in operator/test surfaces.

## Remaining slices

### Compatibility-shim families
- Client binary CLI-doc migration above;
- remaining client/DAT/model wrappers;
- remaining indexing/server-analysis wrappers;
- capture/protocol wrappers;
- spatial/domain/runtime wrappers;
- final application/bootstrap compatibility files such as `gui_server.py`, `settings.py`, `feature_checker.py`, and `id_bridge.py` only after their caller contracts are intentionally retired.

### Standalone operator scripts
PENDING. Move appropriate commands under `scripts/{maintenance,import,diagnostics}` after caller/path audit. Known candidates:
- `build_item_repair_package.py`
- `seed_auction_house.py`
- `discord_inventory.py`
- `discord_holiday_load.py`

### Tests and high-fan-in compatibility removal
PENDING.
- move remaining root `test_*.py` under `tests/legacy/` or focused suites;
- repoint remaining capture regressions from `import build_capture_index` to `workbench.captures.ingestion.build_index` while preserving monkeypatch behavior;
- delete `build_capture_index.py` only after that migration is green;
- consider `test_fixtures/` → `tests/fixtures/` only with workflow/discovery updates.

### Workspace/resource normalization
PENDING.
- `backport-workspace/` → preferred `workspaces/backport/` after reference audit;
- review `client_probe_sets/`, `plot_descriptors/`, and `addons/` separately; do not move stable runtime/resource roots only for cosmetics.

### Final root guard and closeout
PENDING.
- root allowlist permits only intentional project/bootstrap files and approved resource directories;
- fail CI on unexpected root `.py`, `.csv`, `.html`, `.txt`, or report `.md` additions;
- verify editable imports outside repository CWD plus setup/start/reset behavior;
- run Workbench, Src Layout, Character/server-admin, and focused affected suites;
- reconcile README, roadmap, src-layout status, workflow path filters, and component-ownership docs.

## Resume instructions

1. Read this file first.
2. Fetch current `main`; concurrent work may have advanced it.
3. Check for an open `cleanup/*` PR/branch before starting a new slice.
4. Continue the first incomplete next slice.
5. Keep PRs bounded by one logical ownership family.
6. Update this tracker in every cleanup PR.
7. Never merge a cleanup slice with failing required CI.

## Completion definition

Cleanup is complete when reusable implementation is package-owned, supported commands no longer depend on loose root Python filenames, standalone scripts live under `scripts/`, tests live under `tests/`, reference/report artifacts are structured under `data/` or `docs/`, workspace material is under `workspaces/`, and CI prevents new unexplained root clutter.
