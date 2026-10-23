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

The detailed read model in this document is **Agent D-owned**, not a second MCP gateway. Agent C #1330 has proposed the existing bearer-protected `supervisor_scenario_evidence_summary` as a bounded **index/wrapper**; its `toolkit-r8-scenario-discovery/1` envelope is the gateway presentation surface (not approved or deployed). The illustrative downstream `scenario_evidence_summary` notation below describes the D-owned projector concept, **not** another proposed tool registration or network endpoint. Bounded, read-only and scope-limited:

```text
scenario_evidence_summary(
  feature_id, case_id, spec_revision_or_digest,
  run_id? = null, attempt_id? = null,
  include_observation_summaries = true,
  page_size = 10, cursor? = null
) -> scenario_evidence_summary_v0_DESIGN_ONLY_NONCANONICAL
```

**Cross-agent reconciled gateway limits (still PROPOSED, not enforced by this design-only PR):** obey Agent C #1330: maximum **10 redacted evidence records per discovery response**, **65,536 UTF-8 bytes total**, maximum **500 characters per human-facing summary** and a **25-item hard maximum for general scenario discovery**. The detailed D-owned projector must be bounded independently, and any larger raw/long-form observation record stays outside the MCP response, behind future separately approved access. Stable ordering by immutable attempt timestamp plus attempt ID; pagination cursor bound to query filters, dataset revision and authorization scope; fail closed on stale cursor. The wrapper must return `availability=NOT_CONFIGURED`, `record_count=null`, `recent=[]`, `status=UNKNOWN` rather than interpreting an unavailable evidence store as zero historical runs. Redact account/character secrets, local full paths, tokens, packet payloads, private source content and arbitrary client bytes. Return explicit truncation and `next_cursor` rather than silently suppressing evidence. No external URLs fetched, arbitrary repository reads, shell, SQL, packet, GM, runtime control or dynamic plugin dispatch.

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

`test_fixtures/r8_evidence_summary_vectors_synthetic.json` supplies ten complete **synthetic** records under `scenario_evidence_summary_v0_DESIGN_ONLY_NONCANONICAL`. Its `scenario`, `attempt`, `lifecycle`, `provenance`, `evidence`, and `triage` members are the design shape, **not an approved wire format**. All source names/digests/IDs are conspicuously synthetic; their `source_bytes_authenticated`, `decoder_authenticated` and `source_identity_verified` fields are false. All `approved_oracles` arrays are empty. The tests explicitly refuse untrusted promotion.

An actual future version must add strict schema typing, checked timestamps and domains, redaction, source/ref indexes, immutable storage lookup and per-assertion reviewer authority. Do not introduce those by loosening the existing v1 importer or #1313 viewer contract.

## 2A. Shared evidence-reference handoff: one pointer, four consumers

**Proposed reference identity** (not an approved shared wire schema): `scenario_evidence_ref_v0_NONCANONICAL`. The fixture adds **one compact pointer claim per attempt** under `evidence_reference`; it does **not** embed another result record. Every `observed_fact` still points to its *original* capture/source entry, and no capture step becomes a canonical CASE/STEP association. Consumers display the shared `ref_id` as a **string**, never treat the string as independent authentication, and never use it as an executable locator or user-supplied file path.

```json
{
  "contract": "scenario_evidence_ref_v0_NONCANONICAL",
  "ref_id": "evidence:synthetic:missing-server-readback",
  "scenario": {
    "feature_id": "SYNTHETIC_FEATURE",
    "case_id": "SYNTHETIC_CASE",
    "base_revision": "synthetic-revision-1",
    "base_digest_claim": "synthetic:spec-sha256-r1"
  },
  "attempt": {
    "run_id": "synthetic-run-missing-server-readback",
    "attempt_id": "synthetic-attempt-missing-server-readback",
    "operation_ids": ["synthetic-operation-missing-server-readback"]
  },
  "artifact": {
    "kind": "SYNTHETIC_FIXTURE",
    "pointer_claim": "synthetic://capture/missing-server-readback",
    "digest_claim": "synthetic:evidence-missing-server-readback",
    "capture_id": "synthetic-capture-missing-server-readback",
    "timestamp_basis": "UNKNOWN",
    "source_revision_claim": "synthetic:dsp-rev-a"
  },
  "authority": {
    "physical_capture_authenticated": false,
    "decoder_authenticated": false,
    "independent_verification": "NOT_ESTABLISHED",
    "oracle_approval": "NOT_ESTABLISHED",
    "canonical_association": "UNASSIGNED",
    "importer_authority": false
  }
}
```

**Ownership/shape translation, without duplicating records:**

| Consumer | Authorized interpretation of the shared pointer | Must not do |
|---|---|---|
| **D / #1329** | Own the detailed summary, original capture/provenance claims, attempts, conflicts, observed facts and human-review diagnostics. `evidence_reference` points to one immutable retained record *claim*; identical replay reuses the same ID; conflicting attempt/digest has a separate ID, linked by the same attempt key. | Authenticate the physical source by SHA claim; assert an approved oracle; publish canonical associations |
| **C / #1330** | Return a **maximum 10-item sanitized index**, under existing proposed `supervisor_scenario_evidence_summary` + `toolkit-r8-scenario-discovery/1` response. A future reviewed extension may present only `ref_id`, limited attempt/completeness/conflict state and a short redacted excerpt. Missing store ⇒ UNKNOWN. | Copy the full D schema into `data.recent[]`, create a competing evidence schema, claim PASS authority, read arbitrary source paths or grant a capability |
| **E / #1327** | Relate `missing_observations[].capability` (scenario observation *requirement*) to separately reviewed provider descriptors by an explicit versioned mapping. Agent E's provisional `toolkit.persisted.*` IDs remain descriptors, **not registered/readback available** claims. | Substitute a persisted DB observation for client proof, infer effective SELECT grants from source code or convert `PR_ONLY` / `NOT_IMPLEMENTED` into `AVAILABLE` |
| **B / #1328** | Accept `evidence_reference.ref_id` **as a string** in `failure_evidence_refs[]` (proposed future mapping). Independent B preview contract stays `scenario_revision_proposal_preview_v1_NONCANONICAL`, requires operator-selected canonical baseline and digest/revision declarations, and permits text-only `/name`, `/purpose`, `/rationale` 1–12 changes. | Inline D evidence objects into B's strict preview, automatically transform D suggestions into edits, propose `steps`/`assertions`/`runner`/`contract_v2` mutations, save/apply/grant/execute |

**Critical version boundary:** D's conceptual `scenario_revision_proposal_v0_UNTRUSTED_DESIGN` **is not the same JSON contract** as B's `scenario_revision_proposal_preview_v1_NONCANONICAL`. No automatic adapter is approved. A future separately reviewed, human-invoked mapping may produce a new B *text-only* artifact using `failure_evidence_refs=[ref_id]`, pinned `base.revision` and `spec_digest_claim`, exact before-text, allowed paths and all fields demanded by B. Preserve D's original raw references privately; a sanitized `ref_id` is not permission to dereference arbitrary local files. Source and oracle review are separate.

**Namespace and idempotency:** `ref_id` is an opaque stable ID issued only by the future trusted evidence index (all IDs here begin `evidence:synthetic:`). Never derive a real ID from a caller-controlled path alone. `run_id`, `attempt_id`, `operation_ids[]` and scenario revision are separate fields; the digest is a claimed value, not a signature. Exact retry of identical immutable tuple references the *same* `ref_id`. Same run/attempt with conflicting digests creates an explicit pair of competing reference IDs and BLOCKED reconciliation, never an overwrite or PASS. #1202 owns persistent identity, atomic replay and partial→terminal ordering after XIHeadless #105 agreement; no import is implemented here.

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
| `running-partial-observation` | UNKNOWN, nonterminal task | DRAFT_UNTRUSTED | Additional terminal/observer prerequisite only |
| `terminal-with-incomplete-readback` | UNKNOWN, terminal task but incomplete observation | DRAFT_UNTRUSTED | Readback/completeness requirement, cleanup remains UNKNOWN |

`test_fixtures/test_r8_evidence_summary_contract.py` runs stdlib `unittest` over the synthetic matrix, validates deterministic triage, exact replay versus conflicting digest, refuses fabricated authority, permission upgrades and canonical mutations. It intentionally **does not call Toolkit's existing importer, server, browser, MCP or client**.

### Failure-to-regression recommendation categories (advisory only)

The fixture's `proposal_recommendation_kinds[]` is a bounded, deterministic *review queue*, not a JSON Patch, canonical scenario or an executable plan. An AI can propose questions and evidence requirements, not authorize a run:

- **`MINIMAL_REPRODUCER`** — preserve exact feature/case revision, attempt and the smallest observed step sequence; propose a *description* of a supervised future reproduction, with expected oracle still UNAPPROVED. For a reported mismatch this may be paired with **`NEGATIVE_BOUNDARY_CASE`**, e.g. compare unchanged/zero versus changed values only after a reviewed independent expectation. No direct creation of `steps[]` or assertions.
- **`MISSING_OBSERVER_REQUIREMENT`** — specify the missing client/server or persisted readback requirement and why it matters, but do not claim that Agent E's provider is deployed, granted or available. A missing observer is BLOCKED, not FAIL.
- **`SOURCE_ASSOCIATION_REVIEW`** — request a new independently pinned source crosswalk for stale capture/deployment revisions. Never rewrite existing canonical Contract v2 associations or infer capture step IDs are canonical.
- **`SOURCE_IDENTITY_ATTESTATION_REQUEST`** — request source-byte/decoder and identity corroboration without claiming success from indexed digests or an operator ACCEPT of observation text.
- **`CLEANUP_CANCELLATION_DIAGNOSTIC`** — request independently observed terminal, lease-release and cleanup state; cancellation acknowledgement and partial observation remain UNKNOWN. No supervised run can be requested by this record.

Exact replay ⇒ `NO_CHANGE` and **no new proposal**. Conflicting revisions/attempt digests ⇒ `REFUSE_UNTIL_RECONCILED`, **no patch**; a human can investigate the conflict externally. Suggestions never alter approved expected values to manufacture PASS, nor do they claim that a reported FAIL has been authenticated. This design intentionally creates **no automatic conversion** into Agent B's strict preview, canonical importer or feature-testing runner.

## 5. Ownership and acceptance handoff

- **#1325 Agent C:** reconcile the provisional read tool name with existing MCP supervisor conventions and #1200 read-only catalog/preflight; reuse existing spec digest/revision and source citations, enforce pagination/scope/redaction. New design-only contract is not an executable implementation.
- **#1325 Agent B:** display separate observed facts / interpretation / approved oracles / missing and disputed evidence; preview typed before/after *untrusted* proposal without creating or autosaving a scenario. A user may decide to start a later operator-reviewed revision.
- **#1198:** determine an independently reviewed per-assertion oracle-provenance and confidence record (who/what approved, version, observation origin, auth scope). Do not infer authorization from a human's capture-review ACCEPT or from matching JSON hashes. Negative NPC/quest and MOG-09 examples require real separately approved observations later.
- **#1202:** negotiate immutable attempt/digest idempotency, conflicts and partial-to-terminal transitions with XIHeadless #105; legacy Toolkit v1 importer remains unchanged. Existing v1 accepted verdict values and stored data must not be rewritten to introduce UNKNOWN.
- **#1201 / #1255 / XIHeadless #105:** lifecycle state, cancellation acknowledgment, terminal evidence, cleanup, source/deployment revisions and any future runner require separate owner/protocol gates.
- **Agent A #1197:** independent PR review, exact-head CI and ownership overlap resolution. Do not fold this design into #1315/#1318, change the canonical importer, promote oracles or dispatch actions.

### Exit gates (future, not claimed complete)

Contract/protocol owners sign off typed schema + backward-compatibility; independently replayed duplicate/conflict/missing terminal cases; real authenticated source/decoder/deployment checks and approved oracle lineage; bounded output redaction; reviewed UI and API authorization; version-aware non-mutating import migration; approved local acceptance. Until those gates, **design only, no production MCP registration or autonomous scenario authoring**.

**Latest release dependency:** Both #1315 (paired verifier) and #1318 (editor attachment) are now merged into main following protected review; this design does not modify either implementation, claim physical-source attestation, or call the local B20 operator acceptance complete. This design does not modify either implementation or claim local B20 acceptance.

**Could not verify here:** real captures/original source bytes, installed decoder, DSP/client identities, supervised runs, actual importer migration, local B20 acceptance, execution cleanup or independently approved gameplay oracles. All fixture evidence is synthetic.
