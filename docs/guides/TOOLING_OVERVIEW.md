# Mission Toolkit / Workbench tooling overview

Status: living reference  
Last reconciled: **2026-10-04**

This file describes the current major tool families in the consolidated `FFXI-Mission-Toolkit` repository. Older documentation may still refer to historical standalone checkouts such as `FFXI-Tools`; those tools have largely been consolidated under this repository, commonly under `vendor/`, `src/workbench/`, or compatibility entry points at the repository root.

The Workbench is evidence-driven: direct client/server/capture evidence is preferred over external references, and inferred relationships remain explicitly separate from observed facts.

## Workbench shell and runtime

The browser UI runs locally, normally at:

```text
http://127.0.0.1:8420
```

The shared shell organizes the product into Server, Features, Packages, Validation, Client, Research, Domains, Captures, Tools, and Settings workspaces.

Top-level category clicks open section menus; the Sections control exposes the persistent secondary navigation bar.

## Server environment runtime

Named server profiles are now the canonical runtime/admin context.

Supported profile families include:

- LandSandBoat
- Topaz / Topaz-Next
- DSP / Darkstar
- compatible custom forks

Profiles can represent Live/Test/Dev/Backup/Other environments and are managed under Settings. Generic/admin tools resolve the active profile while older lineage-specific comparison/index tools may still intentionally consume explicit DSP/Topaz reference roots.

Native server configuration remains authoritative for DB credentials.

## Character Editor

Location: Server workspace / Character Editor.

Major functions:

- schema-aware character browsing across DSP/Topaz/LSB,
- dense scalar-field editing with preview/apply safety,
- inventory add/move/quantity/remove,
- mission/key-item/quest/Assault/Campaign/Eminence packed state,
- abilities, weapon skills, titles, visited zones, Blue Magic state,
- learned spells and blacklist,
- lineage-aware mission/key-item catalogs,
- LSB and legacy DSP merit metadata,
- audit journals and guarded Undo,
- mission/quest State Surface trace integration.

The editor is intentionally offline-first for mutation. Runtime-owned effects/recasts/pet/session fields remain read-only unless a future adapter proves safe persistence semantics.

Detailed contract: `docs/workbench/CHARACTER_EDITOR_CLOSEOUT.md`.

## Feature Trace / Implementation Path

Feature Trace is the central cross-source implementation-discovery surface.

It indexes and links evidence from:

- server SQL/Lua,
- LSB/Topaz/DSP source adapters,
- client resources/snapshots,
- captures,
- research findings,
- validation,
- package/migration records,
- reference-wiki claims/alignment evidence.

Implementation Path exposes source-native wiring and bounded drill-down without inventing graph relationships. Entity identity bridging is fail-closed when IDs/names are ambiguous.

Focused modes answer implementation, triggers, effects, dependencies, mission progression, runtime, identity, diagnosis, or all-evidence questions without requiring one undifferentiated graph.

Provider-native server traversal covers deterministic relationships including item-detail → base item, spawn → mob group, mob group → pool, pet → pool, supported Blue Magic wiring, instance membership/entity links, and exact wiki claim-alignment paths.

The reconciled drop-chain work adds:

- complete-row read-only identity for `mob_droplist` rows where upstream schemas provide no stable primary key,
- `mob_groups.dropid → mob_droplist`,
- `mob_droplist.itemId → item_basic`,
- end-to-end **spawn → group → pool / drop rows → item** navigation,
- executable scenario benchmarks proving the chain without synthetic canonical graph edges.

The October 4 closure pass also adds exact forward navigation for:

- reviewed/automatic `MAPPED` reference-wiki mappings → exact implementation rows;
- captures → exact client snapshots by stored `client_build`/snapshot `version`;
- Research sessions → explicit canonical feature/entity roots;
- Research proposals and Validation results → exact canonical subjects only when the literal ID resolves in one namespace;
- Validation runs and migrations → explicit canonical feature roots;
- migration actions → explicit canonical artifacts.

All of these links fail closed on missing, duplicate, unresolved, or ambiguous targets. They remain read-only provider/cross-store navigation evidence and do not create canonical graph relationships as a side effect.

Mission/quest State Surface extraction is also provided here and reused by Character Editor.

Detailed workflow/evidence contract: `docs/workbench/BEHAVIOR_FEATURE_TRACE_GUIDE.md`.
Closure matrix and current testing boundary: `docs/workbench/FEATURE_TRACE_CLOSEOUT_2026-10-04.md`.

## Behavior Inspector

Behavior Inspector analyzes Lua-backed behavior for NPCs, mobs, doors/objects, zone scripts, instances, callbacks, timers, helpers, state variables, conditions, and effects.

Current UI modes:

- **Clarified Flow** — default; preserves branch structure and shows source-proven event lifecycle, stage → event → next-stage summaries, and verified same-state continuity without claiming cross-hook runtime ordering.
- **Plain Behavior** — compact evidence-preserving Trigger → Requirements → Actions / Events → Results / State Changes summary.
- **Technical Graph** — full causal/evidence graph with pan/zoom, fit/reset, selected-path highlighting, and technical node identities.

Plain Behavior comes from one backend-generated evidence-preserving projection contract rather than a separate browser interpretation. Internal rule/helper plumbing is collapsed while guards, helper identity/inputs/effects, state, targets, source locations, and exact technical node IDs remain available for drill-down.

Clarified Flow reuses the tested backend contracts for branch grouping, event identity, stage lifecycle, and stage continuity. Cross-hook relationships remain explicitly non-causal/`UNPROVEN` unless independent runtime evidence establishes ordering.

Timer, queue, and listener callbacks are partitioned so the parent shows scheduling/registration and the callback owns its downstream behavior. Duplicate callback-body observations may be suppressed in Plain View using proven source spans while remaining intact in Technical Graph.

The right-side inspector remains available for exact source/evidence drill-down. Unsupported dynamic semantics remain raw/unknown rather than guessed.

Detailed closeout contract: `docs/workbench/BEHAVIOR_INSPECTOR_CLOSEOUT.md`.
Combined Feature Trace workflow: `docs/workbench/BEHAVIOR_FEATURE_TRACE_GUIDE.md`.

## Entity Profile / Dossier

Entity research combines:

- SQL wiring,
- Lua behavior,
- instance/group/pool/drop relationships,
- client identity,
- capture observations,
- events/CSIDs,
- implementation gaps,
- Feature Trace handoffs.

The active server environment is used for administered/runtime context rather than assuming a Topaz-only source root.

## Events / CSID tools

The event toolchain includes:

- client event/DAT extraction,
- event/CSID browsing,
- server/client reconciliation,
- work-area / option flow inspection,
- conservative variable-length EVENT packet decoding,
- xi-events style decompilation/reference workflows where available.

Unsupported formulas or ambiguous client/server ownership remain raw/unresolved instead of being guessed.

## Capture system

The capture system is a canonical evidence source, not only a packet viewer.

Supported families include:

- Windower PacketLogger / PacketViewer / z16-style logs,
- Ashita Packeteer,
- MalRD PacketDB packets and CHATLOG,
- NPCLogger SQLite/Lua/Widescan,
- EventView / ActionView,
- HPTrack / IDView / KITrack / LevelRange / AttackDelay / PathLog,
- MissionTrack / ShopStock / GuildStock / SpawnTrack / WeatherTrack / CraftTrack,
- CheckParam / POITrack / ConquestTrack / PriceLog/findPrice / StatTrack,
- Windower Logger chat,
- PCAP / PCAPNG,
- video/OCR evidence as a separate evidence class.

Core capture services provide exact source provenance, duplicate/overlap diagnostics, parser-safe rebuild rules, cross-source packet correlation, Capture Data Explorer, modular Evidence Search, and spatial/network/video alignment.

Campaign/session manifest import and message-ID shift handling are also integrated.

Reference: `docs/workbench/CAPTURE_FORMAT_AUDIT.md`.

## Packet / protocol tools

Capabilities include:

- manual packet decode,
- bulk packet decode,
- Packet Viewer-style presentation,
- opcode/reference DB support,
- Packetlyzer/XiPackets reference data,
- PCAP/PCAPNG parsing,
- bidirectional TCP reconstruction,
- conservative lobby TCP classification/framing/decoding.

World/search/lobby families remain separate when protocol evidence is incomplete.

## Client snapshots and DAT tooling

### Client snapshots

Portable snapshot support allows client-build comparison without assuming one permanently installed retail version. Snapshot-scoped identity is kept separate from canonical identity until equivalence is proven.

### DAT Inspector

DAT Inspector provides file-id/path resolution, parser summaries, family/zone context, decoded previews, and client evidence navigation.

### Client item asset cache

The client item cache accelerates Character Editor inventory and future item/client surfaces.

- Lazy by default: parse/extract on first request, then persist.
- Optional Settings action: **Build all item DAT cache**.
- Parsed metadata: SQLite manifest/index.
- Icons: ordinary PNG files for efficient browser/filesystem caching.
- Cache is isolated by client installation/snapshot identity.
- Source DAT size/mtime changes invalidate affected entries.
- Clearing the cache simply returns to lazy extraction.

This is intentionally an extensible Client Asset Cache foundation; models/textures/maps should only be added when their parser/identity semantics are stable enough to cache safely.

## Item Editor

The Item Editor and its DAT tooling are packaged under `src/workbench/editors/items` with compatibility imports for older entry points.

Capabilities include:

- active named server-environment targeting,
- SQL/client reconciliation,
- item browsing/search/editing,
- validation and constrained writes,
- backup/journal-oriented server/client changes,
- client DAT patch proposal/apply workflows for supported record families,
- rollback/fingerprint/drift safeguards where implemented.

The Item Editor's older direct icon path remains compatible; shared client caching is being generalized incrementally rather than forcing all client tooling through one cache implementation at once.

## Zone Editor / spatial tooling

The modern Zone Editor (`/zoneplot2`) supports:

- SQL-backed entity/spawn editing,
- active environment targeting,
- 2D spatial editing,
- labels/IDs/positions/search,
- movement/rotation and bulk alignment workflows,
- detection/spawn/roam visualization where supported,
- client/navmesh/model context,
- bookmarks/templates/review helpers,
- 3D/model handoffs.

Capture 2D/3D spatial views use the same broader spatial/display conventions and are protected by route regression coverage.

The older legacy Zone Editor has been retired from the preferred workflow.

## Model and animation tooling

The Workbench integrates ideas/data structures from open-source FFXI asset tooling, including `xi-model-viewer`/xi-tools derived concepts where licensing permits.

Current model surfaces include:

- model catalog,
- model metadata correlation,
- server/capture-aware model selection,
- zone/model viewing,
- animation/schedule research,
- character/equipment model handling where supported.

Unrecognized individual gear-slot/catalog records no longer abort the entire model catalog.

## xi-tinkerer / client parser foundation

`xi-tinkerer` / `xi-tinkerer-py` supplies supported in-process parsing for client DAT/resource families. It is a foundational dependency for several client, event, model, and zone workflows.

No client game data is distributed with this repository.

## Reference/vendor tooling

The repository may include or reference third-party/vendor tools such as:

- xi-tinkerer / xi-tinkerer-py,
- xi-events related tooling,
- xi-model-viewer,
- Packetlyzer,
- POLUtils-derived/extraction utilities,
- AltanaViewer data references,
- Windower/Ashita logging tools,
- FFXI resource/reference datasets.

Third-party code retains its own license. Vendor/reference tools are not automatically considered authoritative; the Workbench records whether data came from the user's own client/server/capture versus an external reference dataset.

## Video / OCR tooling

Video/OCR capabilities include:

- YouTube/video frame workflows,
- saved overlay/preprocessing profiles,
- chat/EventView/NPCLogger/capturebar-style OCR regions,
- cross-frame consensus,
- packet-symbol-assisted correction,
- capture/video timestamp anchors and drift diagnostics.

Raw OCR is retained alongside corrected/derived values.

## Wiki / reference research

BG Wiki and FFXIclopedia are reference evidence, not unquestioned truth.

The Workbench supports claim-level alignment, revision provenance, contradiction detection, and exact fail-closed links from reviewed mappings into implementation records where the mapping ledger proves a unique target.

## Research Sessions

Research Sessions provide persistent assisted-research workflows with:

- provider/model selection,
- permissions and budgets,
- timeouts,
- replay/tool transcripts,
- evidence IDs,
- proposals/findings,
- final reports,
- local Ollama support.

Research proposals remain separate from verified implementation facts. Feature Trace may navigate explicit stored Research references to canonical nodes when the literal ID resolves uniquely; that navigation does not promote a proposal into verified implementation truth.

## Package / migration / validation tooling

The package/validation layer supports:

- dependency-aware package scope,
- conditional/reviewable dependencies,
- patch-plan drift detection,
- approval states,
- apply journals,
- rollback,
- validation runs linked to evidence,
- deterministic source/target conversion where implemented.

Feature Trace can follow explicit stored feature/subject/artifact references from Research, Validation, and Package records back to canonical Workbench nodes under exact-ID/fail-closed rules.

Phase D source-layout work continues to relocate mature root-level modules into logical `src/workbench/...` packages without breaking compatibility entry points.

## Historical standalone tools

Older docs and scripts may still mention standalone names such as:

- `mission_toolkit.py`,
- `build_database.py`,
- `id_bridge.py`,
- `wiki_lookup.py`,
- `mob_look_decode.py`,
- `model_schedule_dump.py`,
- older NPCLogger cross-reference scripts.

Some remain useful compatibility/research entry points, while others have been absorbed into richer Workbench surfaces. Prefer the browser Workbench and canonical `src/workbench/...` modules for current development unless a historical tool is specifically required for a legacy dataset.

## Decision order for current work

For most research/admin questions:

1. Start in **Feature Trace**, **Entity Profile**, **Behavior Inspector**, or the relevant **Server/Client/Capture** workspace.
2. Use Feature Trace for cross-source breadth and identity/wiring; use Behavior Inspector for source-proven Lua behavior.
3. Use exact server/client/capture evidence before external reference sources.
4. Use named Server Environments for administered targets rather than hard-coded lineage paths.
5. Drill into Clarified Flow/Technical Graph or specialized source views when the simplified view is insufficient.
6. Keep ambiguous mappings unresolved until another evidence source proves them.
7. Use package/apply/editor workflows only after preview/validation and with the relevant backup/audit safety path enabled.

For current capability status, see `docs/workbench/ROADMAP_CURRENT.md` rather than historical per-session inventories.
