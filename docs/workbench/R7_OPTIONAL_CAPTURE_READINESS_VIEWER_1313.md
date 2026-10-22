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
  after either selector changes.
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
