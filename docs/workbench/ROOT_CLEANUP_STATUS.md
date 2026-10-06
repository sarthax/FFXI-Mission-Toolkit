# Root Directory Cleanup Status

Status: ACTIVE  
Started: 2026-10-06  
Current merged baseline: `main` at `c39ea9ccdc959e79c00baec2b29035db0febcf07` after PR #556  
Current work branch: `cleanup/root-entrypoints-phase2`  
Goal: reduce repository-root clutter without reintroducing import/path coupling or moving runtime state accidentally.

This document is the resume point for the post-Phase-D repository-structure cleanup. `docs/workbench/SRC_LAYOUT_MIGRATION_PLAN.md` remains the historical migration plan; this file tracks the final compatibility/operator/data cleanup after reusable implementation ownership moved under `src/workbench/...`.

## Target root shape

The desired repository root is approximately:

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

`addons/` may remain at root while external/addon workflows depend on that exact location. Other resource directories may remain temporarily when relocation would change persisted/runtime paths for little benefit.

## Safety rules

1. Do not move runtime DB/config/capture/cache state merely to make root look cleaner.
2. Do not delete a compatibility shim until every repository caller is repointed or the compatibility surface is deliberately retained.
3. Prefer package entry points (`python -m workbench...`) or canonical callable imports over invoking physical root filenames.
4. Preserve exact behavior while relocating files; refactor semantics separately.
5. Update setup/start/reset scripts, workflows, tests, docs/examples, subprocess callers, and GUI handlers atomically with each removed entry point.
6. Run Source Layout Regression plus relevant Workbench/Character/admin regressions for every behavioral slice.
7. Add a root-clutter regression so new loose implementation/data artifacts do not silently return.

## Inventory categories

### A. Intentional root files — keep

- `.gitignore`
- `README.md`
- `LICENSE`
- `pyproject.toml`
- `requirements.txt`
- thin bootstrap launchers: `setup.bat`, `start.bat`, `reset_install.bat`

### B. Compatibility Python shims — remove after caller migration

This includes most remaining small root `build_*.py`, `backport_*.py`, audit/index/packet/client wrappers, `gui_server.py`, `settings.py`, and similar historical import/CLI aliases whose implementation already lives under `src/workbench/...`.

Do not mass-delete these. For each shim:

1. identify its canonical packaged module;
2. search all repository callers by filename/import name;
3. repoint callers to packaged import or `python -m` entry point;
4. add/adjust regression coverage;
5. delete only when no supported caller requires the old path.

### C. Standalone operator/maintenance scripts — move under `scripts/`

Planned structure:

```text
scripts/
  bootstrap/
  maintenance/
  import/
  diagnostics/
```

Known candidates include `build_item_repair_package.py`, `seed_auction_house.py`, Discord intake/load utilities, and one-off spatial/repair tools that are not product libraries. Bootstrap implementations are already structured under `scripts/bootstrap/`; their temporary root wrappers are being retired in Slice 2.

### D. Tests — move under `tests/`

All remaining root `test_*.py` files should move under `tests/legacy/` or the appropriate structured test subtree after imports are package-clean. `test_fixtures/` should be reviewed separately for eventual normalization under `tests/`.

### E. Reference/generated artifacts — move out of root

Completed in Slice 1:

- `appraisal_item_id_xref.csv` -> `data/reference/appraisal/item_id_xref.csv`
- `appraisal_pools_with_item_ids.csv` -> `data/reference/appraisal/pools_with_item_ids.csv`
- `uncharted90_names.txt` -> `data/reference/uncharted90_names.txt`
- `mission_toolkit_gui_artifact.html` -> `docs/archive/ui/mission_toolkit_gui_artifact.html`
- `backport_coverage_report.md` -> `docs/reports/backport/backport_coverage_report.md`

Future root reference/report artifacts should follow the same rule: data under `data/reference/...`, historical presentation under `docs/archive/...`, generated/review reports under `docs/reports/...`.

### F. Workspace material

`backport-workspace/` is a working-artifact tree, not a root-level product directory. Preferred final home: `workspaces/backport/`, after all explicit references are updated and any generated subtrees are classified.

## Execution slices

### Slice 1 — baseline + low-risk non-code relocation

Status: MERGED — PR #556, merge commit `c39ea9ccdc959e79c00baec2b29035db0febcf07`

- [x] Create this resumable tracker.
- [x] Re-audit root against current post-Phase-D `main` and historical disposition map.
- [x] Move reference CSV/TXT artifacts with no runtime callers.
- [x] Move/archive obsolete root HTML/report artifacts.
- [x] Extend Source Layout regression to require the new structured paths and forbid the old root artifact paths.
- [x] Validate Workbench Regression #2716 and Src Layout Regression #596 green before merge.

Notes:

- No runtime DB/config/cache/capture state moved.
- The initial guard is intentionally narrow: compatibility Python shims remain allowed until their callers are repointed in Slices 2–3.
- `docs/guides/DIST_PACKAGING.md` and older migration-plan wording contain historical root examples and should be reconciled as the later shim/operator slices land rather than treated as runtime callers.

### Slice 2 — bootstrap and stable package entry points

Status: IN PROGRESS on `cleanup/root-entrypoints-phase2`

Completed on the branch:

- [x] `setup.bat` installs the project editable (`pip install -e .`) before package-module commands are used.
- [x] `setup.bat` calls `scripts/bootstrap/install_xi_tinkerer.py` and `scripts/bootstrap/install_external_tools.py` directly.
- [x] `setup.bat` writes settings through `workbench.runtime.settings_store`, not root `settings.py`.
- [x] `setup.bat` uses packaged module entry points for database, NPC, dialog, global-table, capture, SQL, LSB, and BG Wiki commands.
- [x] `start.bat` launches `python -m workbench.app.host`, not root `gui_server.py`.
- [x] `reset_install.bat` calls `scripts/bootstrap/reset_install.py`, not root `reset_install.py`.
- [x] Added direct `python -m` CLI behavior to the canonical dialog-index and capture-index adapters without duplicating their implementations.
- [x] Removed root bootstrap wrappers `install_xi_tinkerer.py`, `install_external_tools.py`, and `reset_install.py`.
- [x] Updated bootstrap/source-layout regressions to require those root wrappers to stay absent and to verify the structured launcher contracts.

Still required before Slice 2 closes:

- [ ] Audit repository code/tests/workflows/docs for remaining active calls/imports that treat root compatibility filenames as stable interfaces.
- [ ] Classify historical prose separately from executable callers; do not retain shims solely because old migration documentation names them.
- [ ] Identify the first logical compatibility-shim families ready for deletion in Slice 3.
- [ ] Run and merge with green Source Layout + Workbench regression.

### Slice 3 — remove compatibility shim forest

Status: PENDING

- [ ] Delete proven-unused root compatibility `.py` files in logical families (indexing, backport/migrations, capture/protocol, client/DAT, reference/research, spatial/domain).
- [ ] Keep temporary aliases only when an actual supported external/bootstrap workflow still requires them.
- [ ] Tighten root-clutter regression after each family is removed.

### Slice 4 — operator scripts

Status: PENDING

- [x] `scripts/bootstrap/`: installer/reset Python helpers are already physically structured; Slice 2 is removing their obsolete root wrappers.
- [ ] `scripts/maintenance/`: item-repair, AH seeding, one-off maintenance utilities.
- [ ] `scripts/import/`: Discord/reference import utilities.
- [ ] `scripts/diagnostics/`: remaining standalone diagnostic commands.
- [ ] Repoint docs/examples and preserve repo-root path resolution through `workbench.runtime.paths`.

### Slice 5 — tests

Status: PENDING

- [ ] Move remaining root `test_*.py` to `tests/legacy/` or focused suites.
- [ ] Remove repository-root import assumptions.
- [ ] Review `test_fixtures/` -> `tests/fixtures/` only after workflow path filters and test discovery are updated safely.

### Slice 6 — workspace/resource normalization

Status: PENDING

- [ ] Move `backport-workspace/` -> `workspaces/backport/` after reference audit.
- [ ] Review whether `client_probe_sets/`, `plot_descriptors/`, and `addons/` should remain stable resource roots or move beneath `data/`.
- [ ] Do not relocate runtime state directories as part of this cosmetic/structural cleanup.

### Slice 7 — final root guard and closeout

Status: PENDING

- [ ] Root allowlist permits only intentional launch/config/project files and explicitly approved resource directories.
- [ ] Fail CI on unexpected root `.py`, `.csv`, `.html`, `.txt`, or report `.md` additions.
- [ ] Verify editable install/imports from outside repo root.
- [ ] Verify setup/start/reset launcher behavior.
- [ ] Run Workbench, Source Layout, Character Editor/server-admin, and focused affected suites.
- [ ] Update `README.md`, `ROADMAP_CURRENT.md`, and `SRC_LAYOUT_STATUS.md` with final root contract.

## Resume instructions

When resuming:

1. Read this file first.
2. Fetch current `main`; do not assume the baseline SHA above is still current.
3. Check open PRs/branches for another root-cleanup slice before creating a new branch.
4. Continue the first incomplete slice above.
5. Keep each PR logically bounded and merge only after its relevant CI is green.
6. Update this checklist in the same PR so the next session knows exactly what moved and what remains.

## Completion definition

The cleanup is complete when product implementation is package-owned, supported commands no longer depend on loose root Python filenames, standalone scripts live under `scripts/`, tests live under `tests/`, reference/report artifacts are structured under `data/` or `docs/`, workspace material is under `workspaces/`, and CI prevents new unexplained root clutter.