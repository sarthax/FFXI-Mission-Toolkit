# GUI Information Architecture

Status: proposed navigation and workspace mapping; **no GUI routes or templates are changed by this document**.

Source of truth for current route coverage: `docs/workbench/GUI_ROUTE_MAP.json`.
The current branch registers **134 FastAPI routes**, and every route has exactly one canonical home.

## Goals

1. Preserve every current tool and route.
2. Give every tool one canonical home, while allowing contextual entry points from other workspaces.
3. Keep **Captures** first-class and prominent.
4. Keep mutation/editor workflows distinct from read-only analysis.
5. Expose the new Workbench backend without turning the GUI into a list of low-level commands.
6. Preserve existing specialized/legacy tools until a replacement is proven feature-complete.

## Proposed top-level navigation

### Home / Project

Purpose: current project context, source/target snapshot context, source health, recent work, blockers, and shortcuts.

Canonical content:
- Project/dashboard landing page.
- Current source and target snapshots.
- Server/client/capture source health.
- Recent analyses, validations, packages, and captures.
- Help and roadmap.

Existing routes:
- `/`
- `/help`
- `/roadmap`

Contextual links:
- Data/index rebuild controls remain visible from Home, but their canonical home is Settings > Sources & Indexes.

### Features

Purpose: answer “what implements this feature, what does it require, and what is missing?”

Primary future views:
- Feature Explorer.
- Feature Checker.
- Feature Trace.
- Capability requirements and observations.
- Implementation surfaces across Lua, SQL, C++, packets, client, runtime.
- Evidence-backed gaps and contradictions.
- Missions/quests/NPC/item/system entry points.

Existing GUI seed:
- `/missions`

New GUI capabilities to expose:
- canonical Feature Checker;
- bidirectional Feature Trace;
- FeatureSurface comparison results;
- capability requirement/observation detail;
- implementation and validation dimensions;
- feature candidates from packet/capture/entity roots.

Contextual entry points:
- Captures → feature candidates / trace.
- Server entity/event/packet → related features.
- Client DAT/binary evidence → related features.
- Backport & Migration → analyze selected feature.

### Backport & Migration

Purpose: answer “can this move from source to target, what changes, and what blocks it?”

Subsections:
- Migration Analyzer.
- FeatureSurface Differences.
- Schema / representation drift.
- Binding compatibility.
- ID/content collision analysis.
- Lua conversion.
- SQL conversion.
- Route support matrix.
- Migration actions and blockers.
- Legacy Backport Package workflow.

Existing routes:
- `/iddrift`, `/iddrift/{slug}`
- `/zone/{zone_name}/drift`
- `/backport/lua-convert` GET/POST
- `/backport/sql-convert` GET/POST
- `/backport/bindings`
- `/backport/package` GET/POST

Disposition:
- ID Drift and Zone Drift become views inside the broader Migration Analyzer.
- Lua/SQL converters remain directly reachable specialist tools.
- Binding page becomes one view over the newer binding compatibility engine.
- Existing package workflow remains a **legacy compatibility workflow** until the new Packages workspace completely covers it.

New GUI capabilities to expose:
- migration backend support matrix;
- normalized logical-schema comparison;
- collision.inspect / migration.collisions;
- migration plan explanation;
- dependency-aware action order;
- MANUAL_REQUIRED / BLOCKED reasons;
- generated proposal and reshape findings.

### Captures

Purpose: first-class runtime evidence workspace. Captures answer **what happened**, independent of whether static implementation proves why.

This remains a top-level navigation item and is expected to grow substantially.

Subsections:
- Capture Library.
- Import / Ingest.
- Capture Detail.
- Metadata, tags, annotations.
- Entity/NPC observations.
- History/state changes.
- NPC and player paths.
- Actions / skills / animations.
- HP observations.
- Events / message-or-event IDs.
- Key item events.
- Attack delay observations.
- Raw packets.
- Packet/event timeline.
- Data query/export.
- Visual path/zone plotting.
- Search and correlation.
- Capture Backtrace.
- Feature/entity/packet correlation.
- Future capture comparison and runtime analysis.

All existing `/captures*` routes remain canonical here.

Contextual entry points:
- Captured entity → Server > Entity.
- Captured packet → Server > Packets.
- Captured model → Client > Model Viewer.
- Capture → Features > Feature Trace/candidates.
- Capture → Validation.
- Capture → Tools > Research.

Important separation:
- Captures record observations.
- Validation decides whether observations satisfy expected behavior.
- Server/Client views describe implementation evidence.

### Server

Purpose: inspect server-side source/data independently of a migration or feature.

Subsections:
- Items & Key Items.
- Entities.
- Zones.
- Zone 3D Viewer.
- SQL / Logical Data.
- Dialog / Text.
- Events / CSID.
- Packets / Protocol.
- Lua/API surfaces.
- Bindings.
- C++ symbols/functions.
- Enums/constants.
- Build targets.
- Logical schema coverage.
- Data Quality / Gaps.

Existing canonical routes include:
- `/items*`
- `/entity*`
- `/dialog`
- `/keyitems`
- `/zones`
- `/zones/{zoneid}/view3d*`
- `/gaps`
- `/sql`
- `/events*`
- `/packets*`

New GUI capabilities to expose:
- Topaz/DSP/LSB/Topaz-Next/custom-fork adapter identity;
- logical-record views beside physical rows;
- cross-profile schema coverage;
- C++ function/class/enum/binding/build relationships;
- packet handler graph;
- snapshot capability observations.

### Client

Purpose: client-side DAT, EXE/DLL and capability evidence.

Subsections:
- Client Overview / Build.
- Dialog Drift (`/dialogdrift`): read-only cross-zone drift table with inferred per-zone offsets.
- Research Gaps (`/researchgaps`): read-only list of what the graph cannot answer yet, with next-action recommendations.
- DAT Inspector. (implemented, read-only: `/datinspector`)
- Client ↔ Server Item Comparison.
- Model Viewer.
- EXE/DLL Binary Inspector. (implemented, read-only: `/binaryinspector`)
- Binary Diff.
- Strings / Imports / Exports / Sections.
- Address/Xref Evidence.
- Function Candidates.
- FTABLE/VTABLE evidence.
- Client capability observations.

Existing routes:
- `/modelviewer`
- `/modelviewer/resolve.json`
- `/modelviewer/dat`

New GUI capabilities to expose:
- generic read-only `ItemDatAdapter`;
- core client/server field bindings;
- snapshot-scoped client DAT capability records;
- `client.binary-info`;
- `client.sections`;
- `client.imports`;
- `client.exports`;
- `client.string-search`;
- `client.address-evidence`;
- `client.binary-diff`;
- `client.byte-search`;
- `client.xrefs`;
- `client.function-candidates`.

Mutation boundary:
- DAT editing is **not** folded into Client Inspector.
- Item/DAT mutations remain under Tools > Editors > Item Editor.

### Validation

Purpose: answer “does the target satisfy the expected state/behavior?”

This is a new primary workspace. Existing validation logic is backend-first and currently lacks a consolidated GUI home.

Subsections:
- Validation Dashboard.
- Validation Runs.
- Validation Results by dimension.
- Live Target DB Validation.
- Capture / Runtime Validation.
- Package Validation Requirements.
- Client/Server comparison validation.
- Contradictions / Missing / Unknown.
- Validation history.

New GUI capabilities to expose:
- canonical `ValidationRun`;
- canonical `ValidationResult`;
- validation suite orchestration;
- read-only live target validation;
- target-snapshot capability status;
- runtime/capture validation;
- validation dimensions kept independent.

Contextual entry points:
- Feature → validations.
- Capture → validate against expectation.
- Package → validation requirements.
- Server logical record → live target check.

The specialized `backport_sql_live_check.py` remains preserved as a diagnostic/specialized tool rather than being removed.

### Packages

Purpose: review and deliver migration artifacts after analysis.

This is a new primary workspace.

Subsections:
- Package Library.
- Package Review Summary.
- Manifest / Contents.
- Generated Artifacts.
- Provenance / Hash Journal.
- Validation Requirements.
- Collision / Blocker Summary.
- Patch Preview.
- Approval State.
- Apply Readiness.
- Apply Journal.
- Rollback.

New GUI capabilities to expose:
- dependency-aware package plan;
- package manifest;
- converter preflight;
- package assembly;
- cohesion verification;
- generated target artifacts;
- proposal-only artifacts;
- patch plan and drift gate;
- approval linkage;
- apply readiness;
- patch lifecycle;
- package review summary;
- reversible file apply/rollback journal.

Legacy relationship:
- current `/backport/package` remains available under Backport & Migration until this workspace replaces its user-facing coverage.

### Tools

Tools is an intentional home for focused utilities. It is **not** a dumping ground: every tool has a named subsection and contextual links from its related workspace.

#### Tools > Research

Existing:
- `/llm*`
- `/wiki*`

Future:
- evidence-aware research sessions;
- graph search/trace;
- reference search/compare;
- bounded source search/read;
- typed Workbench research tools;
- proposal/research audit trail.

The current LLM UI is marked REWORK, not removed.

#### Tools > Editors

##### Zone Editor

All `/zoneplot*` routes remain here.

Capabilities preserved:
- server selection;
- zone data;
- reachability/navmesh;
- mesh/cache;
- entity position editing;
- animation editing;
- entity delete/add;
- catalogues;
- drop editing;
- SQL sync;
- snapshots/backups/restore.

Contextual entry points:
- Server > Zones.
- Captures > Paths / entities.
- Backport & Migration.

##### Item Editor

All `/itemedit*` routes remain here.

Capabilities preserved:
- search and item detail;
- item create/update/delete/restore;
- server item tables;
- mods / pet mods / latents;
- bitmask/mod/pet/latent metadata;
- client DAT target selection;
- live vs Xi-Pivot mode;
- DAT backups/restore;
- Xi-Pivot manifest/export;
- clone template.

Contextual entry points:
- Server > Items.
- Client > DAT Inspector.
- Backport & Migration.

#### Tools > Lookup & Decode

Planned homes for direct utilities that do not need full workspace screens:
- entity/NPC ID decoding;
- zone/local-index decoding;
- model/DAT resolution;
- packet/opcode decode;
- DAT path lookup;
- ID conversion helpers.

Some are currently embedded in larger pages/CLIs and should be exposed as compact tools rather than duplicated.

#### Tools > Diagnostics

Planned homes:
- binding audit;
- Lua sanity checks;
- schema coverage;
- specialized live SQL checker;
- package diagnostics;
- binary diagnostics;
- index/source health.

Diagnostics should link back to the canonical entity/feature/migration/validation result when one exists.

#### Tools > Specialized

Existing:
- Nyzul viewer/editor support via `/nyzul*`.

Future specialized tools remain visible here until/unless they mature into first-class system packages.

### Settings

Purpose: configuration and maintenance, not analysis.

Subsections:
- General.
- Sources & Indexes.
- Server roots.
- Client install/build.
- Graph/capture/reference databases.
- Live DB configuration.
- Xi-Pivot / output paths.
- Appearance.
- External tools.
- Backups & Recovery.
- Application restart/shutdown.

Existing routes:
- `/settings` GET/POST
- `/rebuild/{source}/confirm`
- `/rebuild/{source}`
- `/install/{tool}`
- `/theme/toggle`
- `/backup/*`
- `/shutdown`
- `/restart`

## Canonical-home versus contextual-entry rule

Every capability has **one canonical home**. Other workspaces may link into it with context preselected.

Examples:
- Binding compatibility: canonical in Backport & Migration; linked from Server binding detail and Feature Explorer.
- Capture packets: canonical in Captures; linked into Server packet definitions/handlers.
- Item Editor: canonical in Tools > Editors; linked from Server item detail and Client DAT Inspector.
- Zone Editor: canonical in Tools > Editors; linked from Server zone detail and capture plots.
- Model Viewer: canonical in Client; linked from Server entities and capture entities.
- Validation run: canonical in Validation; linked from Features, Captures and Packages.

Contextual entry points must not create duplicate backend implementations.

## Route inventory disposition

Machine-readable route ownership is in `GUI_ROUTE_MAP.json`.

Disposition semantics:
- **KEEP** — retain tool/route and functionality substantially as-is; may receive shell styling/context links.
- **REWORK** — preserve behavior but redesign presentation/integration.
- **MERGE** — keep capability, but surface it as a view/tab/action in a broader workspace.
- **LEGACY** — retain compatibility access until a replacement is verified feature-complete.
- **NEW GUI** — backend capability exists but lacks equivalent GUI exposure.

Current route ownership summary:
- Home / Project: 3 routes.
- Features: 1 route.
- Backport & Migration: 10 routes.
- Captures: 20 routes.
- Server: 18 routes.
- Client: 3 routes.
- Tools: 66 routes.
- Settings: 13 routes.
- Validation: 5 current routes covering dashboard, runs/results, and Live Target validation.
- Packages: 7 current routes covering Package Library, Dependency Closure / Scope Review, canonical package creation, and Review & Readiness.

The high Tools count is intentional because Zone Editor and Item Editor expose many supporting API/mutation routes. These remain coherent editor applications rather than being split across navigation.

## High-value merge/rework candidates

1. **Feature/Mission browsing**
   - Rework `/missions` into the first Feature Explorer entry point.
   - Preserve its current data while adding Feature Checker/Trace context.

2. **Backport pages**
   - Merge ID drift, zone drift, bindings, converter state, collisions, schema drift and migration planning into one Migration Analyzer shell.
   - Preserve direct converter pages for focused operation.

3. **Captures**
   - Keep all existing data views.
   - Reorganize capture detail into tabs/panels rather than separate disconnected utilities.
   - Add backtrace/correlation as first-class capture views.

4. **Server lookup pages**
   - Entity, zone, SQL, events, packets and item pages become related Server Inspector surfaces with deep links between them.

5. **Item and Zone editors**
   - Do not merge them into inspection pages.
   - Keep mutation workflows under Tools > Editors with explicit “Open in Editor” links.

6. **LLM / Research**
   - Rework the current LLM page into Research history/session UX later.
   - Preserve current logs and actions during the transition.

7. **Legacy Backport Package**
   - Keep until Packages workspace reaches feature parity.
   - Do not silently redirect destructive/apply behavior.

## Shared UI patterns required before broad page migration

### Persistent project context

The shell should always make visible:
- current source snapshot/family;
- current target snapshot/family;
- current client snapshot/build when applicable;
- current feature/package context when selected.

### Evidence/status semantics

Use one shared presentation for:
- VERIFIED
- INFERRED
- DISCOVERED / present-unverified
- UNKNOWN
- MISSING
- CONTRADICTED
- FAILED
- BLOCKED
- MANUAL_REQUIRED

Do not invent workspace-specific equivalents that obscure canonical status.

### Evidence drill-down

Every evidence-backed result should be able to expose:
- evidence ID;
- source/snapshot;
- path/table/location;
- confidence/status;
- related canonical node;
- raw/detail payload where useful.

### Analysis versus mutation

Read-only inspection and analysis should look visually distinct from:
- editor mutations;
- package apply;
- restore/rollback;
- live/server writes.

Mutation views require clear target context and should not be triggered from passive detail panels.

### Progressive disclosure

Default:
- status;
- findings;
- blockers;
- important relationships.

Expandable advanced detail:
- raw SQL;
- JSON;
- evidence IDs;
- exact C++ signatures;
- graph edges;
- binary addresses;
- packet bytes.

### Deep-link contract

Contextual links should carry stable identifiers rather than copying state:
- feature ID;
- entity ID;
- item ID;
- zone ID;
- capture ID;
- packet node/opcode;
- snapshot IDs;
- migration/package/run IDs.

## Captures growth contract

Captures are intentionally not treated as a secondary validation input.

Future capture work should fit under the top-level Captures workspace, including:
- richer NPCLogger fields;
- spawn/despawn history;
- movement/path comparison;
- action skill identification;
- HP/level/attack-delay inference;
- event/CSID analysis;
- packet decoding;
- client-build correlation;
- capture-to-capture diff;
- source/server/client correlation;
- automated validation candidates.

Validation may consume this data, but capture exploration and research remain independently accessible.

## Migration sequence

No route removal is required for the first migration pass.

Recommended implementation sequence:

1. Shared shell/navigation and project/snapshot context.
2. Captures workspace organization.
3. Features / Feature Explorer.
4. Backport & Migration shell.
5. Validation workspace.
6. Client Inspector.
7. Server Inspector consolidation.
8. [x] Packages workspace — Package Library, Dependency Closure / Scope Review, canonical package creation, and Review & Readiness are exposed; target approval/apply/rollback remain gated future UI work pending dependency-coverage proof.
9. Tools subsection navigation.
10. Settings/source-health cleanup.
11. Only after feature parity, consider legacy-route redirects or retirement.

## Acceptance criteria before any route retirement

A legacy/current route may be retired only when:
1. every capability on that route has a mapped replacement;
2. mutation behavior, backups and rollback are preserved where applicable;
3. contextual deep links exist from the relevant workspaces;
4. the replacement uses the same backend service or a verified successor;
5. regression confirms the route/tool capability has not disappeared;
6. the user-facing migration is documented.

Until then, KEEP/MERGE/REWORK means preserve the existing route.

## Inventory validation

The route map is intended to be checked against `gui_server.py` in CI:
- registered route count must remain accounted for;
- every method/path pair must appear exactly once in the canonical route map;
- no route may have an empty canonical home;
- newly added GUI routes must be deliberately assigned a home rather than silently bypassing the information architecture.

## Domains framework (2026-09-26)
- `/domains` (overview) and `/domains/{key}` (detail) are driven by `workbench/domains/definitions.json`; every planned Domains nav entry now links to its domain (sub-areas anchor within the page).
- A definition lists per domain: archetype (see DOMAIN_PLUGIN_ARCHITECTURE.md), entity kinds and the fields each must hold, the existing editor (or none), server file globs, a compare description, and the BG Wiki basis (categories/templates/headings measured from the offline dump; reference only).
- Status is computed live: each glob is resolved against the Topaz, DSP and LSB roots. "Present" means files exist, not that the feature is complete. A wrong glob shows 0 matches, never a false claim.
- Assault (`/domains/assault`) and Nyzul (`/nyzul`) remain their own built pages, linked from the overview.
- Next for each domain: per-entity list views reading the SQL/Lua, then target-vs-reference compare, then editors (reuse Zone Plot / Item Editor where they already fit). Sub-area (e.g. per Abyssea zone) data is not split out yet.
