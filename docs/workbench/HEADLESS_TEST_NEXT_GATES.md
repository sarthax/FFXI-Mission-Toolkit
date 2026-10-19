# Headless MCP Feature Testing — next execution and investigation gates

Status: implementation plan, **not** evidence of executable support. Baseline: Toolkit main at `9c72bc64` (2026-10-19). The source-backed MOG-09 runner and operator GUI already exist; the guided draft editor/presets are separate **design-only** functionality.

## Reconciliation of actual boundaries

| Concern | Existing implementation | Remaining gap |
|---|---|---|
| Deterministic launch | `execution_cli.execute_mog09` with fixed XiHeadless `tools/observation_runner.py` | One hard-coded scenario; no reviewed extensible dispatch |
| Runner readiness | `execution_preflight.SUPPORTED` only lists `moghancement/MOG-09` | Does not prove DLL provenance, runner semantics, server revision or live prerequisites |
| Specifications | `test_specifications.validate_spec` permits published executable identity only for MOG-09 | Drafts cannot be promoted into an executable catalog |
| Evidence | Imported immutable records; GUI run inspector; declarative reevaluation | Source/client/server evidence completeness and authenticity remain case-specific |
| Operator authority | Separate operator token and approved disposable character; GUI and CLI | No general scoped authorization/cancel contract; **no LLM launch** |
| Recovery | Durable checkpoints; explicit interrupted reconciliation | No reliable cross-process cancel, process ownership or verified cleanup |
| Investigation | Supervisor read-only results, failed assertions, bounded logs | Missing original assertion drill-down + trace-ranked source evidence |

## Slice A — one-run investigation dossier (read-only; preferred next PR)

Create an authenticated `GET /api/supervisor/run-evidence?run_id=...` with strict run ID syntax/length, exact immutable run lookup, and bounded output. Normalize both `evidence.assertions` (observation-runner output) and `evidence.evaluation` (legacy evaluator records) **without** coercing missing fields into PASS. Include: recorded verdict, each assertion ID, observed/expected values (bounded and redacted), assertion verdict/reason, provenance (DSP/Toolkit/headless SHA, DLL hash when present), timestamps, and references to separately held artifacts (never arbitrary path reads).

Add a lightweight Toolkit run-detail inspector link into this normalized view without changing imported evidence, running a test, or exposing private supervisor auth in browser HTML. First implement service layer and test it; only after verifying the exact import schema add the supervisor GET route to the filtered OpenAPI allowlist.

**Acceptance fixtures:** imported modern `assertions` only, legacy `evaluation` only, both shapes, missing/invalid arrays, oversized values, unrecognized run, deliberately contradictory recorded PASS with failed evaluation, token absent/wrong, and successful auth. A model must be able to locate a *real* failing assertion without mistaking imported records for trusted independent proof.

## Slice B — model-facing source-aware investigation

Read-only source lookup indexed/pinned to explicit approved DSP, XiHeadless and Toolkit revisions. Query must be scoped to selected failed assertion and known relevant behavior, and return exact path/line/revision excerpts with uncertainty markers. Plug ranked Feature Trace/Behavior Trace results into the dossier, not an exhaustive graph dump. Logs and Lua comments are data, never instructions. No arbitrary filesystem paths, SQL, shell, or MCP calls.

**Acceptance:** one synthetic failure yields a bounded hypothesis with supporting *and refuting* evidence plus discriminating local acceptance steps. Cite revision and separate observed behavior from source inference.

## Slice C — governed runner registry (not a generic script executor)

Replace the single-entry `SUPPORTED` mapping only after a second independently reviewed deterministic XiHeadless script and its evidence contract exist. Registry entries should be **source-controlled code**, not operator-editable JSON, and must bind exact (feature, case, version), script path under approved checkout, fixed allowed arguments, side-effect class, character scope, privilege requirements, preflight adapter, report schema, cleanup strategy, and timeouts. A draft cannot select an executable runner by editing `runner` or `execution_status`.

Promotion gates: source review → deterministic synthetic regression → fresh local isolated run → independent server/client postconditions → cleanup/interrupt acceptance → operator approval → registry PR. Keep imported results append-only. For `INV-OBS-01`, first resolve location numbering/truncation (Safe 2/wardrobes) and key-item decoding; don't claim evidence completeness from only inventory rows.

## Slice D — execution lifecycle and approvals

Maintain two separate identities: read-only LLM supervisor and local operator. Never expose launch in the supervisor OpenAPI surface. Operator launch requires signed-in local operator context, explicit character/environment selection, reviewed immutable test ID/version, clear side-effect summary, one-time approval bound to the exact execution manifest, and durable job audit. Failed/timeout/abandoned tests do not become PASS. Reconciliation must not signal cleanup completed unless verified. Implement process-group isolation and cancellation only after the runner contract accounts for bot logout and DSP state restoration.

## Local acceptance still required

- Pull a reviewed XiHeadless commit containing the observation runner; confirm actual built DLL corresponds to source revision.
- Use disposable approved DSP character and isolated artifacts DB; verify MOG-09 read-only `!moghancement info` provenance and its original six assertions.
- Confirm the operator GUI launch, job updates, report validation/import, failed-assertion drilldown and manual interrupted-job path on Windows.
- Do not grant model-triggered gameplay actions merely because local MOG-09 runs have passed.

## Cross-references

- `docs/workbench/ROADMAP_CURRENT.md` — 2026-10-19 AI supervisor investigation backlog.
- `docs/workbench/LOCAL_TEST_SUPERVISOR_SETUP.md` — existing launch/auth/recovery procedures.
- `src/workbench/server_admin/feature_testing/execution_cli.py`
- `src/workbench/server_admin/feature_testing/execution_preflight.py`
- `src/workbench/server_admin/feature_testing/test_specifications.py`
