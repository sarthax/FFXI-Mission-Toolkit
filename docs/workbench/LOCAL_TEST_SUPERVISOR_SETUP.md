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
