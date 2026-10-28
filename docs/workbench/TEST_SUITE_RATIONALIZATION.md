# Mission Toolkit — test-suite rationalization baseline

**Date:** 2026-10-28. **Reference:** draft CI-budget PR #1480 (branch `chore/actions-budget-local-first-v1`). **A bounded, assertion-preserving typed-route test deduplication was added to this branch; no distinct negative/security cases were removed.** Test execution and fixture-assertion changes require separate focused review and local verification.

## Baseline: distinguish files, tests and workflows

A Git tree inventory of PR #1480 before this document counted **958 matching Python/Node test files** across `test_fixtures/`, `tests/` and a few bundled vendor trees: **945 Python** files and **13 .cjs** files. The primary repository test areas contain **823 files in `test_fixtures/`** and **131 in `tests/`**; the remaining four were bundled vendor paths. These are **file counts, not individual test-case or assertion counts**, and are not a measure of independent behavioral confidence.

Exact Git blob SHA grouping found **zero byte-identical files** among those 958 paths. This does *not* rule out logically duplicated assertions or fixture cases: distinct files can restate the same assumptions. Conversely, two tests with similar names can protect distinct actors, versions, policies or negative boundaries. Do not delete tests based on naming similarity or the inventory count.

The repo has **36 GitHub workflow YAML files** in draft PR #1480: **33 PR-targeted** workflows retaining distinct path filters and **three manually dispatched legacy cross-fork** workflows. Test *execution frequency* can be reduced immediately without weakening tests by using the local-first and ready-for-review CI scheduling policy in [CI_LOCAL_FIRST.md](CI_LOCAL_FIRST.md). **The count of files alone does not justify any suite deletion.**

## Confidence taxonomy

| Category | Retain / consolidate | Acceptance evidence |
| --- | --- | --- |
| Source-backed packet/field decoding, status high bits, target/actor/zone identity, partial/truncated records | **Retain distinct positive, negative and boundary cases** | Version-pinned source or independently captured fixtures; reject false attribution |
| Persistence, item/inventory safety, lease/cancellation, state transitions, race isolation | **Retain strong adversarial cases** | Independently specified invariant; failure catches a real unsafe state |
| Public API contracts, import/export schemas, migrations and UI regressions | **Retain consumer-visible guarantees** | Fails when contract or user-visible behavior regresses |
| Parameter variations for the *same* predicate, scope and failure mode | **Consolidate carefully** (e.g. parametrized cases) | Preserve case identities and distinct edge boundaries while reducing duplicated setup |
| Synthetic proposed behavior and personality/scenario policy | **Prune redundant permutations only with an evidence ledger** | Mark synthetic outcome as **advisory/NOT_TESTED**, never gameplay PASS |
| Repeated tests proving only a constant, a getter, or a helper called twice | **Review for removal or folding into a meaningful contract test** | A replacement test fails under a realistic mutation or independently specified error |

## Minimum standard for every new test

Before adding a test, state (a) the concrete invariant or observed source, (b) the distinct regression it catches that nearby tests miss, (c) the smallest independent oracle, (d) whether evidence is synthetic, source-read, captured or live, and (e) the local command that runs it. Prefer parameterization and shared fixtures over copying an entire test class to vary one value. A new independent protocol or destructive-safety case is more valuable than meeting a numeric target.

For removal/consolidation, first establish that two tests have the **same independent invariant and failure mode**—not just similar input. Maintain a brief old-to-new case mapping, demonstrate both focused and impacted-suite tests on the **actual commit**, and ensure no change hides a FAIL/UNKNOWN result. Never count a skipped or quota-blocked GitHub Actions check as a pass.

## Completed bounded refactor — scenario typed-step routes

In `test_fixtures/test_scenario_typed_steps_1411.py`, the two write endpoints (`/scenario-developer/typed-step` and `/scenario-developer/typed-import`) independently repeated the same **nonlocal client** and **cross-origin** rejection assertions. Separately, three successful routes (`typed-library`, `typed-step`, `typed-import`) duplicated the same `subprocess.Popen` and `sqlite3.connect` monkeypatch guards.

The cleanup replaces duplicate setup/assertion bodies with two `pytest.mark.parametrize` tests, each with named route IDs. No request paths, expected response codes, forbidden operations or distinct boundary cases are removed:

| Existing coverage | Resulting coverage |
| --- | --- |
| Typed step rejects nonlocal and foreign origin; typed import rejects the same | `test_typed_writes_reject_nonlocal_and_cross_origin` with separate `typed-step` and `typed-import` parameters |
| Typed library and typed-step run without process or SQLite calls; typed import separately checks the same | `test_typed_routes_do_not_spawn_processes_or_open_database` with three independent route parameters |
| Typed step refuses `text/plain`; import rejects >40KB payload | Preserved as distinct focused tests; not combined into a generic status-code check |
| Catalog picker header, source-unavailable and duplicate-ID safeguards | Unchanged |

The file still contains **15 named test functions** (some are parameterized), and its line count moved from **191 to 197** to keep the shared operation table and per-endpoint IDs legible. **This is duplicate setup elimination, not a reduction in logical cases or test execution time.** Local verification command:

```bash
python -m pytest -q test_fixtures/test_scenario_typed_steps_1411.py
```

**Actual execution: NOT_RUN** in this GitHub-only session; user/local agent should run it before promoting the PR. Hosted CI remains blocked by the monthly Actions allowance. Do not present the refactor as a passing test until that output is recorded.

## Bounded next review

Start with a single scoped module, not all 958 files: select the next actively edited test fixture family; inventory its source authority, compare same-predicate cases, extract repeated setup, then run only that family's tests locally. Preserve unique boundary cases such as identity recycling, short packets, stale fields, negative indexes and failed writes. Report **case/fixture change count** and actual test results before any deletion is proposed.

**This pass is scheduling + test policy, not a claim of reduced test count or validated live behavior.** The first concrete test refactor should be a separate, owned slice with local-test evidence, not silently bundled into a 36-workflow CI configuration change.
