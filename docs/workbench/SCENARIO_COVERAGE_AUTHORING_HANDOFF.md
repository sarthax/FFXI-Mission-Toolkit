# Coverage-driven scenario authoring — behavior reference handoff

Issue [#1207](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1207), parent [#1197](https://github.com/sarthax/FFXI-Mission-Toolkit/issues/1197). **Follow-up to now-merged [PR #1272](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1272), submitted separately against current `main`. Coordinate the destination contract with Agent B's now-merged [PR #1273](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1273). No real client DAT, server or runtime evidence used.

## Existing data truth and scope

The base matrix projects declared test features and cases from `data/testing/feature_test_readiness.json`, exact `feature_id + case_id` matches to canonical `test_specifications.specifications()`, and imported result revisions from `feature_testing.results.recent_results()`. The new `scenario_coverage.authoring` module **decorates** this matrix; it does not replace or change its recorded/recalculated verdicts, readiness categories, orphan inventories or previous tests.

The readiness case's **title** is a source-declared *test intent*, not a verified Behavior Trace node, normative requirement, valid DSP oracle or evidence of a source edge. We do **not** infer unspecified behavior from a Feature Catalog name, trace graph or application route. The only behavior references provided for authoring are exact, currently declared `feature_id` and `case_id` pairs in that readiness catalog. Missing category slots (positive, negative, boundary, persistence, recovery) mean *no scenario declared of that category*; they do **not** assert a missing behavior implementation or fabricate a requirement.

### Navigation and visibility

- `GET /feature-testing/coverage`: the existing table remains. The new feature-level drilldown groups declared test intents and missing categories, with distinct planned/specification/executable/observed/verified labels.
- Each intent links to the existing `/feature-testing/scenario/{feature_id}/{case_id}` Scenario Detail, exact imported run if available, filtered imported run history, source catalog navigation, Feature Trace and Behavior Trace investigation. Trace links remain **unverified research navigation**, not confirmed relationships.
- The original coverage matrix's `VERSION_MISMATCH`, `REVISION_UNPINNED` and recorded vs recalculated verdict semantics remain. New revision-alert banners raise contradictory/stale stage versions to the top; multiple historical engine revisions are labeled *different*, not unconditionally wrong.
- Unsupported canonical observation names (if present) are shown as missing capabilities; `headless_candidates` remain unverified candidate names rather than supported permissions. Readback/oracle remain UNKNOWN unless independently attested by a separate trusted provider. Actual local execution preflight is not inferred from `verified_runner`.
- No coverage percentages and no promotion of imported PASS to independent verification.

## Proposed read-only Agent B handoff contract

The link `Create scenario for this behavior` points to:

```text
/scenario-developer?context_ref=%2Ffeature-testing%2Fcoverage%2Fcontext%2F{feature_id}%2F{case_id}
```

where each ID is validated against a strict bounded alphanumeric/underscore/hyphen syntax and an **exact existing readiness catalog pair** before returning context. No free-text query or arbitrary URL, command, synthetic ID, expected value, assertion, source reference or pass verdict is inserted into the link.

A same-origin GET of `/feature-testing/coverage/context/{feature_id}/{case_id}` returns a small JSON object:

- `contract: "coverage_behavior_reference_v1"`
- `feature_id`, `behavior_ref`, `label`, `category`
- `source: "data/testing/feature_test_readiness.json"` and exact source pointer, `source_revision: "UNPINNED"`
- `reference_kind: "declared_test_case_intent_not_behavior_trace_identity"`
- `proposed_case_id: null`, `expected_oracle: "UNKNOWN"`, and **empty** `assertions`, `observations`, `capability_bindings`.
- `context_only: true`, `design_only: true`, `review_required: true`, `auto_populate_allowed: false`, `auto_save_allowed: false`, `execution_enabled: false`.

**Consumed by the editor (#1260 follow-up):** `GET /scenario-developer?context_ref=...` accepts only the same-origin path `/feature-testing/coverage/context/{feature_id}/{behavior_ref}` (strict identifier pattern; anything else is ignored with a visible notice). The editor GETs that read-only reference, verifies the `coverage_behavior_reference_v1` contract flags (`context_only`, `design_only`, `review_required`, no auto-populate, no auto-save, execution disabled) and that the feature is a known editor domain, then starts an **unsaved** design-only draft. Only the label and source pointer are carried over; no assertion, observation, oracle or ID comes from the reference. The case ID is a placeholder (`SYNTH-<ref>-DRAFT`) the operator must replace with a new unique ID. Nothing is saved, forked from a published ID, or granted any capability.

### Coordination requests (Agent B)

1. Confirm acceptance of the `coverage_behavior_reference_v1` `context_ref` URL and same-origin GET shape; if changing the interface, coordinate before either PR merges.
2. Display the source-declared intent as **proposed review context only**; keep user-entered draft title, purpose, assertions, expected oracle and IDs as NEW/UNKNOWN. The canonical schema has no reviewed `behavior_ref` property; do not add one without Agent A approval.
3. Preserve distinct draft lifecycle state `design_only` and `unassigned` runner with case-specific operator authorization for any future mutation; prevent persisted false oracle/source provenance.
4. If draft handoff is unavailable, show the selected `feature_id / case_id` source reference and a warning, rather than silently claiming a populated draft.

## Synthetic acceptance and limitations

`test_fixtures/test_scenario_coverage_authoring.py` adds tests for: a fully independently verified synthetic example (using the base matrix's test-only trusted attestation seam), planned-only uncovered intent, blocked unsupported observation/capability, optimistic imported PASS with no independent evidence, stage revision mismatch, distinct historical run revisions, declared recovery vs missing-category slots, exact bounded context and illegal/forged requests, preserved base filters and deterministic HTML for alerts/handoff. The base `test_scenario_coverage_matrix.py` remains unchanged and runs with the added suite in the same offline CI workflow.

**Could not verify here:** whether Agent B adopts the link, real operator browser routing, locally generated DATs or DSP source, a trusted specification digest from an importer, independent evidence completeness or a live gameplay scenario. All require separate reviewed integration and local testing. The new endpoint and links are GET/read-only; no draft persistence, GM command, XiHeadless runner, packet injection or server state write.
