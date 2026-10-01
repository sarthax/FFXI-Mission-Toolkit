# FFXI Mission Toolkit / Workbench

A local, browser-based research, reverse-engineering, validation, capture-analysis, and development workbench for Final Fantasy XI private-server work.

The project began as a mission/data lookup utility. It has grown into a broader evidence-driven toolkit that connects server source, SQL, Lua, client DAT/resources, packet captures, video/OCR evidence, wiki/reference claims, client-build snapshots, migration packages, and runtime observations into one searchable local workspace.

The guiding rule is simple: **preserve what was observed, keep inference separate, and do not manufacture certainty when the evidence is incomplete.**

> **Current planning/status:** [`docs/workbench/ROADMAP_CURRENT.md`](docs/workbench/ROADMAP_CURRENT.md)  
> **Historical implementation ledger:** [`docs/workbench/ROADMAP.md`](docs/workbench/ROADMAP.md)

## What it is for

The Workbench is designed to answer questions such as:

- Where is this NPC, mob, item, event, CSID, packet, Lua API, or server feature actually implemented?
- Is a server entity wired correctly across SQL, Lua, instance registration, groups/pools, client identity, and runtime evidence?
- What changed between two FFXI client builds?
- Which packet/capture observations support a behavior or implementation claim?
- What source, capture, client, or reference evidence contradicts another source?
- What dependencies must move together when porting or rebuilding a feature?
- Can a mission, quest, battle system, or instance be reconstructed from source + capture evidence without silently guessing missing mechanics?
- Which proposed SQL/Lua/client changes are supported strongly enough for review, and which remain unresolved?

## Major capability areas

### Feature Trace and implementation discovery

- Cross-source **Feature Trace** catalog across server SQL/Lua, LandSandBoat/Topaz/DSP-style sources, client resources, captures, research, validation, and packages.
- **Implementation Path** views for tracing entities/features through source-native wiring without inventing graph relationships.
- Evidence dossiers with bounded drill-down from canonical features to runtime observations and exact source/capture provenance.
- Entity identity bridging across server IDs, client ENTITY resources, capture observations, and multiple client builds with fail-closed ambiguity handling.
- Lua API → C++ binding/registration/implementation evidence where exact source evidence exists.

### Entity, behavior, mission, and event research

- **Entity Profile / Dossier** combining SQL wiring, Lua behavior, client identity, captures, events/CSIDs, implementation gaps, and related evidence.
- **Behavior Inspector** for NPCs, mobs, doors, zone scripts, instances, timers, callbacks, state transitions, helpers, conditions, and effects.
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
- Proposal-first client DAT patch orchestration with fingerprints, drift detection, approval gates, backups, and deterministic rollback for supported record families.

### Protocol and packet research

- Manual and bulk packet decode, including multiline PacketLogger/PacketViewer-style hex grids.
- PCAP/PCAPNG frame parsing and generic bidirectional TCP reconstruction with gaps/retransmissions/conflicts preserved explicitly.
- Conservative lobby classification/decoding for known structurally valid commands.
- World/search/lobby transport research kept separated where protocol evidence is incomplete.
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

### Editors and domain workspaces

- Modern **Zone Editor** (`/zoneplot2`) with spatial editing, detection overlays, navmesh/client-mesh context, bookmarks/templates, review tools, bulk alignment, and server-aware editing workflows.
- 3D zone/model viewers integrated into the shared Workbench shell.
- Nyzul layout tooling modernized onto the Zone Editor interaction model.
- Domain-oriented workflows for Assault, Nyzul, and Salvage rather than forcing every named system into the generic feature list.
- Salvage currently includes a reconstruction dossier, visual workspace, and conservative unresolved floor/room candidate segmentation; proposal compilation is still under active development.

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

The project is **not globally read-only** anymore.

Most research/indexing/capture/client-inspection workflows are read-only, but some explicit development workflows can write when the user chooses them, including server editing, approved package/file application, and supported client patch operations. Those paths use review/approval, validation, backup/journal, fingerprint, or rollback mechanisms where implemented.

Automatic SQL/Lua application from reconstruction evidence and fully generalized client-record creation are **not** currently claimed as complete.

## Requirements

Typical local use requires:

- **Python 3.11+**
- A legally owned FFXI client installation for client DAT/resource analysis
- At least one supported server/source checkout for server-side research and editing workflows
- `xi-tinkerer` / `xi-tinkerer-py` for supported DAT/zone/model parsing paths
- Optional additional server forks, client snapshots, capture archives, local Ollama models, and external tooling depending on the workflows you use

No FFXI game data is distributed with this repository. Client-derived data is read from your own installation.

See [`docs/guides/TOOLING_OVERVIEW.md`](docs/guides/TOOLING_OVERVIEW.md) for the external/vendor tooling inventory.

## Quick start

1. Install Python 3.11+ and ensure `python` is available on PATH.
2. Run `setup.bat` for first-time dependency/configuration setup.
3. Configure your client/server paths when prompted or through the toolkit configuration/settings workflow.
4. Start the toolkit with:

```bat
start.bat
```

5. Open:

```text
http://127.0.0.1:8420
```

The older setup guide still documents the original Topaz-centric installation path and remains useful for setup mechanics, but it does not yet describe the full current Workbench product surface. See [`docs/guides/SETUP.md`](docs/guides/SETUP.md).

## Workspace map

The shared Workbench shell organizes the product into these broad areas:

- **Home / Project** — source/configuration overview and project entry points
- **Features** — Feature Trace, Implementation Path, entity/event behavior and generic feature research
- **Packages** — dependency scope, package creation/review, migration planning
- **Validation** — validation runs and evidence-backed checks
- **Client** — snapshots, DAT inspection, model/item/client-build tooling
- **Research** — Research Sessions and wiki/reference workflows
- **Domains** — named systems such as Assault, Nyzul, and Salvage
- **Captures** — ingestion, Data Explorer, Evidence Search, spatial/network/video evidence
- **Tools** — lower-level entity, packet, binding, ID-drift, editor, and diagnostic utilities

## Project status

The toolkit is under active rework and expansion. The root README intentionally summarizes only durable current capability; it does not attempt to duplicate the complete implementation ledger.

For the authoritative capability inventory, incomplete areas, and active priorities, use:

- [`docs/workbench/ROADMAP_CURRENT.md`](docs/workbench/ROADMAP_CURRENT.md) — current capability/status roadmap
- [`docs/workbench/ROADMAP.md`](docs/workbench/ROADMAP.md) — historical implementation ledger
- [`docs/workbench/AUDIT_STATUS.md`](docs/workbench/AUDIT_STATUS.md) — implementation/audit notes

Current near-term work is focused on evidence-backed Salvage reconstruction/compiler development, followed by broader behavioral dependency closure, client/server synchronization, protocol/capture research, and additional named-system workflows.

## Screenshots

The screenshots currently stored under `docs/screenshots/` represent earlier generations of the UI and are intentionally not embedded here as the primary project presentation. The shared shell, Capture Evidence Search/Data Explorer, Feature Trace, domain workspaces, Zone Editor, client tooling, and research surfaces have changed substantially since those images were captured.

A refreshed screenshot set should be captured from the current Workbench before screenshots are promoted back onto the project home page.

## License

The repository's own code is released under the [MIT License](LICENSE).

Bundled or vendored third-party tools retain their own licenses in their respective subdirectories. Those licenses apply to those tools specifically. Preserve the applicable third-party license files when redistributing vendor content.

No FFXI game DATs, extracted game data, models, or other Square Enix game assets are distributed as part of this repository.
