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

- The selected sandbox path must be absolute, nonsymlink and different from the default production Settings directory.
- The sandbox **own** `settings.json` must explicitly set `enabled=true`; missing, invalid or partial settings fail closed, without migrating or reading production `settings.json`.
- The effective token **values**, selected checkout, disposable character allowlist and supervisor database connection fields must **match the enabled sandbox settings**. A production process environment override (even a valid production token) is reported as **untrusted configuration**, not accepted execution authority. Never show token/allowlist/DB password in errors.
- Results, drafts, jobs DB and artifacts root must stay **within the sandbox data dir** (resolved path, rejecting symlink path and escape). Redirecting only the draft/results DB paths does not establish supervisor isolation.
- This single provenance condition is required in **preflight**, the operator-token authorization path and Setup UI readiness (Build & Run uses preflight). Missing sandbox supervisor setup stays unavailable/blocked even when the production shell has otherwise complete runner credentials.
- The label for ready prerequisite checks is explicitly advisory: **"Prerequisites detected — operator approval still required."** It does not claim an authorized execution.
- Existing `execution_enabled=false` and `launch_implemented=false` advisory fields remain unchanged. Independent operator launch confirmation, loopback, origin and bearer/character checks remain mandatory.

This is a **settings/provenance gate**, not an installed DSP/client/decoder attestation, cannot prove a process cannot access any external data outside the fixed execution flow, and is not a substitute for running each sandbox in a separate process with a deliberately scrubbed environment. Existing normal production configuration is intentionally unchanged.

## 3. Offline regression acceptance (all inputs synthetic)

`test_fixtures/test_sandbox_supervisor_isolation_1333.py` covers:

- Explicit isolated data dir with production-like supervisor `settings.json` elsewhere and inherited token/charid/checkout/DB variables. **Sandbox settings missing ⇒ BLOCKED**, UI not ready, selected checkout not inherited, operator token refused.
- Direct fixed MOG-09 `execute_mog09(...approved=True)` with inherited production-like shell env fails *before subprocess invocation*; mock subprocess asserts no launch/artifact creation. Not a live execution.
- Partial and malformed sandbox JSON settings refused without an HTTP 500.
- Complete synthetically enabled sandbox setup (tokens, allowlist, checkout, DB requirements in same isolated file) can reach `ready_for_operator_review=true` while `execution_enabled=false` and `launch_implemented=false`. Operator auth remains separately checked.
- Wrong supervisor/operator token, character allowlist, or DB password overrides ⇒ BLOCKED, even when a correct sandbox token was previously configured.
- Results/drafts/jobs/artifact paths escaping the isolated directory ⇒ BLOCKED.
- No explicit `MISSION_TOOLKIT_TEST_DATA_DIR`: existing normal environment precedence remains, with existing operator token checks and advisory `execution_enabled=false`.
- Explicit isolated path equaling production default Settings directory refused.

The focused CI workflow additionally reruns preexisting test execution settings, preflight/CLI and operator-jobs fixture suites. No real supervisor token, production allowlist, actual character ID, database or source capture is present in fixtures.

## 4. B20 isolation prerequisites — **operator checklist, NOT RUN**

Before the separately authorized local B20 capture viewer acceptance:

1. **Dedicated sandbox process**: choose a fresh absolute test data directory outside both Git/source and the production default `%LOCALAPPDATA%/MissionToolkit/test_execution`. Start Toolkit with `MISSION_TOOLKIT_TEST_DATA_DIR` set **before** any import of the feature-testing router, and record the isolated process/port.
2. **Scrub inherited secrets**: use a clean process environment without production `MISSION_TOOLKIT_SUPERVISOR_*` and `MISSION_TOOLKIT_TEST_OPERATOR_TOKEN`; do not copy production settings into the sandbox or echo tokens in acceptance notes. Redirect jobs, drafts, results and artifacts into the isolated tree.
3. **Negative readiness control**: with *no sandbox `settings.json`*, visit Setup and Build & Run and confirm sandbox isolation unavailable, no **"Ready to run"**, and token-only operator job/launch APIs fail. Repeat with malformed/partial configuration and intentionally wrong *synthetic* credentials. Do **not** click Launch.
4. **Positive configuration proof (only if needed for a separately authorized execution acceptance)**: create new isolated synthetic/disposable configuration and verify only safe prerequisite labels appear. A preflight-ready state **never** constitutes execution or gameplay authority; require separate owner approval, authorized runner character and monitored local testing.
5. **B20 paired viewer**: in the editor opt-in capture panel choose original reviewed JSON and matching noncanonical sidecar; test valid pair, mismatched capture/review decisions/digest, duplicate refs, forged oracle and identity approval, UNKNOWN/BLOCKED, canonical association UNASSIGNED, stale selection disposal across editor navigation. Verify no sidecar canonical import/save or execution path. Avoid real capture credentials.
6. **Record evidence separately**: log exact Toolkit commit and CI, sandbox configuration *paths only*, local browser version, operator-approved outcome and specific failed assertions. Do not interpret CI-only green as B20 complete, capture byte/decoder authenticity, independent source/client/DSP proof, or approved gameplay oracle.

## 5. #1329 / #1330 / #1327 evidence compatibility

Unchanged by this fix. #1329's `scenario_evidence_ref_v0_NONCANONICAL` remains a redacted pointer claim, preserving immutable distinct run/attempt IDs and conflicting digests. #1330's proposed Bearer-authenticated discovery wrapper remains limited to 10 redacted references and 64 KiB and must report unavailable evidence as UNKNOWN, never zero observations. #1327 provider descriptors cannot establish deployed readback permission, client agreement or normative oracle approval. No canonical importer promotion, auto scenario edits or run dispatch.

**Independent Agent A review and explicit owner authorization required before merge.** This GitHub-only security slice cannot establish local service/browser or gameplay acceptance.
