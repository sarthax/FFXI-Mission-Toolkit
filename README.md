# FFXI Mission Toolkit / Workbench

A local, browser-based research, reverse-engineering, validation, capture-analysis, administration, and development workbench for Final Fantasy XI private-server work.

The project began as a mission/data lookup utility. It has grown into a broader evidence-driven toolkit that connects server source, SQL, Lua, client DAT/resources, packet captures, video/OCR evidence, wiki/reference claims, client-build snapshots, migration packages, runtime observations, and guarded server administration into one searchable local workspace.

The guiding rule is simple: **preserve what was observed, keep inference separate, and do not manufacture certainty when the evidence is incomplete.**

> **Current planning/status:** [`docs/workbench/ROADMAP_CURRENT.md`](docs/workbench/ROADMAP_CURRENT.md)  
> **Recent merged changes:** [`docs/workbench/RECENT_CHANGES_2026-10-03.md`](docs/workbench/RECENT_CHANGES_2026-10-03.md)  
> **Historical implementation ledger:** [`docs/workbench/ROADMAP.md`](docs/workbench/ROADMAP.md)

## What it is for

The Workbench is designed to answer questions such as:

- Where is this NPC, mob, item, event, CSID, packet, Lua API, or server feature actually implemented?
- Is a server entity wired correctly across SQL, Lua, instance registration, groups/pools, client identity, and runtime evidence?
- What does this NPC, mob, door, instance, or mission step actually do in plain language?
- Which character flags, key items, mission states, titles, inventory rows, spells, merits, or packed fields represent a player state?
- What changed between two FFXI client builds?
- Which packet/capture observations support a behavior or implementation claim?
- What source, capture, client, or reference evidence contradicts another source?
- What dependencies must move together when porting or rebuilding a feature?
- Can a mission, quest, battle system, or instance be reconstructed from source + capture evidence without silently guessing missing mechanics?
- Which proposed SQL/Lua/client changes are supported strongly enough for review, and which remain unresolved?

## Major capability areas

### Server environments and administration

The Workbench now treats server targets as named environments rather than a single Topaz/DSP path.

- Named **Live / Test / Dev / Backup / Other** profiles can point to LandSandBoat, Topaz, DSP, or compatible custom forks.
- Settings is the canonical place to create, edit, enable, test, activate, and remove server profiles.
- The active environment is shown in the shared shell and is consumed by generic/admin tooling.
- Zone Editor, Item Editor, model/client correlation, Entity Profile, and Character Editor use the active profile where appropriate.
- Multiple environments from the same server family are supported without silently collapsing them into one root.
- Native server configuration remains authoritative for database credentials; passwords are not surfaced by the toolkit.
- LIVE-target selections require explicit confirmation in editor workflows that can write.
- Legacy Topaz/DSP path settings remain only as bootstrap/fallback or lineage-specific comparison roots.

### Character Editor

The Character Editor is now a guarded DSP / Topaz / LandSandBoat administration surface rather than a single-schema prototype.

Current capabilities include:

- Dense character overview with sticky tabs/header, changed-field apply bar, filters, pagination, friendly field labels, units, and compact current-state-first presentation.
- Inventory browsing and guarded add/move/quantity/remove operations across directly verifiable persistent containers.
- Client-derived item names/icons with lazy icon loading and persistent client DAT cache support.
- Scalar character/job/stat/skill/point fields where the detected schema exposes verified editable columns.
- Packed mission, quest, key-item, Assault, Campaign, Eminence, ability, weaponskill, title, visited-zone, and Blue Magic state through lineage-aware codecs.
- Learned spell and blacklist administration.
- Semantic merit catalogs using the active checkout's native metadata, including current LSB data and legacy DSP merit sources where available.
- Legacy DSP mission/assault name resolution from checkout-local `missions.lua` banners.
- Mission/quest **State Surface** tracing that links current character state to source-evidenced charvars, key items, items, events, titles, mission/quest state, gil/fame, and source lines.
- Guarded preview/apply transactions, offline verification, stale-state fingerprints, audit journals, and supported Undo operations.
- LSB-only administrative fields when an explicit lineage/schema allowlist proves safe persistence semantics.

Runtime-owned status effects, recasts, pet/session state, and unknown lineage-specific fields remain intentionally read-only.

See [`docs/workbench/CHARACTER_EDITOR_CLOSEOUT.md`](docs/workbench/CHARACTER_EDITOR_CLOSEOUT.md).

### Feature Trace and implementation discovery

- Cross-source **Feature Trace** catalog across server SQL/Lua, LandSandBoat/Topaz/DSP-style sources, client resources, captures, research, validation, and packages.
- **Implementation Path** views for tracing entities/features through source-native wiring without inventing graph relationships.
- Evidence dossiers with bounded drill-down from canonical features to runtime observations and exact source/capture provenance.
- Entity identity bridging across server IDs, client ENTITY resources, capture observations, and multiple client builds with fail-closed ambiguity handling.
- Lua API → C++ binding/registration/implementation evidence where exact source evidence exists.
- Mission/quest **State Surface** extraction reused by Character Editor for evidence-backed progression inspection.

### Entity, behavior, mission, and event research

- **Entity Profile / Dossier** combining SQL wiring, Lua behavior, client identity, captures, events/CSIDs, implementation gaps, and related evidence.
- **Behavior Inspector** for NPCs, mobs, doors, zone scripts, instances, timers, callbacks, state transitions, helpers, conditions, and effects.
- Behavior Inspector now defaults to a **Plain Behavior** presentation that groups each behavior into **Trigger → Requirements → Actions / Events → Results / State Changes** and translates common Lua/API concepts into end-user language.
- The technical graph remains available with wheel zoom, drag-pan, fit/reset controls, causal-path highlighting, and a persistent right-side node inspector.
- Mission/quest extraction with guarded state transitions, prerequisite closure, branch/convergence analysis, timers, trades, key items, event chains, helper calls, and stress metrics.
- Events/CSID browser with conservative server/client reconciliation and variable-length EVENT decoding where formulas are statically provable.
- Generic reusable frameworks for multi-zone progression and minigame/puzzle/state-machine content.

### Captures and Evidence Search

The capture system is a first-class evidence source rather than just a packet dump viewer.

Supported ingestion families include current and historical formats such as:

- Windower PacketLogger / PacketViewer-style logs
- Ashita Packeteer
- MalRD PacketDB, including packet and chat evidence
- NPCLogger SQLite/Lua/Widescan variants
- EventView, ActionView, HPTrack, IDView, KITrack, LevelRange, AttackDelay, PathLog
- MissionTrack, ShopStock, GuildStock, SpawnTrack, WeatherTrack, CraftTrack, CheckParam, POITrack, ConquestTrack, PriceLog/findPrice, StatTrack, and related structured formats
- PCAP / PCAPNG network captures
- Windower Logger chat files
- Video/OCR-derived evidence kept separate from raw packet evidence

Capture features include:

- Exact row/block/source provenance and content-addressed source manifests.
- Duplicate/session-overlap detection and parser-specific safe rebuild rules.
- Cross-source packet correlation that distinguishes verified, ambiguous, and unsupported matches.
- **Capture Data Explorer** for structured/raw datasets without forcing users through giant raw-table dumps.
- Modular **Evidence Search** for Events/Dialogue, Raw Protocol, Entities, Battle/Actions, Items/KIs, Vendors/Shops, Crafting, Chat/Text, Spatial/Movement, and Environment/World State.
- Related-evidence handoffs using explicit provenance and identity keys rather than fuzzy timestamp/name proximity.
- 2D/3D spatial views with paths, entities, labels, IDs, positions, and client mesh context.
- Campaign/session manifest import support and message-ID shift handling for capture campaigns.

### Video, OCR, and evidence alignment

- Video/YouTube OCR workflows with saved screen-layout/preprocessing profiles.
- Packet/chat/capturebar-style OCR profiles and cross-frame consensus.
- Packet-symbol-assisted OCR correction with raw OCR preserved alongside corrected values.
- Manual/packet/event/screenshot anchors for capture ↔ video timeline alignment, including offset/drift diagnostics.
- Screenshot/key-event/note evidence stored with provenance and linked into the evidence graph where appropriate.

### Client snapshots, DAT inspection, models, and item tooling

- Portable client-build snapshots and cross-build EVENT/ENTITY comparison.
- DAT Inspector with DAT ID, zone/family, relative-path selection, parser summaries, navigation, and decoded previews.
- Client ENTITY identity extraction and canonical entity reconciliation.
- Model catalog/viewer and server/capture-aware 3D zone viewing.
- Item Editor with SQL/client reconciliation, constrained edits, backups, validation, batch workflows, and rollback-oriented client patching.
- Zone Editor and Item Editor use named active server environments instead of assuming one Topaz/DSP target.
- Persistent **client item DAT cache** supports lazy extract-on-first-use or optional one-time full prebuild. Parsed metadata is indexed in SQLite and icons are stored as normal PNG assets for browser/filesystem caching.
- Character inventory defers icon requests for collapsed storage containers and uses lazy image loading.
- Proposal-first client DAT patch orchestration with fingerprints, drift detection, approval gates, backups, and deterministic rollback for supported record families.

### Protocol and packet research

- Manual and bulk packet decode, including multiline PacketLogger/PacketViewer-style hex grids.
- Packetlyzer/XiPackets opcode-reference improvements and corrected packet field handling where verified.
- PCAP/PCAPNG frame parsing and generic bidirectional TCP reconstruction with gaps/retransmissions/conflicts preserved explicitly.
- Evidence-backed lobby/search/map classification and framing, including source-backed search/cache evidence, strict same-flow sequencing, and exact UDP map handoff where the capture proves it.
- Unknown or ambiguous streams remain fail-closed rather than being assigned protocol semantics by port number or guesswork.
- Packet Viewer handoffs from decoded/capture evidence.

### Research Sessions and reference evidence

- Persistent **Research Sessions** with provider/model selection, permissions, budgets, timeouts, replay, tool transcripts, evidence IDs, proposals, and final reports.
- Local Ollama-backed research support without silent provider fallback.
- Contradiction browsing across canonical findings, snapshots, and research proposals without choosing a winner automatically.
- BG Wiki / FFXIclopedia claim-level evidence mapping with revision provenance, conflict detection, and human review.

### Packages, migration, and validation

- Dependency-aware package planning and scope review.
- Conditional dependencies remain reviewable instead of silently becoming required.
- Patch-plan drift checks, explicit approval states, deterministic file apply journals, and rollback support.
- Validation dashboard/runs tied back into canonical evidence.
- Source/target conversion and migration support where transformations are deterministic and audited.
- Phase D implementation ownership is complete: reusable Workbench Python implementation lives under `src/workbench/...`; root `gui_server.py`, `settings.py`, and historical CLI/import files remain only as intentional compatibility/launcher surfaces where supported checkout workflows still need them.

### Editors and domain workspaces

- Modern **Zone Editor** (`/zoneplot2`) with spatial editing, detection overlays, navmesh/client-mesh context, bookmarks/templates, review tools, bulk alignment, and server-aware editing workflows.
- 2D/3D plot/viewer routing is guarded by live-app regressions and integrated handoffs.
- 3D zone/model viewers integrated into the shared Workbench shell.
- Nyzul layout tooling preserves compatible DSP/Topaz-era handling and routes modern LandSandBoat checkouts through the native `floor_generation.lua`/YAML adapter, failing closed on unsupported mappings.
- Domain-oriented workflows for Assault, Nyzul, and Salvage rather than forcing every named system into the generic feature list.

## Evidence model and safety philosophy

The Workbench deliberately distinguishes:

- **Observed** — directly present in source, SQL, client data, capture rows, packet bytes, screenshots, or revision-stamped references.
- **Derived** — deterministic transformations of observed evidence.
- **Inferred / candidate** — plausible relationships that still require corroboration.
- **Proposed** — generated SQL/Lua/client/package changes awaiting review.
- **Verified / approved** — explicitly validated or human-approved where the workflow supports it.

Missing evidence is not treated as proof that something does not exist. Ambiguous identity, unsupported packet formulas, incomplete captures, conflicting source forks, and unresolved client mappings are preserved as uncertainty rather than silently normalized away.

## Supported source families

The Workbench can operate across multiple server/source families and custom forks. Current adapters and logical-schema work include:

- LandSandBoat
- Topaz / Topaz-Next style repositories
- DSP / Darkstar-style repositories
- Custom forks using compatible or mapped schemas

Different forks are not assumed to be schema-identical. Cross-source normalization and representation drift are explicit parts of the model.

## Write behavior

The project is **not globally read-only**.

Most research/indexing/capture/client-inspection workflows remain read-only, but explicit development/admin workflows can write when the user chooses them. Character/server editing paths use lineage/schema contracts, offline checks, preview/approval, stale-state checks, audits and Undo where implemented. Package/file and supported client patch workflows use approval, validation, backup/journal, fingerprint, or rollback mechanisms where implemented.

Automatic SQL/Lua application from reconstruction evidence and fully generalized client-record creation are **not** currently claimed as complete.

## Requirements

Typical local use requires:

- **Python 3.11+**
- A legally owned FFXI client installation for client DAT/resource analysis
- At least one supported server/source checkout for server-side research and editing workflows
- `xi-tinkerer` / `xi-tinkerer-py` for supported DAT/zone/model parsing paths
- Optional additional server forks, client snapshots, capture archives, local Ollama models, and external tooling depending on the workflows you use

No FFXI game data is distributed with this repository. Client-derived caches are generated locally from the user's own installation and are ignored by Git.

See [`docs/guides/TOOLING_OVERVIEW.md`](docs/guides/TOOLING_OVERVIEW.md) for the current tooling inventory.

## Quick start

1. Install Python 3.11+ and ensure `python` is available on PATH.
2. Run `setup.bat` for first-time dependency/configuration setup.
3. Configure your FFXI client path and at least one server/source checkout.
4. Start the toolkit with:

```bat
start.bat
```

5. Open:

```text
http://127.0.0.1:8420
```

6. Open **Settings → Server Environments** and define the Live/Test/Dev/Backup profiles you intend to use. The active environment becomes the default server context for generic/admin tools.
7. Optional: under Settings, use **Build all item DAT cache** to pre-extract item metadata/icons once. If you do nothing, the cache fills lazily as assets are requested.

See [`docs/guides/SETUP.md`](docs/guides/SETUP.md) for current setup and environment guidance.

## Workspace map

The shared Workbench shell organizes the product into these broad areas:

- **Home / Project** — source/configuration overview and project entry points
- **Server** — Character Editor and server administration/environment-aware tools
- **Features** — Feature Trace, Implementation Path, Entity/Behavior research, Events/CSIDs, and generic feature research
- **Packages** — dependency scope, package creation/review, migration planning
- **Validation** — validation runs and evidence-backed checks
- **Client** — snapshots, DAT inspection, model/item/client-build tooling
- **Research** — Research Sessions and wiki/reference workflows
- **Domains** — named systems such as Assault, Nyzul, and Salvage
- **Captures** — ingestion, Data Explorer, Evidence Search, spatial/network/video evidence
- **Tools** — lower-level packet, binding, ID-drift, editor, and diagnostic utilities
- **Settings** — server environments, client paths/caches, and shared runtime configuration

Top-level category clicks open their section menus; the Sections control exposes the persistent secondary navigation bar.

## Project status

The toolkit is under active rework and expansion. The root README summarizes durable current capability; it does not duplicate the full implementation ledger.

For the authoritative capability inventory, current incomplete areas, and recent merged work, use:

- [`docs/workbench/ROADMAP_CURRENT.md`](docs/workbench/ROADMAP_CURRENT.md) — current capability/status roadmap
- [`docs/workbench/RECENT_CHANGES_2026-10-03.md`](docs/workbench/RECENT_CHANGES_2026-10-03.md) — October 1–3 reconciliation and merged-change summary
- [`docs/workbench/ROADMAP.md`](docs/workbench/ROADMAP.md) — historical implementation ledger
- [`docs/workbench/AUDIT_STATUS.md`](docs/workbench/AUDIT_STATUS.md) — historical/implementation audit notes

Near-term work is focused on Feature Trace real-data validation, protocol real-capture validation, proven Client Asset Cache expansion, broader client/server synchronization and named-system reconstruction, and remaining Auction House live-write validation on a real Test server.

## Screenshots

The screenshots currently stored under `docs/screenshots/` represent earlier generations of the UI and are intentionally not embedded here as the primary project presentation. The shared shell, Character Editor, Behavior Inspector, Capture Evidence Search/Data Explorer, Feature Trace, domain workspaces, Zone Editor, client tooling, and research surfaces have changed substantially since those images were captured.

A refreshed screenshot set should be captured from the current Workbench before screenshots are promoted back onto the project home page.

## License

The repository's own code is released under the [MIT License](LICENSE).

Bundled or vendored third-party tools retain their own licenses in their respective subdirectories. Those licenses apply to those tools specifically. Preserve the applicable third-party license files when redistributing vendor content.

No FFXI game DATs, extracted game data, models, or other Square Enix game assets are distributed as part of this repository.
