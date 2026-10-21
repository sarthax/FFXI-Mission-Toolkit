# R7 Scenario Developer — bounded local browser acceptance handoff

**Issue:** #1302 · **Draft editor PR:** #1307 · **Parent:** #1197  
**Owner:** local Toolkit operator, after eligible GitHub review and owner-authorized integration  
**Status:** DOCUMENTATION ONLY — **not performed or approved by remote Agent B**.

**Dependency checkpoint:** Optional direct case/step `source_associations` is still proposed by DRAFT #1309; Agent D's extra `indexed_evidence_provenance` is still proposed by DRAFT #1308. The source-registry display and reviewed-decision importer already on main/#1307 remain the only accepted editor paths. B16–B20 are gated, not completed.

## Preconditions and boundaries

1. Pull the reviewed/approved Toolkit commit and start the existing local Workbench using the documented Toolkit procedure. Use a **disposable synthetic draft**, not a live character or DSP account.
2. Use the existing same-origin local UI (`/scenario-developer`). Do not expose the authoring route to a network origin or supply a production operator token. Have a **test-scoped operator token** only if explicitly authorized by the owner.
3. Record exact Toolkit revision, browser/version, current `contract_v2` contract revision, selected synthetic feature/case, and draft revision before and after each acceptance step. Do not paste operator tokens, private captures or secrets into a GitHub issue.
4. The documented offline fixture is `test_fixtures/scenario_contract_v2_synthetic.json` (fixture wrapper is **not itself a valid draft**; use only its canonical specification and adapt it to the editor's existing read-only design-draft policy). Use MOG-09/INV-OBS-01 for *legacy viewing*, not new live execution.
5. **NO live DSP login, gameplay, GM/SQL/packet mutations, automated execution or original-capture attestation.** Save is restricted to an owner-authorized disposable draft in the existing local draft store.

## Operator clickthrough matrix

| ID | Action and controlled stimulus | Required observation / refusal |
|---|---|---|
| B01 | Open an ordinary legacy v1 draft without `contract_v2` | Same Guided/Advanced editor and canonical preview as before R7; no invented v2 namespace or source claims. |
| B02 | Open the merged Coverage Matrix and inspect a legitimate same-origin `context_ref` link | Source intent appears **before** draft creation. Explicit **Begin authoring** re-fetches the context. Changed/expired/off-origin references and double-clicks cannot create duplicate authoring drafts. |
| B03 | Open a valid optional-v2 synthetic design-only draft; expand Source Registry | Show declared repository/path, pinned revision, line range and claimed SHA-256. No digest => `UNKNOWN / UNHASHED`; digest present => `DECLARED / NOT INDEPENDENTLY REHASHED`. A declared source is **UNASSIGNED**, not automatically case/step-attached. |
| B04 | Expand a typed candidate parameter, ambiguous NPC, and unresolved catalog identity | Candidate remains candidate; ambiguous/unresolved cannot select identity. `independently_source_verified` remains a *declared source-pinned metadata claim*, **not authenticated client/DSP identity**. |
| B05 | Expand an oracle linked to an assertion, then the related step | Oracle source is shown under **oracle-linked expected-value candidate evidence**, not as an independent step citation. Expected result is **UNAPPROVED / UNKNOWN** until distinct authoritative evidence and review. No source record or capture observation promotes normative assertions. |
| B06 | Inspect step readbacks, capability, operation class and permissions | Required client/server readbacks appear `NOT INDEPENDENTLY OBSERVED`; permission list appears `NOT GRANTED`; every execution gate is **BLOCKED**. No Run/GM/packet/action button is activated. |
| B07 | Compare compatibility for missing runtime/source evidence, mismatched stored base-spec hash, and supported read-only pinned test data | Display **UNKNOWN**, **BLOCKED**, and **MATCHED_PINNED_ONLY** distinctly *only* when returned by canonical compatibility report. Pinned-only does not mean source authenticity or execution. No observed hashes/revisions are fabricated. |
| B08 | Guided → Advanced JSON → Guided with no edits; then edit a step/title/expected field in Advanced | Optional namespace and all keys remain intact. Provisional Advanced display changes without auto applying/saving. A changed v1 core with stale base-spec SHA shows BLOCKED on server validation; Save is refused, never silently re-fingerprinted. |
| B09 | New, Fork published, Clone draft, Open another saved draft while current draft is edited, and repeat with loaded revision | Each destructive switch prompts to discard or refuses during save. Fork/Clone keeps optional metadata as a **claim requiring re-review**; no silent source/hash approval. Cancel keeps prior document. |
| B10 | With a valid **test** operator token, preview, save, close/reopen and edit a disposable v2 draft; then try stale expected revision | Round-trip JSON metadata is identical until explicitly edited. Revision advances only for the correct document and successful save; stale revision fails. Newer same-document edits remain marked UNSAVED if they arrive after save dispatch. |
| B11 | Save without a token, with bad token, with 32 KiB ASCII-escaped Unicode-overlimit JSON, or with unsupported identity/permission/metadata key | Clear validation or refusal, no partial draft, no changed revision, no auto-upgrade. Compact UTF-8 review-upload bounds and SQLite ASCII-escaped **storage** size are separate. |
| B12 | Use the original **reviewed decision JSON** evidence import; manually include/exclude each proposed step and candidate binding | Every step and binding requires confirmation; unsupported/rejected/unreviewed bindings fail closed; indexed-projection digest is **only internally consistent**, never physical capture authentication. No implied oracle, approval, save, or execution. |
| B13 | Select another evidence file while inspection POST is pending; edit a draft while preview/save/fork request is pending; navigate away and back | Older async results cannot reinstate an earlier file's proposals, mutate another document identity/revision, or silently discard unsaved work. |
| B14 | Present Agent D's optional `capture_reviewer_readiness_sidecar_v0_NONCANONICAL` rather than reviewed decision JSON | The existing review-import route **rejects it**. No sidecar fields are imported into canonical draft, source hash attested, parser/decoder verified or capability registered. Future *opt-in read-only* display, if separately accepted, needs distinct checks of indexed vs original projection hashes and source/capture IDs. |
| B15 | Check the source-attribution schema status | Until canonical PR **#1309** is approved and merged, `source_associations` is **not an accepted editor input**. Declared and oracle-linked sources are *not* explicit step citations. After merge, test case/step links **only through the accepted `source_attribution_report(spec)`**, retaining all permission/oracle restrictions. |

## Canonical association and evidence-producer *integration-only* checks (not yet runnable)

These checks are **BLOCKED / NOT RUN** until #1309 and #1308 are independently approved, merged into Toolkit main, and consumed in a reviewed editor-only extension of #1307. Do not simulate completion using staged aliases, an untrusted sidecar, or oracle context.

| ID | Exact owner-authorized browser check after integration | Acceptance |
|---|---|---|
| B16 | Open a canonical v2 design draft whose accepted `source_associations[]` declares a case-only source | Case citation appears **EXPLICIT_CITATION_CLAIM** at case scope, not on any step. `source_attribution_report(spec).steps[step_id]` remains UNKNOWN. No oracle/identity approval. |
| B17 | Open a draft with step-only association to a real canonical step ID and a separate unassociated source | Explicit step citation appears only for the linked step. Case citation and unassigned registry stay UNKNOWN/UNASSIGNED; duplicate source text, step order and linked assertion are **not** alternate link mechanisms. |
| B18 | Edit, reorder, clone/fork, preview, save and reopen a v2 draft with optional explicit associations | No metadata loss or silent link inference. Changed canonical step ID invalidates old link until independently reviewed; stale base-spec SHA remains BLOCKED until manually reconciled. Owner test token only; SQLite ASCII-escaped 32 KiB limit still applies. |
| B19 | Present invalid association (unknown source/step ID, duplicate scope/target, empty refs, case with non-null target, inconsistent source hash) | Canonical server **rejects** preview/save with actionable diagnostics, no revision or permission change, no fallback JS step matcher. |
| B20 | Select a reviewed, separately validated #1308 readiness sidecar for **opt-in read-only inspection** (not the existing reviewed-decision import) | Display capture ID, original evidence ref/table/row, parser name/version, claimed locator vs manifest digest, index/source warnings, ambiguous identity, missing client/server readbacks and UNKNOWN/BLOCKED; keep `decoder_version=null`, indexed hashes **NOT REHASHED**, `canonical_step_id=null`, normative expected null, permissions false and execution disabled. Verify original capture/source refs and both separately scoped projection SHA-256s. Declared metadata is not authenticated. Without an accepted read-only inspection surface, mark **BLOCKED**, never POST the sidecar to the editor's reviewed-decision intake. |

**Current remote development scope:** #1307's pre-#1309 view displays source registry declarations as UNASSIGNED and oracle-linked source candidates separately. It does **not** treat the proposed optional association as accepted or claim to display new indexed-provenance diagnostics. Synthetic compatibility fixtures prove non-promotion and preserve pending metadata, not browser UI completion. Local browser acceptance is requested **only after** these integration gates are complete and approved.

## Evidence to capture in the browser acceptance report

- Exact Toolkit git SHA, exact accepted editor PR #1307 SHA, optional #1309/#1308 merge SHAs **if applicable**, browser version, local host URL *without secrets*, synthetic fixture IDs, test-only draft revisions.
- For each B01–B15: **PASS / FAIL / BLOCKED / NOT RUN**, short UI observation, sanitized screenshot or locally stored log path (if allowed). Fail a test if a review/permission/source claim is silently upgraded.
- State whether operator authentication was exercised. Clearly separate **offline CI**, **local browser review**, **source byte rehash**, **live DSP/client reconciliation**, and **gameplay observations**; passing one never proves the others.

## Cross-agent contracts, not implicit integrations

**Agent C — [draft #1309](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1309):** Proposed, not yet accepted optional `contract_v2.source_associations[]` with exact `scope:"case"|"step"`, `target_id:null|existing_step_id`, `source_refs[]` pointing to canonical `sources[].ref`. Expected read-only helper: `source_attribution_report(spec)`; `UNKNOWN` versus `EXPLICIT_CITATION_CLAIM`, never authenticated or runnable. Do not read invented staging aliases. **Do not adopt until eligible approval and merge.**

**Agent D — [draft #1308](https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1308):** Noncanonical `capture_readiness_authoring_projection_v1_NONCANONICAL` adds `steps[].indexed_evidence_provenance[]` with original evidence-ref table/row, source-local clocks/locators, **two indexed digest claims**, parser support (not authenticated decoder), `UNKNOWN/BLOCKED` source issues, suggested conditional job/mob readbacks. It is a **separate sidecar** with `automatic_import=false`, `oracle_approval_state=UNAPPROVED`, `normative_expected=null`, `independent_source_authentication=false`, `indexed_digests_rehashed=false`, `execution_enabled=false`. Never submit as the reviewed-decision envelope; any optional display requires separately reviewed identity and projection SHA matching.

This checklist does not authorize local testing, source attestation, merges, schema changes or execution.
