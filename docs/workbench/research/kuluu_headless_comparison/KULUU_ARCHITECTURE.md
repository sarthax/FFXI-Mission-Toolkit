# Kuluu architecture (source-level audit)

Source: `https://github.com/jondwillis/kuluu-ffxi`, shallow clone at `<local>/research\kuluu\kuluu-ffxi`, HEAD `a7752b3` (merge of PR #1025). Kept **outside** the Mission Toolkit tree. Submodules `vendor/server` (LandSandBoat) and `vendor/POLUtils` initialised for the build only.

**Licence: GPL-3.0-or-later** (`LICENSE`, `LEGAL.md`). The README states the code is largely AI-generated and "audited against upstream LSB source by review agents", with no warranty. Process-boundary implications are in `INTEGRATION_OPTIONS.md`.

## Size and layout
~193k lines of Rust across a Cargo workspace (nightly-2026-06-01 pinned in `rust-toolchain.toml`).

| Crate | Role |
|---|---|
| `ffxi-proto` | Packet framing, Blowfish/MD5/zlib/checksum, login + lobby tables, typed map packets, S2C decoders (`decode/`), entity stream. Build script pulls version tables from `vendor/server`. |
| `kuluu-session` | The session engine, no rendering: `auth_client` (JSON/TLS), `auth_binary` (Horizon), `pol_inhouse` (PlayOnline), `lobby_client`, `map_client`, `session/`, `state.rs` (4.4k lines, `AgentCommand`/`AgentEvent`), `reactor.rs` + `supervisor.rs` + `goal_store.rs`, `agent_codec/agent_io/agent_socket`, `event_dialog`, `delivery_box`, `auction`, `fishing`, `net_health`, `relay` |
| `kuluu-mcp` | `rmcp` MCP server wrapping a session; `attach.rs` to attach to a running GUI client |
| `kuluu` | Bevy GUI client + CLI (`play`, `play --headless`, `install ...`) |
| `kuluu-render`, `ffxi-dat`, `ffxi-actor`, `ffxi-audio`, `ffxi-event`, `ffxi-install`, `kuluu-nav`, `ffxi-nav-recast` | Rendering, DAT parsing, actor/animation, audio, event VM, retail-install management, navigation |
| `ffxi-agent/` | LLM harness assets: `CLAUDE.md`, `OPERATING.md`, playbooks, MCP config |

Separation of concerns is real: `kuluu-session` has no Bevy dependency (it depends on `kuluu-nav`/`ffxi-nav-recast` only), so the headless path needs no GPU.

## Lifecycle
auth (`AuthFlavor`: `json|lsb`, `binary|hxi|horizon`, `playonline|pol`) -> lobby (data 54230 / view 54001; 0x26 login carrying a version stamp, first 6 chars compared to the server's `login.CLIENT_VER`, `VER_LOCK` off/exact/at-least) -> character list/select -> map handoff -> map session (Blowfish, key rotation on zone change) -> `Stage` progression to InZone -> `Disconnected`. The **supervisor** wraps the session: exponential reconnect backoff (1s initial, 60s max, `supervisor.rs`), goals persisted by `goal_store.rs` so they resume after reconnect. The **reactor** ticks ~200 ms and owns goals: `Idle`, `Following{target,distance}`, `Engaged`, path-to, `bank_when_full`.

## MCP surface (`kuluu-mcp/src/main.rs`, 1685 lines)
Tools (from `#[tool]` attributes): `follow`, `engage`, `path_to`, `walk`*, `debug_heights`*, `screenshot`*, `cancel`, `bank_when_full`, `chat`, `tell`, `request_zone_change`, `end_event`, `snapshot`, `cast`, `weaponskill`, `job_ability`, `use_item`, `disconnect`, `raise_menu`, `tractor_menu`, `homepoint_menu`, `wait_for_event`, `read_resource`. (* GUI session only.) Resources: `scene://current` (prose summary), `party://members`, `diagnostics://session`, `goal://current`, `inventory://current`; `resources/subscribe` emits `notifications/resources/updated`. `wait_for_event` blocks on typed event kinds (e.g. `low_hp`) with ~1 tick latency. Error handling: typed `McpError`; server validates movement ("out-of-bounds steps are rejected").

## Raw headless
`cargo run -p kuluu --no-default-features -- play --headless` runs the same session without MCP (JSON `AgentCommand` in / `AgentEvent` out via `agent_codec.rs` over stdio or `agent_socket.rs`). Typed event/command enums live in `kuluu-session/src/state.rs`.

## Tests
Unit: 222 test fns in `session/tests.rs`, 89 in `reactor/tests.rs`, plus `ffxi-proto/tests`. Live (self-skip when `SERVER_HOST:54231` unreachable): `play_lifecycle`, `zone_change` (needs gmlevel>=1), `agent_session` (JSON-RPC conformance), `action_dispatch`, `disconnect_recovery`, `delivery_box_live`, event 503/531/568 tests. Every live test assumes **LandSandBoat** (`xidb` fixture, `Stage` order).

## Dependencies relevant to us
- Retail FFXI install is needed for geometry/nav/DAT features (`kuluu install ...`); a pure headless session that only does protocol should not need it, **but this was not tested**.
- Nightly Rust toolchain, `vendor/server` submodule at build time, Windows supported (README lists x86_64/ARM64 builds).

## Build/run record
See `POC_PLAN.md` "Commands executed" for the exact PASS/FAIL/BLOCKED/NOT RUN status.
