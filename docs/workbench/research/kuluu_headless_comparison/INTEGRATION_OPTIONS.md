# Integration options

## Licensing and process boundary (applies to every option)
Kuluu is **GPL-3.0-or-later**. Copying or linking its code into the Toolkit or into XiHeadless-DSP would make the combined work GPL. Our own licensing for XiHeadless-DSP is itself an open item (upstream xiheadless licence not yet checked). Therefore:
- Do **not** copy Kuluu source, protocol tables or generated files into our trees.
- Interoperate only across a **process boundary** (MCP/JSON over stdio or socket), with Kuluu built and kept in a separate directory (`<local>/research\kuluu` today).
- Any patch to Kuluu (e.g. a DSP auth flavour) must stay in a fork that is itself GPL.
- Ideas (tool names, event kinds, goal persistence) are not copyrightable; reimplementing them independently is fine.

## Option A - stay independent
Keep XiHeadless-DSP; add features on our own.
- Pros: only option that works on DSP today; zero licence exposure; no new toolchain.
- Cons: no MCP, no typed event contract, no unit tests, thin decoders, wardrobes unknown, not in git; we carry all protocol upkeep.
- Effort: per-gap, small each.

## Option B - Kuluu as external backend
Run Kuluu's `kuluu-mcp` against the server.
- Blocked on DSP: auth (33 B vs 102 B/TLS), lobby, map key, packet layouts (see `DSP_COMPATIBILITY.md`). Would need a GPL fork with a DSP auth flavour plus an unknown number of decoder adaptations (large, open-ended; Kuluu's decoders are LSB-audited, not DSP).
- Viable **only for LSB/Horizon** servers, which we do not currently run.
- Cost of adoption: nightly Rust, 193k-LOC AI-written codebase, submodules, retail DAT install for nav.

## Option C - hybrid with a common automation contract (recommended)
Define a small, backend-neutral contract (commands: move/follow/engage/cast/use_item/chat/end_event/snapshot/disconnect; events: typed kinds incl. `zone_changed`, `low_hp`, `event_started`, `chat`; resources: scene, party, inventory, diagnostics) with **capability negotiation** (`capabilities://` list, e.g. `wardrobes`, `nav`, `events`). Backends:
1. XiHeadless-DSP exposes it (new thin MCP/JSON-RPC adapter over existing `Capabilities`), the sole DSP backend.
2. Kuluu is an optional second backend for LSB, reached via its existing MCP, adapter written by us (no Kuluu code reused).
3. Toolkit consumes the contract, plus feeds results into Feature Trace and the live-client feed.
- Pros: reversible, no licence mixing, uses Kuluu's design where good, no DSP regressions.
- Cons: extra adapter layer; Kuluu backend has no consumer until we run an LSB server.

## Classification of overlapping components
| Component | Class | Note |
|---|---|---|
| DSP auth/lobby/map handshake | **A Retain** | Only working implementation. |
| Blowfish/MD5 key rotation, DSP key16 quirk | **A Retain** | DSP-specific. |
| Stationary-jitter / spawn-pass workaround | **A Retain** | DSP-specific. |
| ScenarioBrain + `prep_*.py` DB staging + `expect` keys | **A Retain** | Server-state validation is our unique value. |
| Brain/role/party logic | **A Retain** | Not present in Kuluu. |
| Ashita bridge, capture, replay, Feature Trace | **E Keep separate** | Different layer. |
| MCP surface | **C Adapt** | Reimplement the idea (tool list, resources, `wait_for_event`) over our capabilities. |
| Typed event/command codec | **C Adapt** | Define a JSON schema; independent implementation. |
| Goal persistence (resume after reconnect) | **C Adapt** | Small addition to `BotHost` reconnect loop. |
| Packet decoders | **B Integrate (reference only)** | Use Kuluu layouts as a cross-check when adding opcodes; verify on DSP first. |
| Wardrobe/container decode | **B Integrate (reference only)** | Check DSP container set first. |
| Unit/layout tests | **C Adapt** | Add a test project with synthetic packet fixtures. |
| Navigation (DotRecast vs recast+DAT) | **E Keep separate** | Ours needs no retail install. |
| Any of ours | **D Retire** | None identified. |

## Recommendation
Option C, staged: first the contract + our adapter (benefit is immediate and independent of Kuluu), Kuluu backend later only if an LSB server enters scope.
