# R6 design and scoping — revision impact selection (#1210) inside regression intelligence (#1199)

**Status:** DRAFT / PROPOSAL. Not implemented. Owner decisions recorded 2026-10-27: helper script generates the
change set (Q1), and new `dsp_source` citations must pin a revision while existing ones only warn (Q2); see §8. Written from a cloud (repo-only) session on
Toolkit `main`; no local data, live server, client or Headless output was inspected.
**Parents:** #1199, #1197. **Related:** #1198 (oracle provenance), #1202 (merged offline reconciliation),
#1211 (revision comparison; only its boundary is defined here), #1212, #1213.
**Cross-repo issues** named by #1199/#1210 (xiheadless-dsp #105, #122, #127, #128; darkstar-to-valhalla #59)
were **not read** for this draft. Anything this document needs from them is listed under *Open questions*,
not assumed.

## 1. What this is for, and what it is not

Given two DSP revisions, say **which Toolkit features and scenario cases a change might affect, why, and how sure
we are**, so an operator can choose what to run. Then, given results at two revisions, say **whether a
verdict change is a behavior change or something else** (#1211).

Non-goals, taken from the issues' acceptance text:

- No automatic test launch, fix, merge, close or dispatch from a selection. A ranked list is a *suggestion*;
  "selected" never means "run" and never means "affected".
- No second dependency graph. Feature Trace's existing relationships and the scenario contract's explicit
  source citations are the only link sources.
- No inference of impact from names, file proximity, display order or similarity. Missing link means `UNKNOWN`,
  and the unknowns are reported.
- No local acceptance claimed by CI; live/operator acceptance stays with the owner.

## 2. Existing assets this builds on (verified in the repo)

| Asset | Where | What it already gives |
|---|---|---|
| Scenario source citations | `contract_v2.sources[]`: `ref, repository, path, line_start, line_end, revision, classification, sha256` (see `R7_CONTRACT_V2_SOURCE_ASSOCIATIONS_DECISION.md`, `test_fixtures/scenario_contract_v2_synthetic.json`) | Explicit file + line-span claims per scenario, with optional 40-hex `revision`. In the synthetic fixture `revision` and `sha256` are `null`. |
| Case/step scoping of citations | optional `contract_v2.source_associations[]` (`scope` = `case`/`step`) | Which case or step a source supports. Omission means `UNKNOWN`, not "applies to all". |
| Scenario/feature identity | specification `feature_id`, `case_id`; test inventory `data/testing/feature_test_readiness.json` (`features[].cases[]`, `required_artifacts` incl. `server_commit`) | Stable keys for "available scenario IDs". |
| Result store | `src/workbench/server_admin/feature_testing/results.py`; append-only SQLite keyed `(run_id, case_id, stage)`; fields: verdict, `observed_at`, `dsp_commit`, `headless_commit`, `toolkit_commit`, `evidence` | Exact revisions per result. **Verdicts are only `PASS, FAIL, BLOCKED, SKIPPED`.** |
| Importer / history views | offline importer, `/feature-testing/results`, `/feature-testing/run/{run_id}` | Read-only history; imported records are explicitly *unauthenticated*. |
| Feature catalog | `feature_catalog/features.json` `source_refs` | Toolkit-side implementation paths only (templates/modules), **not** DSP paths. Not usable as a DSP impact link. |
| Feature Trace | `src/workbench/devtools/features/trace_*.py`; rule: "catalog rows … never manufacture graph relationships" | Evidence-backed relationships between server/client/capture objects, where an index exists. |

### Gaps found

1. **No DSP diff input exists in the Toolkit.** The Toolkit does not read the DSP checkout's git history.
2. **Scenario sources may be unpinned.** `revision: null` is valid. In the repo's checked-in contract-v2
   fixtures only 1 of 5 cited sources pins a revision; that is a small synthetic sample, and real authored
   scenarios were not inspected, so the true rate is unknown. A line span without a pinned revision cannot be
   assumed to still point at the same code in a later revision.
3. **The result store has no `UNKNOWN` verdict.** `UNKNOWN` exists in specs, oracles and readiness, but a stored
   result is PASS/FAIL/BLOCKED/SKIPPED. "PASS → UNKNOWN" in #1199's acceptance therefore cannot be a stored
   transition today; it has to be *derived* (see §5).
4. **`BLOCKED` carries a free-form `evidence` JSON** with no controlled reason class, so "environment-blocked"
   versus "absent fixture" versus "oracle unknown" cannot be distinguished mechanically yet.
5. **No environment fingerprint** is recorded with results (the DSP-side issue named in #1199 owns that).

## 3. #1210 — diff-to-feature/test impact selection

### 3.1 Shape

A **pure, offline function**; no network, no git, no DB writes, no process launch:

```
select_candidates(change_set, scenarios, trace_links) -> ImpactReport
```

Proposed home: `src/workbench/server_admin/feature_testing/impact_selection.py`, with a read-only JSON/CSV
export. A UI view is out of scope for the first slice (that is #1212).

### 3.2 Input: a supplied change set

**Decision (owner):** a helper script in this repository generates it. The script runs on the operator's machine
against a local DSP checkout (`git diff --name-status -M --unified=0 base head`, hunks taken from the zero-context
headers), writes the JSON below, and is the only place that touches git. The Toolkit selector itself still only
validates and reads the file; it never runs git. Proposed home: `tools/dsp_change_set.py`. Requirements: read-only
git commands only; both refs resolved to full 40-hex SHAs before writing; refuse a dirty or shallow checkout that
cannot produce the diff; no network; output bounded by the same limits the validator enforces. Fields:

```json
{
  "schema_version": 1,
  "repository": "<owner/repo as written in contract_v2.sources[].repository>",
  "base_sha": "<40-hex>", "head_sha": "<40-hex>",
  "changes": [
    {"status": "M", "path": "scripts/…", "old_path": null, "hunks": [[start, end], …] or null},
    {"status": "D", "path": "…"},
    {"status": "R", "path": "new", "old_path": "old"}
  ]
}
```

Validation: both SHAs full 40-hex and different; status in `A,M,D,R`; paths repository-relative, no `..`, no
absolute or drive paths, bounded count/length; `hunks` optional and, if present, ordered non-overlapping
base-side line ranges. The report echoes both SHAs; nothing is "latest".

### 3.3 Link classes (explicit, never fuzzy)

A scenario case is linked to a change only by one of these, in descending strength:

| Class | Rule | Notes |
|---|---|---|
| `DIRECT_SPAN` | a cited source has the same `repository` + `path` as a change, **its `revision` equals `base_sha`**, and its `[line_start,line_end]` overlaps a base-side hunk | The only class that claims a line-level overlap. |
| `DIRECT_PATH` | same `repository` + `path`, but no hunk data, or the citation's `revision` is null/different from `base_sha`, or no line overlap | Reason code records *why* it was not `DIRECT_SPAN` (`NO_HUNKS`, `SOURCE_REVISION_UNPINNED`, `SOURCE_REVISION_DIFFERS`, `NO_LINE_OVERLAP`). Unpinned spans are deliberately **not** trusted for line overlap. |
| `INFERRED` | the case's feature is related to the changed path by an **existing Feature Trace relationship** | The report must cite the trace edge it relied on. If no provider edge exists, there is no inferred link. |
| `UNKNOWN` | a changed path matches no citation and no trace edge | Listed in a mandatory `unlinked_changes` section; never silently dropped. |

Deleted and renamed files:

- `D` with a citation → class `DIRECT_*` plus flag `SOURCE_REMOVED`. The cited span can no longer be resolved at
  `head_sha`; the case is flagged for human review (its oracle source may be gone), not auto-failed.
- `R` is treated as delete of `old_path` plus add of `path` with `renamed_from` recorded, so a citation of the old
  path is flagged `SOURCE_RENAMED` and never silently re-pointed.

### 3.4 Deterministic ranking and confidence

Confidence is an **ordinal label**, not a probability: `DIRECT_SPAN > DIRECT_PATH > INFERRED > UNKNOWN`. Order
candidates by the tuple `(class rank, SOURCE_REMOVED first, number of distinct changed sources desc, feature_id,
case_id)`. Every candidate carries machine-readable `reasons[]` (code + the repository/path/lines/trace-edge that
justify it). Identical input must give byte-identical output (the fixtures assert this).

Candidates for the same case from several changes are merged, keeping the strongest class and all reasons.

### 3.5 Output (sketch)

```json
{
  "schema_version": 1, "base_sha": "…", "head_sha": "…",
  "candidates": [
    {"feature_id": "…", "case_id": "…", "confidence": "DIRECT_SPAN",
     "flags": ["SOURCE_REMOVED"], "reasons": [{"code": "SPAN_OVERLAP", "source_ref": "…", "path": "…", "lines": [10,14]}]}
  ],
  "unlinked_changes": [{"path": "…", "status": "M"}],
  "cases_without_sources": ["…"],
  "launch": "NOT_PERFORMED"
}
```

`cases_without_sources` makes the blind spot visible: cases that cite nothing can never be selected, and the
report says so rather than implying full coverage.

### 3.6 Fixtures required by the acceptance (all synthetic, labelled)

1. **Direct link:** pinned citation overlapping a hunk → `DIRECT_SPAN`.
2. **Inferred link:** no citation, but a synthetic trace edge → `INFERRED` citing that edge.
3. **Unknown link:** changed path with no citation/edge → in `unlinked_changes`, no candidate.
4. **Deleted file:** cited path removed → `SOURCE_REMOVED`.
5. Extra edge cases: rename; unpinned citation (must degrade to `DIRECT_PATH`, not `DIRECT_SPAN`); citation at a
   different revision; case with no sources; determinism (shuffle input order, same output); malformed change-set
   rejection (bad SHA, `..` path, identical SHAs).

## 4. Trace links across feature → scenario → DSP source (#1199 scope item 1)

No new store. The link is **computed on read** from three existing, explicit things: the scenario's
`feature_id`/`case_id`, its `contract_v2.sources[]`/`source_associations[]`, and Feature Trace edges. Two
consequences to state plainly:

- Improving impact coverage means **pinning and citing sources in scenarios**, which is authoring work (Scenario
  Developer / #1198), not analyzer work.
- A reporting aid worth adding in the first slice: a per-feature **source-citation coverage** line (cases with ≥1
  pinned source / cases with unpinned sources / cases with none), so low coverage is visible before anyone trusts a
  selection.

## 4a. Citation pin policy (owner decision)

**Rule:** a `contract_v2.sources[]` entry with `classification: "dsp_source"` must carry a full 40-hex `revision`
when it is **newly added**. Existing unpinned entries are **warned about, never blocked**, so saved scenarios keep
loading and saving.

Definitions needed to make "new" testable (proposed; implementation detail for the editor slice):

- **New citation:** a `dsp_source` entry whose `ref` is absent from the previously saved revision of the same case,
  or any `dsp_source` entry in a case with no saved revision yet. Save/validate **rejects** it with a field-specific
  error naming the source `ref` and the missing `revision`.
- **Existing citation:** a `ref` already present in the saved revision. If unpinned it produces a warning in
  validation feedback ("unpinned; impact selection will treat it as file-level only"), and the save succeeds.
- Editing an existing unpinned citation's span or path is treated as a change to it; whether that makes it "new"
  is left as open question 7.
- The rule applies only to `dsp_source`. Other classifications are unchanged.
- A pin is a **claim**, not authentication (consistent with the R7 decision: metadata does not authenticate bytes).
  Validation checks format only (40 lowercase hex), not that the commit exists.

Consequences for the selector: pinned citations can reach `DIRECT_SPAN`; legacy unpinned ones stay at
`DIRECT_PATH` with reason `SOURCE_REVISION_UNPINNED` until someone adds a pin. The §4 citation-coverage report
therefore also tracks the count of legacy unpinned citations so the warning debt is visible.

**Ownership note:** enforcing this touches the canonical validator
(`src/workbench/server_admin/feature_testing` / scenario authoring) and the Scenario Developer's validation feedback.
Per #1411's constraints, shared editor paths need the coordinator/owner grant, so this is a separate slice (WP5), not
part of the analyzer.

## 5. #1199 — comparing results across two revisions (boundary for #1211)

Not designed in detail here; only the contract the selector must not contradict.

**Comparability gate (all required before any transition is called a regression):** same `case_id` and stage;
identical test-definition content digest; compatible schema version; fixture context equal or explicitly
compatible; both runs carry full 40-hex `dsp_commit`; environment fingerprint present and compatible. Otherwise
the pair is reported `NOT_COMPARABLE` with the failing condition. The existing store keys results by
`(run_id, case_id, stage)` and records revisions, so the join is possible; the test-definition digest and
environment fingerprint are **new inputs** that do not exist yet.

**Transition vocabulary** (derived at read time; the store is not changed by this design):

| Left → right | Reported as | Condition |
|---|---|---|
| PASS → FAIL | `REGRESSION_CANDIDATE` | comparable only |
| FAIL → PASS | `FIXED_CANDIDATE` | comparable only |
| PASS → no record / oracle unknown | `NOT_ESTABLISHED` (this is the "PASS→UNKNOWN" case) | derived; there is no stored `UNKNOWN` verdict |
| any → BLOCKED | `ENVIRONMENT_BLOCKED`, `FIXTURE_ABSENT` or `ORACLE_UNKNOWN` | needs a controlled reason class (open question 3) |
| SKIPPED | `SKIPPED` | never counted as pass or fail |

A changed verdict is **never** attributed to the DSP change by the selector; the report shows both revisions, the
test-definition link, source SHAs, run IDs and oracle provenance side by side, and a human decides.

The side-by-side synthetic fixture from #1199's acceptance (PASS→FAIL, PASS→UNKNOWN, environment-blocked) belongs
to #1211's slice, built on this vocabulary.

## 6. Safety and privacy

- Inputs are repository-relative paths and SHAs only: no DAT contents, captures, credentials, account or player
  data.
- Imported results stay "unauthenticated evidence"; the selector and comparison never upgrade that.
- Output is a read-only artifact. No route, button or CLI in this design launches anything.
- Never invent ids: all fixtures use clearly synthetic repository names, paths and all-`a`/`b` style SHAs marked as
  format examples (as the existing importer docs do).

## 7. Proposed work packages

| # | Package | Files (proposed) | Acceptance |
|---|---|---|---|
| WP1 | Change-set schema + validator | `…/feature_testing/impact_changeset.py`, tests | Rejects the malformed cases in §3.6 |
| WP2 | Selector core + fixtures | `…/impact_selection.py`, `test_fixtures/…impact…` | Issue #1210 acceptance: direct, inferred, unknown, deleted; deterministic reasons/confidence; no launch |
| WP3 | Source-citation coverage report | same package | Counts match fixtures; shows unpinned/none |
| WP0 | Change-set helper script (owner decision Q1) | `tools/dsp_change_set.py`, tests with a throwaway synthetic git repo | Emits a file WP1 accepts; refuses dirty/shallow checkouts; read-only git only |
| WP4 | (#1211) Comparability gate + transitions | separate issue/PR | Needs open questions 3–4 settled |
| WP5 | Pin policy enforcement (§4a) | canonical validator + validation feedback; needs editor-path grant | New unpinned `dsp_source` rejected; existing unpinned warned and still saves; non-`dsp_source` unchanged |

WP0–WP3 are remote-safe and offline (WP0's tests build a throwaway local git repo). Each ships with a dedicated CI workflow path-filtered to its files.

## 8. Open questions for the owner

1. ~~Diff source.~~ **Resolved:** helper script in the repo (WP0, §3.2).
2. ~~Pin policy.~~ **Resolved:** required for new `dsp_source` citations, warn-only for existing (§4a).
3. **BLOCKED reason class.** May the evidence contract (#1198/#1202) add a controlled `reason_class`
   (`ENVIRONMENT`, `FIXTURE_ABSENT`, `ORACLE_UNKNOWN`, `OTHER`)? Without it #1199's "environment failure versus
   absent fixture versus unknown oracle" cannot be mechanical.
4. **UNKNOWN.** Is derived `NOT_ESTABLISHED` acceptable, or should the store verdict set be extended?
5. ~~Trace edges.~~ **Answered from the repo (2026-10-27):** no Feature Trace provider in the repository links DSP
   source *file paths* to Toolkit features. The provider registry
   (`src/workbench/devtools/features/trace_providers.py`) and its `PROVIDER_LINKS` relate database identity rows
   (items, NPCs, mobs, groups, pools, spells, abilities, instances) and wiki/research/validation/migration records
   by id; none carries a repository path. The only path-bearing objects are the core index tables
   (`features`, `artifacts.path`, `functions`, `bindings`) that `_trace_impl.py` reads from an externally built index
   database, and whether that index contains feature→file edges depends on the local index, which this session could
   not inspect. **Consequence:** the selector takes trace links as an injected, explicit input
   (`trace_links`: path → feature, each with the edge it came from). With none supplied, `INFERRED` is empty and
   the report says so; filling it from the index is a later adapter, not part of WP2.
6. **Cross-repo contracts** (xiheadless-dsp #105/#122, darkstar-to-valhalla #59): confirm they do not already fix
   the change-set or fingerprint shape before WP1 starts.
7. **What makes a citation "new"?** Is an existing unpinned citation whose path or line range is edited treated as
   new (and so must then be pinned), or does it stay warn-only until removed? §4a leaves this open.

## 9. Dependencies and sequencing

#1210 is marked blocked by #1199, R5 catalog work and contract acceptance. WP1–WP3 only need the already-merged
contract v2 source fields and Feature Trace, so they can start now (questions 1, 2 and 5 are resolved; WP0 and WP1 are in PR #1435);
WP4 additionally waits on #1198, #1202 and questions 3–4.
