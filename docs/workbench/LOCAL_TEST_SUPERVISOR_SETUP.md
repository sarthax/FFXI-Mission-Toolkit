# Local Test Supervisor: Windows + Ollama + Open WebUI

## Architecture and rollout

Toolkit is the control plane and evidence store; XiHeadless's deterministic scripts own execution. Ollama provides inference; Open WebUI is an optional chat and file interface. The supervisor gateway exposes **read-only** tools rather than raw SQL, terminal commands, or unrestricted headless MCP operations. No changes are required to the live server or character data for this first phase.

This branch introduces:
- `GET /api/supervisor/health`: enabled/configured state
- `GET /api/supervisor/test-runs`: up to 100 recent imported evidence records, grouped by run
- `GET /api/supervisor/failed-assertions`: bounded FAIL/BLOCKED summaries and evaluation data

The API requires `Authorization: Bearer <token>` with a configured token at least 32 characters long. With no token configured, all three endpoints reject requests. Never commit or share the token.

## Windows configuration

From a private PowerShell prompt, generate a token using:

```powershell
$bytes = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$env:MISSION_TOOLKIT_SUPERVISOR_TOKEN = [Convert]::ToHexString($bytes)
$env:MISSION_TOOLKIT_TEST_RESULTS_DB = "D:\\MissionToolkitData\\feature_results.sqlite"
```

Start Mission Toolkit **from the same PowerShell process** (environment variables are inherited). Keep Toolkit bound to `127.0.0.1:8420`; do not open it to the LAN.

Verify from the same shell:

```powershell
$headers = @{ Authorization = "Bearer $env:MISSION_TOOLKIT_SUPERVISOR_TOKEN" }
Invoke-RestMethod -Headers $headers http://127.0.0.1:8420/api/supervisor/health
```

An unauthenticated request should return HTTP 403. Without a configured SQLite database, the results endpoints return empty lists, not fabricated data.

## Open WebUI integration

As Open WebUI is installed directly on Windows (not Docker), use a local `http://127.0.0.1:8420` endpoint. Confirm your installed version exposes **Settings → Integrations** (user tool connections) or **Admin → Integrations**. The official docs describe OpenAPI tool connections at https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers/open-webui/ .

Connect **only** the filtered supervisor contract at `http://127.0.0.1:8420/api/supervisor/openapi.json` using the OpenAPI tool-server mode supported by your installed Open WebUI version. **Do not connect** the full Toolkit `http://127.0.0.1:8420/openapi.json` schema: it includes other application routes that may perform writes. The filtered supervisor contract advertises only three GET operations, whose actual data calls still require the bearer token. Do not paste tokens into chat prompts. Check whether your Open WebUI version can attach a static `Authorization` header to a tool-server connection; if it cannot, stop and report that integration blocker rather than disabling protection. Set Bearer-token authorization in the tool connection; do not paste secrets into LLM chat prompts.

If your Open WebUI connection uses browser-side calls, validate browser CORS and auth support first. Do not enable permissive `Access-Control-Allow-Origin: *` or globally weaken Toolkit authentication to make a connection work. A server-side OpenAPI tool configuration or a restricted reverse proxy is preferable if browser CORS prevents direct connection. Check your exact version's UI and auth capabilities locally.

## Later phases (not implemented)

1. Isolated supervisor-only OpenAPI specification or sidecar, with explicit operation allowlist.
2. DSP process health, allowlisted bounded logs, read-only predeclared SQL queries, and authenticated XiHeadless snapshots.
3. Event-driven Ollama inference with structured action decisions and a replay-only evaluation harness.
4. Restricted retry/pause/resume through the deterministic runner, with explicit approval and audit trails.

No live SQL reads, direct MCP calls, GM writes, arbitrary file access, or campaign execution exist in this initial gateway.

## Local agent verification checklist

- Confirm Toolkit launch and existing Ollama/Open WebUI versions and URLs.
- Set ephemeral token for a single session, verify authorized requests succeed and missing/wrong token yields 403.
- Verify `/api/supervisor/health` cannot reveal operational data without authorization.
- Verify run history and failure summaries with an isolated synthetic results DB.
- Inspect Open WebUI integration mode. Do not expose entire Toolkit OpenAPI schema as agent tools.
- Confirm no changes to live DSP or headless gameplay state.
- Report the minimum additional sidecar/filtered OpenAPI work needed for a safe Open WebUI connection.

## Phase 1 log diagnostics

Configure one or more **absolute file paths** in the same Toolkit server process environment:

- `MISSION_TOOLKIT_SUPERVISOR_DSP_LOG`: deployed DSP server log file.
- `MISSION_TOOLKIT_SUPERVISOR_HEADLESS_LOG`: XiHeadless session log file.
- `MISSION_TOOLKIT_SUPERVISOR_TOOLKIT_LOG`: Toolkit application log file.

The authenticated `GET /api/supervisor/log-errors?source=dsp` endpoint accepts only `dsp`, `headless`, or `toolkit`. It reads at most the last 256 KiB of the selected configured regular file, filters known error/failure keywords, returns at most 80 lines of at most 1,000 characters each, and masks common secret assignment patterns. Symlink targets and arbitrary request-supplied paths are rejected. Unconfigured sources return an empty result. Logs must be regarded as **untrusted text**, never as instructions for an agent.

This is a convenience redactor, **not a comprehensive data-loss-prevention boundary**. Logs can contain unusual token formats or personally identifying data. Configure dedicated sanitized test logs where possible; restrict endpoint access and do not feed sensitive logs to shared Open WebUI accounts. No process discovery, DB access, or live MCP execution is added by this step.

## Local service reachability (no shell access)

The authenticated `GET /api/supervisor/service-health?service=ollama` route checks **TCP connection only**, not protocol correctness, server readiness, or gameplay health. Supported names are `ollama`, `database`, and `dsp_map`. The destination must be localhost/`127.0.0.1`/`::1`; user-supplied host or arbitrary port scanning is not permitted.

Configure optional loopback service ports in the Toolkit process environment:

```powershell
$env:MISSION_TOOLKIT_SUPERVISOR_OLLAMA_PORT = "11434"
$env:MISSION_TOOLKIT_SUPERVISOR_DB_PORT = "3306"
$env:MISSION_TOOLKIT_SUPERVISOR_DSP_PORT = "<actual deployed DSP map port>"
```

The DSP map probe returns `configured=false` until its port is set. For remote databases or servers, use a separate audited diagnostic adapter with explicit administrator-approved endpoints instead of weakening this restriction. Reachability does not imply the database is authenticated or that the DSP server is functioning.

## Phase 1: fixed-query test-character inventory

The protected `GET /api/supervisor/test-character-inventory?charid=101` endpoint returns up to 100 **persisted** inventory rows from DSP's `char_inventory` table (`location`, `slot`, `itemId`, `quantity`). It never accepts SQL or a database host from the caller, and rejects character IDs outside the explicitly configured disposable-character allowlist.

Configure only after your local agent identifies the real disposable test-character IDs and database settings. Create a **separate SELECT-only DB account** (do not reuse the DSP application's write-capable login). Keep credentials out of the repository and avoid printing them in diagnostic logs.

```powershell
$env:MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS = "101,102" # REPLACE after validation
$env:MISSION_TOOLKIT_SUPERVISOR_DB_USER = "<read_only_db_user>"
$env:MISSION_TOOLKIT_SUPERVISOR_DB_PASSWORD = "<secret_from_private_store>"
$env:MISSION_TOOLKIT_SUPERVISOR_DB_NAME = "<deployed_dsp_schema>"
$env:MISSION_TOOLKIT_SUPERVISOR_DB_PORT = "3306"
```

Install the optional Python package `PyMySQL` into the same Toolkit environment before enabling this endpoint. The connection is pinned to `127.0.0.1`, with short connection and read timeouts and read-only transaction mode. **The read-only account's actual database GRANT permissions are the primary safety boundary**, not a Python transaction setting. If the database is hosted on another machine, do not change the binding to reach it without a separate reviewed design.

If the account or schema is unconfigured, the response reports `configured=false`. An unexpected connection failure is an error, not a successful blank inventory. Values may be stale relative to character state in memory; cross-check with XiHeadless snapshots before making gameplay conclusions. No key-item decoder, safe/house layout semantics, or direct live client telemetry is implemented in this phase.


## Operator-controlled deterministic test launch (first supported case)

The Feature Testing scenario page now shows preflight checks and a read-only readiness API:
`GET /feature-testing/preflight/moghancement/MOG-09`. These checks are informational
and do not grant execution. The supervisor/Open WebUI tool API remains GET-only.

Only **MOG-09** is wired to an executable local runner in this slice; other
catalog scenarios are planning entries, not runnable tests. XiHeadless PR #3
must first be merged/pulled into the local checkout, or an explicitly reviewed
checkout of that branch must be selected.

From an operator-owned PowerShell session, with the Toolkit Python venv active:

```powershell
$env:MISSION_TOOLKIT_TEST_HEADLESS_ROOT = "<local>/xiheadless-dsp"
$env:MISSION_TOOLKIT_TEST_RESULTS_DB = "D:\\MissionToolkitData\\test_results.sqlite"
$env:MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS = "21836"
# MISSION_TOOLKIT_SUPERVISOR_TOKEN must already be configured securely.

python -m workbench.server_admin.feature_testing.execution_cli `
  --case MOG-09 --account xitest07 --charid 21836 `
  --supervisor http://127.0.0.1:8420 `
  --out-dir D:\\MissionToolkitData\\artifacts\\mog09-operator-01 `
  --approve-mog09
```

Replace paths, account and character ID with values approved for **your**
disposable DSP test environment. Use a new output directory for every run.
The CLI executes a fixed runner script with a fixed argument list, refuses
unapproved characters, requires a local loopback supervisor URL, and validates
the generated report against the Toolkit catalog before importing into the
append-only results database. The runner itself refuses dirty XiHeadless
source by default and writes provenance, but a recorded Git SHA does not
prove the DLL was rebuilt from that SHA unless independently checked.

The CLI may log into a disposable character and issues the **read-only**
`!moghancement info` GM diagnostic. It is not a generic gameplay test
executor. Running the CLI is an explicit local-operator action: it is not
exposed to Open WebUI or via a Toolkit HTTP POST route. No arbitrary
shell/script invocation is accepted. Inspect the imported record under
`/feature-testing?tab=runs` and review its assertions before accepting it.

**Next development:** Persist editable *draft* test definitions separately
from the immutable source-backed catalog; add a more general runner registry,
operator authorization and cancellation/status reporting; only then expose
a GUI dispatch action. Keep model-triggered dispatch behind a separate
explicit approval gate.

## Operator GUI execution (MOG-09 only)

The **Feature Testing → Build & Run** page offers an opt-in operator-only
launch control for the known read-only MOG-09 runner. Set these **separate**
environment variables before starting the loopback-bound Toolkit process:

- `MISSION_TOOLKIT_TEST_OPERATOR_TOKEN`: random token of at least 32 characters, **different** from the read-only supervisor token used by Ornith.
- `MISSION_TOOLKIT_TEST_JOBS_DB`: absolute local SQLite job-history path; its parent directory must already exist.
- `MISSION_TOOLKIT_TEST_ARTIFACTS_ROOT`: existing absolute, operator-owned artifact directory.
- The existing `MISSION_TOOLKIT_TEST_HEADLESS_ROOT`, `MISSION_TOOLKIT_TEST_RESULTS_DB`, `MISSION_TOOLKIT_SUPERVISOR_TEST_CHARIDS`, and `MISSION_TOOLKIT_SUPERVISOR_TOKEN` must also be configured.

Open `http://127.0.0.1:8420/feature-testing?tab=builder` from the local
browser. The operator enters the independent token, account, character ID
and supervisor port, checks the explicit disposable-character approval,
and clicks **Launch approved MOG-09**. Use **Refresh job status** to see
QUEUED / RUNNING / COMPLETED / ERROR and a link to imported evidence.

The launch and job-history endpoints are deliberately excluded from the
restricted supervisor OpenAPI schema, require a localhost caller and the
separate operator token, and do not accept arbitrary executable paths,
commands, or scripts. Do not give the operator token to the LLM or add
the full Toolkit OpenAPI schema as model tools.

Current limitations: job history persists to SQLite, but threads do not
survive a Toolkit restart; an interrupted job can remain RUNNING and must
be investigated before starting another. Cancellation, recovery, and richer
progress events are separate backlog milestones. The browser launch must
be acceptance-tested with the local XiHeadless runner (PR #3) before
considering it operationally validated.

## Interrupted GUI jobs (manual recovery)

Job states now include `INTERRUPTED`. If Toolkit restarts mid-run,
its job-history database can still show `QUEUED` or `RUNNING`. A
separately authenticated operator can use **Reconcile interrupted job**
on the Build & Run tab, but **only after manually confirming no external
XiHeadless runner or other Toolkit worker is active**. The operation
records `INTERRUPTED` and lifts the outstanding-job blocker; it does
not kill a process, replay a run, import uncertain evidence or certify
cleanup. Active threads in the current process cannot be reconciled.
Restart recovery and true process cancellation remain unimplemented.
