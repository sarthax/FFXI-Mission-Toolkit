# Current Workbench Roadmap

Status: ACTIVE REWORK  
Last fully reconciled against merged PR and branch history: **2026-10-06**  
Authoritative repository: `sarthax/FFXI-Mission-Toolkit`  
Authoritative branch: `main`

This is the authoritative current planning and capability inventory for the Mission Toolkit / Workbench. It is organized by durable capability, not by the chronological order of individual pull requests.

`ROADMAP.md` remains the historical implementation ledger. `AUDIT_STATUS.md` remains a historical/implementation audit log. When older status text conflicts with this file, use this file plus merged `main` history.

## Status rules

- `[x]` = merged to `main` and covered by regression/CI or equivalent validation.
- `[~]` = substantial foundation exists, but the capability is intentionally incomplete or evidence-limited.
- `[ ]` = planned / not yet implemented.
- Closed PRs that were superseded, transplanted, or replaced are not roadmap capabilities.
- As of this reconciliation, Behavior Inspector, Feature Trace provider/closure work, native modern-LSB Nyzul support, Research contradiction/evidence deepening, protocol PR #545, and final Phase D source-layout ownership cleanup are merged into `main`; current `main` is the product baseline for these capabilities.

---

# 1. Core Workbench architecture

- [x] Canonical evidence/provenance model for source, feature, entity, implementation, dependency, capture evidence, findings, migrations, validation, packages, and research output.
- [x] Feature and Package remain distinct concepts.
- [x] `src/workbench/...` is the canonical implementation layout; mature editors, capture tooling, validation code, runtime bridges, application host, settings store, and related modules are package-owned while thin compatibility imports/launchers preserve older entry points.
- [x] Source Layout Regression protects packaged imports and editable-install behavior.
- [x] Shared shell navigation has top-level category menus plus persistent Sections navigation.
- [x] Global runtime context exposes the active named server environment without leaking credentials.

# 2. Server environments and runtime context

Merged October 3 work changed the Workbench from a family-only/single-root model to first-class named environments.

- [x] Named profiles: Live, Test, Dev, Backup, Other.
- [x] Profiles support LandSandBoat, Topaz, DSP, and compatible custom forks.
- [x] Settings is the canonical environment-management surface.
- [x] Profiles can be created, edited, enabled/disabled, activated, tested, and deleted.
- [x] Native server configuration remains authoritative for DB connection discovery.
- [x] Active environment is visible in the shared shell.
- [x] Generic/admin tooling resolves the active environment through the canonical runtime bridge.
- [x] Zone Editor, Item Editor, model catalog, Entity Profile, Character Editor, and generic Zone Plot paths consume named environments where appropriate.
- [x] Multiple same-family environments are preserved independently rather than collapsed by lineage.
- [x] Legacy Topaz/DSP paths remain only as bootstrap/fallback/reference compatibility roots.
- [x] LIVE-target editing requires explicit confirmation where the UI exposes mutation.
- [x] DSP/Topaz config inputs may be server root, `conf`, or native `map*.conf`; LSB settings paths are normalized to the canonical root.
- [~] Some older lineage-specific utilities still intentionally use explicit DSP/Topaz reference roots rather than the active admin environment.

# 3. Character Editor

The Character Editor is now a mature guarded administration surface across DSP / Topaz / LandSandBoat rather than an experimental viewer.

## Read / presentation

- [x] Schema-aware character overview across major row-backed and packed-state categories.
- [x] Dense responsive presentation with sticky header/tabs and a sticky changed-fields apply bar.
- [x] Friendly field labels, units, dropdowns for known enums, filtering, hide-zero, changed-only views, pagination, and tab counts.
- [x] Raw physical storage is demoted behind Advanced/collapsed presentation where semantic editors exist.
- [x] Inventory is grouped by container and optimized for current-state browsing.
- [x] Key Items, spells, abilities, weapon skills, titles, and visited zones default to owned/learned/set state with Browse All available.
- [x] Checkout-local mission/key-item catalogs for DSP/Topaz/LSB.
- [x] Legacy DSP mission/assault names resolve from `missions.lua` banner structure; mission value `65535` is shown as None.
- [x] Semantic merit catalogs:
  - LSB structured merit metadata where available;
  - DSP legacy merit catalog derived from checkout-local `sql/merits.sql` plus merit C++/header definitions;
  - lineage-local category/name/rank/cost/job metadata rather than substituting a modern server's definitions.
- [x] MariaDB date/time values are serialized safely at the HTTP boundary.

## Guarded mutation families

- [x] Inventory add, move, quantity, and remove across directly verifiable persistent containers.
- [x] Scalar character/job/stat/skill/point fields on explicit schema allowlists.
- [x] Learned spell learn/unlearn.
- [x] Blacklist add/remove.
- [x] Packed missions and key items.
- [x] Packed quests, Assault, Campaign, Eminence, abilities, weapon skills, titles, visited zones, and Blue Magic state where codec/schema evidence supports them.
- [x] LSB-only persistent administrative fields through explicit allowlists.
- [x] Every supported write path uses offline verification, preview/approval, stale-state recheck/fingerprint, explicit transaction handling, and audit recording.
- [x] Audit Undo covers supported row-backed, scalar, packed, spell, blacklist, inventory, and LSB-admin operations.
- [x] Character Editor DB connections default to autocommit for reads so preview/read operations do not leave an implicit transaction that breaks later explicit writes.

## Progression research integration

- [x] Mission/quest **State Surface** endpoint scans active-server Lua and exposes source-evidenced references to charvars, key items, items, events, mission/quest state, titles, gil/fame, and related hooks/source lines.
- [x] Character state is enriched against those references and literal guards are evaluated where possible.
- [x] UI exposes Trace Current/per-entry trace for mission and quest rows.
- [x] State Surface can hand off to existing Key Item, Variables, Inventory, and Unlock editors.
- [x] Mission trace regression in the State Surface pipeline was fixed in the October 3 usability pass.
- [x] Progression transition bundles group trigger/event, persisted preconditions, runtime-only requirements, state changes, rewards, removals/consumption, completion, next activation/transport, timers, source evidence, and `why blocked` reasoning.
- [x] Transition bundles expose conservative read-only projected results with known before-values only where character evidence resolves them; no mutation is performed or implied.
- [x] Concise progression assessment classifies the selected state as Ready, Waiting on runtime input, Blocked by persisted state, Inconsistent, Completed, No modeled next action, or Unavailable where the evidence supports it.
- [x] Persisted blockers can hand off to their guarded Character Editor surfaces while runtime-only requirements remain diagnostic.
- [x] The progression bundle/result/assessment contract is regression-covered on modern LSB and legacy DSP/Topaz flows, including trade-gated runtime requirements and completed prerequisite chains.
- [~] Continue expanding deterministic progression reasoning only where source/runtime evidence proves additional helper-generated or cross-feature behavior.

## Intentionally read-only

- [~] Status effects and effect timers.
- [~] Recast timers.
- [~] Pet IDs/runtime pet BLOB state.
- [~] Runtime disconnect/session state.
- [~] Unknown lineage-specific fields without a verified persistence contract.
- [x] Progression transition/result previews and assessments are explicitly diagnostic/read-only and do not add an automatic reset/advance write path.

These are deliberate safety boundaries, not generic missing editors.

# 4. Feature Trace / Implementation Path

Feature Trace is now a mature cross-source implementation/evidence navigator at a deliberate real-data testing boundary. Provider-native relationships are read-only navigation evidence and remain distinct from canonical graph truth. The combined workflow and evidence boundary are documented in `docs/workbench/BEHAVIOR_FEATURE_TRACE_GUIDE.md`; the closure matrix and current stopping point are documented in `docs/workbench/FEATURE_TRACE_CLOSEOUT_2026-10-04.md`.

- [x] Cross-source providers for SQL, LSB, Topaz, DSP, Client, Capture, Research, Validation, Package, and reference-wiki records.
- [x] Source-native wiring and bounded provider drill-down.
- [x] Entity identity bridging across server IDs, client ENTITY snapshots, captures, and client-build drift.
- [x] Fail-closed ambiguity for numeric collisions and conflicting identities.
- [x] Evidence Dossier and Implementation Path views.
- [x] Lua API → C++ binding/implementation evidence where source proves the relationship.
- [x] Runtime/capture drill-down to exact normalized observations and source provenance.
- [x] High-volume traversal bounds/truncation reporting.
- [x] Mission/quest State Surface extraction reused by Character Editor.
- [x] Focused Feature Trace modes generate/display provider-native relationship evidence without writing synthetic canonical graph edges.
- [x] Focused modes cover implementation, triggers, effects, dependencies, mission progression, runtime evidence, identity, diagnosis, and all-evidence navigation.
- [x] Deterministic server relationships include supported item-detail → base-item, spawn → group, group → pool, pet → pool, Blue Magic spell/skill, instance membership/entity, and exact reference-wiki claim-alignment paths.
- [x] `mob_droplist` rows are indexed with complete-row read-only composite identity because supported upstream schemas do not provide a stable primary key.
- [x] Deterministic drop-chain traversal supports **spawn → group → pool / drop rows → item** without creating canonical graph edges as a side effect.
- [x] Feature Trace branch reconciliation preserved unique drop-chain work by transplanting it onto newer `main` rather than merging a diverged branch wholesale; superseded alternate scenario UI work was deliberately excluded.
- [x] Executable trace benchmark contracts can verify mode, root kind, relationship concepts/count, and required generators; the NM benchmark proves end-to-end drop/item traversal.
- [x] `MAPPED` reference-wiki mappings can navigate to an exact indexed implementation target when `target_table + target_key` resolve uniquely; ambiguous/unresolved/duplicate targets fail closed.
- [x] Captures can navigate to the exact client identity snapshot for their recorded `client_build` only when one `identity_snapshots.version` matches; duplicate build snapshots fail closed.
- [x] Research sessions, Validation runs, and migrations can navigate from explicit stored canonical feature IDs to exact feature roots.
- [x] Research sessions can navigate from explicit stored entity roots to exact canonical entities.
- [x] Migration actions can navigate from explicit stored artifact IDs to exact canonical artifacts.
- [x] Generic Research/Validation `subject_id` closure requires exactly one canonical namespace match; cross-namespace ambiguity produces no link.
- [x] Provider→canonical closure remains presentation/navigation evidence only and does not persist synthetic canonical graph edges.
- [x] Workbench/Src Layout regressions cover wiki-target closure, capture→client-build closure, provider→canonical feature/entity/artifact closure, duplicate-target rejection, and cross-namespace ambiguity rejection.
- [~] Pause speculative provider expansion until real-object testing identifies concrete deterministic gaps. A future phase may add reverse discovery from canonical nodes back to provider records under the same exact-ID/fail-closed rules.

# 5. Behavior Inspector / scripted behavior

Behavior Inspector is at closeout state as a mature evidence-first scripted-behavior inspector. Its durable capability and safety contract is documented in `docs/workbench/BEHAVIOR_INSPECTOR_CLOSEOUT.md`; its relationship to Feature Trace is documented in `docs/workbench/BEHAVIOR_FEATURE_TRACE_GUIDE.md`.

## Extraction

- [x] Generic Lua behavior model for NPCs, mobs, doors/objects, zone scripts, instances, timers, callbacks, state, conditions, effects, shared helpers, entity references, environment checks, and runtime-relative IDs.
- [x] Named state reads/writes across player/entity/instance/server scopes.
- [x] Verified literal state transitions where read/write identity and guards prove the relationship.
- [x] Shared `xi.<module>.<function>` helper resolution with exact/ambiguous/unresolved states and one-level impact expansion.
- [x] Bare-global helpers included only when reachable from modeled hooks.
- [x] Timer, queue, and listener callbacks retain explicit ownership, source spans, and callback-specific behavior while the complete technical evidence remains available for audit.

## End-user presentation

- [x] **Clarified Flow is the default view**, with Plain Behavior and Technical Graph preserved as adjacent views.
- [x] Clarified Flow preserves source-proven branch structure and exposes event lifecycle identity, stage → event → next-stage summaries, verified stage-value continuity, and navigation back to exact stage/branch evidence.
- [x] Cross-hook event identity and stage continuity remain explicitly non-causal/`UNPROVEN` unless independent runtime evidence proves ordering.
- [x] Behavior chains are grouped as **Trigger → Requirements → Actions / Events → Results / State Changes**.
- [x] Common Lua/API concepts are translated into end-user language while preserving the technical identity as secondary evidence.
- [x] Plain Behavior uses one backend-generated evidence-preserving projection contract consumed by the browser rather than a second semantic implementation.
- [x] Internal rule/helper-call/callee plumbing is collapsed while source-proven guards, helper identity/inputs/effects, state, targets, and exact technical node IDs remain available for drill-down.
- [x] Callback flows are partitioned: parent hooks show scheduling/registration, callback triggers own their downstream effects, and source-span filtering removes duplicate callback-body presentation without deleting Technical Graph evidence.
- [x] Concise summaries use only extracted graph labels, relationships, and proven source spans; unsupported runtime semantics remain unknown rather than inferred.
- [x] Plain Behavior cards drill into the same exact node metadata/evidence rather than creating a separate truth model.
- [x] Technical Graph remains available as the detailed evidence/debug view.
- [x] Technical graph supports wheel zoom, pointer-centered zoom, drag-pan, Zoom +/- controls, Fit, Reset View.
- [x] Selecting a node highlights upstream prerequisites and downstream effects as a directed causal path while dimming unrelated sibling branches.
- [x] Node details live in a persistent right-side inspector with independent scrolling, collapse/expand, and responsive stacked fallback.
- [x] Behavior Inspector and Feature Trace now have an explicit workflow boundary: Behavior explains source-proven Lua behavior; Feature Trace explains cross-source implementation/evidence relationships.
- [x] Further support for new/dynamic Lua idioms is additive evidence expansion, not unfinished foundational Behavior Inspector work; unsupported semantics remain raw/generic evidence rather than guessed behavior.

# 6. Mission / quest extraction

- [x] Generic mission/quest state-machine representation with guarded transitions, ALL/ANY gates, lifecycle effects, branch/convergence modeling, implementation gaps, and source provenance.
- [x] Branch-aware Lua extraction and structurally discovered completion/helper behavior.
- [x] Key-item, item, trade, event, timer, zone, mission/quest prerequisite, reward, teleport, and progression-state extraction across supported LSB DSL patterns.
- [x] Cross-feature prerequisite closure with explicit unresolved symbols.
- [x] Stress metrics and tested complex WotG mission/quest chains.
- [x] Reusable multi-zone progression and minigame/state-machine frameworks.
- [x] Transition bundles combine persistent state writes with event side effects, rewards/removals, completion/next-state activation, runtime requirements, projected outcomes, and blocker reasoning for Character Editor diagnosis.
- [x] Legacy DSP/Topaz handler normalization feeds the same progression-inspector contract for supported patterns.
- [~] Continue extracting helper-generated or highly dynamic transitions only when deterministic evidence supports them; do not infer runtime ordering from static mentions alone.

# 7. Entity / Event / CSID research

- [x] Entity Profile/Dossier aggregates SQL wiring, Lua behavior, captures, client identity, event/dialog references, and implementation gaps.
- [x] Conservative server/client CSID reconciliation.
- [x] Variable-length EVENT decoding for bounded statically provable formulas.
- [x] EVENT flow preserves work-area/options/captured parameters without assigning unsupported gameplay meaning.
- [x] Entity research handoffs connect Feature Trace, Behavior Inspector, Events/CSIDs, captures, and implementation diagnostics.

# 8. Character/client DAT assets and Item Editor

- [x] DAT Inspector and client resource inspection.
- [x] Client ENTITY identity extraction and portable client snapshots.
- [x] Model catalog/viewer and zone/model correlation.
- [x] Item Editor backend is packaged under `src/workbench/editors/items` with root compatibility imports.
- [x] Item DAT tooling is packaged while preserving backup/journal semantics.
- [x] Item Editor consumes named active server environments.
- [x] Item Editor/related client tools preserve SQL/client reconciliation, validation, backups, constrained edits, and rollback-oriented patch workflows.
- [x] Persistent **client item DAT cache**:
  - default lazy extract-on-first-use;
  - optional one-time Build All action in Settings;
  - parsed item metadata stored in SQLite;
  - icons stored as normal PNG files;
  - client-install/snapshot isolation;
  - source DAT size/mtime validation and selective regeneration;
  - cache clear returns automatically to lazy extraction.
- [x] Character inventory uses the cache-backed icon path and defers icon URLs for collapsed containers.
- [~] Extend the generic Client Asset Cache concept beyond item metadata/icons to additional reusable models/textures/maps/assets only where parser semantics are proven.

# 9. Zone Editor / spatial viewers

- [x] Modern Zone Editor under packaged editor source layout.
- [x] Server-aware editing through named environment context.
- [x] Spatial entity/path visualization, labels/IDs/positions/search, navigation helpers, model integration, bookmarks/templates, and review/bulk workflows.
- [x] Capture 2D/3D viewer routes and Zone Editor handoffs are covered by live-app route regressions.
- [x] Model catalog failures from unrecognized gear-slot indices no longer abort the complete catalog.
- [x] Nyzul Editor preserves explicit DSP/Topaz legacy-layout handling while routing modern LandSandBoat checkouts through the native adapter.
- [x] Native modern-LSB Nyzul adapter parses `floor_generation.lua`, current objective/layout selection, YAML-backed entity tables, native boss/Rampart positions, shared spawn pools, and fail-closed unsupported mappings; merged in PR #544.

# 10. Capture ingestion and evidence

## Ingestion families

- [x] Windower PacketLogger / PacketViewer and z16-style sources.
- [x] Ashita Packeteer.
- [x] MalRD PacketDB packets plus CHATLOG.
- [x] NPCLogger SQLite/Lua/Widescan.
- [x] EventView, ActionView, HPTrack, IDView, KITrack, LevelRange, AttackDelay, PathLog.
- [x] MissionTrack, ShopStock, GuildStock, SpawnTrack, WeatherTrack, CraftTrack, CheckParam, POITrack, ConquestTrack, PriceLog/findPrice, StatTrack and related historical structured formats.
- [x] Windower Logger chat files.
- [x] PCAP / PCAPNG network captures.
- [x] Video/OCR evidence remains separate from raw protocol evidence.

## Integrity/search/correlation

- [x] Content-addressed source manifests and exact parser/table lineage.
- [x] Duplicate/session-overlap detection and clock-continuity diagnostics.
- [x] Exact row/block/SQLite provenance and source viewer with hash verification.
- [x] Safe parser-specific rebuild rules.
- [x] Cross-source packet correlation with verified/ambiguous states rather than fuzzy automatic merging.
- [x] Capture Data Explorer for structured/raw datasets.
- [x] Modular Evidence Search across events/dialogue, protocol, entities, battle/actions, items/KIs, shops, crafting, chat/text, movement/spatial, and environment/world state.
- [x] Campaign/session manifest import support and message-ID shift handling.
- [x] Capture spatial JSON routing bug fixed and plot viewer routing guarded by live-app regression.
- [x] Evidence-backed lobby/search/map stream classification and framing from PR #545 is part of the merged baseline, including fail-closed unknown TCP handling and source-backed handoff evidence.
- [~] Continue lobby/world/search protocol research only where representative real captures justify additional decoder certainty or semantics.

# 11. Packet / protocol research

- [x] Manual and bulk packet decode.
- [x] Packet Viewer-style presentation/handoffs.
- [x] Packetlyzer reference DB improvements including XiPackets-named opcodes and corrected verified field offsets.
- [x] PCAP/PCAPNG frame parsing and bidirectional TCP reconstruction with gaps/retransmissions/conflicts preserved.
- [x] Conservative lobby TCP classification/framing/decoder foundation.
- [x] PR #545 merged evidence-backed lobby/search/map classification, source-backed search framing/crypto evidence, strict same-flow sequencing, non-AH response parsing, exact UDP map handoff, and conservative endpoint/session diagnostics without guessing unknown protocol semantics.
- [~] Validate and extend decoder coverage against representative real captures; preserve unknown/ambiguous classifications when evidence is insufficient.

# 12. Video / OCR / temporal evidence

- [x] YouTube/video OCR workflows.
- [x] Saved screen/preprocessing profiles for known overlay families.
- [x] Cross-frame OCR consensus and packet-symbol-assisted correction with raw OCR preserved.
- [x] Capture/video timestamp alignment using explicit anchors and offset/drift diagnostics.
- [x] Screenshot/key-event/note evidence with provenance.

# 13. Research Sessions and wiki/reference evidence

- [x] Persistent Research Sessions with provider/model, permissions, budgets, timeout, replay, tool transcripts, evidence IDs, proposals, and final reports.
- [x] Local Ollama support without silent provider fallback.
- [x] Contradiction browsing across canonical findings, snapshots, and research proposals.
- [x] Evidence-backed contradiction dossiers group existing records into explicit sides with value/status/confidence/source-snapshot provenance, conservative completeness states, ResearchSession scoping, truncation visibility, and exact Feature Trace handoffs; merged in PR #546.
- [x] BG Wiki / FFXIclopedia claim-level alignment and conflict detection with provenance.
- [x] Reference Evidence Detail exposes canonical claim provenance and exact claim/mapping Feature Trace handoffs without duplicating mapped-target closure logic.
- [x] Dual-wiki `REFERENCE_CONFLICT` findings render BG Wiki vs FFXIclopedia side-by-side from importer-preserved claim IDs/excerpts while retaining `REFERENCE_ONLY` semantics and selecting no winner; merged in PR #547.
- [x] Feature Trace can close exact `MAPPED` reference-wiki targets into indexed implementation rows when target identity resolves uniquely.
- [~] Additional claim-to-implementation or provider-specific presentation should be driven by real-data gaps rather than inferred mappings; the planned contradiction/evidence deepening work is otherwise complete.

# 14. Package / migration / validation

- [x] Dependency-aware package planning and scope review.
- [x] Conditional dependencies remain reviewable instead of silently becoming mandatory.
- [x] Patch-plan drift checks, approval states, file apply journals, and rollback.
- [x] Validation runs tied back to canonical evidence.
- [x] Feature Trace can navigate explicit Research/Validation/Package feature/entity/artifact references back to exact canonical nodes without creating graph edges.
- [x] Source/target conversion support where deterministic and audited.
- [x] Phase D packaging moved mature root implementations into logical `src/workbench/...` homes while preserving intentional compatibility imports/launchers.
- [x] Final Phase D source-layout ownership cleanup is complete: the settings store and application host are package-owned, historical root `settings.py` and `gui_server.py` compatibility surfaces are retired, and Workbench/Src Layout/Character Editor regressions cover the final boundary.

# 15. CI / regression safety

- [x] Workbench Regression suite.
- [x] Src Layout Regression suite.
- [x] Dedicated Character Editor Regression suite, including pytest fixtures and executable regression scripts.
- [x] Focused GUI/client snapshot/research/DAT inspector jobs.
- [x] Live-app route regressions for sensitive routing surfaces.
- [x] Character Editor progression regressions cover modern LSB and legacy DSP/Topaz transition-bundle, projected-result, assessment, and UI contracts.
- [x] Behavior Inspector regressions cover extraction, complex state/event flows, callbacks, shared helpers, Clarified Flow/Plain View projection, backend/UI contract parity, stage/event lifecycle contracts, and source-layout service boundaries.
- [x] Feature Trace regressions cover deterministic provider relationships, fail-closed ambiguity, focused modes, executable scenario contracts, NM drop/item traversal, wiki→implementation closure, capture→client-build closure, and provider→canonical feature/entity/artifact closure without synthetic canonical edges.
- [x] Application-host/settings changes are included in Character Editor/server-admin regression path coverage after the final Phase D migration.
- [x] Documentation reconciliation should occur after major multi-PR feature batches rather than allowing README/roadmap drift to accumulate again.

---

# 16. Auction House administration and Economy BI

Operator summary: `AUCTION_HOUSE_CAPABILITY_STATUS.md`. Economy detail: `AUCTION_HOUSE_ECONOMY_INTELLIGENCE.md`.

- [x] Single hub at `/auction-house` (Economy, Items, Sellers, Restock, Inbox, plus Seeder/Presets/Activity/Cleanup/Rewards); legacy page URLs forward to it.
- [x] Write flags are settings-backed (Settings -> Auction House) with an env-var override; the Help page lists every requirement and the blocked code it produces.
- [x] Shared action drawer for Buy/Return/Restock/Inbox with typed profile-name confirmation, backdrop, and a Close button that is not hidden under the site header.
- [x] Inbox delivery supports gil as well as items.
- [x] Economy Intelligence: KPI strip with prior-period deltas and sparklines, Market activity chart, Price movers with thin-evidence flagging, "Where to look" queues (needs supply, oversupplied, stagnant, seller concentration), category sell-through/time-to-sale, player and account lookup.
- [x] Daily snapshots of supply and sell-through in the toolkit SQLite DB (background loop plus "Record now"); Supply history chart.
- [x] Baselines: each snapshot metric compared with the median of its previous snapshots (usual range = median +/- 2 MAD); reports "building" until 7 earlier snapshots exist.
- [x] Admin-impact overlay: completed toolkit actions (seed, restock, Admin Buy, return, rewards, player listing/purchase) marked on the activity chart and listed with item median price 7 days before/after. Pointer, not proof.
- [x] Test-data seeding in the Seeder tab: history, scenarios (monopolised/stagnant/flooded), clear. Test profile only, gated, confined to fake sellers 990000-990024.
- [x] Items page: Recent Sales stacked above uncapped Active listings, price-markup chip vs recent-sale median, listing filters (text/price/type/markup) that scope bulk actions, active seller/item links with Back.
- [x] Supply/sell-through deltas on the Economy supply card (vs snapshot ~7d earlier). Sellers page: markup chip on listings, 30-day sales, gil, sell-through and median time-to-sell per seller, Recent sales stacked above uncapped Active listings, filters, item links with Back.
- [x] Economy anomaly detection (Anomalies card): price shifts, volume spikes, over/underpriced listings, seller listing floods, each against its own history (median/MAD). Restock and Inbox share a multi-character picker (browse, type name/id, remove chips); Restock spreads listings across several sellers.
- [x] Synthetic category seeding consolidated into Restock ("Add a whole category", multi-seller, same preview/confirm path); the Seeder panel now points there. Player-backed listing and Market history stay in the Seeder.
- [x] Presets: 18 built-in Restock/Cleanup presets, editable in a native Presets tab with Edit/Back; Restock uses a configurable default seller (AHRestock, synthetic id in 990000-990999) when no character is picked.
- [x] Native Cleanup tab with seller/item search pickers, preset loading and an empty-state hint showing oldest listing age.
- [x] Items status toggle (Active / Unlisted / All) backed by `/auction-house/console/catalog.json`; unlisted items show sales history.
- [x] Buyers tab (`buyers.json`, `buyer.json`; `buyer_stats.py`, unit-tested): per-buyer spend, overpaid purchases vs item median (>=50%), gil refund of the overpay via the rewards flow. Buyers keyed by name (DSP sold rows have no buyer id); refund needs a `chars` row.
- [x] "Buy as..." (player purchase) folded into Items/Sellers listing rows; Listing Manager kept only as a legacy view.
- [x] Fixed the confirm drawer (missing `dwConfName` element) that blocked Buy/Return/Restock/refund drawers from opening.
- [ ] KPI prior-period deltas for supply and sell-through (needs more than one day of snapshots).
- [ ] Anomaly detection and forecasting (deliberately deferred until snapshot history exists).
- [ ] Live write tests for restock, Buy, Return, MyISAM purchase and gil delivery on a real Test server.
- [ ] "All characters on this account" filter.

---

- [x] Arbitrage tab (underpriced listings, post-for-profit, vendor loops) with a vendor-ratio Cleanup rule and two built-in presets; restock presets accept include/exclude item lists; More tools regrouped; Inbox campaigns now record the chosen template.
- [x] Synth & Crafting module at `/synth` (`server_admin/synth`): schema-adaptive over `synth_recipes` for DSP/Topaz/LSB, ingredient availability + missing report, audit, SQL create/edit/delete preview per flavor, export/port, gated Test-write apply.
- [ ] Open: vendor-loop data exploit (shop prices below BaseSell) is documented but not fixed; synth audit cannot see gathering/fishing/quest sources.


# 17. Workbench UI Framework / Unified Module Layout

The shared `base.html` shell already unifies global navigation, workspace context, theme variables, and common dense UI primitives. The next UI architecture phase should unify **module composition and geometry** so independently developed tools stop drifting in width, spacing, panel sizing, controls, and interaction structure.

- [x] Add a shared Workbench page wrapper above `base.html` for module-level layout contracts rather than navigation/chrome alone.
- [x] Define a small set of canonical page archetypes:
  - Browser — search/filter + result list/table + pagination;
  - Detail/Dossier — summary/header + evidence/detail sections;
  - Workbench/Inspector — navigator + primary workspace + inspector;
  - Editor — navigator + editable surface + properties/actions;
  - Dashboard/Console — status/KPI/action strip + panels/tables.
- [x] Standardize page header/title/status/action regions, help/about affordances, read-only/write-capable badges, empty/loading/error states, and shared filter/search rows.
- [x] Standardize one-, two-, and three-pane layout primitives including reusable sidebar/inspector widths, panel gaps, and responsive stacking; scrolling/sticky behavior remains workspace-specific until migrated.
- [ ] Replace repeated page-local geometry such as arbitrary `main` padding, max-widths, toolbar heights, and control sizing with shared Workbench design tokens.
- [x] Define shared tokens for page padding, toolbar/control height, panel gap, table row density, sidebar sizes, inspector width, and responsive breakpoints.
- [ ] Keep feature-specific visualization/layout behavior where required (Zone Editor canvas, Packet Viewer byte presentation, Auction House economy surfaces, etc.) while removing feature-specific reinvention of basic UI geometry.
- [ ] Convert existing `dense-toolbar`, `dense-panel`, tabs, cards, chips, tables, forms, and inspector patterns into documented reusable primitives where their contracts are already stable.
- [x] Add a UI/template contract regression: new module pages must use the standard Workbench wrapper/archetype or explicitly opt into the legacy/custom allowlist with a reason.
- [ ] Inventory current templates against the archetypes and migrate them systematically by workspace rather than opportunistically when features happen to be edited. Foundation adopters: SQL Browser (Browser), Validation (Dashboard), and Research Evidence (Detail). Research workspace migration is complete: Sessions, Contradictions, Gaps, Session Detail, and Evidence now use the shared wrapper. Validation workspace migration is complete: Dashboard, Runs, Run Detail, and Live Target now use the shared wrapper. Packages workspace migration is complete: Library, Scope Review, Create Package, and Review & Readiness now use the shared wrapper. Backport workspace migration is complete: Package Workflow, Lua Converter, SQL Converter, and Binding Reference now use the shared wrapper. ID Drift workspace migration is complete: Overview and Category Detail now use the shared wrapper. LLM workspace migration is complete: Assistant and Call Detail now use the shared wrapper. Events / CSID workspace migration is complete: Browser and Event Detail now use the shared wrapper. Wiki Compiler migration is complete and now uses the shared Workbench wrapper. Capture Path Plot migration is complete: Single Path and All Paths now use the shared wrapper while retaining specialized visualization geometry. Client Overview migration is complete and now uses the shared Dashboard wrapper. Binary Inspector migration is complete and now uses the shared Workbench wrapper. Behavior Inspector migration is complete and now uses the shared Workbench wrapper. Dialog Drift overview migration is complete and now uses the shared Dashboard wrapper. Per-zone Dialog Drift report migration is complete and now uses the shared Detail wrapper. Roadmap page migration is complete and now uses the shared Dashboard wrapper. Help page migration is complete and now uses the shared Detail wrapper. System confirmation/status pages (backup delete/restore, rebuild, shutdown/restart) are migrated to the shared wrapper. Entity Gaps diagnostic browser migration is complete and now uses the shared Browser wrapper. Key Items browser migration is complete and now uses the shared Browser wrapper. Assault Missions browser migration is complete and now uses the shared Browser wrapper. Zones browser migration is complete and now uses the shared Browser wrapper.
- [ ] Preserve behavior during migration; visual/layout normalization should not silently change feature semantics, write safety, evidence meaning, or route ownership.
- [ ] Perform this phase **after the active root-cleanup/bootstrap retirement work** so cross-cutting template refactors do not collide with repository-structure cleanup.


# Highest-value next work

1. **Complete active root cleanup / bootstrap retirement** — finish the bounded compatibility-shim, standalone-script, workspace/resource, and final root-allowlist work tracked in `ROOT_CLEANUP_STATUS.md` without reintroducing import/path coupling.
2. **Workbench UI Framework / Unified Module Layout** — after root cleanup, introduce the shared page wrapper, canonical page archetypes, design tokens, panel/layout contracts, and template regression described in section 17; then migrate existing modules workspace-by-workspace.
3. **Feature Trace real-data validation** — exercise the current closure model against representative NPC/entity, mission, drop-chain, capture/client-build, reference mapping, and migration/package cases. Implement more Feature Trace wiring only when testing exposes a deterministic gap.
4. **Protocol real-capture validation** — exercise the merged PR #545 lobby/search/map classifier and decoder coverage against representative captures; add semantics only when source/structural evidence proves them and preserve fail-closed unknowns.
5. **Client Asset Cache expansion** — only for proven asset families where reusing pre-extracted data materially improves interactive tools.
6. **Broader client/server synchronization and named-system reconstruction** — extend deterministic comparison/validation workflows without weakening provenance rules.
7. **Auction House live-write validation** — run the remaining restock, Buy, Return, MyISAM purchase, and gil-delivery tests against a real Test server before treating those mutation paths as operationally closed.

A future Feature Trace development phase may add **reverse discovery** from a canonical feature/entity/artifact back to Research, Validation, Package, Capture, or reference records that explicitly point to it. Treat that as a distinct phase after real-data testing, not unfinished cleanup.

A future source-layout/bootstrap phase may retire root compatibility launchers and the root `workbench` bootstrap after every supported setup/start/CI path installs the package or explicitly uses `src`. That is intentionally separate from completed Phase D implementation ownership.

# Documentation map

- `README.md` — durable product overview and quick start.
- `docs/workbench/ROADMAP_CURRENT.md` — this file; authoritative current capability/status inventory.
- `docs/workbench/RECENT_CHANGES_2026-10-03.md` — detailed recent reconciliation and merged-change summary through the prior batch.
- `docs/workbench/CHARACTER_EDITOR_CLOSEOUT.md` — current Character Editor safety/capability contract.
- `docs/workbench/BEHAVIOR_INSPECTOR_CLOSEOUT.md` — current Behavior Inspector capability/evidence/closeout contract.
- `docs/workbench/BEHAVIOR_FEATURE_TRACE_GUIDE.md` — combined Behavior Inspector / Feature Trace workflow, evidence boundaries, and October 4 implementation summary.
- `docs/workbench/FEATURE_TRACE_BRANCH_RECONCILIATION_2026-10-04.md` — branch-level Feature Trace reconciliation and drop-chain transplant record.
- `docs/workbench/FEATURE_TRACE_CLOSEOUT_2026-10-04.md` — current Feature Trace closure matrix, fail-closed rules, regression coverage, and testing boundary.
- `docs/workbench/PHASE_D_ROOT_CLEANUP_STATUS.md` — final Phase D source-layout ownership closeout and remaining compatibility/bootstrap boundary.
- `docs/workbench/UI_FRAMEWORK.md` — shared module wrapper, canonical archetypes, geometry tokens, migration rules, and template contract.
- `docs/guides/SETUP.md` — current user setup and named environment configuration.
- `docs/guides/TOOLING_OVERVIEW.md` — living tooling/component overview.
- `docs/workbench/AUCTION_HOUSE_CAPABILITY_STATUS.md` — Auction House operator summary.
- `docs/workbench/ROADMAP.md` — historical implementation ledger.
- `docs/workbench/AUDIT_STATUS.md` — historical implementation/audit notes.