# Wardrobe 5–8: research exit and DSP transition readiness — 2026-10-21

**Scope:** no DSP code, branch, issue, SQL, server or client runtime changes are authorized by this document. The owner requires a separate personal go-ahead before beginning the high-risk DSP feature. This is a prepared *handoff*, not a claim that the feature works.

## Readiness decisions

| Decision | State | Grounded reason |
|---|---|---|
| Reusable 2019 client research is sufficient for a DSP feature planning/implementation kickoff | **GO — when the owner explicitly directs the move** | 2019 original SHA verified and independent read-only command/mode, layout, packet, UI lifecycle observations; risk areas and unknowns listed in the technical report |
| Begin a single coherent Wardrobe feature branch in DSP | **DEFER — no DSP changes in Toolkit closeout** | User requested one long-lived feature branch containing client, server, SQL, protocol, UI and tests; explicit approval to begin DSP work is still required |
| Claim Toolkit PR #1312 fully integrated to `main` | **NO — PR is draft and divergent** | Requires normal no-force branch reconciliation, current-head CI, review/merge decision in Toolkit; not necessary to invent a server patch |
| Enable container IDs 13–16 on the unmodified 2019 DLL | **NO-GO** | Missing bounds, storage, UI and protocol support |
| Install a real Wardrobe expansion DLL or apply server migrations | **NO-GO** | No reviewed safe runtime allocation, protocol contract, migration, rollback or acceptance evidence |

## Independent original-client confirmation

Authoritative original file: 2,870,352 bytes, SHA-256 `514653a260c51eaec25d88510e51a86fb2a4abd9867f53d5f45a9ccf840f060f`. Read-only POL1 decompression: 3,264,206 bytes, SHA-256 `af2126c057d86559bfad2e164f7f7fd0a26bbc89ab29ea9cbde5cea807c7d2b8`.

Independently checked against the owner-provided original outside GitHub CI, *not only against synthetic fixtures*: four existing Wardrobe names, IDs, handler registrations, corresponding mode-object constructors, `+0x54` vtable slots and constant getters (modes **8, 10, 11, 12**); `/bank2` ID 115 and mode **9**; original `2..12` UI selector bytes; **13 of 13** selected UI object update calls and **13 of 13** cleanup/free/clear blocks; 2019 packet 0x1C capacity destination anchors, container-13 sentinel and 81-slot cursor bound. All these checked local predicates matched the exact original source. The independent script deliberately prints metadata and checks only; it does not contain or write retail executable bytes to GitHub.

Important limitations: independently checked disassembly bytes do not prove every function executes or is safe to modify; not every allocation, alias, parser caller or UI path is mapped. Owner-reported Stage 1–3 boot/network/menu smoke tests do **not** validate Wardrobe 5–8 behavior. Confirmation of installed original DLL restoration after Stage 3 is not recorded.

## Toolkit CI acceptance at prior research head

At research head `71184c0e992e2aecaf606e730fc277834cefc82c`, `2019 Wardrobe Static Audit (Offline)` workflow `39694706290` passed **49 focused synthetic tests on Windows and Ubuntu**; `Src Layout Regression` run `39694706425` and broad `Workbench Regression` run `39694706415` both succeeded. These workflow results do not substitute for a new-head CI run if this handoff document changes.

## Owner's required DSP feature-release model

The DSP repository already maintains long-lived `feature/*` branches and `slice/<feature>-vN` history recorded in `docs/slices/STATUS.json`. Its worker guidelines also distinguish remote static CI from Claude/local-server/MariaDB/client/XIHeadless tests. When transition is authorized:

1. **One feature branch of record:** propose `feature/wardrobe5-8-v1` and a corresponding feature/slice record. Server code, SQL up/down migration, compatibility packet handling, client patch definitions/rollback, UI, scenario tests and documentation must all resolve into **that feature**. Never split a purportedly complete Wardrobe feature across unrelated PRs merged independently to `main`.
2. **Parallel agents are subordinate to the feature:** worker issue/task branches may be used for isolated review and file ownership, but the authorized local integrator assembles their approved changes into the feature-of-record branch. Remote agents must not push directly to protected `feature/**` or `main`. Reuse established `ready`, `needs-local-test`, and `tested-ok` pipeline for evidence; none of those labels is personal authorization to merge.
3. **Version, don't discard:** retain the feature branch and immutable `slice/wardrobe5-8-v1` release tag; use `feature/wardrobe5-8-v2` or the next version tag when the owner decides to release a coherent V2. Do not force-push, auto-delete or rewrite history.
4. **Local acceptance and owner approval:** local agents compile and test on the actual development map server and MariaDB, verify client-build identity and recoverable SQL migrations, execute XiHeadless and 2019 client tests, attach redacted before/after evidence and cleanup result. **The owner personally approves** each feature version's integration and any live DB/server or client rollout. Static GitHub CI passing is only a prerequisite.
5. **Explicit safety/rollback:** no unknown client version gets extended capacity packets; no ID 13–16 sent to the current 2019 client; no server DB mutation without isolated disposable fixtures, backup, migration/rollback evidence and the owner's approval. Do not commit proprietary retail DLLs or real credentials.

## Workstreams for the eventual single feature branch

- **Server:** DSP inventory storage IDs, secure per-character persistence, data migrations, packet 0x1C version compatibility, 0x1E/1F/20 readback, inventory sorting/equipment/trade restrictions.
- **Client:** safe per-store runtime sidecar or reviewed alternative; all accessors and snapshot aliases, mode object creation/teardown, command IDs, UI mode dispatcher, capacity display and pointer lifecycle.
- **Verification:** old-client regression on the unmodified 2019 binary; extended-client assertions, persist/relog/zone/trade/equip/move, disconnect/restart and rollback, XIHeadless evidence of server-authoritative state where client packets alone are inconclusive.

## References and handoff requirements

- Toolkit PR #1312 (full static research and synthetic tests): https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1312
- Toolkit PR #1303 (POL1 repacking and owner-smoke-test evidence): https://github.com/sarthax/FFXI-Mission-Toolkit/pull/1303
- Detailed original-build RVA study: `docs/reports/ffximain_2019_wardrobe_backport_stage4.md`
- Research closeout: `docs/reports/wardrobe_2019_toolkit_research_closeout_handoff.md`
- DSP repository feature policy: `sarthax/darkstar-to-valhalla` `README.md`, `AGENTS.md`, `docs/slices/STATUS.json`, `docs/ai-pipeline/README.md`; actual current branch and server revision must be refreshed when the owner authorizes transition.

**Ready-for-transition notification:** The client research has reached a bounded planning handoff. **Moving implementation to DSP awaits the owner's instruction; it is not blocked on pretending missing client/server runtime implementation is already solved.** Any outstanding Toolkit PR reconciliation/review must be tracked separately and must never trigger a DSP merge.
