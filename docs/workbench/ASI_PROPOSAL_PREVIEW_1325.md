# #1325 ASI — noncanonical scenario proposal preview, isolated first slice

**Status:** DRAFT / PROVISIONAL INTERFACE awaiting Agent C #1200 agreement.
This is a Toolkit-only read-only **detached preview module**, not a second
Scenario Developer and not an MCP or XIHeadless contract. It is intentionally
**not yet mounted in the live Scenario Developer template**. Do not connect
to #1322 catalog/preflight until Agent C confirms the identity/digest fields.

## Inputs: two explicitly selected local JSON documents

- `scenario_revision_baseline_snapshot_v1_NONCANONICAL`: operator-declared
  `revision` (nonnegative integer), `spec_digest_claim` (null or lowercase
  SHA256 *claim*), and `specification` containing the existing canonical v1
  scenario. Optional Contract v2 metadata remains inside `specification`;
  it is NOT rewritten or revalidated by this preview.
- `scenario_revision_proposal_preview_v1_NONCANONICAL`: `proposal_id`,
  `idempotency_key`, `scenario.feature_id/case_id/schema_version`,
  `base.revision/spec_digest_claim`, bounded `changes[]` of exact
  `{path,before,after}` values, reason, and separate lists of Feature Trace
  claims, source declarations, failure evidence claims, coverage-gap claims,
  duplicate scenario IDs, missing observations, blocked execution
  dependencies and **UNAPPROVED** expected candidates. Explicit
  `approved_expected:false` and `execution_enabled:false` mandatory.

The initial allowlist intentionally permits only `/name`, `/purpose`,
and `/rationale` as human-readable proposed text changes. No
`steps/assertions/contract_v2/oracles/runner/execution_status/` changes,
JSON Patch op semantics, arbitrary JSON Pointer traversal, filesystem paths,
mutation or persistence. This protects canonical source associations, direct
CASE/STEP scope, oracle and identity candidates, revised expected outcomes,
optimistic save guards, and legacy v1.

Both files are limited to 128 KiB. `check` validates exact envelopes,
matching scenario identity and selected revision/digest declarations, matching
before-values and uniqueness of changed paths, idempotency and proposed
identity collision with an optional externally supplied known-ID list.
Unexpected keys, malformed text, bad identity, duplicate references,
conflicting before-values, stale revisions or approval/execution claims fail
closed. Missing source/Feature Trace references, unobserved readbacks,
duplicate *candidate scenarios* and unapproved expected candidates render
explicit UNKNOWN/BLOCKED advisory warnings, not an approved oracle or PASS.
The computed result contains **no transformed canonical specification**, no
save payload and no run command. A matching digest *claim* is neither
rehashed from the selected bytes nor proof of saved DB revision.

## Static synthetic proof (not runtime provenance)

- `test_fixtures/asi_proposal_preview_synthetic.json` contains a fully
  declared synthetic v1 scenario and noncanonical proposed purpose edit,
  with fake trace/source/failure/gap labels and blocked observation state.
- `test_fixtures/test_asi_proposal_preview.cjs` rejects stale revision,
  disagreement of digest claims, different identity, duplicate IDs and
  change paths, conflicting before-value, unsupported protected fields,
  forged oracle/execution approval, invalid/extra fields, no-op and malformed
  proposal. Also tests missing citations/duplicates as warnings and a real
  fake-DOM text-only render, stale file selection and disposed in-flight
  preview. Rendering uses textContent and never imports, saves or executes.
- Preview component `gui/static/scenario_proposal_preview.js` has
  `check(baseline,proposal,knownProposalIds)`, `render(host,checked)`,
  `mount(host)` (two operator-selected files) and `dispose()`.
  It requires NO `ScenarioGuidedModel`, no network, no `window.fetch` and
  no editable canonical model access.

## Integration / authority gate

Agent C owns #1200 stable catalog/preflight identity and version metadata.
Agent B requested review of provisional field names and source association /
duplicate semantics on #1200 before connecting this component to an editor
panel, backend route, MCP or live catalog. A separate follow-up will mount
it *inside existing Scenario Developer* only after the interface is agreed,
the current canonical editor changes are integrated, and independent review
accepts the explicit operator-selected baseline mechanics. A stale server
revision cannot be cryptographically or DB-authenticated from this client
preview; canonical validation and optimistic revision checks remain the sole
authoritative save path, and this slice offers **no accept/apply button**.

This slice does not implement ASI-1 gap discovery, ASI-2 MCP tools or
persistence, ASI-3 promotion, ASI-4 failure importer or ASI-5 execution.
No source bytes, deployed revision, headless protocol, independent oracle
or physical capture evidence has been authenticated. B20 is unrelated and
remains local operator only after #1315/#1318 integration merge.

## Reviewed coordination with Agent C #1330 and Agent D #1329

Agent C [#1328 interface review](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1328#issuecomment-6353449160)
accepted the detached UI shape as **compatible, not authoritative**.
The actual R8 catalog proposal's `local_definition_sha256` is a *local
serialization checksum*, not `base.revision`, `spec_digest_claim`,
a persisted-draft revision, or approved source authentication. Do not map
one to the other implicitly. A future editor attachment must explicitly
validate selected baseline identity and revision with the existing
authoritative draft editor (only when authorized), without modifying its
save/revision handling.

Agent D's [#1329 evidence design](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1329)
has **separate** `scenario_evidence_summary_v0_DESIGN_ONLY_NONCANONICAL`
attempt/lifecycle/source/cleanup/fact/interpretation details and
`scenario_revision_proposal_v0_UNTRUSTED_DESIGN` typed proposal semantics.
This UI does not parse or impersonate those wire formats. Existing
`failure_evidence_refs` are opaque claims until a future reviewed
resolver binds attempt ID, digest, source revision, readback completeness,
reported verdict and independent authority. A source ref cannot
silently imply canonical CASE/STEP citation; a reported FAIL is not
an independently approved gameplay FAIL.

The preview now **derives** a non-authoritative `review_status` from
bounded proposal warnings:
- `REFUSE_UNTIL_RECONCILED`: possible duplicate scenario IDs requiring
  explicit human reconciliation;
- `REQUIRE_FRESH_EVIDENCE`: missing readbacks/dependencies/source/trace
  refs or selected baseline digest claim;
- `DRAFT_UNTRUSTED`: no *listed* blocker in the selected claims, but
  still not an approved, authenticated, or executable proposal.

This is an **advisory triage state**, not a human review event or
approval from Agent D's evidence projector. `NO_CHANGE` isn't
emitted by this preview: an unchanged text proposal fails closed.
All states keep `approved_expected=false`, `save_allowed=false` and
`execution_enabled=false`, including when the selected inputs
superficially match.

### Next gated milestone — not in this PR

1. Agent C #1322's published read catalog and Agent A/owner acceptance
   must land before integrating against the catalog/preflight.
2. Agent D #1329 remains a design contract, not a runtime evidence source.
   A reviewed, independently authorized evidence resolver and #1202
   replay handling are prerequisites for displaying authenticated attempt
   metadata rather than raw claimed strings.
3. After the #1315 → #1318 capture-viewer stack and separate #1323
   Advanced-editor fix integrate, attach the *existing* preview UI to the
   existing Scenario Developer with explicit operator opt-in and lifecycle
   disposal, without an apply/save path. Recheck dirty-state guards,
   navigation cancellation, Contract v2 citations and exact-current-head
   CI. Do not open a parallel editor, MCP proxy or canonical schema.
