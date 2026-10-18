# Executive summary: our headless client vs Kuluu

1. **How complete is ours?** A working DSP regression bot (XiHeadless-DSP, C#, outside the Toolkit repo): login, zoning, events, GM-assisted flows, party combat, multi-bot and 98/98 Survival Guide validation are demonstrated. Weak: decoder breadth, no unit tests, no MCP/typed contract, wardrobes unknown, not under git, undocumented in the Toolkit.
2. **How does Kuluu compare?** Much larger (~193k LOC Rust), typed, tested (300+ unit tests, live suites), with an MCP server, goals, supervisor and persistence. But it targets LandSandBoat/Horizon, is largely AI-written, and is GPL-3.0-or-later.
3. **Genuinely missing from ours:** MCP/agent interface, typed event contract with `wait_for_event`, goal persistence across reconnect, unit/layout tests, broader packet decoders, wardrobe handling (unknown).
4. **Should remain:** all DSP protocol work (33-byte auth, lobby order, key16 rules, source-IP binding, jitter fix), ScenarioBrain + DB staging, brains/roles, Toolkit capture/replay/Feature Trace.
5. **Supplement or replace?** Replace nothing. Kuluu can *supplement* as a design reference and, later, an optional LSB-only backend. It cannot connect to DSP without a GPL fork adding a DSP auth flavour and decoder adaptation (source-verified: DSP requires exactly 33 bytes; Kuluu sends 102 bytes or JSON/TLS).
6. **Complexity/risk:** Direct Kuluu-on-DSP: high and open-ended (auth, lobby, map key, packet layouts, containers). Contract + our adapter: low-medium. Licence risk: GPL contamination if code is copied; mitigated by process boundary and no code reuse.
7. **First milestone:** offline automation-contract schema plus mock backend and contract tests (see `POC_PLAN.md`), then an adapter in XiHeadless-DSP.

Audit evidence: `kuluu-mcp` builds on Windows (PASS); live connection to DSP not run (blocked, no disposable stack). See the other documents in this folder.
