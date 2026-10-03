# Recent merged changes — 2026-10-03 reconciliation

This document records the major Workbench changes merged during the late-September / October 1–3 rework wave. It is a handoff/reconciliation aid, not a replacement for `ROADMAP_CURRENT.md` or the historical `ROADMAP.md` ledger.

Authoritative baseline at reconciliation start: current `main` after PR #438.

## Server environment model

PRs #403–#408 and follow-up fixes established named Server Environments as the canonical admin/runtime context.

### What changed

- Added persistent named server profiles for Live/Test/Dev/Backup/Other.
- Profiles carry server family and canonical root without storing DB passwords.
- Active environment became the default context for generic/admin tools.
- Settings became the canonical environment management UI.
- Shared shell now surfaces the active environment.
- Zone Editor and Item Editor selectors were moved from family-only Topaz/DSP choices to named profiles.
- Entity Profile, model catalog, Zone Plot adapters, and generic developer/runtime bridges were aligned with the active profile.
- Multiple same-family environments are preserved distinctly.
- Legacy Topaz/DSP roots remain for bootstrap, compatibility, and lineage-specific comparison tools.
- DSP/Topaz root/config normalization was fixed in PR #421.

## Character Editor maturation

A large sequence of Character Editor work completed the transition from prototype to guarded multi-lineage admin surface.

### Safety / transaction / audit

- Dedicated Character Editor CI gate added (#423).
- Audit logging covers committed row-backed, scalar, packed-state, spell, blacklist, inventory, and supported LSB-admin operations.
- Guarded Undo added for the supported mutation families, including LSB admin closeout (#424).
- Capability reporting now distinguishes supported writes from intentional runtime read-only state (#425).
- MariaDB datetime/date/time serialization fixed (#426).
- MySQL read connections were corrected to avoid implicit transactions blocking explicit apply transactions (#436).

### Inventory / scalar / packed state

Merged work now covers:

- inventory add/move/quantity/remove with container/capacity/stack and stale-row checks,
- verified scalar row fields,
- missions,
- key items,
- quests,
- Assault,
- Campaign,
- Eminence,
- abilities,
- weapon skills,
- titles,
- visited zones,
- Blue Magic set state,
- learned spells,
- blacklist entries,
- explicit LSB administrative fields.

Runtime-owned effects/recasts/pet/session state remains intentionally read-only.

### UX and catalogs

PRs #430, #431, and #438 substantially changed the Character Editor presentation:

- denser responsive field arrays,
- sticky header/tabs,
- sticky changed-fields apply bar,
- filtering / hide-zero / changed-only controls,
- pagination,
- friendly labels and units,
- enum dropdowns,
- raw physical storage moved behind Advanced presentation,
- inventory condensed into storage containers,
- current/owned/learned state shown by default with Browse All options,
- LSB semantic merit metadata,
- legacy DSP semantic merit metadata reconstructed from the checkout's own SQL/C++ definitions,
- legacy DSP mission/assault names parsed from `missions.lua`,
- mission value `65535` presented as None.

## Mission / quest State Surface

PR #432 connected Feature Trace progression evidence directly into Character Editor.

### Current behavior

For a selected mission/quest the State Surface can extract and display source-evidenced references to:

- charvars,
- key items,
- items,
- mission/quest state,
- events/CSIDs,
- titles,
- gil/fame,
- hooks and exact source lines.

Character Editor overlays current character state where supported and evaluates literal charvar guards when possible. Trace actions can jump into existing Key Item, Variables, Inventory, and Unlock editors.

The scan remains read-only and opt-in. Static source references do not prove runtime ordering.

PR #438 fixed a mission-trace regression in this pipeline.

## Client item DAT cache / inventory performance

PR #433 introduced a persistent hybrid client item cache.

### Cache behavior

- Default: lazy extract-on-first-use.
- Optional: one-time **Build all item DAT cache** action in Settings.
- Parsed item metadata stored in SQLite.
- Icons stored as ordinary PNG files.
- Cache isolated per client installation/snapshot.
- Source DAT size/mtime used to detect stale cache entries.
- Full build runs category-by-category and offloads long extraction work from the async event loop.
- Clearing the cache safely returns to lazy mode.

### Inventory behavior

- Character inventory now uses the cache-backed icon route.
- Only the first populated storage container opens initially.
- Collapsed containers receive no icon URLs until expanded.
- Browser lazy loading / async decoding reduces first-render request volume.

The cache schema is intentionally extensible for future client asset families, but models/textures/maps are not claimed as prebuilt cache families yet.

## Item Editor / client tools

Recent work aligned Item Editor and model/client tooling with the named active environment and completed important source-layout packaging.

- Item DAT tooling packaged under `src/workbench/editors/items` (#388).
- Item Editor backend packaged under `src/workbench/editors/items` (#389).
- Root compatibility imports preserve older entry points.
- Backup/journal path semantics were preserved.
- Item Editor consumes named Server Environments (#405–#406).
- Model catalog cache state is isolated by active profile to prevent cross-environment contamination.
- Client/model catalog handling was hardened so one unrecognized gear-slot index does not abort the complete catalog (#420).

## Behavior Inspector redesign

PRs #434, #437, and #439 changed Behavior Inspector from a mostly programmer-facing graph into a dual-level inspection surface.

### Technical graph improvements

- Wheel zoom centered on pointer location.
- Drag empty graph space to pan.
- Zoom +/- controls.
- Fit and Reset View controls.
- Fixed interactive viewport.
- Directed causal-chain highlighting:
  - recursively upstream through incoming prerequisites,
  - downstream through outgoing effects,
  - unrelated sibling branches dimmed.
- Stronger active-edge/node styling.

### Persistent inspector

Node details now live beside the graph in a right-side pane:

- independent scrolling,
- collapse/expand control,
- responsive stacked fallback on narrow screens,
- same underlying detail renderer/evidence source as before.

### Plain Behavior default

Behavior Inspector now defaults to **Plain Behavior**.

Each detected behavior is grouped into:

1. Trigger
2. Requirements
3. Actions / Events
4. Results / State Changes

Common Lua/API concepts are translated into user-facing labels while technical IDs remain available as secondary evidence. Clicking a Plain Behavior card opens the same exact underlying node evidence in the side inspector.

The full Technical Graph remains available as a secondary tab.

## Capture / campaign work

PR #435 reconciled the remaining capture-campaign-import branch into current main after the broader capture pipeline rework.

Merged pieces include:

- campaign/session manifest support,
- message-ID shift handling,
- capture-ingestion integration,
- capture UI/server wiring.

Related October fixes also included:

- Packetlyzer DB/XiPackets opcode naming improvements,
- corrected verified packet field offsets,
- capture spatial endpoint fix,
- 2D/3D plot routing regression protection,
- model catalog robustness (#420, #422).

The larger capture foundation from the preceding rework already includes broad historical/current logger ingestion, exact provenance, safe rebuild rules, cross-source correlation, Evidence Search, Data Explorer, PCAP/PCAPNG, OCR/video alignment, and spatial views.

## Zone / Nyzul / spatial work

- Zone Editor backend packaged under `src/workbench/editors/zone` (#391).
- Named active environment now controls generic/admin Zone Editor operations.
- Checked-in SQL synchronization uses the same active environment as live DB context rather than assuming `non-DSP => Topaz`.
- Plot viewer routing is protected by live-app regression coverage (#422).
- Nyzul Editor source-root resolution was fixed (#427):
  - use active configured profile when it contains the legacy file set the parser understands,
  - otherwise use another enabled compatible profile,
  - explicitly reject incompatible modern-LSB floor-generation layout rather than parse it incorrectly.

Native modern-LSB Nyzul floor-generation support remains future work.

## Shell / navigation

PR #429 modernized top-level navigation:

- clicking a workspace/category opens its section menu,
- explicit overview links remain available,
- Sections toggles a persistent secondary bar,
- environment-management links point to Settings rather than Character Editor.

## Source-layout / Phase D

The root-to-`src/workbench` migration continued in bounded slices with compatibility shims and regression coverage.

Recent packaged areas include major Item Editor/DAT tooling, Zone Editor backend, validation/settings bridges, bootstrap/reset support, and other runtime adapters.

Important rule preserved during this rework: do not move a mature component unless compatibility entry points, data paths, and focused regressions prove the relocation is safe.

## Regression / CI state

The project now relies on multiple overlapping safety gates:

- Workbench Regression
- Src Layout Regression
- Character Editor Regression
- focused DAT Inspector UX jobs
- client snapshot GUI/identity jobs
- research-session GUI jobs
- live-app route regression fixtures for sensitive routes

Recent Behavior Inspector, client cache, State Surface, and server-environment merges were promoted only after the relevant gates were green.

## Current high-value follow-up

The most natural next progression work is **Progression Transition** modeling: convert the current State Surface facts into one coherent unit per transition:

- trigger/hook,
- preconditions,
- event/CSID/option,
- persistent state effects,
- rewards/removals,
- mission/quest completion and next activation,
- exact source evidence,
- current-character evaluation / "why blocked" diagnostics.

Other active directions include further Plain Behavior refinement, selective Client Asset Cache expansion, native modern-LSB Nyzul support, deeper protocol/capture research, and continued low-risk source-layout cleanup.

## Documentation policy after this reconciliation

Use:

- `README.md` for the durable product overview,
- `ROADMAP_CURRENT.md` for authoritative current status,
- this file for the October 1–3 handoff/reconciliation,
- `ROADMAP.md` / `AUDIT_STATUS.md` as historical ledgers.

Do not infer current capability from an old open/closed branch name or an old per-session document when current main and `ROADMAP_CURRENT.md` say otherwise.
