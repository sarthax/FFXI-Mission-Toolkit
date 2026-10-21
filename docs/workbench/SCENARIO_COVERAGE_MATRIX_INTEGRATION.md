# Feature → Scenario Coverage Matrix (#1207)

**Status:** isolated, read-only implementation; synthetic testing only. Parent #1197. Planning source: [Scenario & Evidence Workbench roadmap PR #1258](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1258). No client, DSP, SQL-write, GM, or headless actions are used.

## Source-backed integration

| Existing source | Existing contract | Matrix use |
| --- | --- | --- |
| `data/testing/feature_test_readiness.json` | Feature IDs, scenario cases, intended kind, blocker list, candidate capabilities | Declared feature-to-scenario relationships and categories. A planned case contributes **planned**, not **specified** or **executed**. |
| `data/testing/test_specifications.json`, `feature_testing.test_specifications.specifications()` | Canonical allowlisted scenario specs; `design_only` vs `verified_runner` | Exact `(feature_id,case_id)` join only. No mutation to schema or validator. Computed spec SHA-256 is a *matching reference* only; not evidence of review. |
| `feature_testing.results.recent_results(path,limit=500)` | Local append-only imported records with `stage`, `verdict`, timestamps and DSP/headless/toolkit SHAs | Latest imported run/stages are visibly labeled **recorded/imported/unverified**. Mixed FAIL/BLOCKED/SKIPPED never turns into PASS. Empty DB/500-record truncation is explicit. |
| `feature_testing.normalized_evidence.normalize_mog09`, `assertion_engine.evaluate` | Deterministic replay of imported MOG-09 assertions | Only attempt if imported `evidence.spec_digest` exactly matches canonical projection hash. Otherwise recalculated **UNKNOWN**. A replay PASS is still not independent evidence. |
| `feature_catalog.features.json`, `feature_catalog.load_catalog()` | Separate operator-facing Feature Catalog namespace | Catalog links are **navigation only**; do not infer that names or IDs are implementation/evidence matches. Curated Assault/Nyzul and Missions documentation links are unverified navigation. |
| `/features/trace`, `/behavior` | Research graph and behavior inspection UIs | Exploration links only; no fabricated edges or source oracles. |

Routes: `GET /feature-testing/coverage` (HTML) and `GET /feature-testing/coverage/model.json` (bounded read-only model), registered through the host with a small independent `create_coverage_router(templates)` mount. Feature Testing viewer/editor, scenario schema, runner and existing catalog adapters were not modified.

## Status semantics and conservative rules

Each category (positive, negative, boundary, persistence; observation and other kinds preserved) has **planned**, **specified**, **recorded**, and **independently verified** *counts*, no percentages. The last category is zero in production until a separate trusted verifier exists. Incoming `evidence_json` cannot assert its own independent authenticity: fields like `independently_verified=true` are intentionally ignored.

- **complete:** every declared case has a trusted source oracle/readback, a compatible imported PASS and an independently confirmed complete execution. The current production route never supplies these trusted assessments, so imported results alone cannot achieve this state.
- **partial:** some cases meet the full trusted criteria, or a non-blocked case has recorded evidence that is not yet independently verified; missing cases remain visible.
- **untested:** declared/valid source-backed case with no run yet, where trusted oracle/readback prerequisites are separately established (synthetic fixture only at present).
- **blocked:** missing canonical spec, design-only runner, unresolved source oracle/readback, local readiness blockers, evidence mismatch, or incomplete history window.

**Readiness is not authorization.** A verified runner declaration is not an approved local preflight. Missing oracle or readback never becomes PASS or verified coverage. Evidence revisions are not automatically comparable just because DSP/headless/toolkit hashes exist; a matching *scenario specification* digest is also required. The current importer does not require such a digest, so typical legacy recalculation is UNKNOWN in this matrix (historical run detail pages may still show their non-authoritative legacy replay). No historical evidence is rewritten.

## Limitations, blockers, dependencies

1. **Feature Catalog ↔ test domain crosswalk:** current IDs differ (e.g. curated UI `assault`/`nyzul` vs testing `assault_nyzul`). No authoritative typed relationship registry. The matrix defaults to exact test-readiness IDs and labels catalog/trace links as **unverified navigation**, not coverage.
2. **#1259 / schema PR #1263:** BDD fields are pending; it does not yet establish scenario digest provenance, per-assertion pinned source-oracle authority, or a reviewed feature relation. No schema edits here.
3. **#1202 / #1198 imported evidence:** importer stores `dsp_commit`, `headless_commit`, `toolkit_commit`, but currently does not require `spec_digest`, completeness attestation, or independent observer authentication. A missing/mismatched digest intentionally blocks comparable recalc. Confirmation requires versioned schema and trusted evidence provenance.
4. **#1200 / XiHeadless #105/#107/#126:** execution readiness, operator authorization, cleanup, complete server readback and replayability are separate local acceptance gates. This matrix does not invoke preflight or a runner and never allocates accounts.
5. **#1260 / Feature Testing viewer:** the matrix only links to viewer/read-only run history; no shared-viewer files changed. Viewer and matrix should converge on UNKNOWN/BLOCKED, not promote imported PASS.
6. **Runtime:** cannot inspect locally generated client DATs, server source snapshots or real account/session/DB state here. CI validates only synthetic cases. An operator must assess a real imported campaign before claiming cross-source verification.

## Local checks

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q test_fixtures/test_scenario_coverage_matrix.py
```

In the running Toolkit, open `/feature-testing/coverage`, filter domain and state, inspect scenario/run links and compare the read-only JSON. The page must display missing/mismatched spec digest, missing oracles and untrusted imported PASS as **UNKNOWN/BLOCKED**, not completed coverage. Run with `MISSION_TOOLKIT_TEST_RESULTS_DB` unset and then with a disposable imported-report database to verify both states; do **not** use a production DB for acceptance.

## Test case provenance

`test_scenario_coverage_matrix.py` constructs labelled **synthetic** cases to demonstrate complete/partial/untested/blocked and maliciously optimistic imported evidence. The simulated `trusted_assessments` is an **in-process testing seam only**, not an HTTP field or production attestation service. The live coverage router passes no trusted assessments. This is structural validation, not runtime acceptance.
