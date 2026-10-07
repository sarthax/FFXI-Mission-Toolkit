# Root Directory Cleanup Status

Status: ACTIVE  
Started: 2026-10-06  
Current merged baseline: `main` at `e9168de6d3e29b816c64f91e2e4f6c20dda3399a` after PR #589  
Current work branch: `cleanup/build-condition-index-phase3c23`  
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

- PR #556 — moved root reference/report artifacts; Workbench #2716 + Src Layout #596 green.
- PR #557 — structured bootstrap/package entry points; removed root bootstrap wrappers; Workbench #2717 + Src Layout #597 green.
- PR #558 — removed setup-linked index/reference shims except deferred `build_capture_index.py`; Workbench #2730 + Src Layout #610 green.
- PR #559 — decoupled packaged migration services from root `backport_*`; Workbench #2731 + Src Layout #611 green.
- PR #560 — live SQL checker canonical alias locked; Workbench #2732 + Src Layout #612 green.
- PR #561 — removed `backport_binding_audit.py`, `backport_lua_sanity_check.py`; Workbench #2734 + Src Layout #614 green.
- PR #562 — removed `backport_binding_index.py`, `backport_item_audit.py`; Workbench #2735 + Src Layout #615 green.
- PR #563 — removed `backport_coverage_check.py`, `backport_map_confidence_check.py`; Workbench #2736 + Src Layout #616 green.
- PR #564 — removed `backport_map_lint.py`; Workbench #2738 + Src Layout #617 green.
- PR #565 — removed `engine_change_index.py`, `engine_migration_compare.py`; Workbench #2739 + Src Layout #618 green.
- PR #566 — removed `dialog_drift_overview.py`, `research_gaps.py`; Workbench #2740 + Src Layout #619 green.
- PR #567 — removed `ffxiclopedia_adapter.py`; Workbench #2741 + Src Layout #620 green.
- PR #568 — moved dialog audit to final Devtools namespace and removed root `audit_dialog_drift.py`; Workbench #2742 + Src Layout #621 green.
- PR #569 — synchronized the cleanup tracker.
- PR #570 — retired Client binary analyze/index/diff root CLIs and migrated active docs; Workbench #2743 + Src Layout #622 green.
- PR #571 — retired `dat_extractor_bin.py`; Workbench #2744 + Src Layout #623 green.
- PR #572 — retired `dat_inspector.py`; Workbench #2745 + Src Layout #624 green.
- PR #573 — retired `client_model_catalog.py`; Workbench #2746 + Src Layout #625 green.
- PR #574 — retired `client_model_resolver.py`; packaged resolver ownership retained.
- PR #575 — retired `client_overview.py`; Workbench #2748 + Src Layout #627 green.
- PR #576 — retired `mob_model_tables.py`; package migration regression preserved.
- PR #577 — retired `binary_inspector.py`; Workbench #2750 + Src Layout #629 green.
- PR #578 — retired `model_viewer.py`; Workbench #2752 + Src Layout #630 green.
- PR #579 — retired `mob_look_decode.py`; Workbench #2757 + Src Layout #635 green.
- PR #580 — retired `gear_tables.py`; Workbench #2758 + Src Layout #636 green.
- PR #581 — retired `model_schedule_dump.py`; Workbench #2761 + Src Layout #639 green.
- PR #582 — retired `build_altana_index.py`; Workbench #2762 + Src Layout #640 green.
- PR #583 — retired `cpp_api_index.py`, `cpp_dependency_index.py`, and `build_integration_index.py`; Workbench #2763 + Src Layout #641 green.
- PR #584 — added the post-cleanup Workbench UI Framework / Unified Module Layout roadmap phase.
- PR #585 — retired `pull_mob_positions.py`, `zmesh.py`, and `build_plot_descriptors.py`; Workbench #2764 + Src Layout #642 green.
- PR #586 — retired `fix_zone_door_props.py`; Workbench #2765 + Src Layout #643 green.
- PR #587 — retired `lookup_entity.py` and `entity_profile.py`, removing the temporary Entity Profile root-import alias bridge; Workbench #2766 + Src Layout #644 green.
- PR #588 — retired `lua_event_index.py`; Workbench #2769 + Src Layout #647 green after activating and refreshing the canonical Lua-event regression.
- PR #589 — retired `zone_animation_meta.py`; Workbench #2773 + Src Layout #651 green after activating its package regression and adding explicit optional-dependency stubs.
- PR #590 — retired `build_condition_index.py`; Workbench #2774 + Src Layout #652 green.

## Current slice

### Slice 3c24 — retire wiki compiler root launcher

Status: IN PROGRESS on `cleanup/wiki-compile-phase3c24`.

Changes on this branch:
- [x] remove root `wiki_compile.py`.
- [x] preserve canonical Development reference ownership at `workbench.devtools.reference.wiki_compile`.
- [x] preserve direct packaged CLI execution, including UTF-8 stdout handling, through `python -m workbench.devtools.reference.wiki_compile`.
- [x] migrate the focused package regression from root-alias identity to an explicit root-absence contract.
- [x] add the retired root name and focused migration smoke to Src Layout trigger/execution coverage.
- [x] update the active GUI roadmap to reference the canonical package surface.

Before merge:
- [ ] Run Workbench Regression.
- [ ] Run Src Layout Regression.
- [ ] Fix only regressions caused by wiki compiler launcher retirement.
- [ ] Merge only when green.

## Explicitly retained / deferred

- `build_capture_index.py` — high regression fan-in; dedicated test migration required.
- `backport_convert_7_packages.py`, `backport_convert_gm_debug_tools.py`, `backport_convert_nyzul_package.py` — wrappers seed Settings-derived operator defaults.
- `backport_sql_live_check.py` — active GUI/package/runtime operator guidance still names it.
- `backport_package.py`, `backport_lua_convert.py`, `backport_sql_convert.py` — higher-fan-in operator/test surfaces.

## Remaining slices

### Compatibility-shim families
- remaining Client/model wrappers after caller audits;
- remaining indexing/server-analysis wrappers;
- capture/protocol wrappers;
- spatial/domain/runtime wrappers;
- final application/bootstrap compatibility files such as `gui_server.py`, `settings.py`, `feature_checker.py`, and `id_bridge.py` only after their caller contracts are intentionally retired.

### Standalone operator scripts
PENDING. Move appropriate commands under `scripts/{maintenance,import,diagnostics}` after caller/path audit. Known candidates include `build_item_repair_package.py`, `seed_auction_house.py`, `discord_inventory.py`, and `discord_holiday_load.py`.

### Tests and high-fan-in compatibility removal
PENDING. Move remaining root `test_*.py`, migrate `build_capture_index.py` callers, and consider `test_fixtures/` → `tests/fixtures/` only with workflow/discovery updates.

### Workspace/resource normalization
PENDING. Move `backport-workspace/` to `workspaces/backport/` after reference audit; review `client_probe_sets/`, `plot_descriptors/`, and `addons/` separately.

### Final root guard and closeout
PENDING. Add a strict root allowlist, verify editable imports and bootstrap behavior, run broad regressions, and reconcile README/roadmap/src-layout/ownership docs.

## Resume instructions

1. Read this file first.
2. Fetch current `main`; concurrent work may have advanced it.
3. Check for an open `cleanup/*` PR/branch before starting a new slice.
4. Continue the first incomplete current-slice item.
5. Keep PRs bounded by one logical ownership family.
6. Update this tracker in every cleanup PR.
7. Never merge a cleanup slice with failing required CI.

## Completion definition

Cleanup is complete when reusable implementation is package-owned, supported commands no longer depend on loose root Python filenames, standalone scripts live under `scripts/`, tests live under `tests/`, reference/report artifacts are structured under `data/` or `docs/`, workspace material is under `workspaces/`, and CI prevents new unexplained root clutter.
