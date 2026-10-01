# Current Workbench Roadmap

Status: ACTIVE REWORK
Last fully reconciled against merged PR and branch history: 2026-10-01
Authoritative repository: `sarthax/FFXI-Mission-Toolkit`
Authoritative branch: `main`

This is the authoritative current planning and capability inventory for the Mission Toolkit / Workbench. It is organized by durable capability rather than by the chronological order of individual pull requests.

`ROADMAP.md` remains the historical implementation ledger. When historical status text conflicts with this file, use this file plus merged `main` history.

## Status rules

- `[x]` = merged to `main` and covered by regression/CI or an equivalent merged validation.
- `[~]` = substantial foundation exists, but the capability is intentionally incomplete or evidence-limited.
- `[ ]` = planned / not yet implemented.
- Closed PRs that were explicitly superseded, rebased, transplanted, or replaced are **not roadmap capabilities**. Their surviving functionality is represented only by the later merged implementation.
- Leftover non-`main` branches are not evidence of roadmap work. The 2026-10-01 branch audit found no outstanding feature branch that should be merged into `main`; surviving non-main branches are superseded implementations or no-op leftovers and are cleanup candidates only.

---

# Merged capability inventory

## 1. Core Workbench architecture, evidence model and source adapters

- [x] Canonical Workbench model for Source, Snapshot, Feature, Domain/System, Artifact, Entity, Relationship, Capability, Implementation, Dependency, Evidence, Finding, Migration, MigrationAction, Validation and AnalysisResult.
- [x] Feature and Package are distinct concepts; package artifacts do not replace canonical feature/evidence identity.
- [x] Canonical evidence/provenance graph with Feature Trace, Feature Checker, evidence drill-down, validation links and migration/package relationships.
- [x] Server/source profiles for DSP, Topaz, Topaz-Next, LandSandBoat and custom forks.
- [x] Cross-source logical schema normalization with fail-closed schema handling and explicit representation drift.
- [x] P0/P1 logical schema coverage includes items, equipment, entities, instance/battlefield registries, spells/traits, abilities, weapon skills, mob skills/lists, item modifiers/latents, merits/job points, mob modifiers/spell lists, skill caps/ranks, synthesis and synergy. (PRs #13-#17 plus earlier rework foundation.)
- [x] C++/binding/enum/packet/build analysis foundation with conservative evidence confidence.
- [x] Generic dependency relationships and package traversal preserve UNKNOWN / conditional / reviewable states instead of manufacturing certainty.

## 2. Feature Trace, Implementation Path and implementation discovery

### Catalog/provider layer

- [x] Explicit Feature Trace providers for core SQL, LSB, Topaz, DSP, Client, Capture, Research, Validation and Package records. (PRs #28-#40.)
- [x] Provider alias/search fields with matched-on provenance.
- [x] Composite provider identities, including zone-scoped/group-scoped keys where single numeric IDs are unsafe.
- [x] Source-native provider links and bounded inspection metadata without promoting them into canonical dependency truth.
- [x] Deterministic server-native wiring for item detail→item_basic, spawn→zone-scoped group→pool, instance membership, Blue Magic wiring, key items and server event references.
- [x] Mob group/pool inspection context with source-native levels, respawn, drop/pool/family/model information.

### Canonical identity bridging

- [x] Capture entity observations bridge to canonical entity roots only when one explicit entity-style identifier mapping exists. (PR #148.)
- [x] Server catalog NPC/mob IDs are synchronized into canonical entity identifiers at index rebuild time. (PR #152.)
- [x] Portable client ENTITY snapshots mirror snapshot-scoped identities into canonical Feature Trace only when semantic identity is unique and non-conflicting. (PRs #153, #156.)
- [x] Cross-build numeric drift can resolve to one canonical entity root when explicit identity evidence proves equivalence.
- [x] Namespace collisions between EVENT and ENTITY or unrelated numeric identifiers fail closed rather than suppressing the correct entity mapping. (PRs #147, #165.)

### Implementation Path / dossier / drill-down

- [x] Evidence Dossier separates semantic relationships from runtime aggregates and supports bounded opcode→capture→raw observation hierarchy. (PR #27.)
- [x] Implementation Path resolves exact entity IDs and unique entity-name matches across server/catalog/client representations while preserving source/provider branches.
- [x] Exact provider-native wiring is traversable without inventing canonical graph edges.
- [x] Mapping-state diagnostics distinguish unique mapping, drifted IDs to one root, unmapped, partial, numeric collision and multiple-root ambiguity. (PR #157.)
- [x] Entity research handoffs connect Feature Trace, Entity Dossier, Behavior Inspector, Events/CSIDs, Captures, runtime evidence and path diagnostics. (PR #158.)
- [x] Source-level drill-down resolves exact-provider Lua through Behavior Inspector, gives bounded source previews, hooks/CSIDs and SQL row handoffs. (PR #159.)
- [x] Lua API calls join to provider C++ binding registration/implementation evidence with exact/case-only/unindexed/ambiguous states, callbacks, helper calls and Binding Reference handoffs. (PRs #160-#161.)
- [x] High-volume Feature Trace traversal is bounded and truncation is reported rather than hanging. (PR #114.)

## 3. Entity dossier and Events / CSID analysis

- [x] Entity Profile/Dossier aggregates SQL wiring, source behavior, captures, events/dialog, identity evidence and implementation-gap signals.
- [x] Behavior callback/source ownership is summarized with rules/effects/APIs/CSIDs/scheduled callbacks and exact source spans. (PR #155.)
- [x] Implementation-action queue is created only from concrete evidence-backed attention signals; missing evidence alone does not create an action.
- [x] Event/CSID browser includes source-script references and conservative client/server reconciliation.
- [x] Mission event reconciliation requires source family + zone + actor + CSID or independently established actor identity plus exact EVENT evidence. (PR #42.)
- [x] EVENT flow view preserves literal client work-area references, option values, captured parameter values and server callback stage evidence without assigning gameplay meaning to unknown parameter slots. (PR #150.)
- [x] Safe variable-length EVENT opcode decoding recognizes a bounded static AST subset and leaves unsupported formulas RAW_ONLY. (PR #9.)

## 4. Mission / quest extraction and dependency closure

### Generic mission/state-machine model

- [x] Reusable mission/quest state-machine contract with guarded transitions, ALL/ANY gates, zone-scoped event identity, lifecycle effects, implementation gaps and branch readiness. (PR #24.)
- [x] Mission source extraction emits ordinary canonical Feature/Artifact/Implementation/Entity/Evidence/DependencyEdge records. (PR #41.)
- [x] Preview-first ingestion preserves static-source confidence and never claims runtime correctness.

### Lua/DSL extraction depth

- [x] Branch-aware top-level `if / elseif / else` extraction preserves mutually exclusive outcomes. (PR #43.)
- [x] Post-effect convergence ordering models write→convergence-check→complete rather than impossible preconditions. (PR #44.)
- [x] Completion helpers are structurally discovered rather than tied to one function name. (PR #45.)
- [x] Actor/zone context is derived from literal Lua table scope; same-CSID event chaining prefers actor-scoped handlers. (PR #46.)
- [x] Function-block extraction ignores nested callbacks and function/end tokens inside basic comments/strings. (PR #47.)
- [x] Direct key-item grant extraction supports both `npcUtil.giveKeyItem` and `player:addKeyItem`. (PR #48.)
- [x] Exact distance comparators preserve LT/LE/GT/GE rather than flattening into generic proximity. (PR #49.)
- [x] Mission state materialization refuses unsafe cross-channel guard/write pairings. (PR #50.)
- [x] Explicit client-transport annotations attach only to the exact transition branch. (PR #51.)
- [x] Helper invocation and branch semantics are preserved without inlining asynchronous helper effects into callers. (PR #52.)
- [x] Trade completion extraction ignores comment/string false positives. (PR #53.)
- [x] Stress metrics expose handler coverage, trigger/guard/effect classes, branch completeness, helper calls, event-chain ambiguity, unmatched triggers and unmodeled spans. (PR #54.)
- [x] Mission completion/section gates are scoped to literal sections and propagated separately from handler-local guards. (PRs #56, #59-#62.)
- [x] Multiline/aliased section checks and conservative eligibility diagnostics are supported.

### Quest DSL and cross-feature closure

- [x] Structural LSB Quest DSL extraction covers quest identity, rewards, sections, status/vars, prerequisite quests/missions, key items, trades, zone guards, quest events, progression writes, completion and teleports. (PR #64.)
- [x] Cross-feature prerequisite closure preserves ALL/ANY semantics and explicit unresolved prerequisite symbols. (PR #65.)
- [x] Content-driven LSB source catalog discovers Mission/Quest definitions from source content rather than filenames and can load missing prerequisites on demand. (PR #66.)
- [x] WotG Bastok stress chain progressively validated quest/mission closure, timers, must-zone semantics, event relays, cross-feature writes, trade alternatives, helper indirection, convergence and documented-but-unenforced dependencies. (PRs #63, #67-#73.)
- [x] Documented source TODO prerequisites are represented separately from executable gating; they do not become runtime truth. (PR #72.)

### Reusable feature frameworks

- [x] Multi-zone progression/hunt framework supports staged objectives, AND/OR prerequisites, fan-out/branch/convergence, cross-zone dependencies, cycles/unreachable detection, evidence provenance and non-destructive canonical graph projection. (PR #55.)
- [x] Reusable minigame/puzzle framework models temporary state, timers, interactions, scoring, terminal outcomes, reset lifecycle, structural gaps and graph projection. (Safely reconciled in PR #74; stale #57/#58 histories are not roadmap items.)

## 5. Generic scripted behavior / Behavior Inspector

### Behavior model and extraction

- [x] Generic scripted-entity behavior model covers mobs, NPCs, doors/objects, escorts, zone scripts and instance callbacks. (PR #117.)
- [x] Bounded LSB Lua extractor handles direct hooks, HPP guards, random windows, timers, spawn/despawn, cross-entity state, action/magic/spell responses, loot overrides and combat modifiers. (PR #118.)
- [x] Extraction expanded across NPC/object/player progression, trades/events/rewards, doors/status/animation/position/pathing, shared systems and bounded reachable helpers. (PR #119.)
- [x] Open-ended `API_CALL` evidence preserves unfamiliar Lua-bound actions instead of dropping behavior outside a closed vocabulary. (PR #120.)
- [x] Hook ownership spans entity, zone, instance and registry/entry callbacks.

### Behavior Inspector visualization

- [x] Behavior Inspector renders condition/state → hook/rule/helper/callback → effect/API → target causal graphs with source provenance. (PR #121.)
- [x] Named state flow for entity/player/instance/zone/server variables preserves reads, writes, exact lines and unevaluated expressions. (PR #122.)
- [x] Anonymous timers, queues and listeners are first-class behavior branches with delay/event trigger identity and balanced callback source spans. (PR #123.)
- [x] Literal switch/case named-state transitions are extracted as verified `from → to` transitions only when read/write identity is proven. (PR #124.)
- [x] Environmental/actor-context conditions include literal Vana'diel time, weather, XYZ, distance and party/alliance access predicates. (PR #127.)
- [x] Direct symbolic entity references, aliases, bounded literal loops, bounded symbolic ranges and runtime-relative ID patterns are modeled conservatively with provenance. (PRs #128-#131, #138-#139.)
- [x] Shared `xi.<module>.<function>` helpers resolve to exact/ambiguous/unresolved source definitions, expose balanced source spans, one-level analysis, upstream/downstream impacts and one-level nested callee visibility. (PRs #132-#142.)
- [x] Instance lifecycle stage/progress is modeled separately from generic instance local variables. (PR #140.)
- [x] Literal server-global lifecycle transitions are modeled only when read/write alias identity and literal guards prove the transition. (PR #144.)
- [x] Non-combat mission/NPC and NM behavior stress proofs validate the generic model without adding content-specific semantics. (PRs #126, #143.)
- [x] Bare-global file-local helpers are included only when explicitly reachable from hooks; uncalled helpers remain unprojected. (PR #199.)

### Conditional/shared system coupling

- [x] Generic conditional/cross-zone/system-state dependency representation is visible in Package Scope and remains reviewable/QUESTIONABLE until approved. (PR #115.)
- [x] Conservative shared-lifecycle discovery detects alternate-zone scripts delegating multiple supported lifecycle hooks to the same real `xi.<system>` module. (PR #116.)
- [x] Supported lifecycle delegation now includes engage/fight/roam/disengage while preserving the multi-hook evidence gate. (PR #198.)

## 6. Acquisition / obtainability / crafting closure

- [x] Source-neutral acquisition catalog normalizes mob drops, synthesis, synergy and scripted item/key-item rewards. (PR #176.)
- [x] VERIFIED non-crafting item acquisition can feed recursive crafting/producibility closure.
- [x] Cross-fork static Lua shop extraction supports DSP/Topaz flat stock and LSB pair-row/general/nation/guild stock shapes with source/location provenance. (PR #177.)
- [x] Shop extraction is call/stock-shape-driven rather than NPC-path-only; zone/instance Lua can participate where source evidence proves stock.
- [x] Curio Vendor Moogle is represented separately as conditional `CURIO_VENDOR` evidence rather than flattened into ordinary static `SOLD_BY`. (PR #191.)
- [x] Canonical ITEM / KEY_ITEM identity reconciliation is fail-closed, namespace-isolated and requires authoritative enum or VERIFIED snapshot bridges. (PR #192.)
- [~] Additional acquisition families such as HELM, gardening, exchange and appraisal remain future extensions; the current audited acquisition foundation is complete for the supported families.

## 7. Capture ingestion, integrity and provenance

### Supported capture/logging families

- [x] Core NPCLogger / ActionView / HPTrack / IDView / KITrack / EventView / LevelRange / AttackDelay / PathLog family ingestion.
- [x] Broad optional past-and-present structured logger ingestion: MissionTrack, ShopStock, GuildStock, SpawnTrack, WeatherTrack, CraftTrack, CheckParam, POITrack, ConquestTrack and historical PriceLog/findPrice. (PRs #98-#99.)
- [x] MalRD PacketDB packet storage and Ashita Packeteer text ingestion into canonical raw packet evidence. (PR #100.)
- [x] PacketDB CHATLOG and CapLog chat/system lines feed canonical `capture_chat_observations` while preserving native-source identity. (PR #104.)
- [x] Whole-session EventView simple/raw logs are preserved with unknown zone/time when the source does not prove those fields. (PR #105.)
- [x] Windower Logger daily chat files are ingested without fabricating timestamps when logging timestamps are disabled. (PR #108.)
- [x] Captain StatTrack player/puppet CSV support was preserved when the stale next-wave branch was reconciled. (PR #112.)
- [x] Capture Help contains an explicit support/gap matrix and capture-tool archaeology documentation. (PRs #101, #108.)

### Integrity / exact provenance

- [x] Dynamic capture-owned table deletion and orphan prevention.
- [x] Content-addressed source manifests, parser/table-family lineage and dimensioned capture health. (PR #83.)
- [x] Path-independent whole-capture content fingerprinting, duplicate detection and same-name source history. (PR #85.)
- [x] Exact row/block/SQLite provenance covers EventView, PacketLogger/PacketViewer, CapLog, KITrack, IDView, HPTrack, ActionView, NPCLogger DB/Lua, LevelRange, NPC/PC paths, Widescan and AttackDelay. (PRs #86-#94.)
- [x] Capture overlap/partial-session and physical-source clock continuity diagnostics preserve warnings without auto-reclassification or timestamp correction. (PR #91.)
- [x] Safe parser-specific rebuild requires original accessible bytes, matching SHA-256 and exact row ownership; ambiguous shared ownership is refused. (PR #92.)
- [x] Exact source viewer verifies SHA-256 before presenting current bytes as original evidence. (PR #95.)
- [x] High-volume PacketViewer/PacketLogger ingest and adjacent provenance/correlation paths were hardened against quadratic behavior. (PRs #113-#114.)

## 8. Capture graph linkage, correlation and Evidence Search

### Canonical/runtime graph linkage

- [x] Raw PacketLogger/PacketViewer and EventView rows project separately to canonical packet nodes with exact normalized row keys. (PR #96.)
- [x] Feature Trace runtime evidence can drill back to exact capture source blocks/rows. (PR #95.)
- [x] Cross-source packet correlation keeps streams independent and records basis, score, candidate count and alignment model. (PR #97.)
- [x] Verified cross-source matches require unique deterministic evidence; repeated or temporal-only candidates remain ambiguous/unverified.

### Capture Data Explorer / Evidence Search

- [x] Legacy giant Capture Query presentation was replaced by grouped Capture Data Explorer cards with curated first-glance fields and full raw/provenance disclosure. (PR #181.)
- [x] Evidence Search modules cover Events/Dialogue, Raw Protocol, Entities, Battle/Actions, Items/KIs, Vendors/Shops, Crafting, Chat/Text, Spatial/Movement and Environment/World State. (PRs #184-#185.)
- [x] Spatial path-heavy evidence is aggregated rather than flooding search with every movement sample.
- [x] Related Evidence supports exact provenance siblings, explicit non-temporal packet correlations, deterministic entity identity, deterministic ordinary-item identity and CapLog native-source chat relationships. (PRs #186-#196.)
- [x] Timestamp/name/text/price proximity is not used as identity semantics.
- [x] Related Evidence presents normalized summaries, family counts and handoffs to Source Locator, Data Explorer, Entity/Item profiles and Packet Viewer.
- [x] Capture Evidence Search/Data Explorer foundation is considered complete; remaining work is real-user UX tuning and future relationships only when stable explicit identity keys exist. (PR #197.)

## 9. Video OCR, screenshots and capture/video evidence alignment

- [x] YouTube/video OCR pipeline with packet/chat profiles, GUI, vendored-tool installers and capture linkage was safely reconciled onto current main. (PR #75.)
- [x] OCR observations preserve video-relative timestamp, frame, crop/FPS/profile/source URL provenance and remain separate from raw binary packet evidence. (PR #76.)
- [x] Parsed on-screen packet opcodes can bridge to canonical packet nodes as `VIDEO_OCR` inferred evidence.
- [x] Capture/video alignment supports manual/packet/event/screenshot anchors, offset or drift fits, ppm/RMS/max residual diagnostics and separate clock bases. (PR #77.)
- [x] Screenshot / key-event / frame / note evidence layer stores provenance and can bridge key evidence into canonical graph records. (PR #78.)
- [x] Cross-frame OCR consensus and packet-symbol-assisted correction preserves raw OCR plus correction provenance. (PR #79.)
- [x] Saved OCR screen-layout and preprocessing profiles support reusable multi-region capture setups. (PR #80.)
- [x] Capturebar HUD OCR profile extracts zone, target/player, XYZ, rotation, jobs/levels and moon context without dialog fuzzy matching. (PR #106.)
- [x] YouTube OCR pages remain correctly owned by the Captures workspace. (PR #102.)

## 10. PCAP/network/lobby protocol research

- [x] Dependency-free classic PCAP and PCAPNG readers preserve exact frames/offsets, common Ethernet/raw-IP/Linux-cooked IPv4/IPv6 metadata and opaque payloads without guessing crypto/compression state. (PR #107.)
- [x] Plaintext UDP payloads are promoted to canonical FFXI chunks only when the entire payload validates.
- [x] Generic bidirectional TCP reconstruction preserves per-direction observed ranges, gaps, retransmissions, overlaps/conflicts and exact contributing frames; missing bytes are never synthesized. (PR #110.)
- [x] Lobby classifier requires structurally valid known-command packets and never classifies from port alone. (PR #111.)
- [x] Lobby decoder persists raw packets plus decoded non-secret fields, ResponseKey feature flags, ResponseNextLogin world/search endpoints, character/world lists, version/expansion fields and common identifiers/status fields.
- [x] Lobby/search/world transport boundaries and retail-vs-private-server protocol distinctions are documented. (PR #109.)
- [ ] Search/cache TCP decoder after real protocol-generation fixtures are available.
- [ ] Cross-plane lobby → search → world endpoint/session correlation.
- [ ] Live world-session producer into the canonical capture path.
- [ ] Validate remaining V2/historical logger variants only against real samples.

## 11. Client snapshots, DAT inspection, item editing and client migration

### Client snapshots / comparison

- [x] Client Overview preserves installed-client fingerprint and imports portable all-zone identity snapshots. (PR #4.)
- [x] Cross-build EVENT comparison exposes normalized totals, event mapping and CSV export.
- [x] ENTITY resources are extracted into snapshots; actor resolution uses zone-scoped semantic evidence and leaves duplicate names ambiguous. (PR #11.)
- [x] Client ENTITY identity is integrated into Feature Trace canonical entity bridging. (PRs #153/#156.)
- [x] Client Overview was redesigned as a dense build-comparison workspace with imported snapshots and EVENT/ENTITY comparison primary. (PR #174.)

### DAT / model / binary inspection

- [x] DAT Inspector supports DAT ID, zone + DAT family and client-relative DAT path selection with root containment validation, readable parser summaries, previous/next DAT and bounded decoded previews. (PR #7.)
- [x] Model Viewer provides client model catalog/view functionality and participates in the compact workstation shell.
- [x] 3D Zone Viewer renders client visual mesh plus capture/entity/path overlays and modern shell/viewer behavior.
- [x] Binary/Binding inspection supports conservative import/binding/build evidence; exact CFG/full disassembly remains intentionally unclaimed unless a future decoder-backed path is added.

### Item editing / client writes

- [x] Item Editor supports SQL/client reconciliation, constrained editing, backups/journal/validation, batch workflows, undo/redo and client DAT handling.
- [x] New-item client record creation fixes preserve the true item ID and display text; delete can clear the exact client record; equip-slot UI enforces known exclusivity rules. (PR #1.)
- [x] Generalized client DAT patch orchestration supports proposal-only `PATCH_EXISTING`, client-record fingerprints, drift detection, explicit approval, writer invocation only after approval, low-level backup metadata and deterministic rollback. (PR #18.)
- [ ] Generalized new-item allocation/injection and coordinated server SQL/client index changes.
- [ ] Broaden generalized client write orchestration beyond currently supported audited record families.

## 12. Research Sessions and evidence-aware research

- [x] Persistent Research Sessions store provider/model, permissions, snapshots, budgets, usage, replay metadata, verification state, typed tool transcript, evidence IDs, proposals and final report. (PR #5.)
- [x] Direct Ollama provider supports local model listing, capability probing and provider-neutral response/usage metadata without silent fallback. (PR #6.)
- [x] Bounded ResearchSession run/replay controls enforce explicit provider/model/budget/timeout controls; replay clones rather than mutates prior transcripts. (PR #10.)
- [x] Contradiction browser identifies conflicting values across canonical findings, snapshot observations and research proposals without choosing a winner. (PR #12.)
- [x] Canonical Evidence detail links findings, relationships, validations, capabilities, implementations, tool calls and proposals.
- [x] Research Sessions and Wiki Compiler received evidence-first workflow redesigns while preserving execution and permission semantics. (PRs #172-#173.)

## 13. Wiki/reference evidence

- [x] Claim-level wiki evidence mapping stores revision-stamped claims and mappings separately for BG Wiki and FFXIclopedia. (PR #81.)
- [x] Automatic mapping is conservative; human confirm/reject is supported; reference evidence has reference-only authority.
- [x] Dual-wiki alignment records agreement, divergence, one-sided claims and deterministic numeric/negation conflicts without selecting a winner. (PR #82.)
- [x] Wiki evidence is exposed through Feature Trace / research surfaces.

## 14. Packages, migration and validation

- [x] Dependency-aware migration/package planning with scope decisions, collision analysis, proposal artifacts, patch-plan drift checks, explicit approval state, deterministic file apply journals, rollback and readiness review.
- [x] Conditional/cross-system dependencies remain reviewable instead of silently becoming REQUIRED.
- [x] Package Scope → Create → Review uses a unified workflow with closure/gate state, compact dependency decisions and grouped materialized/missing/skipped artifacts. (PR #175.)
- [x] Validation Dashboard / Validation Runs are integrated into the shared Workbench shell and canonical evidence relationships.
- [x] High-volume package topological ordering and long dependency chains were stress-hardened. (PR #114.)
- [ ] Database-level apply/rollback equivalent to the mature file-apply path.
- [ ] Approval/apply/rollback GUI only after dependency-completeness gates remain preserved end-to-end.
- [ ] Additional source→target conversion backends only where deterministic audited transformations exist.

## 15. Zone Editor, spatial viewers and development workspaces

- [x] `/zoneplot2` is the active Zone Editor with detection overlay, family colors, layout generator, Review tab, bulk align/spread/mirror, path measure, bookmarks and templates. (PR #162.)
- [x] Legacy Zone Editor page is removed from navigation and `/zoneplot` redirects to `/zoneplot2`; shared APIs retained where the new editor still depends on them. (PR #182.)
- [x] Zone Editor supports server-agnostic live editing across configured server roots and schema differences established in earlier toolkit work.
- [x] Capture 2D/3D spatial viewers use capture observations, entity search, labels/IDs/XYZ, richer tables/hover context, searchable 3D markers and current mesh/nav behavior. (PR #88.)
- [x] Model Viewer and 3D Zone Viewer use the shared compact shell; the 3D viewport tracks available browser height. (PR #166.)
- [x] Server 3D Viewer template compilation regression was fixed and guarded. (PR #182.)
- [x] Nyzul Isle layout editor now follows the dense Zone Editor workspace model. (PR #201.)

## 16. Packet tools

- [x] Packet Decoder supports manual multiline input through POST, including PacketLogger/PacketViewer hex-grid blocks. (PR #182.)
- [x] Bulk Packet Decode accepts multiple files/capture bundles and routes through capture adapters in the modern packet workbench. (PRs #179, #182.)
- [x] Decoded bulk rows hand directly into Packet Viewer with exact direction/opcode/raw bytes.
- [x] Packet tools retain packet decode semantics while using compact command surfaces.

## 17. Named domains / system workspaces

### Assault

- [x] Assault mission workflow is under Domains → Battle Systems rather than generic Features.
- [x] Mission search is lightweight/on-demand; expensive full observed coverage is explicitly user-triggered. (PR #200.)
- [x] Existing Assault mission/capture/package research capabilities remain available through the domain and mission explorer surfaces.

### Nyzul Isle

- [x] Nyzul layout editor exists and is modernized onto the common Zone Editor UX. (PR #201.)
- [x] Reusable minigame/puzzle and multi-zone frameworks provide generic building blocks for Nyzul-like mechanics rather than hard-coding them into the core.

### Salvage

- [x] Salvage domain definition covers Zhayolm, Arrapago, Bhaflau and Silver Sea Remnants as I/II implementation tracks. (PR #203.)
- [x] Evidence-gated Salvage pipeline models instance registry, instance entities, spawns, NPC/door/telepad state, zone/instance Lua, mob Lua, Pathos/cell progression and capture evidence.
- [x] Read-only reconstruction dossier organizes observed entities, doors, interaction candidates, EVENT/options, movement, player path, actions, readiness and explicit gaps. (PR #204.)
- [x] Visual Salvage Reconstruction workspace provides capture/zone selection, readiness, live map, entity roster, door/state review, EVENT/CSID review and Workbench handoffs. (PR #205.)
- [x] Conservative floor/room segmentation foundation treats parser-native player-path legs as unresolved region candidates with bounds and entity/door overlap/ambiguity analysis. (PR #206.)
- [ ] Actual floor/room identity/ownership still requires corroborating boundary evidence.
- [ ] SQL/Lua proposal compiler and automatic application are not yet implemented.

## 18. Shared shell, navigation and UX

- [x] Shared workspace shell organizes Home/Project, Features, Packages, Validation, Client, Research, Domains, Captures and Tools without changing route ownership. (PR #2 foundation plus later IA work.)
- [x] Compact shell v2 replaces permanently stacked global headers with bounded workspace/context controls and dense workstation primitives. (PR #164.)
- [x] Dense shell rollout covers Zone Editor, Model Viewer, 3D Viewer, Item Editor, Feature Trace, Entity/Events/Packet Tools, Captures, Validation, Package Library, library/search pages and dedicated workflow redesigns. (PRs #166-#175.)
- [x] Help was refreshed for current Workbench workflows. (PR #26.)
- [x] Shell branding is configurable: show/hide, brand text, validated local custom icon and reset to default. (PR #178.)
- [x] Reading-heavy help/report pages remain intentionally roomier than workstation pages.

---

# Active roadmap / next work

## Priority 1 — Salvage reconstruction compiler path

- [~] Strengthen candidate floor/room regions with **real boundary evidence**: door transitions, telepad/CSID observations, path discontinuities and reference-map evidence.
- [ ] Introduce explicit reviewed region identity only where boundary evidence is sufficient; retain unresolved/ambiguous topology otherwise.
- [ ] Build evidence-backed entity proposals shaped for `mob_spawn_points` / `npc_list` with explicit mob/NPC/door/telepad classification and per-field provenance.
- [ ] Compare reviewed entity proposals against current server rows and surface exact matches, drift, missing rows and conflicts.
- [ ] Build instance-registration proposals against `instance_entities.sql`; emit only reviewed missing registrations.
- [ ] Build temporal door-state model separating observed initial/final state from open/close trigger conditions.
- [ ] Build telepad/CSID claim model with three independent claims: CSID identity, activation condition and destination.
- [ ] Correlate telepad activation with before/after player position or zone transition; never infer unobserved destinations/options.
- [ ] Generate review-only zone/instance/mob/NPC Lua scaffold proposals with source/evidence TODO markers for unproven mechanics.
- [ ] Close Pathos/cells, starter crates, progression/branch gates, NM pop/unlock conditions, bosses, Rune of Release and drops/rewards.
- [ ] Validate reconstruction/compiler output against an already-built Salvage truth set before using it to accelerate unfinished builds.
- [ ] Keep automatic SQL/Lua application as a separate later approval milestone.

## Priority 2 — Behavioral dependency closure

- [~] Expand automatic conditional/system-state coupling only where explicit source evidence proves a relationship.
- [~] Extend scripted behavior analysis for dynamic data flow, imported helper expansion and richer party/environment/instance semantics without name/path inference.
- [ ] Improve generic relationship projection for source-backed combat/state effects where current analysis remains presentation-only.
- [ ] Continue mission/quest closure for remaining dynamic helpers, DefaultActions/fallbacks, client dialog/event resources, trade/timer/spawn/death/battlefield behavior and additional instance-heavy proofs.
- [ ] Extend acquisition catalog to HELM, gardening, exchange and appraisal only after each family has an audited stable source identity contract.

## Priority 3 — Client/server synchronization

- [ ] Broaden packet ↔ client DAT/EXE/DLL ↔ server relationships using explicit evidence bridges.
- [ ] Expand multi-client capability probes beyond current EVENT/ENTITY structural comparison.
- [ ] Add optional decoder-backed instruction/CFG/xref/function recovery with decoder/version provenance; do not promote current heuristic binary references as decoded control flow.
- [ ] Complete generalized new-item DAT allocation/injection and coordinated server SQL/client index changes.
- [ ] Extend generalized client write orchestration to additional audited record families while preserving specialized mature editors until parity is proven.

## Priority 4 — Protocol / capture research

- [ ] Search/cache TCP decoder after real samples establish protocol-generation framing/encryption behavior.
- [ ] Cross-plane lobby/search/world endpoint and session correlation with each evidence plane preserved independently.
- [ ] Live Windower/Ashita or PacketBridge-style world-session packet producer into canonical capture ingestion.
- [ ] Validate remaining Captain V2/historical variants against real samples rather than assuming backward compatibility.
- [ ] Decide which persistent/global telemetry sources should be represented separately from session-scoped capture identity.

## Priority 5 — Named delivery systems after Salvage

- [ ] Continue Assault and Nyzul development using generic frameworks and evidence services rather than system-specific core schema.
- [ ] Add Abyssea domain/analyzer/workflow when reusable domain interfaces are sufficient.
- [ ] Add Einherjar domain/analyzer/workflow.
- [ ] Add Limbus preservation/comparison workflow when a suitable implementation/client snapshot is selected.
- [ ] Continue other named systems only through optional domain analyzers/plugins.

## Priority 6 — Migration completion / operational product workflow

- [ ] Database-level apply and deterministic rollback with the same evidence/review discipline as file apply.
- [ ] Approval/apply/rollback GUI once dependency-completeness and drift gates are preserved end-to-end.
- [ ] Broaden migration backends only for audited deterministic transformations.
- [ ] Watched-folder/live capture auto-ingestion.
- [ ] Capture-data request/fulfillment workflow.
- [ ] Capture annotations, semantic invalid-data flags and completeness checklists.
- [ ] Capture → server-development drafting/export through canonical evidence + package review.
- [ ] Authenticated remote/hosted access.
- [ ] Discord/reference-history catalog integration.

---

# Explicitly not complete

The following foundations exist nearby but **must not be reported as complete**:

- Search/cache protocol decoding/decryption.
- Cross-plane lobby/search/world correlation.
- Full decoded binary CFG/function recovery.
- Automatic Salvage floor/room naming or ownership from player-path legs alone.
- Salvage entity/instance SQL proposal compilation.
- Salvage door trigger rules from captured door state alone.
- Salvage telepad destinations or Lua ownership inferred from EVENT/CSID rows alone.
- Automatic SQL/Lua apply from reconstruction evidence.
- Generalized new-item client DAT allocation/injection.
- Full generalized client DAT writes across all record families.
- Complete acquisition coverage for HELM/gardening/exchange/appraisal.
- A universal domain-plugin implementation across every named FFXI system.
- Runtime correctness merely because static source evidence exists.

---

# Superseded / deprecated history intentionally excluded

These PR histories are not independent roadmap features because later merged work replaced or safely transplanted their useful content:

- PR #3 packed-binary branch: closed/unmerged; current binary capability is represented by merged rework/main functionality, not this branch.
- PR #25 related-variant branch: superseded by clean generic transplantation/current dependency work.
- PRs #57/#58 minigame branches: superseded by safe reconciliation in PR #74.
- PR #84 capture-integrity branch: superseded by merged capture-integrity work and PR #85 follow-up.
- PR #103 capture-hardening next-wave branch: decomposed/reconciled into merged PRs #104-#112; only those merged capabilities count.
- PR #125 entity-impact branch: intentionally not merged because filename-derived reverse identity conflicted with stricter evidence architecture.
- PR #145 scripted-reward branch: useful functionality was ported onto current main through the unified acquisition work.
- PR #154 client ENTITY bridge: superseded by merged PR #153 and selective follow-up in #156/#165.
- PR #180 Zone/packet fixes: superseded by rebased merged PR #182.
- PR #183 Evidence Search: superseded by rebased merged PR #184.

## 2026-10-01 surviving-branch reconciliation

The repository branch audit found **no remaining branch that should be merged into `main`**. The apparent ahead counts on the two feature branches are artifacts of rebased replacement work, not missing capabilities:

- `capture-evidence-search-modules` — 7 commits ahead / 114 behind at audit time. This was the head of closed PR #183, explicitly superseded by rebased PR #184, which merged the Evidence Search capability onto current `main`. **Do not merge; safe cleanup candidate.**
- `zone-3d-packet-input-fixes` — 23 commits ahead / 115 behind at audit time. This was the head of closed PR #180, explicitly superseded by rebased PR #182, which merged the intended Zone Editor, Server 3D Viewer and packet-input fixes onto current `main`. **Do not merge; safe cleanup candidate.**
- `noop-temp-do-not-use` — 0 commits ahead / 71 behind at audit time. Contains no unique work. **Safe cleanup candidate.**
- `noop-temp-do-not-use-2` — 0 commits ahead / 16 behind at audit time. Contains no unique work. **Safe cleanup candidate.**

Branch ancestry alone must not be interpreted as missing roadmap functionality when a branch was deliberately replaced by a rebased PR. For roadmap reconciliation, merged replacement PRs and current `main` behavior are authoritative.

---

# Roadmap maintenance rules

- Update this file whenever a roadmap-sized capability PR is merged.
- Re-run branch/PR reconciliation before treating a long-lived or diverged branch as missing work.
- Prefer **capability groups** over one bullet per PR; add PR numbers where they help trace provenance.
- Mark completion only from merged `main`, never from an open/stale branch.
- When a PR is superseded or transplanted, retain only the surviving merged capability and remove the obsolete implementation from current planning.
- Preserve observed capture/client/server/reference facts separately from inference and proposal layers.
- Keep fail-closed behavior and uncertainty visible; lack of evidence is not evidence of absence.
- Preserve `ROADMAP.md` as the historical implementation ledger rather than rewriting old chronology into current status.