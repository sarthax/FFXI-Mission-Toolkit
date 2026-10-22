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
