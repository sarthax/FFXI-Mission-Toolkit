# Roadmap and Help Synchronization Audit — 2026-10-10

## Scope and status

This is a **targeted** source-and-documentation audit, not an assertion that every project module was revalidated. Compared merged `main` Key Items code and PR history with `docs/workbench/ROADMAP_CURRENT.md`, `docs/workbench/ROADMAP.md`, the GUI Roadmap, global Help, module Key Items page, Auction House capability/help pages, Live Client bridge guide, and Synth code/UI references.

| Capability | Merged implementation inspected | Prior docs state | Action / outstanding |
|---|---|---|---|
| Key Items | DSP source enum identity, duplicate ID/name detection, cache health, static source references, persistent SQLite index, grouped operation/line citation and clipboard research handoff (#868–#911) | Scattered/underrepresented in GUI Roadmap and Help | New `KEY_ITEMS_GUIDE.md`; update current roadmap, GUI roadmap, global help and module intro. Local DSP smoke test still required. |
| Auction House | Existing AH capability ledger and integrated `auction_house_help.html`; feature complete DSP core with guarded Test-only executors | Already has dedicated authoritative status and operational instructions | Retain existing detailed help; add cross-module summary links and do **not** conflate read-only administration with Test writes. |
| Live Client | Existing `LIVE_CLIENT_BRIDGE.md`, bridge console and setup/telemetry APIs; replay and spatial UI | Guide is extensive and carries dated progress notes | Add concise Help/Roadmap entry with unverified Windows client behavior and mapping calibration. Full chronological reconciliation of the large bridge guide remains future work. |
| Synth & Crafting | `/synth` view, recipe/API and `synth_recipes` tooling, Auction House help cross-reference | Usage guidance is mostly embedded in AH Help and module | Add global Help and roadmap navigation; verify legacy adapter/write gates locally and build a dedicated synth guide in next documentation sweep. |
| Historical roadmap | `ROADMAP.md` retains chronological implementation ledger | Historical entries should not be rewritten to look current | Leave historical ledger unchanged; surface dated reconciliation in `ROADMAP_CURRENT.md`. |

## Editorial rules for future PRs

1. When a module's capability changes, update **`ROADMAP_CURRENT.md` + `gui/templates/roadmap.html` + module guide + in-module help** in the same PR or explicitly link a follow-up doc PR.
2. Make a clear distinction between **merged + CI-covered**, **locally validated**, **partially supported**, **experimental**, and **planned**. Never call a Windows/FFXI runtime integration complete on synthetic CI alone.
3. Separate source/capture evidence from proven runtime execution. Label reference lineages, uncertain identities and truncated results.
4. Keep operator write-gates, Test-profile checks and read-only defaults visible. Do not imply permission to write merely from a linked administration page.
5. Prefer links to an authoritative guide over copying long instructions to multiple pages. Historical ledgers should retain original dated context.
6. Whenever major modules change concurrently, do a targeted doc-sync audit again instead of treating an old full-repository reconciliation date as current.

## Deferred checks

- Live Windows Ashita bridge end-to-end, Zone Viewer axis/heading calibration, replay/waypoint acceptance.
- Auction House recent executor-by-executor DSP Test acceptance and AH help link integrity.
- Synth dedicated help, recipe audit false-positive analysis and DSP/Topaz/LSB Test write compatibility.
- Key Items real DSP checkout data, unexpected alias/ID drift cases, persistent-index scaling and exact Feature Trace deep links.
- Broader modules (Wiki/Japanese translation, captures, Zone Editor, protocol work) need separate recency and help-page reconciliation.

## CI reconciliation

Revalidated after the Campaign/Salvage GUI route-inventory correction merged to `main` (PR #915). This documentation work does not modify the route inventory or server write paths.
