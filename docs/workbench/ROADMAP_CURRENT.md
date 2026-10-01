# Current Workbench Roadmap

Status: ACTIVE REWORK
Last aligned: 2026-10-01
Authoritative repository: `sarthax/FFXI-Mission-Toolkit`
Authoritative branch: `main`

This file is the compact current-status companion to `ROADMAP.md`. The historical roadmap remains valuable as the implementation ledger, but its older priority/status prose may lag recent merges. When the two disagree on what is active or already complete, use this file plus merged PR history as the current planning view.

## Recently completed / promoted

### Capture discovery, evidence search and provenance

- [x] Capture Query was replaced by the Capture Data Explorer model, with curated datasets, raw-row/provenance drill-down and domain-oriented presentation.
- [x] Modular Evidence Search now covers Events/Dialogue, Raw Packets, Entities, Battle, Items/KIs, Vendor, Crafting, Spatial/Movement, Environment/World State and Chat.
- [x] Related Evidence now preserves explicit provenance, deterministic packet matches, deterministic entity identity, ordinary-item identity and CapLog native-source relationships without timestamp-only guessing.
- [x] Capture integrity/provenance hardening is broadly complete: source manifests, parser/row lineage, capture fingerprints, overlap diagnostics, clock diagnostics, safe parser rebuild, orphan-safe deletion and precise source locators.
- [x] Cross-source packet correlation, video OCR evidence, screen-layout profiles, screenshot/key-event evidence and capture/video alignment are integrated.
- [x] PCAP/PCAPNG bounded ingestion, generic TCP flow reconstruction and validated lobby TCP classification/framing are implemented. Search/cache TCP decode and cross-plane correlation remain future work.

### Feature Trace / implementation discovery

- [x] Implementation Path now resolves provider-native SQL/Lua wiring, canonical identity where explicitly proven, runtime evidence, source drill-down, Lua-to-engine bindings and bounded implementation excerpts.
- [x] Entity Profile now acts as a cross-source implementation dossier with SQL/Lua wiring, Feature Trace, Behavior Inspector, capture/event/dialog handoffs and evidence-backed gap signals.
- [x] Bare-global Lua helper extraction was expanded and regression-tested (PR #199).
- [x] Shared lifecycle-system coupling recognizes additional explicit lifecycle delegation while preserving the multi-hook evidence gate (PR #198).

### Domains / named systems

- [x] Assault mission navigation moved under Domains / Battle Systems and expensive coverage calculation is now on-demand (PR #200).
- [x] Nyzul Isle layout editor was modernized onto the dense Zone Editor workspace pattern (PR #201).
- [x] Salvage domain foundation added the four Remnants zones as eight I/II build targets, with an evidence-gated pipeline and generic Workbench handoffs (PR #203).
- [x] Salvage capture reconstruction dossier added a read-only evidence model for entities, doors, EVENT/CSID observations, movement, actions, readiness and unresolved gaps (PR #204).
- [x] Salvage visual reconstruction workspace added a three-column evidence/map/dossier workflow without proposal generation (PR #205).
- [x] Salvage floor/room segmentation foundation added conservative player-path regions, bounds, entity/door overlap candidates and ambiguity handling without asserting unresolved regions as actual game floors/rooms (PR #206).

### UX / workflow alignment

- [x] Compact shared shell and dense-workstation patterns are in place across the main workspaces.
- [x] Package Scope → Create → Review has a unified workflow and clearer closure/readiness presentation.
- [x] Client Overview is now a build-comparison workspace focused on imported snapshots and cross-build EVENT/ENTITY comparison.
- [x] Wiki Compiler and Research Sessions were redesigned around evidence review, run/replay, contradiction review, budgets and proposal/report separation.
- [x] Capture Detail, Timeline, Packet Browser/Viewer, Evidence Search/Data Explorer and spatial viewers received the recent evidence-first UX refresh.

## Active priority order

1. **Salvage reconstruction closure**
   - [~] Strengthen candidate floor/room regions with real boundary evidence: door transitions, telepad/CSID observations, path discontinuities and reference-map evidence.
   - [ ] Build evidence-backed entity proposals shaped for `mob_spawn_points` / `npc_list`; require explicit mob/NPC/door/telepad classification and preserve provenance.
   - [ ] Build instance-registration proposals against `instance_entities.sql`, emitting only reviewed missing registrations.
   - [ ] Build door state modeling that separates observed initial state from transition conditions.
   - [ ] Build telepad/CSID state mapping with CSID identity, activation condition and destination as separate claims.
   - [ ] Add review-only Lua scaffold proposals with TODO/evidence markers for unproven mechanics.
   - [ ] Close Salvage mechanics: Pathos/cells, starter crates, floor progression/branches, NM gates, bosses, Rune of Release, drops/rewards.
   - [ ] Validate the compiler against an already-built Salvage truth set before using it to accelerate unfinished builds.

2. **Behavioral dependency closure**
   - [~] Continue generic conditional/system-state coupling discovery where source evidence proves it.
   - [~] Expand scripted behavior extraction only for source-backed dynamic patterns; do not infer behavior from naming/path conventions.
   - [ ] Continue deeper mission/quest dependency closure and evidence-backed implementation-gap actions.

3. **Client/server synchronization**
   - [ ] Broaden packet ↔ DAT/EXE/DLL ↔ server relationships.
   - [ ] Continue richer client capability validation and multi-client identity/drift workflows.
   - [ ] Generalize item/client write orchestration beyond the current read/compare foundations.

4. **Protocol / capture research**
   - [ ] Search/cache TCP decoder after real capture fixtures validate the protocol generation.
   - [ ] Cross-plane lobby/search/world correlation while retaining each source observation independently.
   - [ ] Live world-session packet producer into the canonical capture path.
   - [ ] Validate remaining historical logger formats only from real samples.

5. **Named delivery systems after Salvage**
   - [ ] Continue reusable domain/archetype work rather than hard-coding named-system semantics into the core.
   - [ ] Abyssea / Einherjar / Limbus are the next named-system candidates after the Salvage reconstruction/compiler path is proven.

6. **Migration completion and product workflow**
   - [ ] Database apply/rollback and approval/apply GUI once review/package safety is sufficient.
   - [ ] Broaden only proven deterministic migration backends.
   - [ ] Continue live ingestion, annotations, capture requests/completeness and capture-to-development export as product workflows mature.

## Explicitly not complete

The following should not be treated as done just because adjacent foundations exist:

- Search/cache TCP decryption/decoding.
- Cross-plane lobby/search/world correlation.
- Automatic Salvage floor/room naming or ownership.
- Salvage entity/instance SQL proposal compilation.
- Salvage door transition rules or telepad destinations inferred from EVENT rows alone.
- Automatic SQL/Lua apply from capture reconstruction.
- Generalized client DAT write orchestration.
- Full domain-plugin contract (`identify`, `discover_surfaces`, `discover_dependencies`, `compare`, migration-rule generation, validation) across all systems.

## Working rules for roadmap updates

- Mark work complete only after it is merged to `main` and relevant regression/CI checks are green.
- Keep observed capture/client/server/reference facts separate from inferred or proposed implementation.
- Record partial work as `[~]` when the foundation exists but the evidence/coverage target is not closed.
- Do not promote domain-specific Salvage/Assault/Nyzul concepts into the universal Workbench schema.
- Update this file whenever a roadmap-sized PR is merged so session restarts do not rely on conversational state.
- Preserve `ROADMAP.md` as the detailed historical implementation ledger; periodically fold durable completed details back into it when a safe full-file edit path is available.
