# R7 #1313 — Optional capture-readiness viewer: offline pair contract

**Status:** Draft, not integrated into Agent B's active Scenario Developer
template/router. This is a new, evidence-owned offline verification and
display module, **not** another reviewer, decoder, canonical importer,
assertion editor, file-authenticator, execution or GM capability.

## Selected files and precise integrity boundary

The operator must explicitly select *both* JSON exports from the **same**
offline Evidence Reviewer screen: (A) "Export design-only review JSON"
(`offline_capture_review_decisions_v1_NONCANONICAL`) and (B)
"Export separate readiness sidecar" (`capture_reviewer_readiness_sidecar_v0_NONCANONICAL`).
No file is read from a server directory, stored, normalized into a canonical
specification, or automatically imported. The two exports must have
**identical human decisions** from the source page; if decisions were modified
between exports, re-export both from the same original reviewer state.

`inspect_paired_readiness(review, sidecar)` (pure Python, no filesystem) uses
the **existing**, strict `inspect_evidence_review` to validate review A,
including original capture identity, indexed row/evidence links, handoff
checksum, original source provenance, manual step/binding decision rules,
and non-execution constraints. It independently reconstructs the
indexed capture observation scope from A, then:

1. Compare B's `capture_id`, `original_evidence_handoff` and
   `review_decisions` **exactly** with A.
2. Recompute the original handoff projection SHA-256 through the existing
   editor-reviewed-decision inspector, and the **differently scoped** indexed
   observation projection SHA-256 through the existing capture readiness
   digest function. Compare both to B; **they are not interchangeable**.
3. Recompute the **entire original** `summarize_capture_readiness` output
   from the original indexed rows and compare it to B's
   `readiness_diagnostics` and `scenario_developer_handoff`. This is
   deliberately conservative: producer views based on additional separately
   supplied catalog/oracle/reconciliation context are refused until a
   distinct trusted, reviewable context-input design is approved. Unknown
   data stays UNKNOWN rather than silently ignored or "verified".
4. Reject duplicate same-step refs, foreign capture row IDs, mismatched
   source table/row key, fake original step or binding decisions, bogus
   selected hashes, edited parser/source digest claims, forced canonical
   step attribution, `oracle_approval_state=APPROVED`, observed readback,
   granted capability or `execution_enabled=true`. Fail closed if the
   selected data is incomplete or exceeds 4.5 MB per JSON.
5. Return only
   `read_only_paired_capture_readiness_view_v1_NONCANONICAL` with original
   step/row/source, index-local filename/span/time basis, parser version and
   independent decoder **NOT ATTESTED** declarations, candidate identities
   and unapproved expected values, original step/binding reviewer decisions,
   conditional missing `job_state`/`mob_state`, other client/server
   readbacks and UNKNOWN/BLOCKED compatibility. Execution, saving,
   import, source verification and canonical linkage remain disabled.

**Important:** An attacker can rewrite **both** user-controlled JSON files
and recompute self-consistent hashes. Matching JSON proves internal
consistency of the two selected representations, *not* authenticity of the
physical capture, input parser/decoder binary, original operator decisions,
retail client, DSP deploy or independent gameplay state. The view explicitly
displays `original_capture_authenticated=false`,
`source_bytes_rehashed=false`, `parser_decoder_authenticated=false`,
`normative_expected=null`, `verdict=UNKNOWN`, and
`canonical_step_associations=UNASSIGNED`.

## Optional DOM module and integration contract

The new `gui/static/scenario_readiness_viewer.js` exports:

- `ScenarioReadinessViewer.mount(container, inspect)`: Adds *two distinct*
  operator file selectors, an explicit "Inspect selected pair" action, status,
  and read-only result. The host supplies a **trusted read-only** async
  `inspect(reviewJson,sidecarJson)` backed by the Python verifier; the
  module has no built-in network/endpoint, local draft or runner access.
  Selection-generation guards discard stale file-read or inspection results
  after either selector changes. The returned mount handle also provides
  `dispose()`: Agent B must call it on New/Open/Fork/Clone/route teardown
  to invalidate all in-flight responses and clear a previously accepted
  advisory. A disposed viewer cannot re-enable its inspection button or
  resurrect a stale response.
- `ScenarioReadinessViewer.verify(model)`: Fails closed if untrusted result
  claims canonical step mapping, source authentication, approved oracle,
  execution or import. This is defense-in-depth; only the backend verifier
  can establish selected JSON **internal** integrity.
- `ScenarioReadinessViewer.render(container, model)`: Renders **text nodes**
  (not raw HTML) for indexed row, source file/line/offset, separate digest
  declarations, step/binding human decisions, uncertain identity and
  unobserved conditional readbacks. No save/import/GM/SQL/packet/run buttons.

### Remaining editor ownership handoff

Agent B owns `gui/static/scenario_developer.js`,
`gui/templates/scenario_developer.html`, and
`src/workbench/server_admin/scenario_authoring/editor_router.py`.
At creation of this PR Agent B's #1307 was still draft/active. **Do not
edit/rebase/push that branch or overwrite shared editor files.** After Agent
B and Agent A explicitly agree on timing and target:

- Add a separate localhost-only, same-origin, JSON POST *read-only*
  `/scenario-developer/handoff/readiness/inspect` endpoint with the same
  request-size and CSRF/origin constraints as the existing review-inspect
  route; delegate only to `inspect_paired_readiness`. Ensure no write
  transaction and no remote file lookup.
- In the existing Scenario Developer, add **separate optional selectors**
  and mount the standalone viewer with an async call to that endpoint.
  Keep `/handoff/evidence/inspect` accepting *only* reviewed-decision
  files exactly as today; no sidecar aliases, no shared state with canonical
  import, Guided/Advanced, save/open/fork/clone, runner/GM, or identity
  acceptance. Preserve all existing optimistic revision, dirty-guard and
  async response safeguards.
- Extend B20's operator-only browser checklist for selected original + sidecar,
  same-capture pairing, malformed/foreign/duplicate refs, forged reviewer
  decision, missing parser, UNKNOWN/BLOCKED, separate hashing scopes,
  change-file-during-inspection, never-save/execute. **NOT RUN** until local
  owner acceptance. This offline branch is not itself the completed
  in-editor wiring.

## Exact-head synthetic acceptance

Dedicated workflow `R7 Optional Capture Readiness Viewer (Offline)` runs
the new paired Python tests **with merged producer regression**, an
independent actual Node DOM presenter/stale-selection test, and independent
syntax checks (no YAML-folded commands). This proves only synthetic
application invariants. No real capture/client/DSP/DB/GM/packets.

Prior to any claim of physical evidence authentication, an authorized
operator must independently preserve and rehash the original capture
bytes, verify installed parser and packet decoder versions/semantics, DSP
commit/revision and client DAT namespaces, source file SHA-256, before/after
authoritative readbacks (inventory/furnishings/jobs/quests/key items/NPC/mob/
instance), then record reviewable evidence and owner-approved oracle/source
associations. These steps are **not done** and are not part of #1313.


## Current-head security hardening and precise review labels

The read-only verifier preserves the original indexed capture records and now
**separately** exposes:

- `steps[].reviewer_step_decision_original` and
  `identity_confidence[].review_decision_original`: the immutable indexed
  observation's originally recorded review decisions.
- `steps[].reviewer_step_decision_selected` and
  `identity_confidence[].review_decision_selected`: choices explicitly
  entered by the operator in the selected `offline_capture_review_decisions`
  JSON, validated by the accepted reviewer inspector and exactly matched
  against the separately selected readiness sidecar's `review_decisions`.
  These fields are **not** a replay or mutation of the original capture,
  and are `null` when that particular item has no selected decision.

The UI must label both categories separately; do not treat ACCEPT/EDIT
human observation review as canonical source authentication, identity
verification, expected oracle approval or gameplay PASS.

The standalone renderer now also refuses *nested* bogus trust claims:
`source_identity_verified=true`, missing readback with
`permission_granted=true`/`capability_registered=true`/VERIFIED status,
duplicate/cross-capture source refs, non-array canonical source refs,
`indexed_digests_rehashed=true`, or an independently claimed decoder version.
The server-side full-producer-recomputation remains the **decisive** check;
client checks are defense in depth and are not sufficient by themselves.

## Local B20 operator acceptance checklist (NOT RUN)

These steps are **blocked** until Agent B's independently reviewed
Scenario Developer route/template attachment is merged. The test operator
must preserve original files and write down the observed on-screen result
for each exact test; no live DSP or gameplay operation is required.

1. Navigate to Scenario Developer with an existing unsaved design draft.
   Opt into the *separate* Capture Readiness panel; confirm it initially
   shows **no accepted evidence** and that no file, network request, save,
   or test execution starts without user selection.
2. Select the original **reviewed-decision JSON** and its **separate
   readiness-sidecar JSON** from the same offline Evidence Reviewer. Press
   **Inspect selected pair**. Confirm original capture ID, table/row/source
   IDs, file locator/offset/time basis, and **two differently scoped indexed
   projection SHA-256s** are shown, with clear **not physically attested**
   disclaimers. Neither digest is a source-byte authentication signature.
3. Confirm original indexed step and binding decisions appear separately
   from selected reviewer decisions. A reviewed ACCEPT/EDIT only certifies a
   human's review *choice*, not an authenticated identity, source-backed
   oracle, normative expected result or gameplay PASS.
4. Confirm all identity candidates (EXACT, INFERRED, AMBIGUOUS,
   UNRESOLVED/UNSUPPORTED where present) retain original uncertainty,
   including no selected canonical identity for AMBIGUOUS. Show
   `canonical_step_id=null`, unassigned source-step scope, UNAPPROVED
   oracle, missing observations and blocked execution.
5. Confirm index-local parser name/version, digest *claims*, no decoder
   attestation, and SOURCE_UNKNOWN warnings display as declarations. With
   synthetic missing parser metadata, report **UNKNOWN**; with conflicting
   well-formed recorded digests, report **BLOCKED**. Neither means
   gameplay PASS or FAIL.
6. Confirm all relevant client/server inventory, furnishings, quest, key
   items, instance/NPC, plus **CONDITIONAL job/mob-state** readbacks display
   as NOT_INDEPENDENTLY_OBSERVED, with permissions and capability
   registration false.
7. Select mismatched captures, changed original step/row identity,
   cross-capture refs, duplicate evidence refs, modified SHA in either
   scope, forged selected reviewer decision, physically verified source,
   approved oracle, changed parser/decoder declaration or any grant of
   execution. Every case must **refuse accepted pairing**, show a neutral
   reason, clear the prior result, and leave the current scenario unchanged.
8. While a large selected pair is being read/verified, change **either**
   selected file or enter another editor state (New/Open/Fork/Clone/Advanced).
   The old async response must not reappear or overwrite newer content.
   Reinspection after changed files requires a fresh explicit click.
9. Attempt to provide a readiness sidecar to the **existing
   `/handoff/evidence/inspect` reviewed-decision importer**. It must still
   reject it; a valid pair-inspection result must never become canonical
   spec JSON, an auto-save payload, an assertion, a canonical CASE/STEP
   association, or a runtime permission.
10. Reopen/reload the Scenario Developer after inspecting a pair. Confirm
    no advisory is silently persisted, selected, trusted, imported, or
    executable; existing legacy v1 and canonical Contract v2 editing,
    revisioned draft save, and all operator/dirty-state guards still work.

The integration reviewer must verify the **actual** callback is a local-only
same-origin JSON POST that calls `inspect_paired_readiness` and catches
malformed/oversized inputs without stack traces. The previous
`/handoff/evidence/inspect` path must remain unchanged. Inspecting a
synthetic fixture in CI is **not** successful B20 acceptance or real
capture/client/server attestation. Record B20 as NOT RUN until the owner
performs and signs off these steps.
