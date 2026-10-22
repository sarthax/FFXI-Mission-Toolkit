# R8 spec-driven supervised execution — current-state interoperability decision

**Scope:** issue #1255; related #1200, #1201, #1202, #1198, #1197; upstream
`sarthax/xiheadless-dsp` #104, #105, #47, #49. **GITHUB-ONLY / OFFLINE.**
This note is **NOT** an approved execution/evidence protocol, a task-start
endpoint, a runner, a Toolkit importer migration, or authorization to operate
a test character. All fixtures are clearly synthetic.

## 1. Inspected baselines, owned interfaces and hard blockers

Toolkit `main@d7b7b26f9925643a82ecdeeece9f8ad24a1d1e2b`
and XIHeadless `main@e5e80350711d5d2ec814c893a17c63baf3ef98a9`
were inspected for this decision. Revalidate **both exact SHA references**
before implementing any live wire, because branches and local acceptance
change independently.

| Existing implementation | Verified supported behavior | Missing for R8 |
|---|---|---|
| `feature_testing/test_specifications.py` + canonical v2 `scenario_contract_v2.py` | Strict outer `schema_version=1`, optional metadata-only v2, explicit case/step *citation claims*, unapproved oracle provenance. Catalog has **MOG-09** (`runner=xiheadless_observation_v1`, `verified_runner`) and **INV-OBS-01** (`runner=unassigned`, `design_only`). | A reviewed, versioned mapping of BDD/assertions/observation requirements to the separate Headless scenario action and expectation grammar, including oracle trust |
| `feature_testing/execution_preflight.py` | Read-only environment checks; exact allowlist **MOG-09 only**; still `execution_enabled=false`, `launch_implemented=false`, even if `ready_for_operator_review` | Versioned zone/role/character/lease and deployment source preconditions for arbitrary cases, #1200 |
| `feature_testing/execution_cli.py` | Explicit **local-operator-only** fixed-script MOG-09 launcher; no shell passthrough; approved disposable character, loopback-only URL, fixed timeout, destination outside repo, validate v1 report before local import | NOT the XIHeadless `task_scenario_start` route; do not wrap into a remote/LLM runner |
| `feature_testing/assertion_engine.py`, `normalized_evidence.py` | Evaluation of supplied values; missing readback ⇒ BLOCKED. MOG-09 normalization derives observations from one runner-supplied assertion payload and explicitly marks it **not independently authenticated** | Source-specific independent client/server readbacks, freshness/completeness and oracle approval #1198 |
| `feature_testing/importer.py`, `results.py` | Trusted-local importer v1 expects `{schema_version:1,results:[...]}` and exact ten fields per row, 40-hex DSP/Headless/Toolkit SHA, UTC time and catalog case; append-only SQLite keyed by `(run_id, case_id, stage)` | No protocol negotiation, `attempt_id`, retry reconciliation, evidence digests or idempotent replay; stored verdicts **PASS/FAIL/BLOCKED/SKIPPED**, **not UNKNOWN**. Structurally populated `assertions/observations` on a PASS does **not** establish independent oracle authenticity. Owned by #1202 |
| XIHeadless `Mcp/ScenarioTaskTools.cs` (#47 issue still OPEN) | Implements `task_scenario_start` and `task_scenario_status` with existing lifecycle/progress and operation-level evidence, **wait_ms-only**; refuses nonempty `expect`, legacy and resource-bearing actions, and parallel running scenario tasks | No reviewed complete assertion evaluator, leased gameplay actions or local scenario acceptance. #47's old PR #80 closed **unmerged**; do not confuse current source presence with feature acceptance |
| XIHeadless `Mcp/McpResult.cs` | `accepted=true`, `completed` OMITTED means admitted; `outcome=accepted` is not task terminal state nor scenario PASS | Typed task-status/cancel/partial/cleanup cross-repo mapping #1201, upstream #105/#112 |
| XIHeadless `Brains/ScenarioEvidence.cs`, `docs/schemas/scenario-evidence.schema.json` (#44) | Explicit opt-in **operation evidence v2** nesting PascalCase v1 operation record. `before/after` are caller-supplied `sha256-json-v1` digests, not observed game-state truth; optional DSP/Headless SHA and URLs | It is **NOT** Toolkit importer report v1 or a completed assertion authority. Must negotiate provenance/manifest #105/#111 and importer #1202 |
| XIHeadless #105 / #49 | #105 `xi-test-execution/1.0.0-draft.1` exists as **UNAPPROVED issue-comment design and synthetic vectors**, not a runtime endpoint. #49's unified acceptance harness remains OPEN, requires local acceptance | No shared approved serialized submit/status/cancel/evidence/terminal run definition yet; **block live adapter** |

The **73** merged domain drafts are separate, stage-only `NOT_RUN`
authoring records. Their case IDs, captures, source references and
`source_associations` are never converted into executable capabilities.

## 2. Decision: deliberately no new execution wire/schema yet

Do not implement a Toolkit `task_scenario_start` client, import a Headless v2
envelope as Toolkit v1 report, silently assign XIHeadless operation IDs as
Toolkit `run_id`, or turn a positive `accepted` into a PASS.

The smallest **safe shipped slice** of this draft PR is a *pure offline
compatibility probe* over existing Toolkit functions and an annotated
ten-vector boundary matrix:
`test_fixtures/r8_execution_boundary_matrix_synthetic.json`
and `test_fixtures/test_r8_execution_boundary.py`.
**Neither file defines a wire protocol, transmits MCP, launches a process,
leases a character, writes SQLite, or changes any runner/importer/UI module.**

A mock calculation returning PASS when supplied MOG-09 values happen to
match **is not a verified supervised observation**, particularly because
Toolkit's MOG-09 normalization receives both alleged client/server values
from one imported runner report. The future R8 gate must require independent
readback proof and reviewed oracle provenance, not just the calculated value.

### Requested eventual pipeline (NOT IMPLEMENTED by this PR)

```text
Toolkit published reviewed (feature_id,case_id,version,digest)
   → #1200 read-only catalog binding + canonical preflight
     [fixed verified runner; explicit character/zone/role/permissions/revisions]
   → approved #105 versioned request/attempt ID mapping
   → #1201 local authorized Headless supervisor submit + poll + cancel
     [admitted ≠ running ≠ terminal, cleanup/lease separately verified]
   → #1255 supervised reviewed operation+assertion execution, after #47 local acceptance
     [client/server readbacks, step outcome, skipped/missing source recorded]
   → #1202 version-aware immutable evidence + atomic idempotent reconciliation
   → #1198 per-assertion independently reviewed normative oracle+provenance
   → supported PASS/FAIL/BLOCKED/UNKNOWN display and revision comparisons
```

The presentation may display **UNKNOWN** without importing it into existing
v1 `results.VERDICTS`; no silent rewrite to `SKIPPED` or `PASS`.
Importer schema changes require #105 consent and a separate #1202-owned
backwards-compatible adapter. Partial runs should remain separately
inspectable, immutable and not treated as finalized evidence.

## 3. Exact #105 decisions required from Headless and Toolkit owners

1. **Identity / revisions:** namespace `request_id`, Toolkit
   `feature_id,case_id`, canonical spec `schema_version`, definition
   digest/revision and exact source associations, Headless task
   `operation_id`, scenario `run_id`, per-action
   `operation_id`, `attempt`, authenticated DSP/Headless/Toolkit SHA.
   None are assumed to alias one another; retries preserve original lineage.
2. **Admission and terminal state:** explicit refused/accepted/running/
   completed/failed/cancelled/timed-out/interrupted mappings; cancel request
   acknowledgement **does not** prove terminated task, nav stop, cleanup or
   lease release.
3. **Preflight:** character lease, role, zone and setup, operation-class,
   disposable account and operator approval, complete authoritative readback,
   source/deployment drift and hash authenticity. Unsupported mutation or
   missing condition ⇒ BLOCKED, with no MCP submit.
4. **Evidence authority:** separate actual client/persisted-server timestamps,
   completeness/freshness, original artifact digests and provenance,
   measured observation, independently approved per-assertion oracle and
   runner assertion outcome. Opt-in `sha256-json-v1` cannot authenticate
   a physical client/DSP source file. Missing authoritative side ⇒ UNKNOWN
   at presentation / BLOCKED for evaluation, never PASS.
5. **Importer compatibility:** preserve v1 report loading and result history;
   establish conversion only from approved terminal evidence, validate
   attempt and unique operation refs/digest, reject conflicting same-ID
   evidence, define replay idempotency and partial→terminal behavior without
   overwrites or fabricated records.
6. **Resource scope:** bounded artifact size and redaction, allowlisted
   characters/zone, crash/timeout recovery, leases/cleanup, cancellation
   propagation, and minimum exact-head offline + local supervised acceptance
   evidence. No new server, GM or packet access granted by this design.

An earlier Headless #105 draft supplies possible identifiers and fixture
shape, but remains **UNAPPROVED**. Do not fork it into a Toolkit-named
`xi-test-execution` protocol or invent an alternate `schema_version`.

## 4. Ten offline synthetic acceptance expectations

These are *review vectors, not network messages*. Tests exercise the
existing Toolkit safety boundaries where callable; the remainder is a
documented HOLD for #105/#47/#1202.

| Vector | Expected R8 gate | Current offline fact |
|---|---|---|
| Supervised observation reported success | UNKNOWN pending independently observed run | Supplied MOG-09 mock values evaluate PASS but evidence authenticity=false |
| Missing preconditions | BLOCKED | MOG-09 preflight without configured local operator prerequisites refuses readiness |
| Missing authoritative readback | BLOCKED | No Safe/readback yields assertion BLOCKED |
| Cancellation | UNKNOWN pending terminal evidence | An MCP admission/cancel acknowledgement is not importer v1 report |
| Partial evidence | BLOCKED | Missing client/server bag observation blocks assertion evaluation |
| Conflicting attempt IDs | BLOCKED | v1 has no attempt/operation fields and rejects duplicate current report keys |
| Unsupported mutation | BLOCKED | INV-OBS-01 stays design_only; cannot assign generic verified runner |
| Stale source revision | BLOCKED | Canonical compatibility rejects contradictory supplied revision |
| Repeated evidence import | NOT IMPLEMENTED | v1 importer is insert-only, not idempotent across separate imports |
| Acceptance without completion | UNKNOWN | Accepted MCP result has no `completed=true` or gameplay oracle; cannot import as v1 report |

**Do not turn the example's `UNKNOWN` into a stored Toolkit v1 row**:
current v1 storage does not permit that verdict. The future #1202 and #1198
review must negotiate storage separately.

## 5. Backlog sequence and owner handoff

| Priority | Existing story | Minimal next step and release dependency |
|---|---|---|
| Gate 0 | XIHeadless #105 + #47 + #49 (+ #110/#111/#112) | Review and **approve** shared schema/fixture conformance, terminal task, lease+cancel behavior and local headless scenario acceptance. #47 wait-only is not spec-driven gameplay. **No runtime wiring yet.** |
| 1 | Toolkit #1200 | Expose read-only existing two-case catalog binding, exact feature/case/oracle and trusted spec version/digest; unsupported case/zone/character/permissions should BLOCKED/UNKNOWN, no submit |
| 2 | Toolkit #1198 | Specify normative vs candidate oracles, independent client/server readbacks, provenance/coverage and UNKNOWN/BLOCKED versus PASS; no implied authority |
| 3 | Toolkit #1201 | Mock reviewed submit/status/cancel adapter using approved #105 lifecycle; no local live action until #47 local cleanup/lease acceptance. Keep accepted ≠ completed |
| 4 | Toolkit #1255 | After 0–3 accepted, add only approved **read-only** MOG-09 vertical slice, preserving current explicit operator path. Never translate 73 staged drafts wholesale |
| 5 | Toolkit #1202 | Versioned atomic, idempotent import of *approved terminal* evidence with attempt IDs, digests and conflict/partial protection; parallel offline fixture work can start sooner after #105 sign-off |
| 6 | Toolkit #1197 | Controlled local end-to-end owner acceptance; source DSP/client/Headless/toolkit SHA & approval evidence, cleanup/lease/zone observed; only then consider wider case coverage |

**Cross-repo handoff to #105:** request one written coordinator decision
for identity fields, terminal/cancellation semantics, HEADLESS v2-to-Toolkit
import boundary, source hash authority, and replay policy. This PR's ten
vectors may be used in the eventual #110 offline conformance tests but
must not be imported as an approved protocol fixture.

### Not verified

No live DSP server/char lease/client/GM/packet capture, no headless MCP
action, no actual cross-repo serialized status/transport on Toolkit,
no independent source hashes, no deployment attestations, no real idempotent
import, no gameplay observation or accepted local browser outcome. Do not
close #1255 or #1197 based solely on these offline tests.


## 6. Cross-repository protocol decision for review — ADOPT/AMEND existing #105 draft

**Decision status: PROPOSED for named reviewers, not APPROVED.** Retain
`xi-test-execution/1.0.0-draft.1` from [Headless #105](https://github.com/sarthax/xiheadless-dsp/issues/105#issuecomment-6304992825).
Do not create a second Toolkit wire schema or equate its protocol version
with Toolkit catalog `schema_version:1`, Headless operation evidence
`schema_version:1/2`, or the proposed #111 manifest schema version.
Incompatible major versions, unsupported core enums and missing required
identity/provenance MUST fail closed; a namespaced optional extension requires
reviewed version-policy approval. Toolkit #1316 remains **offline** regardless
of decisions reached on #105.

### 6.1 Exact compatibility and responsibility table

| Concern | Reusable actual source / draft #105 mapping | Proposed review decision and owner | Current classification |
| --- | --- | --- | --- |
| Scenario identity/version | Toolkit `feature_id,case_id`, `schema_version:1`, canonical v2 source-attribution and v1 assertions. #105 `test_definition.{feature_id,case_id,stage,definition_revision,definition_digest,scenario_id,scenario_digest,oracle_ids[]}` | **Adopt distinct identities**, pins/digests; do not derive Headless action JSON from authored steps. Toolkit #1200 + Headless #105 | Existing catalog; cross-repo mapping BLOCKED |
| Character/zone/environment | Toolkit MOG-09 `execution_preflight` checks approved disposable char, local runner/DLL, token, results DB; #105 `prerequisites.environment_id,environment_profile_revision,required_roles[],capabilities[]` | Explicit operator/runtime verified zone, role, character lease, environment and capability truth; no fabricated IDs. #1200, #47, local owner | Synthetic/partial, requires local testing |
| Resource ownership/leases | Headless `BotTaskLifecycle` and existing char pool; #105 role `slot_id` and per-role cleanup | Keep lease owner/token local, expose sanitized anonymous slot and independently observed release; no auto-reuse if incomplete. #47/#112 + pool owners | Implementation/acceptance BLOCKED |
| Operator permission | Toolkit `execute_mog09(approved=True)` restricted local path; #105 `prerequisites.authorization_ref`, `requested_by=local_authorized_controller` | Operator grant and task capability/operation-class must be checked independently before admission; a doc reference is not authorization itself. #1200/#1201 | Current MOG-09 only |
| Supported steps | Headless `ScenarioTaskTools.Start` validates Headless array, supports **only `wait_ms`** with empty expectations | Restrict R8 future adapter to independently accepted operation subset; no automatic conversion from Toolkit narrative/step `intent` or all staged domains. #47 then #1255 | wait-only code; reviewed general execution BLOCKED |
| Assertion/oracle | Toolkit v1 assertion IDs and evaluator + v2 candidate `oracles[].source_refs`; #105 proposed `result_bundle.assertions[]` per-oracle revision, observation kind, origin, authority | Oracle **approval and independent client/server readback** separate from operation evidence. Candidate is not normative. #1198, #47 | Existing synthetic evaluation; gameplay authority UNKNOWN |
| Request/admission/task | Headless `McpResult.{ok,accepted,completed?,outcome,operation_id}`; proposed `request_id` is RPC, `run_id` campaign, `execution_id` per admitted attempt, `operation_id` lifecycle task; v1 action `OperationId` scoped separately | Approve B1 identifiers, no aliases; refusal has no invented operation. Lifecycle completion never PASS. #105, #1201 | Existing MCP semantics; cross-repo mapping BLOCKED |
| Cancel/timeout/restart | Headless `running/completed/failed/cancelled/abandoned` + journal interruptions; proposed cancel-response `request_accepted`, `observed_state` | ACK not terminal; timeout/journal absent ⇒ UNKNOWN/INTERRUPTED and no unsafe automatic re-dispatch, cleanup separate. #112/#47, #1201 | Lifecycle code exists; local acceptance BLOCKED |
| Operation evidence | #44 opt-in `ScenarioEvidenceV2` nesting PascalCase v1 operation + optional caller-supplied `sha256-json-v1` before/after | Link immutable per-operation evidence by ID and reviewed digest; never project envelope directly to Toolkit importer. #44/#105/#1202 | Code exists; transport bridge BLOCKED |
| Artifact manifest | #111 proposed local `manifest_schema_version:1`, sanitized relative paths, `sha256-bytes-v1`, complete/partial/quarantined states | **Select a separate local sanitized manifest reference**, no duplicate artifact model. Missing/expired/quarantined artifact ⇒ no verified PASS. #111/#55, security | UNAPPROVED / NOT IMPLEMENTED |
| Attempt/replay/partial | #105 `idempotency_key`, `execution_id`, positive `attempt`; Headless same-session lifecycle keys; Toolkit v1 SQLite unique key `(run_id,case_id,stage)` | Approve durable digest-bound admission/replay policy: identical key+digest safe replay only if durable proof; changed digest conflict, unknown after restart no auto-repeat. #112 + #1202 | NOT IMPLEMENTED cross-repo |
| Client/server revisions | Toolkit v1 importer requires 40-hex DSP/Headless/Toolkit commits; #44 accepts null or 40/64-hex; source/deployment claims vs actual bytes distinct | Carry actual pins and optional binary hash/dirty status with unknown reasons. **Never fabricate 40-hex SHA to satisfy v1 import**. #1198/#1202 + local DSP owner | Partial fields; deployed provenance UNKNOWN |
| Final verdict | Toolkit evaluator `PASS/FAIL/BLOCKED`; importer storage `PASS/FAIL/BLOCKED/SKIPPED`, *not* UNKNOWN; #105 proposed four assertion verdicts and independently separate lifecycle task state | Preserve UNKNOWN first-class in a **version-aware holding/report path** owned by #1202; compatible terminal audited rows may later project to v1. No `UNKNOWN→SKIPPED` and no PASS from admission/`Verified`/hash. #1198/#1202 | v1 current; R8 projection BLOCKED |

The table maps existing fields and **proposed #105 field names**, not an
approved JSON schema. Production caller identity, authorization, real source
hashes and lease tokens remain in trusted local machinery; never include raw
account identifiers, credentials or mutable server commands in transport.

### 6.2 Disposition of the ten R8 acceptance vectors

| Fixture (in noncanonical matrix) | Coverage today | Missing acceptance gate |
| --- | --- | --- |
| `supervised_observation_reported_pass` | Existing MOG-09 normalized evaluator computes PASS on **supplied synthetic** values; evidence_auth=false | #47 accepted execution, independent readbacks, #1198 normative oracle, real DSP/client |
| `missing_preconditions` | Existing MOG-09 `preflight` fails without configuration | #1200 versioned/role/zone/lease checks; local grant validation |
| `missing_authoritative_readback` | Current Python evaluator blocks absent rows | Independent DSP and client source, completeness/freshness, local test |
| `cancellation` | Synthetic MCP accepted/acknowledged envelope rejected by importer v1 | #47/#112 terminal state, stop/navigation/lease cleanup, local cancellation |
| `partial_evidence` | Missing MOG-09 fields produce BLOCKED | #111 manifest and #1202 durable partial/terminal reconciliation |
| `conflicting_attempt_ids` | Current v1 rejects duplicate report identity or extra attempt fields | #105 identity/attempt semantics + #1202 digest-aware conflict |
| `unsupported_mutation` | INV-OBS-01 cannot be elevated to verified runner | #47 safety/movement resource controls, explicit permission acceptance; 73 staged cases remain NOT_RUN |
| `stale_source_revision` | Canonical v2 compatibility detects contradictory claims | Independent deployed source/client/build attestation, local run |
| `repeated_evidence_import` | Same JSON parses but second v1 SQLite insert is not idempotent | #1202 version-aware immutable evidence ledger and replay rule |
| `command_acceptance_only` | `accepted=true` without `completed` is rejected as importer report; empty observations BLOCKED | #105/#47 actual task terminal assertion evidence, #1198 verified authority |

**Do not claim these are ten Headless conformance executions**: they are
ten offline Toolkit boundary vectors and existing test regressions. The
`supervised_observation_reported_pass` case is deliberately marked
`UNKNOWN` as an R8 *authority claim* even though the existing evaluator
reports PASS for the provided values. This distinction prevents false
promotion of an unauthenticated runner assertion.

### 6.3 Named decisions to record on XIHeadless #105 (not presumed)

Request **approve/amend/reject** for the *existing* eight #105 review gates:
B1 version and distinct IDs; B2 UNKNOWN holding vs strict v1 projection;
B3 oracle and independent observation authority; B4 lifecycle/cancel ACK;
B5 per-role cleanup/lease verification; B6 durable request-digest
idempotency and retry; B7 #111 out-of-band sanitized manifest digest/reference
vs operation `sha256-json-v1`; B8 operator preflight and actual revisions.
Record coordinator, Headless #47/#112/#111/#55 owners and Toolkit
#1197/#1200/#1201/#1198/#1202 owners as applicable; the draft only becomes
approved when those named reviewers document their decisions.

**Smallest next code assignment after protocol sign-off:**
Headless #110 + mirrored Toolkit test reviewer should validate the **same
versioned, immutable synthetic fixture bytes** using existing test runners,
with file digest and both exact-head CI URLs, no runtime calls. In parallel
the next *Toolkit-owned* feature slice is #1200: read-only feature/case,
spec fingerprint, review/oracle coverage, required roles/zone and
`SUPPORTED/UNKNOWN/BLOCKED` preflight preview; keep
`execution_enabled=false` and no submit button. Only after #47/#49 local
acceptance should #1201 and then #1255 wire supervised scenario execution;
#1202 owns the versioned idempotent import adapter.
