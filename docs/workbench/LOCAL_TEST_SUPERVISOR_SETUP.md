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
