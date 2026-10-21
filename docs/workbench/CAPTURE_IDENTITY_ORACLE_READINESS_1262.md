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

## Reviewer-facing readiness projection (second slice — PR #1287)

`src/workbench/captures/scenario_readiness_summary.py::
summarize_capture_readiness(draft, catalog_snapshots=...,
reconciliations=..., independent_oracles=..., comparison_drafts=...,
expected_capture_projection_sha256=..., expected_dsp_commit=...)`
combines the existing source-only assessment with a **display-only**
`capture_author_readiness_summary_v0_NONCANONICAL` object.

No identity, step, reviewer decision, source-row evidence, game state, oracle,
canonical v1 spec or runner setting is mutated. Its step cards distinguish:

- `identity_matches[].classification=EXACT` means only consistency of a
  uniquely pinned *source record* and reconciliation metadata. It **never**
  sets `independently_verified_client_dsp_identity=true`, and supplies the
  explicit `source_record_exact_not_verified[]` disclosure.
- `identity_matches[].classification=AMBIGUOUS|INFERRED|UNRESOLVED|UNSUPPORTED`
  exposes all source alternatives and the missing/unsafe scope. Bare EventView
  MesNum and untyped raw packets remain unsupported.
- `oracle_readiness.expected_candidate` may be a separately supplied source
  interpretation with pinned Lua/SQL path, line, digest, commit and preconditions,
  but its classification is `INDEPENDENT_SOURCE_CANDIDATE_UNAPPROVED`.
  `normative_expected=null` and `verdict=UNKNOWN` never change.
- `missing_observations[]` names **independent client and server** evidence
  and how to obtain it. NPC/event lanes include client dialog and server
  event state plus **conditional** quest-variable and instance-state
  checks; item and key-item lanes require separate client/authoritative
  inventory or held-key-item readbacks; packet metadata cannot stand in
  for server receipt.
- `source_integrity` distinguishes missing external capture-projection
  fingerprint (UNKNOWN), changed projection (BLOCKED), unavailable parser
  revision, source-manifest SHA mismatch (BLOCKED), and incompatible pinned
  DSP commit (BLOCKED). A source checksum is **not** a signature or proof of
  physical source bytes. Source/decoder revision compatibility is not inferred
  from a matching human-readable name.
- `repeated_capture_diagnostics[]` labels different captured values as
  `POTENTIAL_CONTRADICTION_NEEDS_COMPARABILITY_REVIEW` or
  `REVISION_INCOMPATIBLE`; the preconditions/instance and authoritative
  state remain unknown, so the verdict stays UNKNOWN, never PASS/FAIL.

The existing `scenario_review_offline.render_review_html(draft,
readiness=...)` now optionally displays these diagnostics inside its
**existing** step detail panels, retaining the old one-argument call.
It validates capture identity, indexed projection digest, step identities
and all execution/expected-UNKNOWN invariants before display. The
HTML export still downloads the original reviewer decision-only bundle,
not a rewritten spec or an approved oracle. No new reviewer UI/route, server
request or live client integration was created. Locally supplied candidate
catalogs remain separate arguments and are never fetched by a browser.

### Proposed Agent C contract_v2 alignment — advisory only

Source: draft [PR #1285](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1285),
`docs/workbench/SCENARIO_CONTRACT_V2_PROPOSAL.md` and
`scenario_contract_v2.py` on Agent C's own branch.

The `contract_v2_alignment.metadata_shape_preview` uses only **Agent C's
existing proposed** key names: `contract_version`, `sources`,
`parameters`, `oracles`, `step_requirements`, and `fingerprints`.
It does **not** add a `contract_v2` field to the canonical scenario or
change the v1 validator. Source refs, normative oracles and engine/spec pins
remain empty/null because neither a complete, verified source repository
nor an assertion-bearing canonical v1 specification is supplied. Parameter
`binding_state` is no higher than `candidate`, including when this
adapter reports an EXACT **source-record** match. Ambiguity produces
`binding_state=ambiguous` and `identity=null`. Names and undefined
namespace numbers are not converted to invented numeric IDs. Every
step requirement is `unassigned/unknown`, with explicit readback hints
and `execution_gate=blocked`. Unsupported event/dialog names and
oversized parameters are reported as omissions, not coerced to another type.

This is a **non-importable field-mapping preview** and cannot be fed to
`validate_spec`, the spec draft store, Agent B's Scenario Developer or
XIHeadless. Agent C must accept/reconcile the proposal and approve
source/identity/oracle mapping first. Once approved, the mapping must be
rebased onto **real v1 assertion IDs**, source refs, signed/rehashable
pinning and operator-reviewed readback capabilities.

Synthetic tests: `test_fixtures/test_capture_readiness_summary.py`, alongside
`test_capture_identity_oracle_readiness.py`. They cover exact-but-not-verified,
ambiguous identities, missing client/server/KI/inventory/quest/instance
readbacks, revision drift, contradictory captures, malformed/altered source
hashes, expected-source candidates remaining UNKNOWN, HTML display, and
strictly blocked advisory v2 fields. **No local DAT/server or live testing.**


## Final Agent A review gates, structured readbacks and safe sidecar

Agent A's [independent PR review](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1287#issuecomment-6311826844)
requires this branch to reconcile against current main **without force-push**,
run a dedicated synthetic/offline GitHub Actions gate in addition to Workbench
and source-layout tests, and remain draft until independent review. The focused
workflow is `.github/workflows/capture-evidence-readiness-offline.yml`:
it runs the reverse capture, evidence handoff, reviewer, identity and
readiness pytest fixtures together with an editable `src/` install.

`readiness_steps[].missing_observations[]` is now a concrete diagnostic:
`expected_observation_type`, `reason_for_gap`, original immutable
`evidence_refs`, `suggested_read_only_capability`, `importance`,
`status=NOT_INDEPENDENTLY_OBSERVED`, `how_to_obtain`,
`capability_registered=false`, `permission_granted=false` and
`review_required=true`. It names **conditional** equipment, furnishings,
quest-variable, temporary-item, NPC and instance readbacks without implying
they apply to every captured event. Suggestion strings are NOT registered
MCP actions, endpoints, RBAC grants or executable operations.

The existing offline Evidence Reviewer has a separate **Export readiness
sidecar** button. This emits an untrusted, `NONCANONICAL` JSON bundle with
the full unchanged `original_evidence_handoff` (including source-row
hashes, locators, parser metadata and review decisions), read-only
`readiness_diagnostics`, capture projection checksum and a manual
Scenario Developer pointer. The existing **Export design-only review JSON**
is untouched and retains its original replay validation/format. The
sidecar stores two **distinct** tooling digests,
`indexed_observation_projection_sha256` and
`original_handoff_projection_sha256`, because those digests cover different
projections; neither authenticates capture bytes. `review_decisions`
is collected separately from the immutable `original_evidence_handoff`,
so explicit ACCEPT/EDIT/REJECT notes accompany the diagnostic without
rewriting any source value or silently applying it. There is
no automatic import, save, assertion creation or execution. The readiness
display rejects mismatched capture IDs/projections, changed source refs,
source-verified identity flags, promoted normative expectations, execution
permissions and forged auto-import states. Reviewer source citations in a
downloaded file are *claims*, not independently authenticated physical bytes.

Agent C's [draft #1285](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1285)
still owns all `contract_v2` schema and validation changes. The
advisory vocabulary maps EXACT source-record => **candidate, not
independently_source_verified**; AMBIGUOUS => ambiguous with identity null;
INFERRED => candidate only for a typed recorded identity, otherwise
unresolved; UNRESOLVED/UNSUPPORTED => unresolved or omitted. Source-rule
oracles cannot be projected without a separately authored canonical
assertion ID and independently verified normative DSP rule; UNKNOWN
oracles, empty source refs and blocked step capability remain default.
Capture source hashes must never masquerade as DSP file-content SHA-256.

The manual Scenario Developer handoff requires Agent B's review of source
reconciliation and readback completeness. This sidecar is explicitly
**not a Scenario Developer POST payload** or a v2 spec. Do not import into
#1202 or issue PASS from captured behavior. Real client/DSP correlation and
authenticity checks remain local acceptance tasks.


## Final review reliability: per-gap status and tamper boundaries

Agent A's submitted [COMMENTED code review](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1287)
was on historical head `b9f89479`. Current PR is reconciled to
`main@e9ae790d` (zero behind), with dedicated focused offline CI in addition
to Workbench and Src Layout. A COMMENTED review is **not** an approval;
Agent A must review the current head before any owner-authorized merge.

Every `readiness_steps[].missing_observations[]` now also has
`readiness_state`: `UNKNOWN` for absent independent readbacks, unpinned
parser identity or unavailable digest; `BLOCKED` when a pinned indexed
projection, source manifest/locator digest, or DSP oracle/catalog revision
actually conflicts. This is **evidence compatibility state only**, separate
from gameplay `verdict=UNKNOWN` even when `readiness_state=BLOCKED`. A
projection-wide mismatch blocks every dependent step; a source-row conflict
blocks the steps citing that row. Missing manifest SHA-256 is explicitly
`SOURCE_MANIFEST_DIGEST_UNPINNED` (UNKNOWN), **not** a fabricated
`SOURCE_MANIFEST_DIGEST_MISMATCH` (BLOCKED). Missing parser *name or
version* produces `PARSER_REVISION_UNPINNED` (UNKNOWN).

The existing offline Evidence Reviewer rejects caller-supplied readiness
objects that mark an unobserved readback as verified, grant permissions,
change its source references, claim physical capture authentication or
claim a READY/approved state. Gap records must exactly match safe producer
diagnostics for their original step with `capability_registered=false`,
`permission_granted=false`, and their original evidence refs. Physical
source authenticity and execution permissions **cannot** be supplied by
the offline reviewer. These checks protect *internal advisory consistency*;
a malicious self-consistent sidecar still needs independent local source
verification.

Agent C's unmerged `scenario_contract_v2_adapters.py` exposes
`project_identity_diagnostic(diagnostic,kind=...)`, which expects
`identity/namespace/zone_id` alongside `classification`, whereas Agent
D's source-candidate diagnostic retains original `observed_value` and
`scope`. Do **not** pass Agent D's record directly to this unmerged adapter
or synthesize namespace/zone numeric IDs to fill the mismatch. The
non-importable `contract_v2_alignment.metadata_shape_preview` is already
typed with the same canonical field vocabulary but leaves namespace/zone
unresolved and no verified source refs. A future accepted owner-defined
adapter should explicitly reconcile the two input shapes with independently
authenticated source scopes and reviewer mapping. No canonical schema or
Agent B editor files changed in this PR.
