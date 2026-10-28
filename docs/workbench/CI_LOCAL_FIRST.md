# Mission Toolkit — local-first CI and hosted compute budget

**Scope:** workflow scheduling and contributor policy only. The existing pytest/Node/browser-free/offline validators stay in place; this change does not turn off their contents, change the workbench application, or prove any live FFXI behavior.

## During draft development

- Run the **focused local test** corresponding to the changed module before each meaningful commit. Do not request a GitHub-hosted full suite for every small code change.
- Keep the PR as **draft** while editing. Every PR-triggered workflow in `.github/workflows` skips its **runner job** while `github.event.pull_request.draft` is true; skipped checks are **NOT PASS**.
- Fix failures locally; record commands, counts and commit SHA. Use a single owner and a focused PR. No A–E coordinator or automatic merges.
- For changes with overlapping coverage (scenario tools, feature testing, workbench), choose the specific regression commands locally; do not duplicate broad offline runs without a distinct risk.

## At review and merge

- When a PR is **ready for review**, the existing path-filtered workflows run their full validators; subsequent code pushes to a non-draft PR re-run them.
- A `concurrency` group keyed by workflow and PR cancels an outdated run when a newer commit supersedes it. The **final SHA** must have actual PASS; no inference from an earlier build, skipped state or synthetic-only fixtures.
- Existing mandatory branch-protection check names **must be reviewed before merge**. A skipped check should not be treated as success; an obsolete required check must be reconciled deliberately by the owner, not bypassed.
- Manual `workflow_dispatch` remains available for validating a draft/final branch when needed, except the two retired coordination workflows, which have been deleted.

## What changed

- All focused **pull-request** workflow jobs have a no-runner-on-draft condition; source path filters stay intact.
- `Workbench Regression` keeps its **four jobs** for ready review; draft work no longer schedules them. These jobs share the existing cancel-on-superseded-commit group.
- Obsolete duplicate feature-branch **push** triggers were removed from `live-client-regression` and `selective-retail-fetch`, plus the duplicate `r6-domain-specification-validation` main push. Their PR and manual triggers remain.
- Three former `workbench-rework/audit-foundation` cross-fork smoke workflows (Ancient Vows, Excavation Duty and External Source) are now **manual-only**. Their expensive remote-source checkout behavior is reserved for an explicit verification request.
- Removed the old `add-to-project` and `ready-watch` workflows tied to the retired coordinator model. Their files remain in Git history; removing them does not modify archived issues.

## Local example commands (choose applicable commands; not a full universal suite)

```bash
# Examples; use the specific fixture, module, or workbench regression test
python -m pytest -q test_fixtures/test_scenario_coverage_matrix.py
python -m pytest -q test_fixtures/test_bounded_inventory_r7.py

# Run the relevant workbench regression commands locally when editing
# cross-cutting workbench paths; inspect .github/workflows/workbench-regression.yml
# for the exact current command combinations and environment prerequisites.
```

Do not assume those example files apply to every change. If a workflow requires a special server/database/source checkout, keep that test explicitly under operator scope. **Do not** enable live database changes or account access merely to establish a CI PASS.

## Test-maintenance policy

The current test inventory and criteria for removing only proven redundancy are documented in [TEST_SUITE_RATIONALIZATION.md](TEST_SUITE_RATIONALIZATION.md). Keep distinct safety cases and source-backed protocol fixtures; do not equate large synthetic case counts with independently verified gameplay behavior. Any future test deletion must be reviewed with focused local test evidence and the exact final SHA.

## Validation status of this scheduling change

No GitHub-hosted workflow should be retried while the shared Actions allowance is exhausted. The changed workflow definitions need a final YAML/event-condition sanity check and a **real ready-for-review execution** after the allowance resets. Until then: **CI NOT_RUN / hosted acceptance pending**. Repository code/tests were not modified by this workflow PR.
