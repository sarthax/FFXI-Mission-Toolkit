# PoC plan and command log

## Commands executed (2026-10-18)
| # | Command | Result |
|---|---|---|
| 1 | `git clone --depth 1 https://github.com/jondwillis/kuluu-ffxi` into `<local>/research\kuluu` | PASS |
| 2 | `git submodule update --init --depth 1 vendor/server vendor/POLUtils` | PASS (first build failed without them: FAIL, then fixed) |
| 3 | `cargo build -p kuluu-mcp` (nightly pinned) | **PASS** - `Finished dev ... in 3m 35s`; `kuluu-mcp.exe` and `kuluu-mcp-repl.exe` produced |
| 4 | `kuluu-mcp.exe --help` | PASS (starts; exits `set either FFXI_CHAR_ID or FFXI_CHAR in .env`; no network attempted) |
| 5 | `cargo run -p kuluu --no-default-features -- play --headless` | **NOT RUN** - needs credentials and a reachable server; only target is our DSP server, which Kuluu cannot authenticate against (source-verified) |
| 6 | Kuluu live integration tests | **NOT RUN** - require an LSB stack on 54231 |
| 7 | Kuluu unit tests (`cargo test -p kuluu-session`) | **NOT RUN** (time; not needed for the decision) |
| 8 | Live connection of Kuluu to DSP | **BLOCKED** - no disposable DSP stack approved; auth mismatch expected to fail; no production character used |
| 9 | Source reads: `auth_binary.rs`, `auth_client.rs`, `kuluu-mcp/src/main.rs`; DSP `login_auth.cpp:82` | PASS |
| 10 | Our headless: 98/98 Survival Guide scenario earlier the same day | PASS (separate task, `sg_results.json`) |

No database, live client, Ashita install or service was touched by this audit. Toolkit working tree untouched (research is in worktree `mt_kuluu_research`).

## Proposed smallest reversible PoC (offline contract test, no server)
Goal: prove the Option C contract is implementable without Kuluu code.
1. Write `contract/automation_contract.schema.json` (commands, events, resources, capability list). Hand-authored; Kuluu's tool names are used only as design input.
2. Add a **mock backend** (Python, in the Toolkit test tree) that replays labeled **synthetic fixtures** (`fixtures/synthetic/*.jsonl`, each file stamped `"synthetic": true`) and serves the contract over stdio JSON-RPC.
3. Contract tests: schema validation, `wait_for_event` timeout/match, capability negotiation (backend lacking `wardrobes` returns `unsupported`), reconnect resume of a goal.
4. Exit criteria: tests pass offline; removal = delete the folder.
Nothing connects to DSP, nothing touches the DB.

## Follow-on (needs explicit approval)
- M2: thin JSON-RPC adapter in XiHeadless-DSP over `IPerception/IEvents/IZoning`, run against the existing disposable bot accounts (xitest*).
- M3 (optional, only if LSB appears): Kuluu MCP backend adapter.
