# Capture identity correlation and oracle-readiness diagnostics — #1262

Status: **isolated synthetic-only prototype**, parent #1197, related #1202,
existing review UI in draft PR #1276. Do not merge or wire to a runner.

## Existing services reused, with source anchors

- Indexed OBSERVED capture and source-file locators:
  `src/workbench/captures/scenario_draft.py:24-94,97-200`.
  These carry original row identity, source SHA as *indexed*, parser name and
  parser version where available. They do not rehash the local source bytes.
- Existing candidate binding / reader model:
  `src/workbench/captures/scenario_handoff.py:30-61,110-190,192-331`.
  Binding IDs identify **tooling proposals**, not NPC/CSID/event/zone IDs.
- Independent reviewer decisions and noncanonical export:
  `src/workbench/captures/scenario_review_workflow.py:25-92,196-249`.
  REVIEWED label choice is neither canonical entity truth nor normative oracle.
- **Existing read-only DSP lookup only**:
  `src/workbench/server_admin/scenario_authoring/catalog_adapter.py:15-28,54-108`,
  `search_catalog(server_root, kind, query, limit)`. Supports DSP `npc`,
  `item`, `keyitem`, `zone` as bounded, unreconciled candidates. No new
  SQL/Lua reader or GM command/execution path introduced.
- Dialogs/CSIDs require zone/entity and locally rebuilt DAT-derived indexes;
  see `docs/workbench/SCENARIO_EDITOR_INTEGRATION_AUDIT.md:20-37`.
  The existing DSP lookup **does not** expose global dialog/event identities;
  this lane accepts separately prepared scoped index records only.
- Accepted current canonical schema:
  `src/workbench/server_admin/feature_testing/test_specifications.py:17-119`
  is v1 with optional BDD fields and a narrow allowlist of observed values and
  assertion operations. Agent C's future expanded contract is **not yet
  accepted**; this implementation emits a separate diagnostic envelope, not
  invented schema fields.

## New read-only entry points

`workbench.captures.scenario_identity_readiness.candidate_dsp_catalogs(
    draft, configured_dsp_root, limit=20)`

Delegates to `scenario_authoring.catalog_adapter.search_catalog` for typed
NPC/zone/item/key-item candidates. The path is an operator-configured trusted
DSP checkout, **never browser-supplied**. Output stays bounded/unpinned and
cannot become `EXACT` by itself. It does not load DATs, run packet decoders
or modify source files.

`assess_evidence_readiness(draft, catalog_snapshots=..., reconciliations=...,
independent_oracles=..., comparison_drafts=...)`

Returns `capture_identity_oracle_readiness_v0_DIAGNOSTIC_ONLY`. Neither input
nor output is a canonical scenario specification, a review decision, or an
evidence importer result. Only existing capture and source-catalog fields
are consulted. It never accepts an observed value as an expected value.

### What EXACT actually means

| Classification | Meaning | Gameplay validity? |
| --- | --- | --- |
| EXACT | Exactly one matching **source record within an explicitly attested complete scoped export**, with pinned source digest and an **independent, explicit namespace reconciliation reference** for this exact proposed binding | **Still NOT verified.** A supplied source record/reconciliation claim must be locally audited; it is not an independent DAT/client verification |
| AMBIGUOUS | More than one candidate, duplicate IDs, or inconsistent captured alternatives | Block and show all alternatives |
| INFERRED | Same captured ID/name appears in a bounded catalog query, but source coverage, revision, namespace reconciliation or scope authority is incomplete | Investigative candidate only |
| UNRESOLVED | No candidate supplied or no match in bounded results | Cannot infer absence |
| UNSUPPORTED | Packet opcode, EventView MesNum without typed namespace, non-adapted category, or event/dialog with no zone-scoped index | No identity claim |

An `EXACT` source-record classification is deliberately **not**
`source_identity_verified=true`; that field is always false. The diagnostic
stage verifies only consistency *within provided metadata*, not external
source bytes, client catalogs or operator authorization. Even an exact
catalog match cannot establish what the captured game state should have been.

The correlation key includes binding kind, its unchanged recorded value,
capture-specific zone where present, a source-relative path, an exact source
line and a pinned digest. Event and dialog indexes require exact typed
zone scope; bare CSID/message number is never globally unique. Similar
display names or equal numbers in unreconciled client/DSP namespaces remain
`INFERRED`, not independently verified identities.

### Independent source expectation candidates

A separate `independent_oracles[]` entry must provide exact
`step_id`, `origin=independent_dsp_source`, `from_capture=false`,
`execution_enabled=false`, a safe DSP Lua/SQL relative path, exact line,
40-hex DSP revision SHA, 64-hex file digest, non-empty source-branch
preconditions, independent observer/readback requirement and an explicit
`expected_candidate`. Each is a *review-required source claim*, not a
proven branch interpretation. Where the catalog's DSP commit differs, mark
`REVISION_BLOCKED`. Missing source pins or attempted capture-derived oracle
values are rejected rather than silently filled in.

Even a complete such candidate returns
`oracle.readiness=SOURCE_CANDIDATE_REVIEW_REQUIRED` and
`oracle.normative_expected=null`; operator/source auditing and actual
independent readback are still required. Step verdict remains `UNKNOWN`.
No auto `then`, PASS or executable assertion is constructed.

### Missing observations and repeated captures

Each step enumerates explicit next evidence: authoritative NPC/event state
or scripted branch readback; item and held key-item client+persistent server
views; packet decode/receipt; exact source/decoder/parser revision; missing
source locators; independent zone/entity namespace reconciliation and
oracle source/branch review.

The repeated-capture comparer requires same recorded source lane, exact
zone label and **recorded NPC numeric ID** before comparing recorded event,
dialog, KI or item fields. It reports
`REPEATED_CAPTURE_VARIATION_NOT_PROVEN_CONTRADICTION` alongside original
source-row references, not FAIL: different preconditions or unrelated
instance/identity namespaces can explain changes. Diverging original
indexed file hashes or parser names/versions mark
`SOURCE_OR_PARSER_REVISION_DIFFERENT`. Even same indexed revision cannot
prove comparable game state or a regression.

## Synthetic acceptance and handoff

Fixture: `python test_fixtures/test_capture_identity_oracle_readiness.py`
registered in Workbench Regression. Uses existing clearly labeled synthetic
NPC `7000`, key-item `9000`, ordinary item `5000`, EventView MesNum `15`,
and source-local event/dialog rows. Shows unique pinned source-record
candidate, ambiguous NPC display names, unresolved zone, unsupported opcode,
source-cited *candidate* expected value with no derived normative expectation,
missing independent readbacks, partial/ambiguous source locators and
repeated-capture dialog variance. Tests reject forged source claims, malformed
revisions or path traversal, missing guard/readback, and capture-derived
expected values. No actual NPC/client or DSP ID is asserted.

For Agent B: `manual_editor_handoff` remains unchanged and design-only.
Use this independent diagnostic envelope as **non-normative review guidance**
alongside that handoff. The editor must require its ordinary canonical v1
schema validation and operator-authored oracle/expected assertions; do not
pass the diagnostic as a POST or source of executable bindings.

For Agent C: when a source/revision/capability v2 contract is approved,
map from its *accepted canonical owner-supplied fields*, not by silently
turning this temporary diagnostic envelope into a parallel schema.

For #1202: capture rows are not imported verified runner results. Any later
evidence-import correlation must retain exact per-run source and digest
IDs, differentiate INFERRED/UNKNOWN from verified, and reject revision
conflicts rather than deduplicating across incompatible source manifests.

## Could not verify remotely

- Actual files in user's local DSP checkout; independent SHA verification,
  file:line implementation correctness, handler branch context or current
  source revision. The supplied synthetic catalog/reconciliation claims are
  not signed attestations.
- Local client DAT/event/dialog index, client→DSP identity crosswalk, exact
  current zone/instance binding or packet decoder semantics.
- Real capture clocks, gameplay outcomes, XIHeadless run completeness,
  authoritative server DB readback or local GUI acceptance.
- Agent C's future canonical v2 proposal acceptance and exact approved
  migration/handshake contract.

No raw packets, live clients, server writes, GM operations, schema/editor UI,
review interface, execution controls or Feature Trace/coverage code changed.
