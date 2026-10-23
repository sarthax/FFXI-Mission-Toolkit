# #1333 — Validation sandbox supervisor-isolation security investigation and B20 preconditions

**Status:** P0 safety isolation fix proposed for independent review; GitHub-only/offline. No local server, live DSP, Headless execution, character login, packet capture or database mutation was performed.

## 1. Root cause and severity

Operator acceptance on `main@fa5765da` reported that a sandbox with draft/results DB paths redirected still displayed **"Ready to run"**, while shared production supervisor settings existed in `%LOCALAPPDATA%`. The report established **readiness presentation without a real execution attempt**. It did NOT establish a confirmed unauthorized launch.

Verified source path before this change:

1. `test_execution_settings.data_dir()`: `MISSION_TOOLKIT_TEST_DATA_DIR` selects the settings JSON directory, else `%LOCALAPPDATA%/MissionToolkit/test_execution` (or `HOME` fallback). Explicit isolated data-dir disables legacy file migration.
2. `test_execution_settings.load()` reads the selected `settings.json`, returning disabled/default settings if absent. This already prevented *file-path* fallback to production JSON.
3. `apply_to_environ()` publishes enabled file settings **only for keys absent from `os.environ`**; inherited shell variables (including production `MISSION_TOOLKIT_SUPERVISOR_TOKEN`, `MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS`, headless root, operator token, DB variables) intentionally win in normal operation.
4. `execution_preflight.preflight()` formerly read those effective process variables *directly*, independent of the selected settings directory and Setup `enabled` flag. It returned `ready_for_operator_review=true` if runner, DLL, results DB, allowlist, supervisor token all appeared present. The Build & Run Jinja view used that flag to show **"Ready to run"**.
5. `test_builder.build_plan()` requires preflight + approved requested character; `execution_jobs.enqueue()` uses the builder plan. `execute_mog09()` also runs a new preflight immediately before launching its fixed-script subprocess. `authorize_operator()` used constant-time comparison against the inherited operator token; `router._operator_auth()` additionally requires loopback and same-origin (or explicit valid token). The actual launch route requires `approval=true`.

**Assessment:** definite **configuration-provenance leakage and incorrect readiness presentation**; a **potential execution authorization-boundary risk** under a stronger condition where the same process also inherited usable production operator token, disposable allowlist, runner files and explicit launch approval. The local acceptance report did not exercise those prerequisites, so it is **not evidence of unauthorized execution**. Treat as **P0 precautionary release blocker for isolation assurance**, not a demonstrated breach.

## 2. Deliberately small fail-closed fix

No `MISSION_TOOLKIT_TEST_DATA_DIR`: preserve ordinary shell environment precedence, normal settings discovery, existing supervisor Bearer authentication, approved disposable character checks and fixed MOG-09 runner contract.

**When `MISSION_TOOLKIT_TEST_DATA_DIR` is explicitly configured:**

- An **explicitly present but empty/whitespace** `MISSION_TOOLKIT_TEST_DATA_DIR` is INVALID and fails closed; absence of the variable alone selects normal production discovery. The selected path must be absolute, have no symlinked ancestor, and must not be within the default production Settings directory or repository checkout.
- The sandbox **own** `settings.json` must explicitly set `enabled=true`; missing, invalid or partial settings fail closed, without migrating or reading production `settings.json`.
- The effective token **values**, selected checkout, disposable character allowlist and supervisor database connection fields must **match the enabled sandbox settings**. A production process environment override (even a valid production token) is reported as **untrusted configuration**, not accepted execution authority. Never show token/allowlist/DB password in errors.
- Results, drafts, jobs DB and artifacts root must stay **within the sandbox data dir** (resolved path, rejecting symlink path and escape). A predictable pre-existing `settings.tmp` symlink is never used for sandbox writes: settings use a randomly named private temporary file followed by an atomic replace. Invalid sandbox root or linked settings are rejected **before read, write or artifact creation**. Redirecting only the draft/results DB paths does not establish supervisor isolation.
- **Two scopes, no authority transfer:** sandbox operator/draft access requires its own enabled Setup file, matching long operator token and sandbox-local draft/job storage (never production token); it does **not** require configured gameplay supervisor/DB. Separately, execution preflight requires the full sandbox-owned supervisor/runner/character/DB credentials and all four storage paths; a draft-only sandbox stays execution-BLOCKED. Build & Run uses the latter. The direct fixed MOG-09 launch reruns that preflight before spawning any subprocess. Neither draft UI authorization nor passing preflight grants actual execution.
- The label for ready prerequisite checks is explicitly advisory: **"Prerequisites detected — operator approval still required."** The Launch control is disabled while prerequisites are blocked; the server independently enforces preflight even if clients bypass the UI. It does not claim an authorized execution.
- Existing `execution_enabled=false` and `launch_implemented=false` advisory fields remain unchanged. Independent operator launch confirmation, loopback, origin and bearer/character checks remain mandatory.

This is a **settings/provenance gate**, not an installed DSP/client/decoder attestation, cannot prove a process cannot access any external data outside the fixed execution flow, and is not a substitute for running each sandbox in a separate process with a deliberately scrubbed environment. Existing normal production configuration is intentionally unchanged.

## 3. Offline regression acceptance (all inputs synthetic)

`test_fixtures/test_sandbox_supervisor_isolation_1333.py` covers:

- Explicit isolated data dir with production-like supervisor `settings.json` elsewhere and inherited token/charid/checkout/DB variables. **Sandbox settings missing ⇒ BLOCKED**, UI not ready, selected checkout not inherited, operator token refused.
- Direct fixed MOG-09 `execute_mog09(...approved=True)` with inherited production-like shell env fails *before subprocess invocation*; mock subprocess asserts no launch/artifact creation. Not a live execution.
- Partial and malformed sandbox JSON settings refused without an HTTP 500.
- Draft-only sandbox setup with its own operator token can access draft UI without supervisor execution permissions; complete synthetically enabled sandbox setup (tokens, allowlist, checkout, DB requirements in same isolated file) can reach `ready_for_operator_review=true` while `execution_enabled=false` and `launch_implemented=false`. Operator auth remains separately checked.
- Wrong supervisor/operator token, character allowlist, or DB password overrides ⇒ BLOCKED, even when a correct sandbox token was previously configured.
- Results/drafts/jobs/artifact paths escaping the isolated directory ⇒ BLOCKED.
- No explicit `MISSION_TOOLKIT_TEST_DATA_DIR`: existing normal environment precedence remains, with existing operator token checks and advisory `execution_enabled=false`.
- Explicit isolated path equaling or nested under production default Settings directory, inside the repository checkout, or with a symlink ancestor refused. An explicitly empty or whitespace-only test-data variable must never fall back to production settings or create artifacts. Linked `settings.json` and predictable `settings.tmp` symlink cannot overwrite production bytes.

The focused CI workflow additionally reruns preexisting test execution settings, preflight/CLI and operator-jobs fixture suites. No real supervisor token, production allowlist, actual character ID, database or source capture is present in fixtures.

## 4. B20 isolation prerequisites — **owner-local browser testing, NOT RUN**

**B20 is capture-review/sidecar UI acceptance only, NOT a supervised gameplay or
headless execution campaign. Local operator must NOT supply any usable launch
credentials or click a Launch/Submit Run control.** The only permissible source
content is disposable, synthetic JSON fixture data that contains no character
account, production DB, actual packet, or connected game identity.

### Preparation — independent clean process, safe fixtures

1. Start a **fresh Toolkit process** with an explicitly set nonempty absolute
   `MISSION_TOOLKIT_TEST_DATA_DIR` in a new temporary directory outside
   the source tree and production `%LOCALAPPDATA%/MissionToolkit/test_execution`.
   No path symlink or ancestor symlink; no linked `settings.json` or
   `settings.tmp`. Set the variable **before importing** the Feature Testing
   router. Record only the Toolkit Git SHA, isolated directory pathname and
   distinct loopback port; keep any optional token secret.
2. Launch with an **environment allowlist**, not a copy of the production process
   environment. Explicitly clear `MISSION_TOOLKIT_SUPERVISOR_*`,
   `MISSION_TOOLKIT_TEST_OPERATOR_TOKEN`,
   `MISSION_TOOLKIT_TEST_HEADLESS_ROOT`, and DB credentials/addresses. Never
   use real account/character allowlists, production operator or supervisor
   tokens, working Headless checkout/DLL, or live server connection strings.
   If the unrelated Toolbox supervisor service is online, it must not be
   selected or invoked by this sandbox.
3. Use **synthetic disposable source-review JSON** only. Maintain the original
   reviewed-export fixture and intentionally noncanonical readiness sidecar as
   separately selected operator files, each with synthetic capture IDs/source
   references. Do not mount any production DB, real source captures or secrets.
   If a draft-only UI operator token is needed for local navigation, generate
   a distinct synthetic sandbox-only token; it **must not** configure supervisor
   execution readiness, approval characters, runner binary or readback DB.

### Negative gate — required before any B20 reviewer clicks

4. With the sandbox supervisor `settings.json` **absent**, confirm Setup,
   Build & Run and `/preflight/moghancement/MOG-09` show
   `sandbox_isolation.ok=false`,
   `ready_for_operator_review=false`, `execution_enabled=false`, and the
   Launch button disabled. Repeat with malformed/partial synthetic setup,
   explicitly empty `MISSION_TOOLKIT_TEST_DATA_DIR` in a *separate*
   disposable process, synthetic wrong token/allowlist, and linked settings.
   A test must not return saved production identities, credentials or
   character IDs. **Never submit** the launch endpoint, even as an attempted
   negative: only inspect declarative controls and, when specifically permitted,
   purely mocked local tests.
5. Establish a **clean initial state**: record zero new queued/running jobs and
   zero new result rows (using isolated synthetic storage only), no live
   headless process/worker attached to the sandbox, no outbound client or
   database connection, and no generated game-capture artifact. Verify this
   without querying the production DB or live supervisor.

### B20 browser matrix — inspection only

6. Load matching original reviewed export plus optional noncanonical sidecar;
   confirm read-only annotations, original-vs-selected reviewer choices, both
   independently recomputed JSON projection digests, `UNKNOWN/BLOCKED`,
   canonical association `UNASSIGNED`, and explicit unauthenticated
   physical-source/parser/decoder status. Negative variants must reject
   mismatched capture IDs, duplicate/foreign refs, altered reviews, forged
   identity/oracle approvals, and mismatched digest/projection scopes.
7. Navigate New/Open/Fork/Clone, Advanced/Guided and away from the panel
   while selected files are pending; verify generation cancellation, stale
   readback disposal, safe text-only rendering, no stale selected source
   carry-over and no implicit import/save/approval. Capture each expected
   versus observed UI result with exact commit, browser and fixture IDs.
   These checks cannot prove physical client/decoder authenticity or any
   gameplay oracle and are **not** runner tests.

### Postcondition and cleanup — observable, not assumed

8. Close the sandbox browser/server, confirm the dedicated process and any
   synthetic child processes have terminated, and ensure zero pending or
   newly queued/running test jobs. Confirm synthetic results/import records
   remain unchanged and no fresh runner artifacts were generated.
   Stop only the sandbox process: **never kill shared production services**.
9. Remove **only the recorded disposable sandbox directory** after verifying
   its canonical resolved path is still within the designated scratch root.
   Do not delete any production settings, shared DB, external symlink target
   or source checkout. If an unexpected file, process, job or external write is
   found, **stop and mark B20 BLOCKED** rather than claiming cleanup.
10. Record a signed-off operator acceptance matrix (pass/fail/blocked/not-run,
    screenshots or redacted logs, negative-test results, sandbox teardown
    evidence, exact Toolkit SHA and browser version) in #1313/#1333.
    GitHub CI establishes **synthetic code regression behavior only**: it
    cannot prove browser interaction, process isolation at runtime, no actual
    external writes, source bytes, deployed client/DSP identity or successful
    cleanup. **Do not mark B20 complete until the authorized local
    operator verifies and records every applicable precondition.**

## 5. #1329 / #1330 / #1327 evidence compatibility

Unchanged by this fix. #1329's `scenario_evidence_ref_v0_NONCANONICAL` remains a redacted pointer claim, preserving immutable distinct run/attempt IDs and conflicting digests. #1330's proposed Bearer-authenticated discovery wrapper remains limited to 10 redacted references and 64 KiB and must report unavailable evidence as UNKNOWN, never zero observations. #1327 provider descriptors cannot establish deployed readback permission, client agreement or normative oracle approval. No canonical importer promotion, auto scenario edits or run dispatch.

**Independent Agent A review and explicit owner authorization required before merge.** This GitHub-only security slice cannot establish local service/browser or gameplay acceptance.
