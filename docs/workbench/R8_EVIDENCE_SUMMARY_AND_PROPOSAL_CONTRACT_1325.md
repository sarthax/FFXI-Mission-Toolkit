# R8 #1325 — bounded scenario evidence summaries and failure-driven proposals

**Status:** DESIGN ONLY / NONCANONICAL / SYNTHETIC TESTS. **No MCP function, importer adapter, scenario edit, execution, source authentication, or gameplay verdict is implemented by this PR.**

**Owners/dependencies:** Agent D evidence contracts; Agent C catalog/read discovery (#1200); Agent B Scenario Developer review UI (#1325); Agent A integration; #1198 oracle authority and coverage; #1202 attempt/import deduplication; #1201 lifecycle; #1255 and XIHeadless #105/#110 pending approval. Keep #1313's capture verifier/editor release independent.

## 1. The trust boundary

An evidence summary is **a read-only projection over retained records**, never an origin of truth. In particular, the optional R7 viewer #1315/#1318 establishes **internal consistency of two selected indexed JSON projections only**, and not authenticity of physical capture bytes, decoder binaries, a client identity, a DSP deployment, source-control provenance, or an approved gameplay oracle. Any claim received through a capture, report, MCP tool, reviewer export, LLM analysis, or source locator starts as *data*, not executable instructions or authorization.

Authority must be attributed **per assertion and per observation**. Do not collapse the following into a single `pass`/confidence flag:

| Category | Contract meaning | Promotion forbidden without |
|---|---|---|
| **Observed fact** | An attributed statement of what one observer reported, with `observer`, `source_ref`, time/clock basis, digest *claim*, completeness and authenticated/unauthenticated status | Independent verification of the producer and physical/deployed source if authenticity is asserted |
| **Candidate interpretation** | Correlation/hypothesis, including an agent-suggested negative case or expected value | Independent reviewer approval; never presented as normative expectation |
| **Approved oracle** | An explicitly recorded, version-pinned normative assertion ID/expected value with reviewer authority, evidence scope and provenance | #1198 approval and independently checked source/readback; absence is `UNAPPROVED` |
| **Missing evidence** | A required observation or readback not present, unauthorized, unsupported or unobservable | A separately authorized and obtained observation |
| **Incomplete observation** | Partial/streaming/cancelled/interrupted task without requisite terminal evidence | Terminal receipt *and* completeness/reconciliation; even then terminal != gameplay PASS |
| **Conflicting evidence** | Same identity with different digests, different observation values, revision disagreement or unaligned clocks | Explicit conflict records, resolution and original immutable versions |
| **Original provenance** | Original retained artifact pointer, capture index/row, source locator and optional hash claims, parser identity, time basis | Independent byte/decoder/producer/source authentication; JSON checksums are insufficient |
| **Source revision** | Distinct pinned specification, source file, DSP deployment, Toolkit, Headless, decoder and evidence revisions; unknowns explicit | Consistent comparison under #1198 and source-contract approval |
| **Attempt/run identity** | `request_id` (when negotiated), `run_id`, `attempt_id`, `operation_id` and stable case revision are **different namespaces** | #105 / #1202 agreement; never infer them to be equal |
| **Terminal vs partial** | Admission, running, completed, cancelled, interrupted are lifecycle; evidence completeness and assertions are distinct | #1201 and #1202 reconciliation |
| **Cleanup status** | Independent post-run cleanup observation: `VERIFIED`, `INCOMPLETE`, `FAILED`, `UNKNOWN`; a self-reported cleanup claim is not verification | Authorized evidence and independent verification |

`UNKNOWN` means gameplay truth is not established. `BLOCKED` means an evidence/provenance/evaluation precondition was not met. `FAIL` requires an applicable reviewed normative oracle plus complete, reliable observations; a **reported** failure/mismatch alone is not an *authoritative* FAIL. Source incompatibility is not gameplay FAIL. No omission may cause PASS.

## 2. Proposed read interface — not shipped

Provisional name: `scenario_evidence_summary` (Agent C should first reconcile existing supervisor/MCP conventions). Bounded, read-only, explicitly authorized, scope-limited API:

```text
scenario_evidence_summary(
  feature_id, case_id, spec_revision_or_digest,
  run_id? = null, attempt_id? = null,
  include_observation_summaries = true,
  page_size = 25, cursor? = null
) -> scenario_evidence_summary_v0_DESIGN_ONLY_NONCANONICAL
```

**Proposed limits (require owner review):** allowlisted catalog identities only; default 25 and maximum 100 summaries/page; maximum 25 observations per attempt; up to 4 KiB per sanitized human-facing excerpt; stable ordering by immutable attempt timestamp plus attempt ID; pagination cursor bound to query filters, dataset revision and authorization scope; fail closed on stale cursor. Redact account/character secrets, local full paths, tokens, packet payloads, private source content and arbitrary client bytes. Return explicit truncation and `next_cursor` rather than silently suppressing evidence. No external URLs fetched, arbitrary repository reads, shell, SQL, packet, GM, runtime control or dynamic plugin dispatch.

For every attempt, project:

- **`scenario`:** catalog feature/case, canonical outer version, design-only/runnable status **as already approved**, immutable revision/digest and selected source-association claims. Do not change the canonical v1+optional v2 schema or convert design-only to executable.
- **`attempt`:** independent run, attempt, operation, request IDs; evidence digest *claim*, immutable artifact reference, ingestion time, duplicate/replay classification `FIRST_SEEN|EXACT_REPLAY|IDENTITY_DIGEST_CONFLICT` and conflict references. Digest is never proof of external origin.
- **`lifecycle`:** admission and task phase separately; `terminal_recorded`, `observation_completeness`, missing terminal event(s), cleanup status + independent provenance. Do not turn a cancellation acknowledgment into terminal proof.
- **`provenance`:** original capture index/row, source locator and timestamp basis, parser/decoder claims, spec/source/deployment revisions and independent-authentication booleans. Distinguish selected reviewer decisions from immutable original indexed decisions (#1313).
- **`evidence`:** ordered `observed_facts[]` with field-level origin and confidence; separately `candidate_interpretations[]`, `approved_oracles[]` (only from #1198), `missing_observations[]`, `conflicting_observations[]`, independent readback status and provenance flags.
- **`recorded_outcome`:** original producer's *reported* comparison/verdict verbatim and independently recomputed evaluation when supported. **`authoritative_gameplay_verdict` defaults `UNKNOWN`** and may not be promoted by summary generation. Present source BLOCKED separately. Historic v1 importer verdicts may be displayed as **stored claims**, not silently reclassified as independently attested.
- **`triage`:** deterministic, explainable diagnostic codes; never secretly alter original evidence or an existing importer row.

A rendered summary must always display independent authority status next to any PASS/FAIL claim, even for a report that appears structurally complete. Confidence is a multidimensional provenance/observation matrix, not a single fabricated percentage.

### Minimal read-only envelope and example representation

`test_fixtures/r8_evidence_summary_vectors_synthetic.json` supplies eight complete **synthetic** records under `scenario_evidence_summary_v0_DESIGN_ONLY_NONCANONICAL`. Its `scenario`, `attempt`, `lifecycle`, `provenance`, `evidence`, and `triage` members are the design shape, **not an approved wire format**. All source names/digests/IDs are conspicuously synthetic; their `source_bytes_authenticated`, `decoder_authenticated` and `source_identity_verified` fields are false. All `approved_oracles` arrays are empty. The tests explicitly refuse untrusted promotion.

An actual future version must add strict schema typing, checked timestamps and domains, redaction, source/ref indexes, immutable storage lookup and per-assertion reviewer authority. Do not introduce those by loosening the existing v1 importer or #1313 viewer contract.

## 3. Proposed untrusted failure-to-scenario artifact

`scenario_revision_proposal_v0_UNTRUSTED_DESIGN` is a *separate proposed document* derived from a fixed snapshot of summary inputs, not a canonical case or imported report. The provisional `scenario_propose_revision` route in #1325 must not be enabled until separately reviewed; this PR only tests a synthetic representation.

Required proposal elements:

1. A non-authoritative `proposal_id` and deterministic **idempotency identity** over `(case revision/digest, run_id, attempt_id, evidence digest)`. Namespace identifiers, never conflate `run_id` and `operation_id`. Use versioned serialization for hashing and retain exact immutable source refs. This is only a *proposed* strategy until #1202 acceptance.
2. Pinned `base_revision` and `base_digest`, target case/spec version, source association and deployment revision *claims*, plus conflict and stale-revision checks. Refuse to apply to a different current revision.
3. Explicit **before/after proposed changes** with narrow typed kinds: observation prerequisite, negative case, source refresh, readback request, cancellation/cleanup guard. Descriptions are **not** valid canonical JSON Pointer mutation paths.
4. Separate structured reason codes, affected assertions, source/Feature Trace citations, observed facts, disputed interpretations, supporting/contradicting attempts, missing prerequisites and risks. Untrusted capture or model text may never supply instructions to tools.
5. Status `DRAFT_UNTRUSTED|REQUIRE_FRESH_EVIDENCE|REFUSE_UNTIL_RECONCILED|NO_CHANGE`; hard `canonical_write_allowed=false`, `execution_allowed=false`, `permission_grants_allowed=false`. No `oracle_approval_state=APPROVED` unless independently produced by #1198 review (not supported in these synthetic proposal records).
6. A separate human review state, audit trace, negative-test validation, optimistic revision guard and Git PR required for any future accepted change. Review of a *proposal* does not approve normative expected values or execution permissions. The proposed artifact cannot call the existing canonical reviewer-decision importer.

For determinism, the offline test calculates an example SHA-256 **proposal preview** key from a canonicalized tuple of design-only digest claim + run + attempt + evidence digest. This hash only deduplicates identical **claims**. It cannot authenticate the original evidence. Same tuple + same evidence ⇒ NO_CHANGE; same run/attempt but differing digest ⇒ **explicit identity conflict**, not overwrite.

## 4. Deterministic failure rules and synthetic acceptance matrix

The following rules are **design behavior for human review**, not a production gameplay evaluator; precedence matters:

1. **Conflicting same run/attempt identity and differing evidence digest** ⇒ BLOCKED, refuse until reconciled. Keep both immutable snapshots. Do not decide which is true.
2. **Exact replay of same identity/digest/revision** ⇒ NO_CHANGE. Return existing proposal reference if available; no second proposal and no new success.
3. **Stale source or capture revision** ⇒ BLOCKED, require fresh evidence. Never silently reinterpret using a new source revision.
4. **Conflicting source/deployment revisions or opposing observations** ⇒ BLOCKED, refuse/triage. Do not average values or select newest automatically.
5. **Unauthenticated required source/identity** ⇒ BLOCKED for attribution-dependent checks; request independently approved crosswalk or attestation.
6. **Cancelled/interrupted/running or incomplete observation**, even with some matched values ⇒ UNKNOWN; propose cleanup/coverage instrumentation only. Cleanup remains UNKNOWN until separately verified.
7. **Missing required independent server/client readback** ⇒ BLOCKED; propose a capability/prerequisite, not an expected gameplay result.
8. **Complete observed mismatch**, even with two synthetic observer statements ⇒ retain `reported_gameplay_verdict=FAIL` as a *claim*, but `authoritative_gameplay_verdict=UNKNOWN` with no approved/independently authenticated oracle. Suggest a negative regression for review; **never modify expected values simply to make a previous FAIL become PASS**.

| Synthetic case | Evidence display | Proposed disposition | Safe suggested change |
|---|---|---|---|
| `complete-observed-mismatch` | UNKNOWN; reported FAIL unapproved | DRAFT_UNTRUSTED | Negative-case hypothesis |
| `missing-server-readback` | BLOCKED | DRAFT_UNTRUSTED | Read-only readback prerequisite |
| `stale-capture` | BLOCKED | REQUIRE_FRESH_EVIDENCE | Fresh pinned capture |
| `conflicting-revisions` | BLOCKED | REFUSE_UNTIL_RECONCILED | Explicit revision resolution, no proposed edit |
| `exact-duplicate-attempt` | UNKNOWN | NO_CHANGE | Deduplicate only |
| `unauthenticated-source-identity` | BLOCKED | DRAFT_UNTRUSTED | Provenance/crosswalk review |
| `incomplete-cancelled-execution` | UNKNOWN | DRAFT_UNTRUSTED | Cancellation and cleanup observation |
| `conflicting-duplicate-attempt` | BLOCKED | REFUSE_UNTIL_RECONCILED | Conflict, never overwrite |

`test_fixtures/test_r8_evidence_summary_contract.py` runs stdlib `unittest` over the synthetic matrix, validates deterministic triage, exact replay versus conflicting digest, refuses fabricated authority, permission upgrades and canonical mutations. It intentionally **does not call Toolkit's existing importer, server, browser, MCP or client**.

## 5. Ownership and acceptance handoff

- **#1325 Agent C:** reconcile the provisional read tool name with existing MCP supervisor conventions and #1200 read-only catalog/preflight; reuse existing spec digest/revision and source citations, enforce pagination/scope/redaction. New design-only contract is not an executable implementation.
- **#1325 Agent B:** display separate observed facts / interpretation / approved oracles / missing and disputed evidence; preview typed before/after *untrusted* proposal without creating or autosaving a scenario. A user may decide to start a later operator-reviewed revision.
- **#1198:** determine an independently reviewed per-assertion oracle-provenance and confidence record (who/what approved, version, observation origin, auth scope). Do not infer authorization from a human's capture-review ACCEPT or from matching JSON hashes. Negative NPC/quest and MOG-09 examples require real separately approved observations later.
- **#1202:** negotiate immutable attempt/digest idempotency, conflicts and partial-to-terminal transitions with XIHeadless #105; legacy Toolkit v1 importer remains unchanged. Existing v1 accepted verdict values and stored data must not be rewritten to introduce UNKNOWN.
- **#1201 / #1255 / XIHeadless #105:** lifecycle state, cancellation acknowledgment, terminal evidence, cleanup, source/deployment revisions and any future runner require separate owner/protocol gates.
- **Agent A #1197:** independent PR review, exact-head CI and ownership overlap resolution. Do not fold this design into #1315/#1318, change the canonical importer, promote oracles or dispatch actions.

### Exit gates (future, not claimed complete)

Contract/protocol owners sign off typed schema + backward-compatibility; independently replayed duplicate/conflict/missing terminal cases; real authenticated source/decoder/deployment checks and approved oracle lineage; bounded output redaction; reviewed UI and API authorization; version-aware non-mutating import migration; approved local acceptance. Until those gates, **design only, no production MCP registration or autonomous scenario authoring**.

**Could not verify here:** real captures/original source bytes, installed decoder, DSP/client identities, supervised runs, actual importer migration, local B20 acceptance, execution cleanup or independently approved gameplay oracles. All fixture evidence is synthetic.
