# Full-host Feature Catalog smoke (local, opt-in)

**Purpose:** verify that the **real packaged** `workbench.app.host` imports, mounts all 11 curated operator routes, and returns the expected read-only HTTP responses for core operator pages. This is a distinct evidence layer after static source checks, 21 synthetic HTTP recovery contracts, and five rendered-ASGI tests.

## Why this is local-only

The Workbench host imports `xi_tinkerer`, an optional native Python wheel not installed on the Linux Workbench CI runner. Importing that host can also initialize SQLite schemas and runtime directories. The runner **never imports the host by default**; even with an opt-in flag, it refuses to run when a Git checkout marker is absent, any existing `ffxi_zone_database.db` or `workbench.db` is present, or known private local state is detected.

A passing preflight is **not** evidence of the full host running, and a PASS of these GET probes **does not** verify Ashita connectivity, DSP gameplay, live data, external Wiki scraping, browser JavaScript, or the startup lifespan/scheduler. The script never dispatches a POST.

## Safe Windows workflow for local Claude / an operator

1. Use an **isolated disposable Git worktree or clone**, NOT `<local>/mission_toolkit` or an existing working install. Confirm `git status` and that its root has no Toolkit database or private bridge state. Do not copy local databases, credentials, DATs, account files or capture archives into it.
2. Create a clean Python virtual environment and install the usual Toolkit requirements plus the legitimate, locally available compatible `xi_tinkerer` wheel. Do not check the wheel or Python environment into Git. This tool does **not** install that wheel and has no fallback stub.
3. From the disposable checkout root, run:
   
   ```powershell
   python test_fixtures/full_host_operator_smoke.py
   ```

   This outputs a single JSON object, `result: "NOT_RUN"`, with the detected prerequisites. Nothing is imported or modified.
4. Only if the prerequisites are satisfied, and the checkout is deliberately disposable, run:

   ```powershell
   python test_fixtures/full_host_operator_smoke.py --execute --ack-disposable-checkout > "$env:TEMP\toolkit-full-host-smoke.json"
   ```

   Host module import may create **new local SQLite/cache files in this disposable checkout**. No HTTP server socket is opened. The script requests only GET routes; the FastAPI application lifespan is not started.
5. Inspect the JSON report. `result: "PASS"` requires all 11 workflow route/method mounts and all eight HTTP probes to match both status and expected page marker. `"FAIL"` means the host import, a mount or a probe failed; the report names the failed check without including arbitrary exception messages. `"NOT_RUN"` indicates a missing precondition. Do **not** report a PASS when the result is `NOT_RUN`.
6. Save the report with the related Git commit SHA in local test evidence; provide a **redacted** summary on the relevant PR/issue or to the project owner. Keep original local worktrees, account configuration and captured evidence unchanged. Do not automatically promote Feature Catalog validation status based on one smoke run.

## Routes probed (all read-only)

- `GET /help`, `/roadmap`, `/feature-catalog`
- `GET /features/trace?q=synthetic-missing-graph` (expected degraded HTML) and `/features/trace/runtime.json?root=synthetic` (expected 404 with no graph in the disposable checkout)
- `GET /live-client/bridge/console` (local-only console, **not** connecting a client)
- `GET /captures/review?status=pending&kind=synthetic-unmatched` (empty queue)
- `GET /captures/search?module=events&message_id=non-numeric` (expected HTTP 422 before DB access)

The test additionally verifies correct GET/POST **route registration** for the 11 operator workflow bindings, but does not invoke POST, mutate review decisions, save settings or create Wiki jobs.

## Evidence matrix

| Stage | Automated in GitHub CI? | What a green result actually establishes |
|---|---|---|
| Static catalog/handler crosswalk | Yes | Curated handlers, controls and source markers still match |
| Isolated negative-path HTTP contracts | Yes | 21 curated failure conditions have associated synthetic HTTP tests |
| Native-free rendered ASGI/Jinja | Yes | Five synthetic page-rendering tests pass with production templates |
| Genuine full-host import and read-only GETs | **No**; local opt-in only | Actual packaged app mounts and serves the tested pages in a disposable checkout |
| Browser interaction with local corpus | No | Requires separate operator acceptance |
| Live Ashita / DSP gameplay | No | Requires explicit authorized gameplay/testing process |

The older `test_fixtures/test_mounted_sidebar_routes.py` still reports **NOT RUN** in native-wheel-free GitHub CI. It should not be conflated with the explicit full-host smoke evidence here.
